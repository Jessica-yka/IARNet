import json
import os
import random
import re
from itertools import repeat

import numpy as np
import torch
from PIL import Image
from torch_geometric.data import Data, InMemoryDataset
from torchvision import transforms as T
from tqdm import tqdm
import jieba


class ValueFeatureOneHotEncoder(object):
    def __init__(self, segment_schema):
        self.segment_schema = segment_schema

    def transform(self, value):
        value = value.item()
        one_hot_value = np.array([0] * (len(self.segment_schema) + 1))
        for i in reversed(range(len(self.segment_schema))):
            if value >= self.segment_schema[i]:
                one_hot_value[i] = 1
                return one_hot_value
        one_hot_value[len(self.segment_schema)] = 1
        return one_hot_value


class WeiboGraphDataset(InMemoryDataset):
    def __init__(self, root, w2id,
                 transform=None,
                 pre_transform=None,
                 data_max_sequence_length=256,
                 comment_max_sequence_length=256,
                 max_comment_num=10):
        self.w2id = w2id
        self.unkown_idx = len(w2id)
        self.data_max_sequence_length = data_max_sequence_length
        self.comment_max_sequence_length = comment_max_sequence_length
        self.max_comment_num = max_comment_num
        self.root = root
        normalize = T.Normalize(mean=[0.485, 0.456, 0.406],
                                std=[0.229, 0.224, 0.225])
        self.transforms = T.Compose([
            T.Resize(256),
            T.RandomResizedCrop(224),
            T.RandomHorizontalFlip(),
            T.ToTensor(),
            normalize
        ])

        super(WeiboGraphDataset, self).__init__(root, transform, pre_transform)
        self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_file_names(self):
        return []

    @property
    def processed_file_names(self):
        return ['weibo_glove.dataset']

    def download(self):
        pass

    class BertInputFeatures(object):
        """Private helper class for holding BERT-formatted features"""

        def __init__(
                self,
                tokens,
                input_ids,
                input_mask,
                segment_ids,
        ):
            self.tokens = tokens
            self.input_ids = input_ids
            self.input_mask = input_mask
            self.segment_ids = segment_ids

    def convert_sentence_to_features(self, sentence, max_sequence_length):
        words = jieba.lcut(sentence)
        words = words[:max_sequence_length]
        input_ids = []
        for word in words:
            if word in self.w2id:
                input_ids.append(self.w2id[word])
            else:
                input_ids.append(self.unkown_idx)
        input_mask = [1] * len(input_ids)

        while len(input_ids) < max_sequence_length:
            input_ids.append(0)
            input_mask.append(0)

        assert len(input_ids) == max_sequence_length
        assert len(input_mask) == max_sequence_length

        return [input_ids, input_mask]

    def get_padding_features(self, features):
        max_length = self.max_sequence_length + 2
        input_mask = [1] * len(features)
        input_ids = features
        while len(input_ids) < max_length:
            input_ids.append(0)
            input_mask.append(0)

        assert len(input_ids) == max_length
        assert len(input_mask) == max_length

        return [input_ids, input_mask]

    def get_data_features(self, data):
        encoder = {}
        encoder['reposts_count'] = ValueFeatureOneHotEncoder([0, 100, 200, 350, 500, 750, 1000, 10000, 500000, 1000000])
        encoder['bi_followers_count'] = ValueFeatureOneHotEncoder(
            [0, 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 2000, 3000])
        encoder['city'] = ValueFeatureOneHotEncoder(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 23, 25, 26, 27, 28, 31, 32, 34,
             35, 39, 51, 52, 1000])
        encoder['province'] = ValueFeatureOneHotEncoder(
            [11, 12, 13, 14, 15, 21, 22, 23, 31, 32, 33, 34, 35, 36, 37, 41, 42, 43, 44, 45, 46, 50, 51, 52, 53, 54, 61,
             62, 64, 65, 71, 81, 82, 100, 400])
        encoder['friends_count'] = ValueFeatureOneHotEncoder([0, 100, 200, 300, 400, 500, 700, 900, 1100, 2000, 3000])
        encoder['attitudes_count'] = ValueFeatureOneHotEncoder([0, 1, 2, 3, 10, 50, 100, 300, 500, 1000])
        encoder['followers_count'] = ValueFeatureOneHotEncoder(
            [0, 10, 1000, 10000, 50000, 100000, 500000, 1000000, 5000000, 10000000, 100000000])
        encoder['verified_type'] = ValueFeatureOneHotEncoder([-1, 0, 1, 2, 3, 4, 5, 6, 7, 10, 200, 220])
        encoder['statuses_count'] = ValueFeatureOneHotEncoder(
            [0, 2500, 5000, 10000, 20000, 40000, 60000, 100000, 200000, 300000, 400000])
        encoder['favourites_count'] = ValueFeatureOneHotEncoder(
            [0, 5, 10, 25, 40, 80, 150, 250, 400, 1000, 10000, 30000])
        encoder['comments_count'] = ValueFeatureOneHotEncoder(
            [0, 10, 30, 50, 100, 150, 300, 1000, 5000, 10000, 20000, 30000])
        all_feature_one_hot = []
        for item in encoder.items():
            all_feature_one_hot.extend(item[1].transform(np.array([[int(data[item[0]])]])).tolist())
        if data['gender'] == 'f':
            all_feature_one_hot.extend([1, 0, 0])
        elif data['gender'] == 'm':
            all_feature_one_hot.extend([0, 1, 0])
        else:
            all_feature_one_hot.extend([0, 0, 1])
        return np.array(self.get_padding_features(all_feature_one_hot))

    def get_comment_features(self, comment):
        encoder = {}
        encoder['bi_followers_count'] = ValueFeatureOneHotEncoder(
            [0, 5, 10, 20, 40, 75, 100, 500, 1000])
        city = [i for i in range(1, 47)]
        city.extend([51, 52, 53, 81, 82, 83, 84, 90, 1000, 2000])
        encoder['city'] = ValueFeatureOneHotEncoder(city)
        encoder['friends_count'] = ValueFeatureOneHotEncoder([0, 50, 100, 150, 200, 300, 400, 1000, 3000])
        encoder['attitudes_count'] = ValueFeatureOneHotEncoder(
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50, 100, 200, 300, 500, 1000, 10000])
        encoder['followers_count'] = ValueFeatureOneHotEncoder(
            [0, 10, 1000, 10000, 50000, 100000, 500000, 1000000, 5000000, 10000000, 100000000])
        verified_type = [i for i in range(-1, 8)]
        verified_type.extend([10, 200, 202, 300])
        encoder['verified_type'] = ValueFeatureOneHotEncoder(verified_type)
        encoder['statuses_count'] = ValueFeatureOneHotEncoder(
            [0, 100, 200, 500, 1000, 2000, 3000, 5000, 10000])
        encoder['comments_count'] = ValueFeatureOneHotEncoder(
            [0, 1, 3, 4, 5, 10, 20, 100])
        all_feature_one_hot = []
        for item in encoder.items():
            all_feature_one_hot.extend(item[1].transform(np.array([[int(comment[item[0]])]])).tolist())
        return np.array(self.get_padding_features(all_feature_one_hot))

    def get_image_features(self, data):
        img_url = data['picture']
        img_id = img_url[img_url.rfind('/') + 1:]
        img_path = os.path.join(self.root, f"image/{img_id}")
        data = Image.open(img_path).convert('RGB')
        data = self.transforms(data)
        return data

    def preprocessing_text(self, text):
        if text.startswith('转发微博') and len(text) <= 7:
            return None
        if text.startswith('轉發微博') and len(text) <= 7:
            return None
        if text.startswith('回复'):
            text = text[text.find(':') + 1:]
        re_tag = re.compile('@.+?\s@.+?\s')
        text = re.sub('@.+?\s@.+?\s', '', text)
        text = re.sub('</?\w+[^>]*>', '', text)
        text = re.sub(",+", ",", text)  # 合并逗号
        text = re.sub(" +", " ", text)  # 合并空格
        text = re.sub("[...|…|。。。]+", "...", text)  # 合并句号
        text = re.sub("-+", "--", text)  # 合并-
        text = re.sub("———+", "———", text)  # 合并-
        text = re.sub('[^\u4e00-\u9fa5]', '', text)
        text = text.strip()
        if text == '':
            return None
        return text

    def prepare_comment_features(self, data_list, data_id):
        comment_node = []
        comment_features = []
        for i in range(1, len(data_list)):
            comment = data_list[i]
            if comment['parent'] != data_id:
                continue
            text = self.preprocessing_text(comment['text'])
            if text == None:
                continue
            comment_node.append(self.convert_sentence_to_features(text, self.comment_max_sequence_length))
            comment_features.append(self.get_comment_features(comment))
        return comment_node, comment_features

    def process(self):
        # Read data_utils into huge `Data` list.
        data_list = []
        pbar = tqdm(total=4665)
        with open(os.path.join(self.root, 'Weibo.txt')) as all_samples:
            sample = all_samples.readline()
            while sample != '':
                pbar.update(1)
                print()
                try:
                    sample_file = sample[4:sample.find('\t')]
                    sample_label = 0 if sample[sample.find('label') + 6] == '0' else 1
                    with open(os.path.join(self.root, f'Weibo/{sample_file}.json')) as sample_reader:
                        sample_json = json.loads(sample_reader.read())
                        # node type:
                        # 0: root / 1: root feature / 2:comment / 3:comment feature
                        node_type = []
                        source_nodes_comment_profile_to_comment = []
                        target_nodes_comment_profile_to_comment = []
                        source_nodes_comment_to_data = []
                        target_nodes_comment_to_data = []
                        source_nodes_data_profile_to_data = []
                        target_nodes_data_profile_to_data = []
                        root_node_features = self.convert_sentence_to_features(sample_json[0]['text'],
                                                                               self.data_max_sequence_length)
                        node_type.append(0)
                        root_feature_node_features = self.get_data_features(sample_json[0])
                        node_type.append(1)
                        img_features = self.get_image_features(sample_json[0])
                        comment_node_features, comment_feature_node_features = \
                            self.prepare_comment_features(sample_json, sample_json[0]['mid'])
                        node_type.extend([2] * len(comment_node_features))
                        node_type.extend([3] * len(comment_node_features))
                        node_count = 0
                        source_nodes_data_profile_to_data.append(1)
                        target_nodes_data_profile_to_data.append(0)
                        for i in range(2, len(comment_node_features) + 2):
                            source_nodes_comment_to_data.append(i)
                            target_nodes_comment_to_data.append(0)
                            source_nodes_comment_to_data.append(0)
                            target_nodes_comment_to_data.append(i)
                        node_count = node_count + 2 + len(comment_node_features)
                        for i in range(0, len(comment_node_features)):
                            source_nodes_comment_profile_to_comment.append(node_count + i)
                            target_nodes_comment_profile_to_comment.append(2 + i)

                        node_features = [root_node_features, root_feature_node_features]
                        node_features.extend(comment_node_features)
                        node_features.extend(comment_feature_node_features)
                        node_features = torch.LongTensor(node_features)
                        data = Data(x=node_features,
                                    node_type=torch.LongTensor(node_type),
                                    edge_index_comment_profile_to_comment=
                                    torch.LongTensor([source_nodes_comment_profile_to_comment,
                                                      target_nodes_comment_profile_to_comment]),
                                    edge_index_comment_to_data=
                                    torch.LongTensor([source_nodes_comment_to_data,
                                                      target_nodes_comment_to_data]),
                                    edge_index_data_profile_to_data=
                                    torch.LongTensor([source_nodes_data_profile_to_data,
                                                      target_nodes_data_profile_to_data]),
                                    y=torch.LongTensor([sample_label]),
                                    img_features=img_features)
                        data_list.append(data)
                except BaseException:
                    sample = all_samples.readline()
                    continue

                sample = all_samples.readline()

        data, slices = self.collate(data_list)
        torch.save((data, slices), self.processed_paths[0])

    def get(self, idx):
        data = self.data.__class__()

        if hasattr(self.data, '__num_nodes__'):
            data.num_nodes = self.data.__num_nodes__[idx]

        for key in self.data.keys:
            item, slices = self.data[key], self.slices[key]
            s = list(repeat(slice(None), item.dim()))
            s[self.data.__cat_dim__(key, item)] = \
                slice(slices[idx], slices[idx + 1])
            data[key] = item[s]
        if data.node_type.view(-1).shape[0] > self.max_comment_num * 2 + 2:
            comment_num = int((data.node_type.view(-1).shape[0] - 2) / 2)
            selected_comment = random.sample(range(2, comment_num + 2), self.max_comment_num)
            selected_node = selected_comment + [i + comment_num for i in selected_comment]
            selected_node.extend([0, 1])
            data.x = torch.index_select(input=data.x, index=torch.tensor(selected_node), dim=0)

            def reconstruect_edge(max_comment_num):
                source_nodes_comment_profile_to_comment = []
                target_nodes_comment_profile_to_comment = []
                source_nodes_comment_to_data = []
                target_nodes_comment_to_data = []

                for i in range(2, max_comment_num + 2):
                    source_nodes_comment_to_data.append(i)
                    target_nodes_comment_to_data.append(0)
                    source_nodes_comment_to_data.append(0)
                    target_nodes_comment_to_data.append(i)
                node_count = 2 + max_comment_num
                for i in range(0, max_comment_num):
                    source_nodes_comment_profile_to_comment.append(node_count + i)
                    target_nodes_comment_profile_to_comment.append(2 + i)
                return (torch.LongTensor([source_nodes_comment_to_data,
                                          target_nodes_comment_to_data]),
                        torch.LongTensor([source_nodes_comment_profile_to_comment,
                                          target_nodes_comment_profile_to_comment]))

            data.edge_index_comment_to_data, data.edge_index_comment_profile_to_comment = \
                reconstruect_edge(self.max_comment_num)
            data.node_type = [0, 1]
            data.node_type.extend([2] * self.max_comment_num)
            data.node_type.extend([3] * self.max_comment_num)
            data.node_type = torch.LongTensor(data.node_type)
        return data


if __name__ == '__main__':
    from model.util import *
    vectors, iw, wi, dim = read_vectors('/sdd/yujunshuai/model/chinese_pretrain_vector/sgns.weibo.word')
    dataset = WeiboGraphDataset('/sdd/yujunshuai/data/weibo/', wi)
    print(dataset[0])

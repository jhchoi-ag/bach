'''
전일가 대비 금액 과  다른  값의 상관 관계를 파악하여, 금액 변화를 예측해 본다.
각 종목별, 거래량 및  가격이 많이  다름으로, 일부 항목은 전시간과 차이 값으로 계산한다.
'''

from collections import defaultdict
import os
import argparse
from pathlib import Path

#import statsmodels.api as sm
#import numpy as np
#import matplotlib.pyplot as plt
from scipy import stats

class Record:

    def __init__(self):
        self.code = '' # 0
        self.name = '' # 17
        self.curr_price = 0 # 4
        self.trading_amount = 0 # 10
        self.trading_amount_delta = 0
        self.time = ''  # -1
        self.sell_remaining_amount = 0 # 13
        self.buy_remaining_amount = 0  # 14
        self.priority_sell_remain_amount = 0 # 15
        self.priority_buy_remain_amount = 0 # 16
        self.net_buy_program_amount = 0 # 43
        self.td_net_buy_foreign_amount = 0 # 44
        self.td_net_buy_agency_amount = 0 # 45
        self.td_net_buy_individual_amount = 0 #51

    @classmethod
    def to_record(cls, text):
        sub_list = text.split(',')
        sub_list.append(sub_list.pop(0))

        record = Record()
        record.code = sub_list[0].strip()
        record.name = sub_list[17].strip()
        record.curr_price = int(sub_list[4]) 
        record.trading_amount = int(sub_list[10]) 
        record.time = sub_list[-1].split(':')[1].strip()
        record.sell_remaining_amount = int(sub_list[13].strip()) # 13
        record.buy_remaining_amount = int(sub_list[14].strip())  # 14
        record.priority_sell_remain_amount = int(sub_list[15].strip()) # 15
        record.priority_buy_remain_amount = int(sub_list[16].strip()) # 16
        record.net_buy_program_amount = int(sub_list[43].strip()) # 43
        record.td_net_buy_foreign_amount = int(sub_list[44].strip()) # 44
        record.td_net_buy_agency_amount = int(sub_list[45].strip()) # 45
        record.td_net_buy_individual_amount = int(sub_list[46].strip()) #51

        return record

    @classmethod
    def get_list_by(cls, item_name, target_list):
        return [ getattr(r, item_name) for r in target_list ]


class Correlation:
    def __init__(self, names, items):
        self.record_dicts = defaultdict(list)
        self.names = names # list
        self.price_dicts = defaultdict(list)
        self.control_items = items 
    
    def put(self, line_text):
        record = Record.to_record(line_text)

        if (t := record.time[-6:]) < '090000' or t >= '153000':
            return

        if record.name not in self.names:
            return

        record_list = self.record_dicts[record.name]
        if len(record_list) > 0:
            record.trading_amount_delta = record.trading_amount - record_list[-1].trading_amount
        record_list.append(record)

        price_list = self.price_dicts[record.name]
        price_list.append(record.curr_price)

    def do(self, file_name):
        for name in self.names:
            self._do(file_name, name)

    def _do(self, file_name, name):
        p_dict = {}
        record_list = self.record_dicts[name]
        price_list = self.price_dicts[name]

        print(f"{name} - {len(record_list)} {len(price_list)}")
        for item in self.control_items:
            control_list = Record.get_list_by(item, record_list) 
            p = self._correlate(price_list, control_list)
            p_dict[item] = p

        only_file_name = Path(file_name).name
        print(f"{len(p_dict)}")
        for item, value in p_dict.items():
            print(f"{only_file_name} - {item} : {value}") 

    def _correlate(self, experimental, control):
        #s = stats.pearsonr(experimental, control)
        p = stats.spearmanr(experimental, control)
        return p[0]

def proc_parser():
    "입력값 파싱"
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', '-path', help='로그 파일 디렉터리', default='/Users/jhchoi/Project/trading/bach/log')
    parser.add_argument('--file', '-file', help='로그 파일 명')
    parser.add_argument('--names', '-names', nargs='*', help='종목명', default='')
    parser.add_argument('--items', '-items', nargs='*', help='비교항목')
    return parser.parse_args()

def get_input_files(path):
    rets = [os.path.join(path,f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith('.log')]
    rets.sort()
    return rets

def get_reader(file_name):
    def read_file(inst):
        print(f"START - {file_name}")
        with open(file_name, 'r') as fd:
            while True:
                line = fd.readline()
                if not line:
                    break
                inst.put(line)
        print(f"do start - {file_name}")
        inst.do(file_name)
        print(f"do end - {file_name}")
    return read_file

if __name__ == '__main__':
    PARAMS = proc_parser()
    file_name = os.path.join(PARAMS.path, PARAMS.file)
    reader = get_reader(file_name)

    correlation = Correlation(PARAMS.names, PARAMS.items)
    reader(correlation)

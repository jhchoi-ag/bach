# -*- coding: utf-8 -*-

import argparse
import json
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

class Account(object):
    def __init__(self):
        self._id
        self._pw
    def load(self, filename):
        if not filename:
            return False

        with open(filename, 'r') as f:
            json_data = json.load(f)
            self._id = json_data['id']
            self._pw = json_data['pw']
            return True

class DashinAccount(Account):
    def __init__(self):
        pass

def process_args():
    parser = argparse.ArgumentParser(
        description='Loading Account'
    )

    parser.add_argument('-f', '--filename', help='account.json')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    # 설정 파일은 따로 읽습니다.
    args = process_args()
    account = DashinAccount()
    account.load(args.filename)

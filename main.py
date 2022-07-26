# -*- coding: utf-8 -*-

import argparse
import json
import logging
import sys
import logging
import logging.handlers

reload(sys)
sys.setdefaultencoding('utf-8')

gLog = None

def setupLog():
    gLog = logging.getLogger()
    gLog.setLevel(logging.DEBUG)

    fmt = logging.Formatter('%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s] %(message)s')
    f_handler = logging.handlers.TimedRotatingFileHandler(filename='io', when='midnight', interval=1, encoding='utf-8')
    f_handler.setFormatter(fmt)
    f_handler.suffix = '%Y%m%d'

    gLog.addHandler(f_handler)

import win32com.client

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
        self._instCpCybos = None

    def connect(self):
        self._instCpCybos = win32com.client.Dispatch("CpUtil.CpCybos")

        if self._instCpCybos.IsConnect == 1:
            gLog.info("connection success")
        else:
            gLog.error("connection fail")
            return False
        
        gLog.info("connection type:{0}"
            .format('cybosplus' if self._instCpCybos.ServerType == 1 else 'other ex) HTS')
            )
        # LT_TRADE_REQUEST=0, LT_NONTRADE_REQUEST=1, LT_SUBSCRIBE=2 
        gLog.info("allowed request TRADE:{0} SELECT:{1}, SUBS:{2}, until {3} s"
            .format(self._instCpCybos.GetLimitRemainCount(LT_TRADE_REQUEST)
                ,self._instCpCybos.GetLimitRemainCount(LT_NONTRADE_REQUEST)
                ,self._instCpCybos.GetLimitRemainCount(LT_SUBSCRIBE),
                ,self._instCpCybos.LimitRequestRemainTime / 1000)
                )

'''
class StockCodeList(object):
    def __init__(self):
        self._inst = win32com.client.Dispatch("CpUtil.CpStockCode")

    def updateCodeList(self, type_list):
        max_cnt = self._inst.GetCount()
        for i in range(max_cnt):
            try:
                code = self._inst.GetData(0, i)
            except IOError:
                gLog.error("IOError Code:{0}".format(code))
                return False
'''

MARKET_TYPE = {
    'NULL': 0,
    'KOSPI': 1,
    'KOSDAQ': 2,
    'FREEBOARD': 3,
    'KRX': 4,
    'KONEX': 5
}
R_MARKET_TYPE = {v: k for k, v in MARKET_TYPE.iteritems()}

class StockCodeMgr(object):
    def __init__(self):
        self._inst = win32com.client.Dispatch("CpUtil.CpCodeMgr")

    def getMarketKind(self, market):
        if not market in MARKET_TYPE.items():
            return None
        return self._inst.GetStockMarketKind(market)

'''
def process_args():
    parser = argparse.ArgumentParser(
        description='Loading Account'
    )

    parser.add_argument('-f', '--filename', help='account.json')
    args = parser.parse_args()
    return args
'''

if __name__ == '__main__':

    setupLog()

    account = DashinAccount()
    account.connect()

    stockmgr = StockCodeMgr()
    ret = stockmgr.getMarketKind(MARKET_TYPE['KOSDAQ'])

    for i in ret:
        gLog.info(l)
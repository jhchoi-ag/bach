# -*- coding: utf-8 -*-

from collections import namedtuple
import collections
import datetime
import copy
import logging
import os
import sys
import logging
import logging.handlers
import time

reload(sys)
sys.setdefaultencoding('utf-8')

def setupSysLog(filename):
    log = logging.getLogger(filename)
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter(fmt='%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    f_handler = logging.FileHandler(filename='{0}.log'.format(filename))
    f_handler.setFormatter(fmt)

    log.addHandler(f_handler)
    return log

def setupDataLog(filename):
    log = logging.getLogger(filename)
    log.setLevel(logging.INFO)

    fmt = logging.Formatter('%(message)s')
    f_handler = logging.handlers.TimedRotatingFileHandler(filename='{0}.log'.format(filename), when='midnight', interval=1)
    f_handler.setFormatter(fmt)
    f_handler.suffix = '%Y%m%d'

    log.addHandler(f_handler)
    return log    

gLog = setupSysLog(os.path.join('log', 'sys'))

import win32com.client

class DashinAccount(object):
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

        self.get_limit()

    def get_limit(self):
        # LT_TRADE_REQUEST=0, LT_NONTRADE_REQUEST=1, LT_SUBSCRIBE=2 
        gLog.info("allowed request TRADE:{0} SELECT:{1}, SUBS:{2}, until {3} s"
            .format(self._instCpCybos.GetLimitRemainCount(0)
                ,self._instCpCybos.GetLimitRemainCount(1)
                ,self._instCpCybos.GetLimitRemainCount(2)
                ,self._instCpCybos.LimitRequestRemainTime / 1000)
                )

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
        if not market in MARKET_TYPE.values():
            return None
        return self._inst.GetStockListByMarket(market)

    def doFunc(self, func, *args):
        return getattr(self._inst, func)(*args)

class Stock(object):
    '종목을 이루는 기본 값 으로 TargetCodes 를 통해 관리된다.'
    def __init__(self):
        self._attributes = collections.OrderedDict()
        self._datas = collections.OrderedDict()

        self._attributes['Code'] = '' # 종목코드
        self._attributes['Name'] = '' # 종목명
        self._attributes['MemeMin'] = 1 # 매매최소단위
        self._attributes['SupervisionKind'] = 0 # 0: 정상종목, 1: 거래정지, 2:거래중단
        self._attributes['StatusKind'] = 0 # 0: 정상종목, 1: 거래정지, 2:거래중단
        self._attributes['Capital'] = 1 #  0: 제외, 1: 대형, 2:중형, 3:소형
        self._attributes['Kospi200Kind'] = 0 # 0: 아님, 1 : 맞음
        self._attributes['Section'] = 1 # 11: 수익증권, 1:주권, 2:투자회사, 14:선물, ..
        self._attributes['LacKind'] = 0 # 0: 구분없음, 1: 권리락, 2: 배당락, 3:분배락, ...
        self._attributes['YdOpenPrice'] = 0 # 전일 시작가
        self._attributes['YdHighPrice'] = 0 # 전일 최고가
        self._attributes['YdLowPrice'] = 0 # 전일 최하가
        self._attributes['YdClosePrice'] = 0 # 전일 종가
    
    def set(self, code, name, *args):
        self._attributes['Code'] = code
        self._attributes['Name'] = name
        self._attributes['MemeMin'] = args[0]
        self._attributes['SupervisionKind'] = args[1]
        self._attributes['StatusKind'] = args[2]
        self._attributes['Capital'] = args[3]
        self._attributes['Kospi200Kind'] = args[4]
        self._attributes['Section'] = args[5]
        self._attributes['LacKind'] = args[6]
        self._attributes['YdOpenPrice'] = args[7]
        self._attributes['YdHighPrice'] = args[8]
        self._attributes['YdLowPrice'] = args[9]
        self._attributes['YdClosePrice'] = args[10]

    def _get(self, key):
        try:
            return self._attributes[key]
        except KeyError:
            return ''        

    @property
    def Code(self):
        return self._get('Code')

    @property
    def Name(self):
        return self._get('Name')

    @classmethod
    def to_code_list(cls, stocks):
        return [stock.Code for stock in stocks if stock.Code]
    
    def input_by_time(self, collected_at, varname, value):
        dict = self._datas.setdefault(collected_at, collections.OrderedDict())
        dict[varname] = value

    def __repr__(self):
        raw = []
        #for k, v in self._attributes.items():
        #    raw.append(k + ':' + str(v))
        for k, v in self._datas.items():
            raw.append('Collected:'+ k)
            for _, sub_v in v.items():
                #raw.append( sub_k + ':' + str(sub_v))
                raw.append(str(sub_v))
        return ','.join(raw)

class CollectMarket(object):
    '시장 상황을 수집합니다.'
    Column = namedtuple('Column', 'index name desc')
    def __init__(self):
        self._inst = win32com.client.Dispatch("CpSysDib.MarketEye")
        
        self._column_list = []
        self._column_list.append(CollectMarket.Column(0, 'Code', '종목코드'))
        self._column_list.append(CollectMarket.Column(1, 'Time', '시간 hhmm'))
        self._column_list.append(CollectMarket.Column(2, 'Sign', '대비부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)'))
        self._column_list.append(CollectMarket.Column(3, 'DiffY', '전일대비'))
        self._column_list.append(CollectMarket.Column(4, 'CurrPrice', '현재가'))
        self._column_list.append(CollectMarket.Column(5, 'OpenPrice', '시가'))
        self._column_list.append(CollectMarket.Column(6, 'HighPrice', '고가'))
        self._column_list.append(CollectMarket.Column(7, 'LowPrice', '저가'))
        self._column_list.append(CollectMarket.Column(8, 'SellCallPrice', '매도호가'))
        self._column_list.append(CollectMarket.Column(9, 'BuyCallPrice', '매수호가'))
        self._column_list.append(CollectMarket.Column(10, 'TradingAmount', '거래량'))
        self._column_list.append(CollectMarket.Column(11, 'TradingPrice', '거래대금(원)'))
        self._column_list.append(CollectMarket.Column(12, 'MargetSegment', '장구분(0:장전, 1:동시호가, 2:장중)'))
        self._column_list.append(CollectMarket.Column(13, 'SellRemainingAmount', '총매도호가잔량'))
        self._column_list.append(CollectMarket.Column(14, 'BuyRemainingAmount', '총매수호가잔량'))
        self._column_list.append(CollectMarket.Column(15, 'PriorityCellRemainingAmount', '최우선매도호가잔량'))
        self._column_list.append(CollectMarket.Column(16, 'PriorityBuyRemainingAmount', '최우선매수호가잔량'))
        self._column_list.append(CollectMarket.Column(17, 'Name', '종목명'))
        self._column_list.append(CollectMarket.Column(20, 'TotalAmount', '총상장주식수'))
        self._column_list.append(CollectMarket.Column(21, 'PercentOfForeign', '외국인보유비율'))
        self._column_list.append(CollectMarket.Column(22, 'YdTradingAmount', '전일거래량'))
        self._column_list.append(CollectMarket.Column(23, 'YdClosePrice', '전일종가'))
        self._column_list.append(CollectMarket.Column(24, 'TradingForce', '체결강도'))
        self._column_list.append(CollectMarket.Column(25, 'TradingType', '체결구분(1:매수체결, 2:매도체결)'))
        self._column_list.append(CollectMarket.Column(32, '19ClosePriceSum', '19일종가합'))
        self._column_list.append(CollectMarket.Column(33, 'UpperLimitPrice', '상한가'))
        self._column_list.append(CollectMarket.Column(34, 'LowerLimitPrice', '하한가'))
        self._column_list.append(CollectMarket.Column(35, 'TradingUnit', '매매수량단위'))
        self._column_list.append(CollectMarket.Column(38, 'OverTimeCurrPrice', '시간외단일현재가'))
        self._column_list.append(CollectMarket.Column(39, 'OverTimeOpenPrice', '시간외단일시가'))
        self._column_list.append(CollectMarket.Column(40, 'OverTimeHighPrice', '시간외단일고가'))
        self._column_list.append(CollectMarket.Column(41, 'OverTimeLowPrice', '시간외단일저가'))
        self._column_list.append(CollectMarket.Column(42, 'OverTimeCellCallPrice', '시간외단일매도호가'))
        self._column_list.append(CollectMarket.Column(43, 'OverTimeBuyCallPrice', '시간외단일매수호가'))
        self._column_list.append(CollectMarket.Column(44, 'OverTimeTradingAmount', '시간외단일거래량'))
        self._column_list.append(CollectMarket.Column(62, 'ForeignTradingAmount', '외국인순매매(주식수)'))
        self._column_list.append(CollectMarket.Column(63, 'YearHighestPrice', '52주최고가'))
        self._column_list.append(CollectMarket.Column(64, 'YearLowestPrice', '52주최저가'))
        self._column_list.append(CollectMarket.Column(68, 'OverTimeBuyRemainingAmount', '시간외매수잔량'))
        self._column_list.append(CollectMarket.Column(69, 'OverTimeCellRemainingAmount', '시간외매도잔량'))
        self._column_list.append(CollectMarket.Column(71, 'CapitalPrice', '자본금(백만)'))
        self._column_list.append(CollectMarket.Column(84, '4ClosePriceSum', '4일종가합'))
        self._column_list.append(CollectMarket.Column(85, '9ClosePriceSum', '9일종가합'))
        self._column_list.append(CollectMarket.Column(116, 'NetBuyProgramAmount', '프로그램순매수'))
        self._column_list.append(CollectMarket.Column(118, 'TdNetBuyForeignAmount', '당일외국인순매수'))
        self._column_list.append(CollectMarket.Column(120, 'TdNetBuyAgency', '당일기관순매수'))
        self._column_list.append(CollectMarket.Column(121, 'YdNetBuyForeignAmount', '전일외국인순매수'))
        self._column_list.append(CollectMarket.Column(122, 'YdNetBuyAgency', '전일기관순매수'))
        self._column_list.append(CollectMarket.Column(127, 'ShortCellingAmount', '공매도수량'))
        self._column_list.append(CollectMarket.Column(153, '59ClosePriceSum', '59일종가합'))
        self._column_list.append(CollectMarket.Column(154, '119ClosePriceSum', '119일종가합'))
        self._column_list.append(CollectMarket.Column(156, 'TdNetBuyIndividual', '당일개인순매수'))
        self._column_list.append(CollectMarket.Column(157, 'YdNetBuyIndividual', '전일개인순매수'))
        self._column_list.append(CollectMarket.Column(158, '5ClosePrice', '5일전종가'))
        self._column_list.append(CollectMarket.Column(159, '10ClosePrice', '10일전종가'))
        self._column_list.append(CollectMarket.Column(160, '20ClosePrice', '20일전종가'))
        self._column_list.append(CollectMarket.Column(161, '60ClosePrice', '60일전종가'))  
        self._column_list.append(CollectMarket.Column(162, '120ClosePrice', '120일전종가'))       

    def get_column_list(self):
        return [column[0] for column in self._column_list]

    def collect(self, stocks):
        collected_at = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        step = 200 # 한번에 최대 200 까지 읽을 수 있데요.
        print('--debug:', collected_at, len(stocks))
        result_list = []
        for i in range(int(len(stocks)/step)+1):
            sub_list = stocks[step*i:step*(i+1)]
            if not self.request(sub_list):
                continue
            if not self.response(collected_at, result_list, sub_list):
                continue
        return result_list

    def request(self, stocks):
        self._inst.SetInputValue(0, self.get_column_list())
        self._inst.SetInputValue(1, Stock.to_code_list(stocks))
        self._inst.BlockRequest()
        status = self._inst.GetDibStatus()
        if status:
            gLog.error('Request status is abnormal {0}'.format(status))
            return False
        return True

    def response(self, collected_at, result_list, input_list):
        status = self._inst.GetDibStatus()
        if status:
            gLog.error('Response status is abnormal {0}'.format(status))
            return False

        cnt_of_stocks = self._inst.GetHeaderValue(2)
        cnt_of_columns = len(self._column_list)

        for i in range(cnt_of_stocks):
            # r_item 은 매번 새로운 놈이 되겠어요. 복사하니까요.
            r_item = copy.deepcopy(input_list[i])
            result_list.append(r_item)
            for c in range(cnt_of_columns):
                column = self._column_list[c]
                r_item.input_by_time(collected_at, column.name, self._inst.GetDataValue(c, i))

        return True

class TargetCodes(object):
    '개장 전 1회 시행으로, 매매 대상 Code List 를 유지합니다.'
    def __init__(self):
        self._allow_supervisionKind = {0} # 0: 일반종목, 1: 관리
        self._allow_statusKind = {0} # 0: 정상종목, 1: 거래정지, 2:거래중단
        self._allow_stockCapital = {1,2,3} # 0: 제외, 1: 대형, 2:중형, 3:소형
        self._allow_stockSectionKind = {1} # 11: 수익증권, 1:주권, 2:투자회사, 14:선물, ..
        self._allow_stockLacKind = {0} # 0: 구분없음, 1: 권리락, 2: 배당락, 3:분배락, ...

        self.Stocks = []

    def load(self, market_type):
        mgr = StockCodeMgr()
        code_list = mgr.getMarketKind(MARKET_TYPE[market_type])

        for code in code_list:
            if mgr.doFunc('GetStockSectionKind', code) not in self._allow_stockSectionKind:
                continue
            if mgr.doFunc('GetStockLacKind', code) not in self._allow_stockLacKind:
                continue
            if mgr.doFunc('GetStockSupervisionKind', code) not in self._allow_supervisionKind:
                continue
            if mgr.doFunc('GetStockStatusKind', code) not in self._allow_statusKind:
                continue
            if mgr.doFunc('GetStockCapital', code) not in self._allow_stockCapital:
                continue
            
            # 로그를 찍어보아요.
            stock = Stock()
            stock.set(code
                    ,mgr.doFunc('CodeToName', code)
                    ,mgr.doFunc('GetStockMemeMin', code)
                    ,mgr.doFunc('GetStockSupervisionKind', code)
                    ,mgr.doFunc('GetStockStatusKind', code)
                    ,mgr.doFunc('GetStockCapital', code)
                    ,mgr.doFunc('GetStockKospi200Kind', code)
                    ,mgr.doFunc('GetStockSectionKind', code)
                    ,mgr.doFunc('GetStockLacKind', code)
                    ,mgr.doFunc('GetStockYdOpenPrice', code)
                    ,mgr.doFunc('GetStockYdHighPrice', code)
                    ,mgr.doFunc('GetStockYdLowPrice', code)
                    ,mgr.doFunc('GetStockYdClosePrice', code)
                    )
            
            self.Stocks.append(stock)



if __name__ == '__main__':

    kosdaqLog = setupDataLog(os.path.join('log', 'kosdaq'))
    kospiLog = setupDataLog(os.path.join('log', 'kospi'))

    account = DashinAccount()
    account.connect()

    kosdaq = TargetCodes()
    kosdaq.load('KOSDAQ')

    kospi = TargetCodes()
    kospi.load('KOSPI')

    kosdap_collector = CollectMarket()
    kospi_collector = CollectMarket()

    while True:
        now = datetime.datetime.now()

        # 월~금만.
        if not now.isoweekday() in (1,2,3,4,5):
            time.sleep(60)
            continue

        # 8시 20분 ~ 18:10분 까지..
        if now.hour < 8 or now.hour >= 17:
            time.sleep(60)
            continue

        if now.hour == 8 and now.minute < 40:
            time.sleep(60)
            continue

        if now.hour == 16 and now.minute > 10:
            time.sleep(60)
            continue

        if now.second % 5 == 0:
            results = kosdap_collector.collect(kosdaq.Stocks)
            for r in results:
                kosdaqLog.info(r)

            results = kospi_collector.collect(kospi.Stocks)
            for r in results:
                kospiLog.info(r)
        
        account.get_limit()
        time.sleep(0.3)
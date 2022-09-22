'''
두번째 전략.
1분간, 
현재가 1분,3분,5분,10분 이평성 우상향 and 각 이평선 마다 시간별 우상향
거래량 1분,3분,5분,10분 이평성 우상향 and 각 이평선 마다 시간별 우상향 

결과값은, 종목 명 나열
매수시각, 종목명, 매수가격, 마지막 가격, 수익률만 작성해 봐요. 
'''

'''
decision2.py + trader 는 매수 시각이  얼마나 지났는가에  따라, 가변적으로 값을 변경 함. + Achive 를 2개 이상 수용 가능.
'''

# python decision.py -path '' -out result.out
from collections import OrderedDict, defaultdict
import datetime
import os
import argparse
import time
import unicodedata

G_INIT_MONEY = 1000000 # 처음이니까, 돈이 많으면 얼마나 살 수 있는지 보려구요.
G_UNIT_BUY_PERCENT = 0.33 # 33%
#G_MOVING_AVERAGE_LIST = [1,2,4,7,10] # 분 단위 입니다.
#G_MOVING_AVERAGE_LIST = [1,3,6,10,15] # 분 단위 입니다.
#G_MOVING_AVERAGE_LIST = [1,5,10,15] # 분 단위 입니다.
#G_MOVING_AVERAGE_LIST = [1,4,8,12] # 분 단위 입니다.
#G_MAX_ARCHIVING = 60 / 5 * G_MOVING_AVERAGE_LISTS[-1]
G_LESS_CAPITAL = 200000000000

def rate(numerator, denominator):
    if not denominator:
        return 0
    return (numerator / denominator) * 100

WIDTHS = {
    'F': 2,
    'H': 1,
    'W': 2,
    'N': 1,
    'A': 1, # Not really correct...
    'Na': 1,
}

def pad(text,width):
    text_width = 0
    for ch in text:
        width_class =unicodedata.east_asian_width(ch)
        text_width += WIDTHS[width_class]
    if width <= text_width:
        return text
    return text + ' '*(width - text_width)

class Record:
    def __init__(self):
        self.curr_price = 0
        self.trading_amount = 0
        self.open_price = 0
        self.sell_call_price = 0
        self.buy_call_price = 0
        self.name = ''
        self.code = ''
        self.trading_unit = 0
        self.time = ''

    def __repr__(self):
        text = f"c_price:{self.curr_price} "
        text += f"trading_amount: {self.trading_amount} "
        text += f"o_price:{self.open_price} "
        text += f"sell call price:{self.sell_call_price} "
        text += f"buy call price: {self.buy_call_price} "
        text += f"name: {self.name} "
        text += f"code: {self.code} "
        text += f"trading_unit: {self.trading_unit} "
        text += f"time: {self.time}"
        return text

class ItemBox:
    def __init__(self, moving_average):
        self.items = []
        self.moving_average = moving_average
        self.max_archiving = 60 / 5 * self.moving_average[-1]
        self.moving_average_dict = OrderedDict()
        for key in self.moving_average:
            self.moving_average_dict[key] = 0

    def is_fill_item(self):
        return len(self.items) >= self.max_archiving

    def calculate_moving_average(self):
        # moving_average_dict.keys() 란 이평선:1분,5분,10분,20분, 등. 의 단위를 말해요.
        for k in self.moving_average_dict.keys():
            cnt = len(self.items)
            if cnt > k:
                self.moving_average_dict[k] -= self.items[-int(k+1)]
            self.moving_average_dict[k] += self.items[-1]        

    def get_moving_average(self, key):
        v = self.moving_average_dict[key]
        cnt = len(self.items) 
        if cnt >= key:
            cnt = key
        return int(v/cnt)

    def is_increase(self, seq, reverse=False, is_contain_equal=False):
        def oper(i, j):
            if reverse and is_contain_equal:
                return i >= j
            elif reverse and not is_contain_equal:
                return i > j
            elif not reverse and is_contain_equal:
                return i <= j
            else:
                return i < j
        return all(oper(i, j) for i, j in zip(seq, seq[1:]))

    def is_rightward(self):
        v = []
        for key in self.moving_average_dict.keys():
            v.append(self.get_moving_average(key))

        # 모두가 다르고, 앞에가 커야 해요.
        return self.is_increase(v, reverse=True, is_contain_equal=False)

    def get_diff_sequence_moving_averages(self):
        v = []
        for key in self.moving_average_dict.keys():
            v.append(self.get_moving_average(key))

        v1 = v[1:]
        return [b - a for a, b in zip(v, v1)]

    def is_diff_sequence_rightward(self):
        v = self.get_diff_sequence_moving_averages()
        # 모두가 다르고, 앞에가 커야 해요.
        return self.is_increase(v, reverse=True, is_contain_equal=False)

    def is_buy(self):
        return self.is_rightward() and self.is_diff_sequence_rightward()
        #return self.is_rightward()

class PriceBox(ItemBox):
    def __init__(self, moving_average):
        super().__init__(moving_average)

    def put(self, record):
        self.items.append(record.curr_price)
        if self.max_archiving < len(self.items):
            self.items.pop(0)
        self.calculate_moving_average()

class TradingAmountBox(ItemBox):
    def __init__(self, moving_average):
        super().__init__(moving_average)
        self.last_trading_amount = 0

    def put(self, record):
        value = record.trading_amount - self.last_trading_amount
        self.items.append(value)

        if self.max_archiving < len(self.items):
            self.items.pop(0)
        self.calculate_moving_average()
        self.last_trading_amount = record.trading_amount

class Archives(dict):
    def __init__(self, moving_average_list):
        self.moving_average_list = moving_average_list

    def __missing__(self, key):
        value = Archive(self.moving_average_list)
        self[key] = value
        return value

    def __repr__(self):
        return f"Archives {self.moving_average_list}"

class Archive:
    # 종목 별로, 시간별 이력을 가지고 있습니다.
    def __init__(self, moving_average_list):
        self.priceBox = PriceBox(moving_average_list)
        self.tradingAmountBox = TradingAmountBox(moving_average_list)
        self.code = ''

    def put(self, record):
        if not self.code:
            self.code = record.code

        self.priceBox.put(record)
        self.tradingAmountBox.put(record)

    def is_buy(self):
        if not self.priceBox.is_fill_item():
            return False
        #print(f"{self.code} - priceBox.is_buy() {self.priceBox.is_buy()}, tradingAmountBox.is_buy() {self.tradingAmountBox.is_buy()}")
        return self.priceBox.is_buy() and self.tradingAmountBox.is_buy()

    def is_sell(self, record):
        # 매도 조건은 없습니다.
        return False

class TradingRecord:
    EVENT_BUY = 'BUY'
    EVENT_SELL = 'SEL'
    TRADING_COST_RATE = 0.3

    def __init__(self):
        self.buy_event_time = ''
        self.sell_event_time = ''
        self.event_type = TradingRecord.EVENT_BUY
        self.code = ''
        self.name = ''
        self.buy_price = 0
        self.sell_price = 0
        self.last_price = 0
        self.highest_price = 0
        self.amount = 0

    @classmethod
    def buy(cls, record, money):
        print(f"사는 군요.  {record.time} {record.name}")
        t_record = TradingRecord()
        t_record.buy_event_time = record.time
        t_record.code = record.code
        t_record.name = record.name
        t_record.buy_price = record.sell_call_price
        if t_record.buy_price == 0 or record.trading_unit == 0:
            print(f"매매 불가 - {record}")
            return None

        t_record.amount = round(money/(t_record.buy_price * record.trading_unit))
        if t_record.amount <= 0:
            print(f"매매 불가 돈이 없어요 - 잔액:{money} 필요한 돈:{t_record.buy_price * record.trading_unit}")
            return None
        return t_record

    @classmethod
    def sell(cls, trading_record, record):
        print(f"파는 군요.  {record.time} {record.name}")
        trading_record.sell_event_time = record.time
        trading_record.event_type = cls.EVENT_SELL 
        trading_record.sell_price = record.buy_call_price

    @property 
    def buy_cost(self):
        cost = self.buy_price * self.amount
        fee = cost * TradingRecord.TRADING_COST_RATE * 0.01
        return cost + fee

    @property
    def sell_cost(self):
        cost = self.sell_price * self.amount 
        fee = cost * TradingRecord.TRADING_COST_RATE * 0.01
        return cost - fee

    @property
    def holiding_period(self):
        buy_time = datetime.datetime.strptime(self.buy_event_time, '%Y%m%d%H%M%S')
        sell_time = datetime.datetime.strptime(self.sell_event_time, '%Y%m%d%H%M%S')
        return f"{str(sell_time - buy_time):8s}"

class Asset:
    def __init__(self, money):
        self.asset_log = []
        self.balance = money
        self.buy_percent = G_UNIT_BUY_PERCENT
        self.loan_cnt = 1
        self.asset_log.append(('', self.balance))

    def delete(self, time, money):
        self.balance -= money
        self.loan_cnt += 1
        self.asset_log.append((time, self.balance))

    def add(self, time, money):
        self.balance += money
        self.loan_cnt -= 1
        self.asset_log.append((time, self.balance))

    @property
    def buy_price_unit(self):
        return self.balance * (self.buy_percent * self.loan_cnt) 

class Trader:
    def __init__(self):
        self.possessions = OrderedDict()
        self.trading_log = []
        self.asset = Asset(G_INIT_MONEY)

    def is_possession(self, code):
        return code in self.possessions

    def buy(self, record):
        if self.is_possession(record.code):
            return

        #asset_balance = self.asset.balance
        #if asset_balance < self.asset.buy_price_unit:
        #    return

        t_record = TradingRecord.buy(record, self.asset.buy_price_unit)
        if not t_record:
            return
    
        self.possessions[t_record.code] = t_record
        self.asset.delete(t_record.buy_event_time, t_record.buy_cost)
        #self.trading_log.append(t_record)

    def is_sell(self, record, diff_highest_rate, diff_buying_rate):
        if not self.is_possession(record.code):
            return False

        # t_record 업데이트.
        t_record = self.possessions[record.code]
        t_record.last_price = record.curr_price
        if t_record.highest_price < t_record.last_price:
            t_record.highest_price = t_record.last_price

        # 매도조건.
        # 최고가 대비 하락시, 매도.
        decision_diff_highest_rate = self._decision_value(t_record.buy_event_time, record.time, diff_highest_rate)
        if rate(t_record.last_price - t_record.highest_price, t_record.highest_price) <= decision_diff_highest_rate:
            return True

        # 구매가 대비 하락시, 매도.
        if rate(t_record.last_price-t_record.buy_price, t_record.buy_price) <= diff_buying_rate:
            return True

        return False

    def _decision_value(self, str_buy_time, str_now_time, dict_table):
        buy_time = datetime.datetime.strptime(str_buy_time, '%Y%m%d%H%M%S')
        now_time = datetime.datetime.strptime(str_now_time, '%Y%m%d%H%M%S')
        delta = (now_time - buy_time).total_seconds() / 60
        for k, v in dict_table.items():
            if k > delta:
                return v
        return next(reversed(dict_table.values()))

    def sell(self, record):
        t_record = self.possessions.get(record.code, None)
        if not t_record:
            return

        TradingRecord.sell(t_record ,record)
        self.asset.add(t_record.sell_event_time, t_record.sell_cost)
        self.trading_log.append(t_record)

        del self.possessions[record.code]

    def out_trading_log(self):
        text_list = []
        text_list.append("----- 매매기록 -----")
        text = f"매수 시각, 매도 시각, 보유기간, 코드, 이름, 매수가, 매도가, 최고가, 현재가, 수량"
        text_list.append(text)
        for tr in self.trading_log:
            text = f"{tr.buy_event_time}, {tr.sell_event_time}, {tr.holiding_period}, {tr.code}, {pad(tr.name, 16)}, {tr.buy_price:>12.0f}, {tr.sell_price:>12.0f}, {tr.highest_price:>12.0f}, {'-':12s}, {tr.amount:>12n}, "
            benefit_price = (tr.sell_price - tr.buy_price) * tr.amount
            text += f"수익금액: {benefit_price:>12.0f}, 수익률: {rate(tr.sell_price-tr.buy_price, tr.buy_price):5.2f}"
            text_list.append(text)
        self.trading_log = []
        return '\n'.join(text_list)

    def print_asset(self):
        text_list = []
        text_list.append("----- 자산현황 -----")
        #for (time, balance) in self.asset.asset_log:
        #    text = f"{time} {balance}"
        #    text_list.append(text)
        self.asset.asset_log = []
        
        # 남은 금액과 아직 팔리지 않은 last_price 의해 평가된 금액이에요.
        evaluation_money = 0
        for tr in self.possessions.values():
            text = f"{tr.buy_event_time}, {'-':12s}, {tr.code}, {pad(tr.name,16)}, {tr.buy_price:>12.0f}, {'-':12s}, {tr.highest_price:>12.0f}, {tr.last_price:>12.0f}, {tr.amount:>12n}"
            text_list.append(text)
            evaluation_money += (tr.last_price * tr.amount)

        total_money = self.asset.balance + evaluation_money
        text = f"수익: {total_money - G_INIT_MONEY:>12.2f}, 수익율: {rate(total_money-G_INIT_MONEY, G_INIT_MONEY):5.2f}, 총 금액: {total_money:>12.0f}, 현금: {self.asset.balance:>12.0f}, 평가금액: {evaluation_money:>12.0f}"
        text_list.append(text)
        return '\n'.join(text_list)

class Handel:
    def __init__(self):
        #self.archives_5m = Archives([1,3,5,7]) # Item 의  List
        #self.archives_5m = Archives([1,3,5,7,9]) # Item 의  List
        #self.archives_5m = Archives([5,10,20,60,120]) # Item 의  List
        #self.archives_5m = Archives([1,2,4,12,24]) # Item 의  List
        #self.archives_5m = Archives([1,2,3,4]) # Item 의  List, -1.89, -18,908, 프레스티지바이오, 태광
        #self.archives_5m = Archives([1,2,3,5,8]) # Item 의  List, N/A
        #self.archives_5m = Archives([2,3,5,13]) # Item 의  List, -22.90, -228.967, 씨에스베어링, 대주전자재료 등 총 222회 거래
        #self.archives_5m = Archives([2,3,5,7,13]) # Item 의  List, -1.18, -11,787
        self.archives_5m = Archives([1,5,10,15]) # Item 의  List, +2.69, +26,884 휴림로봇, 원티드랩, 포스코엠텍, 에스티팜, 아바텍 등
        #self.archives_5m = Archives([1,4,8,12]) # Item 의  List, +0.75, +7,546 휴림로봇, 에스에프에이 등
        #self.archives_5m = Archives([1,6,12,18]) # Item 의  Lis등, -4.47, -44,704 로보티즈, 레인보우로보틱스 등

        #self.archives_4m = Archives([1,4,8,12]) # Item 의  List
        self.archives_4m = Archives([1,3,5,7]) # Item 의  List
        self.archives = defaultdict(Archive) # Item 의  List
        self.trader = Trader()

        # 시작가 대비, diff_rise_rate 보다 높으면 매수금지.
        self.no_buying_rise_rate = 12.0

        # 최고가 대비, diff_highest_rate 보다 낮으면 매도.
        self.diff_highest_rate = OrderedDict({60:-3.0, 120:-2.0, 180:-1.5, 181:-1.0})
        #self.diff_highest_rate = OrderedDict({180:-5.0, 181:-1.0})
        # 매수가 대비, diff_buying_rate 보다 낮으면 매도.
        self.diff_buying_rate = -2.0

    def is_no_buying(self, record):
        if record.market_cap < G_LESS_CAPITAL:
            return True
        # 이미 올라 있으면 안사요.
        return rate(record.curr_price - record.open_price, record.open_price) > self.no_buying_rise_rate

    def reset_archive(self):
        self.archives_5m.clear()
        self.archives_4m.clear()

    def do(self, in_line):
        # 필요 값만 추출할까요?
        record = self._to_record(in_line)

        # 09시 전에는 안해요.
        if record.time[-6:] < '090000':
            return

        archive_4m = self.archives_4m[record.code]
        archive_4m.put(record)

        if not self.is_no_buying(record) and archive_4m.is_buy():
            self.trader.buy(record)

        archive_5m = self.archives_5m[record.code]
        archive_5m.put(record)

        if not self.is_no_buying(record) and archive_5m.is_buy():
            self.trader.buy(record)

        if archive_4m.is_sell(record) or archive_5m.is_sell(record):
        #if archive_5m.is_sell(record):
            self.trader.sell(record)

        if self.trader.is_sell(record, self.diff_highest_rate, self.diff_buying_rate):
            self.trader.sell(record)

    def out_condition(self, write_file_name):
        condition = f"G_UNIT_BUY_PRICE:{G_UNIT_BUY_PERCENT}, G_INIT_MONEY:{G_INIT_MONEY}, G_LESS_CAPITAL:{G_LESS_CAPITAL} MOVING_AVERAGE:{self.archives_4m}, {self.archives_5m}"
        #condition = f"G_UNIT_BUY_PRICE:{G_UNIT_BUY_PRICE}, G_INIT_MONEY:{G_INIT_MONEY}, G_LESS_CAPITAL:{G_LESS_CAPITAL} MOVING_AVERAGE:{self.archives_5m}"
        condition += f" no_buying_rise_rate:{self.no_buying_rise_rate}, diff_highest_rate:{self.diff_highest_rate}, diff_buying_rate:{self.diff_buying_rate}"
        with open(write_file_name, 'a') as fd:
            print(condition + '\n')
            fd.write(condition + '\n')

    def out(self, write_file_name):
        with open(write_file_name, 'a') as fd:
            # 매매 일지를 print 합니다. - 몇 시에 얼마에 사서, 얼마에 팔았고, 수익이 어떻게 되었고..
            report = self.trader.out_trading_log()
            print(report+'\n')
            fd.write(report+'\n')

            # 현재 stock 의 가치를 적습니다. - 몇 시에 얼마에 샀고, 현재 수익이 어떻게 되었고..
            # 총 자산이 얼마다. 까지.
            report = self.trader.print_asset()
            print(report+'\n')
            fd.write(report+'\n')

    def _to_record(self, in_line):
        sub_list = in_line.split(',')
        sub_list.append(sub_list.pop(0))
        record = Record()
        record.curr_price = int(sub_list[4]) 
        record.trading_amount = int(sub_list[10]) 
        record.open_price = int(sub_list[5])
        record.sell_call_price = int(sub_list[8])
        record.buy_call_price = int(sub_list[9])
        record.name = sub_list[17].strip()
        record.code = sub_list[0].strip()
        record.trading_unit = int(sub_list[27]) 
        record.time = sub_list[-1].split(':')[1].strip()

        record.market_cap = int(sub_list[18]) * record.curr_price
        return record

def get_input_files(path):
    rets = [os.path.join(path,f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith('.log')]
    rets.sort()
    return rets

def read_file(file_name):
    with open(file_name, 'r') as fd:
        while True:
            line = fd.readline()
            if not line:
                break
            yield line

def proc_parser():
    "입력값 파싱"
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', '-path', help='로그 파일 디렉터리', default='/Users/jhchoi/Project/trading/bach/log')
    parser.add_argument('--output_file', '-out', help='출력 파일명')
    return parser.parse_args()

if __name__ == '__main__':
    PARAMS = proc_parser()

    algorithm = Handel()
    in_files = get_input_files(PARAMS.path)
    str_time = time.strftime('%Y%m%d_%H%M%S')

    out_file_name = os.path.join(PARAMS.path, PARAMS.output_file + '.' + str_time)
    algorithm.out_condition(out_file_name)

    for file_name in in_files:
        print(f"---------- {file_name}")
        algorithm.reset_archive()
        for in_line in read_file(file_name):
            if not in_line:
                break
            algorithm.do(in_line)
        algorithm.out(out_file_name)

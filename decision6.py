
from abc import *
from collections import OrderedDict, deque
import datetime
import os
import argparse
import statistics
import sys
import time
import unicodedata

G_INIT_MONEY = 1000000  # 초기 자본금 
G_UNIT_BUY_PERCENT = 0.33  # 1건 거래시, 최대 거래금은 전체 자본의 33% 만 가능
G_LESS_CAPITAL = 200000000000
G_UNIT = 1  # 1 이면 5sec, 12 이면 1 min 

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
        self.yd_trading_amount = 0
        self.open_price = 0
        self.sell_call_price = 0
        self.buy_call_price = 0
        self.name = ''
        self.code = ''
        self.priority_buy_remain_amount = 0
        self.priority_sell_remain_amount = 0
        self.net_buy_program_amount = 0
        self.trading_unit = 0
        self.time = ''

    @classmethod
    def to_record(cls, text):
        sub_list = text.split(',')
        sub_list.append(sub_list.pop(0))
        record = Record()
        record.code = sub_list[0].strip()
        record.curr_price = int(sub_list[4]) 
        record.open_price = int(sub_list[5])
        record.sell_call_price = int(sub_list[8])
        record.buy_call_price = int(sub_list[9])
        record.trading_amount = int(sub_list[10])
        record.priority_sell_remain_amount = int(sub_list[15].strip())
        record.priority_buy_remain_amount = int(sub_list[16].strip())
        record.name = sub_list[17].strip()
        record.yd_trading_amount = int(sub_list[20].strip()) # 22
        record.trading_unit = int(sub_list[27]) #35
        record.net_buy_program_amount = int(sub_list[43].strip()) #116
        record.close_price_sum_19 = int(sub_list[24].strip()) / 19 # 32
        record.close_price_sum_4 = int(sub_list[41].strip()) / 4 # 84
        record.close_price_sum_9 = int(sub_list[42].strip()) / 9 #85
        record.year_highest_price = int(sub_list[36].strip()) #63
        record.year_lowest_price = int(sub_list[37].strip()) #64
        record.time = sub_list[-1].split(':')[1].strip()

        record.market_cap = int(sub_list[18]) * record.curr_price
        return record

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
        self.items = deque() 
        self.moving_average = moving_average
        self.max_archiving = 60 / 5 * self.moving_average[-1] + 1
        self.moving_average_dict = OrderedDict()
        for key in self.moving_average:
            self.moving_average_dict[key] = 0

    def is_fill_item(self):
        return len(self.items) >= self.max_archiving

    def calculate_moving_average(self):
        # moving_average_dict.keys() 란 이평선:1분,5분,10분,20분, 등. 의 단위를 말해요.
        for k in self.moving_average_dict.keys():
            conv_k = k * G_UNIT
            cnt = len(self.items)
            if cnt > conv_k:
                self.moving_average_dict[k] -= self.items[-int(conv_k+1)]
            self.moving_average_dict[k] += self.items[-1]        

    def get_moving_average(self, key):
        v = self.moving_average_dict[key]
        cnt = len(self.items)
        conv_k = key * G_UNIT
        if cnt >= conv_k:
            cnt = conv_k
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

    def is_rightward(self, reverse=True):
        v = []
        for key in self.moving_average_dict.keys():
            v.append(self.get_moving_average(key))

        # 모두가 다르고, 앞에가 커야 해요., 앞에 값이 최신이니까요.
        return self.is_increase(v, reverse=reverse, is_contain_equal=False)

    def is_leftward(self, reverse=False):
        return self.is_rightward(reverse=reverse)

    def get_diff_sequence_moving_averages(self):
        v = []
        for key in self.moving_average_dict.keys():
            v.append(self.get_moving_average(key))

        v1 = v[1:]
        return [b - a for a, b in zip(v, v1)]

    def is_diff_sequence_rightward(self, reverse=True, is_contain_equal=False):
        v = self.get_diff_sequence_moving_averages()
        return self.is_increase(v, reverse=reverse, is_contain_equal=is_contain_equal)

    def is_diff_sequence_leftward(self, reverse=False, is_contain_equal=False):
        return self.is_diff_sequence_rightward(reverse=reverse, is_contain_equal=is_contain_equal)

    def is_buy(self):
        if not self.items:
            return False

        #return self.is_rightward() and self.is_diff_sequence_rightward(is_contain_equal=False)
        #return self.is_rightward()
        return self.is_rightward() and self.is_diff_sequence_rightward(is_contain_equal=False)

    def is_sell(self):
        if not self.items:
            return False

        return self.is_leftward() and self.is_diff_sequence_leftward(is_contain_equal=True)

class TradingAmountBox(ItemBox):
    def __init__(self, moving_average):
        super().__init__(moving_average)
        self.last_trading_amount = 0

    def put(self, record):
        value = record.trading_amount - self.last_trading_amount
        self.items.append(value)

        if self.max_archiving < len(self.items):
            self.items.popleft()
        self.calculate_moving_average()
        self.last_trading_amount = record.trading_amount

    #def is_buy(self):
        #first_key = self.moving_average[0]  # 첫번째 이평선
        #last_key = self.moving_average[1]  # 마지막 이평선
        #return self.get_moving_average(first_key) >= self.get_moving_average(last_key) * 100       


class PriorityBuyRemainAmountBox(ItemBox):
    def __init__(self, moving_average):
        super().__init__(moving_average)

    def put(self, record):
        self.items.append(record.priority_buy_remain_amount)
        if self.max_archiving < len(self.items):
            self.items.popleft()
        self.calculate_moving_average()

    def is_buy(self):
        first_key = self.moving_average[0]  # 첫번째 이평선
        last_key = self.moving_average[1]  # 마지막 이평선
        return self.get_moving_average(first_key) >= self.get_moving_average(last_key) * 3


class PriceBox(ItemBox):
    def __init__(self, moving_average):
        super().__init__(moving_average)

    def put(self, record):
        self.items.append(record.curr_price)
        if self.max_archiving < len(self.items):
            self.items.popleft()
        self.calculate_moving_average()


class GeneralBox(ItemBox):
    def __init__(self, moving_average, item_name='curr_price'):
        super().__init__(moving_average)
        self.item_name = item_name

    def put(self, record):
        self.items.append(getattr(record, self.item_name))
        if self.max_archiving < len(self.items):
            self.items.popleft()
        self.calculate_moving_average()


class GeneralReverseBox(ItemBox):
    def __init__(self, moving_average, item_name='curr_price'):
        super().__init__(moving_average)
        self.item_name = item_name

    def put(self, record):
        self.items.insert(0, getattr(record, self.item_name))
        if self.max_archiving < len(self.items):
            self.items.popleft()
        self.calculate_moving_average()

class ArchivePrices(dict):
    def __init__(self, buy_base_line):
        self.buy_base_line = buy_base_line

    def __missing__(self, key):
        value = ArchivePrice(self.buy_base_line)
        self[key] = value
        return value

    def __repr__(self):
        return f"ArchivePrices {self.buy_base_line} G_UNIT:{ArchivePrices.G_UNIT} "


class ArchivePrice:
    def __init__(self, buy_base_line):
        self.prices = deque()
        self.buy_base_line = buy_base_line
        self.max_cnt = list(buy_base_line.keys())[-1] * ArchivePrices.G_UNIT + 1 # 5초 마다 put 하니까요.

    def _get_inclination(self, before_minute):
        # n 분 전과 현재가를 비교하여, 몇 퍼센트의 증감이 있었는지 보고한다.
        index = before_minute * ArchivePrices.UNIT 
        if len(self.prices) <= index:
            return (False, None)

        before_price = self.prices[-index]
        curr_price = self.prices[-1]

        return (True, rate(curr_price - before_price, before_price))

    def put(self, record):
        if record.market_cap < G_LESS_CAPITAL:
            return False

        self.prices.append(record.curr_price)
        if len(self.prices) > self.max_cnt:
            self.prices.popleft()

    def is_buy(self):
        if self._is_buy_condition_avg():
            self.prices.clear()
            return True
        return False

    def _is_buy_condition(self):
        for minute, base_rate in self.buy_base_line.items():
            if self.max_cnt < (minute * ArchivePrices.UNIT):
                minute = self.max_cnt

            bret, v = self._get_inclination(minute)
            if not bret:
                return False

            if v < base_rate:
                return False
        
        return True

    def _is_buy_condition_avg(self):
        if self.max_cnt > len(self.prices):
            return False

        curr_price = self.prices[-1]
        for minute, base_rate in self.buy_base_line.items():
            avg_price = statistics.median([self.prices[index] for index in range(-minute * G_UNIT,-minute)])
            if rate(curr_price - avg_price, avg_price) < base_rate:
                return False
        return True

    def is_sell(self, record):
        return False


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
        self.price_box = PriceBox(moving_average_list)
        self.trading_amount_box = TradingAmountBox(moving_average_list)
        #self.priority_buy_remain_amount_box = PriorityBuyRemainAmountBox(moving_average_list)
        #self.net_buy_program_amount_box = GeneralBox(moving_average_list, 'net_buy_program_amount')
        #self.priority_sell_remain_amount_box = GeneralReverseBox(moving_average_list, 'priority_sell_remain_amount')
        self.code = ''

    def put(self, record):
        if not self.code:
            self.code = record.code

        if record.market_cap < G_LESS_CAPITAL:
            return False

        self.price_box.put(record)
        self.trading_amount_box.put(record)
        #self.priority_buy_remain_amount_box.put(record)
        #self.net_buy_program_amount_box.put(record) 
        #self.priority_sell_remain_amount_box.put(record)

    def is_buy(self):
        if not self.price_box.is_fill_item():
            return False
        #return self.price_box.is_buy() and self.priority_buy_remain_amount_box.is_buy()
        return self.price_box.is_buy() and self.trading_amount_box.is_buy()
            #and self.net_buy_program_amount_box.is_buy()
            #and self.trading_amount_box.is_buy()

    def is_sell(self, record):
        # 매도 조건은 없습니다.
        return False
        #return self.price_box.is_sell()

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
        self.priority_buy_remain_amount = 0
        self.net_buy_program_amount = 0

    @classmethod
    def buy(cls, record, money):
        t_record = TradingRecord()
        t_record.buy_event_time = record.time
        t_record.code = record.code
        t_record.name = record.name
        t_record.buy_price = record.sell_call_price
        if t_record.buy_price == 0 or record.trading_unit == 0:
            print(f"매매 불가 - {record}")
            return None

        t_record.amount = int(money/(record.trading_unit * record.sell_call_price))        
        if t_record.buy_cost > money:
            t_record.amount -= 1

        if t_record.amount <= 0:
            print(f"매매 불가 돈이 없어요 - 잔액:{money} 필요한 돈:{t_record.buy_price * record.trading_unit}")
            return None
        print(f"사는 군요  {record.time} {record.name}")
        return t_record

    @classmethod
    def sell(cls, trading_record, record):
        print(f"파는 군요  {record.time} {record.name}")
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
        self.balance = money
        self.buy_unit = self.balance * G_UNIT_BUY_PERCENT

    def delete(self, money):
        self.balance -= money

    def add(self, money):
        self.balance += money

    @property
    def buy_price_unit(self):
        return self.buy_unit if self.balance > self.buy_unit else self.balance

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

        money = self.asset.buy_price_unit
        t_record = TradingRecord.buy(record, money)
        if not t_record:
            return
    
        self.possessions[t_record.code] = t_record
        self.asset.delete(t_record.buy_cost)

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
        r = rate(t_record.last_price - t_record.highest_price, t_record.highest_price) 
        if r < decision_diff_highest_rate:
            return True

        # 구매가 대비 하락시, 매도.
        diff_rate = rate(t_record.last_price-t_record.buy_price, t_record.buy_price)
        if isinstance(diff_buying_rate, list):
            return diff_buying_rate[0] >= diff_rate or diff_buying_rate[1] <= diff_rate
        else:
            return diff_buying_rate >= diff_rate

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
        self.asset.add(t_record.sell_cost)
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

class Musician(metaclass=ABCMeta):
    def __init__(self):
        pass

    @abstractmethod
    def is_no_buying(self, record):
        pass

    @abstractmethod
    def reset_archive(self):
        pass

    @abstractmethod
    def do(self, in_line):
        pass

    @abstractmethod
    def out_condition(self, write_file_name):
        pass

    def write_condition(self, file_name, condition):
        with open(file_name, 'a') as fd:
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
    

class Haydn(Musician):
    # 5초 or 1분 단위로, 이전 특정 시점 대비 얼마나 올랐는가에 따라 매매.
    def __init__(self):
        #self.archives = ArchivePrices(OrderedDict({4:6, 10:9, 16:12}))  # -1.66 
        self.archives = ArchivePrices(OrderedDict({1:2.6, 3:3.6, 10:4.6, 20:5.6, 30:5.6, 60:5.6}))  # -2.83  
        self.trader = Trader()

        self.no_buying_rise_rate = 12.0
        self.diff_highest_rate = OrderedDict({60:-2.5, 90:-2.0, 120:-1.0, 150:-0.5}) # 분:증가 퍼센트
        self.diff_buying_rate = [-3,2]

    def is_no_buying(self, record):
        # 이미 올라 있으면 안사요.
        ascent_rate = rate(record.curr_price - record.open_price, record.open_price)  
        return ascent_rate > self.no_buying_rise_rate

    def reset_archive(self):
        self.archives.clear()

    def do(self, in_line):
        # 필요 값만 추출할까요?
        record = Record.to_record(in_line)

        # 09시 전에는 안해요.
        if record.time[-6:] < '090000':
            return        

        archive = self.archives[record.code]
        archive.put(record)

        if not self.is_no_buying(record) and archive.is_buy():
            self.trader.buy(record)

        if archive.is_sell(record) or \
            self.trader.is_sell(record, self.diff_highest_rate, self.diff_buying_rate):
            self.trader.sell(record)

    def out_condition(self, write_file_name):
        condition = f"BUY_INCLINATION: {self.archives} "
        condition += f" no_buying_rise_rate:{self.no_buying_rise_rate}, diff_highest_rate:{self.diff_highest_rate}, diff_buying_rate:{self.diff_buying_rate}"
        self.write_condition(write_file_name, condition)


class Handel(Musician):
    def __init__(self):
        super().__init__()

        self.archives_A = Archives([1,3,5,7]) # Item 의  List
        self.archives_B = Archives([1,5,10,15]) # Item 의  List, +2.69, +26,884 휴림로봇, 원티드랩, 포스코엠텍, 에스티팜, 아바텍 등
        self.trader = Trader()
        # 시작가 대비, diff_rise_rate 보다 높으면 매수금지.
        self.no_buying_rise_rate = 12.0
        # 최고가 대비, diff_highest_rate 보다 낮으면 매도.
        #self.diff_highest_rate = OrderedDict({20:-3.0, 40:-1.5, 60:0}) # 12.86
        #self.diff_highest_rate = OrderedDict({10:-2.0, 20:0})  # -7.46 
        #self.diff_highest_rate = OrderedDict({60:-3.0, 120:-1.5})  # origin
        self.diff_highest_rate = OrderedDict({60:-2.0, 120:-1.0}) 
        #self.diff_highest_rate = OrderedDict({10:0})  # -13.46 
        #self.diff_highest_rate = OrderedDict({5:-2.0, 10:-1.0, 15:0})  # -8.47 
        #self.diff_highest_rate = OrderedDict({5:-1.5, 10:-1.0, 30:0})  #  -15.03

        # 매수가 대비, diff_buying_rate 보다 낮으면 매도.
        self.diff_buying_rate = [-3.0,3.0] 

    def is_no_buying(self, record):
        # 이미 올라 있으면 안사요.
        ascent_rate = rate(record.curr_price - record.open_price, record.open_price)  
        return ascent_rate > self.no_buying_rise_rate

    def reset_archive(self):
        self.archives_A.clear()
        self.archives_B.clear()

    def do(self, in_line):
        # 필요 값만 추출할까요?
        record = Record.to_record(in_line)

        # 09시 전에는 안해요.
        if record.time[-6:] < '090000':
            return

        archive_A = self.archives_A[record.code]
        archive_A.put(record)

        if not self.is_no_buying(record) and archive_A.is_buy():
            self.trader.buy(record)

        archive_B = self.archives_B[record.code]
        archive_B.put(record)

        if not self.is_no_buying(record) and archive_B.is_buy():
            self.trader.buy(record)

        if archive_A.is_sell(record) or archive_B.is_sell(record):
        #if archive_B.is_sell(record):
            self.trader.sell(record)
            #del self.archives_B[record.code]

        if self.trader.is_sell(record, self.diff_highest_rate, self.diff_buying_rate):
            self.trader.sell(record)
            #del self.archives_B[record.code]

    def out_condition(self, write_file_name):
        condition = f"{__file__} 우하향시 - 매도, G_UNIT_BUY_PERCENT:{G_UNIT_BUY_PERCENT}, G_INIT_MONEY:{G_INIT_MONEY}, G_LESS_CAPITAL:{G_LESS_CAPITAL} MOVING_AVERAGE: {self.archives_B} "
        condition += f" no_buying_rise_rate:{self.no_buying_rise_rate}, diff_highest_rate:{self.diff_highest_rate}, diff_buying_rate:{self.diff_buying_rate}"
        self.write_condition(write_file_name, condition)


def get_input_files(path):
    rets = [os.path.join(path,f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith('.log')]
    rets.sort()
    return rets

def read_file(file_name):
    with open(file_name, 'r', encoding='utf-8') as fd:
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
    #algorithm = Haydn()
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
import asyncio, requests
import os, sys
import json
import traceback
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getredis import get_redis
from config.infor_load import spot_host, RENAME_SPOT_CURRENCY
from config.infor import SYMBOLS_OUT, SYMBOLS_PAIR
from libs import requestSession
from libs.database.getmysql import G_MysqlSession, Hedge_MysqlSession


async def getRate(SYMBOLS_PAIR_USDT=SYMBOLS_PAIR):
    ret = {}
    tasks = [[asyncio.create_task(get_redis.hgetall(i)), i] for i in SYMBOLS_PAIR_USDT]
    for i, symbol in tasks:
        price = await i
        if price:
            ret[symbol] = np.mean([float(v) for k, v in price.items() if 'update' not in k])

    url = spot_host + '/openApi/market/trade'
    for symbol in set(SYMBOLS_PAIR_USDT) - set(ret.keys()):
        data = {'symbol': symbol, 'size': 1}
        try:
            async with requestSession.G_RequestSession.request.get(url=url, params=data, timeout=30) as r:
                res = await r.json()
                if res.get('errno') == 0 and res.get('errmsg') == 'success' and res.get('result', {}).get('data'):
                    ret[symbol] = float(res['result']['data'][0]['price'])
        except:
            mm = traceback.format_exc()
            print(symbol, mm)
    ret['USDT-USDT'] = 1
    return ret


async def getRateUsdt(SYMBOLS_PAIR_USDT=SYMBOLS_PAIR):
    ret = {}
    SYMBOLS_PAIR_USDT = SYMBOLS_PAIR_USDT + ['BTC-USDT', 'ETH-USDT']
    tasks = [[asyncio.create_task(get_redis.hgetall(i)), i] for i in set(SYMBOLS_PAIR_USDT)]
    for i, symbol in tasks:
        price = await i
        if price:
            ret[symbol] = np.mean([float(v) for k, v in price.items() if 'update' not in k])
    Rate = {'USDT': 1}
    for k, v in ret.items():
        base, quote = k.split('-')
        if base == 'USDT' and v:
            Rate[quote] = 1 / v
        elif quote == 'USDT':
            Rate[base] = v
        elif quote in ['BTC', 'ETH']:
            Rate[base] = v * ret[quote + '-USDT']
        else:
            pass
    return Rate


# 自动获取交易对
def get_symbols():
    res = requests.get(spot_host + '/openApi/market/symbols', timeout=15, verify=False)
    symbols = []
    if res.status_code == 200:
        res = res.json()
        if res["errno"] == 0:
            symbols = [x["symbol"] for x in res["result"] if x["symbol"].split('-')[0] not in SYMBOLS_OUT]
    symbols = [s for s in symbols if s in SYMBOLS_PAIR]
    return symbols


def get_trade(symbols, size=1):
    trade = {}
    for s in symbols:
        res = requests.get(spot_host + '/openApi/market/trade', params={'symbol': s, 'size': size}, timeout=15, verify=False)
        if res.status_code == 200:
            res = res.json()
            if res["errno"] == 0 and res["result"]['data']:
                trade[s] = res["result"]['data'][0]['price']
    return trade


def get_precision():
    res = requests.get(spot_host + '/openApi/market/precision', timeout=15, verify=False)
    if res.status_code == 200:
        res = res.json()
        return {k: v for k, v in res["result"].items() if k not in SYMBOLS_OUT}
    return {}


async def get_pool_threshold(rate):
    hedge_param = {}
    sql = "select * from hedge_config"
    res, title = await Hedge_MysqlSession.fetch_all(sql=sql)
    for i in res:
        j = json.loads(i[1])
        threshold = min(j['hedge_threshold_USDT'] / float(rate.get(i[0], 0)), j['hedge_threshold']) if float(rate.get(i[0], 0)) else j['hedge_threshold']
        hedeg_ex = [ex for ex, v in j['exchanges'].items() if float(v.get('percent', 0)) > 0]
        hedge_param[i[0]] = {'threshold': threshold, 'status': j['status'], 'hedeg_ex': hedeg_ex}
        # hedge_param.append({'currency': i[0], 'threshold': threshold, 'status': j['status'], 'hedeg_ex': hedeg_ex})

    return hedge_param


async def get_pool():
    sql = """SELECT d.coin,SUM(d.amount) from (
    SELECT coin,amount from abc_asset_gap union 
    SELECT coin,amount from external_asset_gap union 
    SELECT coin,amount from fee_asset_gap
    ) d GROUP BY d.coin"""
    res, title = await Hedge_MysqlSession.fetch_all(sql)
    hedge = {i[0]: i[1] for i in res}
    return hedge


async def get_mongo_amount(now_time_dt, asset_position, type=None):
    # 获取每日的数据
    def get_next_zero_time(dt):
        datetime_obj = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        # 将日期加1天，并将时间部分设置为 00:00:00
        new_datetime_obj = datetime_obj + timedelta(days=1)
        new_datetime_obj = new_datetime_obj.replace(hour=0, minute=0, second=0)
        # 转换为字符串
        new_time_str = new_datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
        return new_time_str

    if type == 'ex_orders':
        sql = f"select begin_time,end_time, currency,amount from trades_orders_day ;"

    else:
        sql = f"select begin_time,end_time,currency,amount from mongodb_day ;"
    results, title = await G_MysqlSession.fetch_all(sql)
    print(sql)

    df = pd.DataFrame(results, columns=title)
    for coin, v in RENAME_SPOT_CURRENCY.items():
        dt = v['ts']
        dt_next = get_next_zero_time(dt)

        if dt < now_time_dt <= dt_next:
            if asset_position.get(coin):
                asset_position[v['now_name']] = asset_position.get(coin) + asset_position.get(v['now_name'], 0)
                asset_position.pop(coin)

        if now_time_dt > dt:
            df['currency'][(df['end_time'] <= dt_next) & (df['currency'] == v['last_name'])] = v['now_name']

    df = df.groupby(['currency'])['amount'].sum().reset_index()
    return df.set_index('currency')['amount'].to_dict(), asset_position


if __name__ == "__main__":
    # asyncio.run(getRateUsdt())
    asyncio.run(getRate())

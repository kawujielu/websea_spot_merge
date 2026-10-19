# coding=utf-8
import asyncio
import json
import loguru
import pandas as pd
import numpy as np
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getredis import get_redis_swap_kline, get_redis
from libs import heartbeat, sendmessage, get_time

from config.infor_swap import libs_dex_config

# 不提示警告
pd.set_option('mode.chained_assignment', None)
import httpx, time, random, redis
from collections import Counter

swap_chain = {'ETH': 'eth', 'BNB': 'bsc'}


def get_swap():
    swap = {}
    LEN = 0
    # for i in ['s_uni_mappers', 's_sushi_mappers', 's_pancake_mappers', 's_mdex_mappers', 's_matic_mappers', ]:
    for i in ['uniswapv2', 'uniswapv3', 'sushi', 'pancake', 'mdex', 'matic']:
        # a = getattr(libs_dex_config, i)
        a = libs_dex_config.s_dex_mappers[i]
        for symbol, v in a.items():
            base, quote = symbol.split('-')
            if base in ['ETH', 'BNB']:
                if swap.get(base, {}):
                    swap[base][quote] = v['second_address']
                else:
                    swap[base] = {quote: v['second_address']}
                LEN += 1
            if quote in ['ETH', 'BNB']:
                if swap.get(quote, {}):
                    swap.get(quote, {})[base] = v['first_address']
                else:
                    swap[quote] = {base: v['first_address']}
                LEN += 1
    return swap, LEN


#  eth量 刷量部分 USDt
#  bsc 如果是ETH 就是eth的量 如果是USD 就是USDT的量
# 提供数据，比本位

async def get_url(contractaddress, chain, resolution, quote, from_time, to_time):
    # resolution = '1D' 一天
    url = f'https://api.dex.guru/v1/tradingview/history'
    data = {"symbol": f"{contractaddress}-{chain}_{quote}",
            "resolution": resolution,
            "from": from_time,
            "to": to_time,
            }
    headers = {
        "User-Agent": 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Mobile Safari/537.36',
        # "User-Agent": 'Mozilla/5.0 (Windows NT 6.3 WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
        "Connection": "keep-alive",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8"
    }
    try:
        res = httpx.get(url=url, headers=headers, params=data, timeout=10)
        await asyncio.sleep(random.randint(1, 4))
    except Exception as e:
        loguru.logger.info(f'error:{e}')
        res = {}
    return res


async def get_swap_kline(contractaddress, symbol, chain, quote, rate_eth):
    to_time = int(time.time())
    from_time = int(to_time - 60 * 10)
    resolution = 1

    res = await get_url(contractaddress, chain, resolution, quote, from_time, to_time)
    rate = await get_redis.hgetall('BTC-USDT')
    rate = np.mean([float(v) for k, v in rate.items() if len(k) <= 5])
    if not rate:
        rate = 0

    rate1 = rate_eth if quote == 'ETH' else 1
    info = {}
    if res and res.status_code == 200:
        res = res.json()
        LEN_ts = len(res['t'])
        counter = Counter(res['v'])[0]
        if LEN_ts - counter >= 10 / 2 and rate != 0:
            info['volume'] = []
            info['volume_usdt'] = []
            info['ts'] = []
            info['update_time'] = int(time.time())
            for i in range(LEN_ts - 4, LEN_ts):
                info['volume'].append(round(res['v'][i] * rate1 / rate, 6))
                info['volume_usdt'].append(int(res['v'][i] * rate1))
                info['ts'].append(get_time.ATime().timestamp_to_timearray(res['t'][i]))
            # rdb.hmset(symbol, info)
            # rdb.expire(symbol, 60)
            print('---->>>', symbol, info)
        time.sleep(random.randint(1, 3))
    else:
        sendmessage.send_telegram_msg(message='swap_kline_1min', ser='Alarm')
        time.sleep(10 * 5)

    await get_redis_swap_kline.hset('swap_kline', symbol + '-USDT', json.dumps(info))


async def run_1min(swap, LEN):
    symbol_len = 0
    rate_eth = await get_redis.hgetall('ETH-USDT')
    rate_eth = np.mean([float(v) for k, v in rate_eth.items() if len(k) <= 5])
    if not rate_eth:
        rate_eth = 0

    for chain, v in swap.items():
        for symbol, address_list in v.items():
            await get_swap_kline(contractaddress=address_list, symbol=symbol, chain=swap_chain[chain],
                                 quote='USD', rate_eth=rate_eth, )
            symbol_len += 1
    if symbol_len == LEN:
        await heartbeat.i_live_well(server='kline-去中心化币种', frequency=60 * 16, index=31)


async def spot_run():
    while True:
        try:
            swap, LEN = get_swap()
            await run_1min(swap, LEN)
        except Exception as e:
            time.sleep(1 * 60)
            mess = f'error：swap_kline --{e}'
            sendmessage.send_telegram_msg(message=mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())

# coding=utf-8
import asyncio
import copy
import datetime
import random
import math
from web3 import Web3
import requests, time
import pandas as pd
import json
import os, sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
from config import infor_swap, infor
from spot.spot_setting import getRate
from exchange.mdex_libs.mdex import MdexSwap

path = sys.path[0]
filename = f'{path}/dex_pool_start.json'
# 币种树立增减幅度
PRO = 0.5
# 池子数量增减幅度
PRO_POOL = 1
# 计价货币的价值减少量
QUOTE_VALUE = 50 * 10000
QUOTE_VALUE_OTHER = {  # 'FCL': 40 * 10000,
}
QUOTE_VALUE_ALARM = 15 * 10000
QUOTE_VALUE_ALARM_OTHER = {  # 'BRIGHT': 15 * 10000,
}
AMOUNT_U = 50 * 10000
AMOUNT_COEF = 0.5

BASE_COIN = ['USDT', 'BNB', 'HT', 'ETH', 'BTC']


async def get_rate():
    SYMBOLS = [i + '-USDT' for i in BASE_COIN]
    # res_ht = float(requests.get('https://api.huobi.pro/market/trade?symbol=htusdt', timeout=10).json()['tick']['data'][0]['price'])
    rate = await getRate(SYMBOLS)
    rate = {k.replace('-USDT', ''): v for k, v in rate.items()}
    # rate['HT'] = res_ht
    rate_copy = copy.deepcopy(rate)
    for k, v in rate_copy.items():
        if k != 'USDT':
            rate[f'W{k}'] = v
        else:
            rate['BUSD'] = v
            rate['USDC'] = v
    return rate


async def sql_pool():
    sql = 'select * from swap_pool;'
    results, title = await G_MysqlSession.fetch_all(sql)
    index_chain = title.index('chain')
    index_symbol = title.index('symbol')
    index_pair_address = title.index('pair_address')
    index_amount_base = title.index('amount_base')
    index_amount_quote = title.index('amount_quote')
    results_old = {}
    for i in results:
        symbol = i[index_symbol]
        base, quote = symbol.split('-')
        chain = i[index_chain]
        pair_address = i[index_pair_address]
        amount_base = i[index_amount_base]
        amount_quote = i[index_amount_quote]
        results_old[symbol] = {'chain': chain, 'pair_address': pair_address, 'amount_base': amount_base, 'amount_quote': amount_quote}
        results_old[quote + '-' + base] = {'chain': chain, 'pair_address': pair_address, 'amount_base': amount_quote, 'amount_quote': amount_base}

    return results_old


def monitor_maker_pool(results):
    # 池子监控
    results_pool = []
    for i in results:
        results_pool.append({'symbol': i[2].split('-')[0], 'address_res': i[3].lower()})
    dice_mappers = []

    for chain, list_mapper in infor_swap.DEX_NODE_MAPPERS.items():
        for mapp in list_mapper['node_pools_mappers']:
            for currency, address in mapp.items():
                pair = address['pair_name']
                first, second = pair.split('-')
                curr = second if first in BASE_COIN else first
                dice_mappers.append({'symbol': curr, 'address_mapp': address['pair_address'].lower()})
    df1 = pd.DataFrame(results_pool)
    df2 = pd.DataFrame(dice_mappers)

    df = pd.merge(df1, df2, on=['symbol'], how='outer')
    df = df[['symbol', 'address_res', 'address_mapp']]
    df = df[df['address_mapp'] != df['address_res']]
    mess = ''
    if not df.empty:
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            address_res = df['address_res'].iloc[i]
            address_mapp = df['address_mapp'].iloc[i]

            mess += f'【{symbol}】\n' \
                    f'做市池子：{address_mapp}\n' \
                    f'监控池子：{address_res}\n'

    if mess != '':
        message = '做市池子和监控池子不一致，请检查池子\n' + mess
        sendmessage.send_telegram_msg(message, 'EmerWarning')


async def run_old():
    # 基础货币价格
    Rate = await get_rate()
    # 历史池子数量
    results = await sql_pool()

    h = datetime.datetime.now().hour
    m = datetime.datetime.now().minute
    if m < 35 and m > 25:
        # 做市池子是否和监控池子一致
        monitor_maker_pool(results)
        await heartbeat.i_live_well(server='做市价格池子监控', frequency=60 * 61 * 2, index=29)

    temp = []
    mess1, mess2, message = "", "", ""
    mess3, message_Alarm = "", ""
    for chain_name, node_mappers in infor_swap.DEX_NODE_MAPPERS.items():
        self_s = MdexSwap(random.choice(node_mappers['node_pools']))
        for pools_mappers in node_mappers['node_pools_mappers']:
            for currency, address in pools_mappers.items():
                symbol = address['pair_name']
                base, quote = symbol.split('-')
                pair_address = address['pair_address']
                base_address = address['first_address']
                quote_address = address['second_address']
                if currency == base:
                    symbol = base + '-' + quote
                    first_address = base_address
                    second_address = quote_address
                else:
                    symbol = quote + '-' + base
                    first_address = quote_address
                    second_address = base_address

                heco_first = self_s.erc20_contract(Web3.toChecksumAddress(first_address))
                heco_second = self_s.erc20_contract(Web3.toChecksumAddress(second_address))
                # first_decimal, second_decimal = int(heco_first.functions.decimals().call()), int(heco_second.functions.decimals().call())
                first_decimal, second_decimal = int(address['first_decimal']), int(address['second_decimal'])
                baseamount = heco_first.functions.balanceOf(Web3.toChecksumAddress(pair_address)).call() / math.pow(10, first_decimal)
                quoteamount = heco_second.functions.balanceOf(Web3.toChecksumAddress(pair_address)).call() / math.pow(10, second_decimal)

                baseamountOLD = results[symbol]['amount_base']
                quoteamountOLD = results[symbol]['amount_quote']
                quote_rate = Rate.get(quote, 0)

                quote_pro = (quoteamount - quoteamountOLD) / quoteamountOLD
                quote_reduce_usdt = (quoteamount - quoteamountOLD) * quote_rate
                quote_now_usdt = quoteamount * quote_rate
                side = '增加' if quote_pro > 0 else '减少'
                mess = f"【{base}-{quote}】\n" \
                       f"当前{base}: {int(baseamount)}\n" \
                       f"初始{base}: {int(baseamountOLD)}\n" \
                       f"当前{quote}: {int(quoteamount)}\n" \
                       f"初始{quote}: {int(quoteamountOLD)}\n" \
                       f"{side}幅度: {round(quote_pro * 100, 2)}%\n" \
                       f"{side}市值｜U: {int(quote_reduce_usdt)}\n" \
                       f"当前市值｜U:{int(quote_now_usdt)}\n"

                quote_now_usdt = quoteamount * quote_rate
                QUOTE_VALUE1 = QUOTE_VALUE_OTHER[base] if base in QUOTE_VALUE_OTHER.keys() else QUOTE_VALUE
                QUOTE_VALUE_ALARM1 = QUOTE_VALUE_ALARM_OTHER[base] if base in QUOTE_VALUE_ALARM_OTHER.keys() else QUOTE_VALUE_ALARM
                if abs(quote_now_usdt) < QUOTE_VALUE1:
                    mess2 += mess
                if abs(quote_now_usdt) < QUOTE_VALUE_ALARM1:
                    mess3 += mess
                time.sleep(random.uniform(0, 2))
            if mess1 != "":
                message = f'当前<币种>数量增减幅度超过{round(PRO * 100, 2)}%\n{mess1}\n'
            if mess2 != "":
                message += f'\n当前<币种>市值低于{round(QUOTE_VALUE / 10000)}W USDT\n{mess2}\n'
            if message != "":
                sendmessage.send_telegram_msg(message, 'dex_info')
                print(message)
            if mess3 != "":
                mes = f'\n当前<币种>市值低于{round(QUOTE_VALUE_ALARM / 10000)}W USDT\n请检查做市和对冲\n{mess3}\n'
                sendmessage.send_telegram_msg(mes, 'EmerWarning')

            return temp


async def get_dex_pool():
    # 基础货币价格
    # Rate = await get_rate()
    swap_pool = {}
    for chain_name, node_mappers in infor_swap.DEX_NODE_MAPPERS.items():
        if not node_mappers['node_pools']:
            continue
        self_s = MdexSwap(random.choice(node_mappers['node_pools']))
        for pools_mappers in node_mappers['node_pools_mappers']:
            for currency, address in pools_mappers.items():
                symbol = address['pair_name']
                first, second = symbol.split('-')
                pair_address = address['pair_address']
                base_address = address['first_address']
                quote_address = address['second_address']

                if currency in infor.SYMBOLS_LIST:
                    if currency == first:
                        symbol = first + '-' + second
                        first_address = base_address
                        second_address = quote_address
                        base, quote = first, second
                        first_decimal, second_decimal = int(address['first_decimal']), int(address['second_decimal'])
                    else:
                        symbol = second + '-' + first
                        first_address = quote_address
                        second_address = base_address
                        base, quote = second, first
                        second_decimal, first_decimal = int(address['first_decimal']), int(address['second_decimal'])

                    heco_first = self_s.erc20_contract(Web3.toChecksumAddress(first_address))
                    heco_second = self_s.erc20_contract(Web3.toChecksumAddress(second_address))
                    # first_decimal, second_decimal = int(heco_first.functions.decimals().call()), int(heco_second.functions.decimals().call())
                    # first_decimal, second_decimal = int(address['first_decimal']), int(address['second_decimal'])
                    baseamount = heco_first.functions.balanceOf(Web3.toChecksumAddress(pair_address)).call() / math.pow(10, first_decimal)
                    quoteamount = heco_second.functions.balanceOf(Web3.toChecksumAddress(pair_address)).call() / math.pow(10, second_decimal)
                    # quoteamount_u = Rate.get(quote, 0) * quoteamount
                    swap_pool[symbol] = {'address': pair_address, 'baseamount': baseamount, 'quoteamount': quoteamount}
    # swap_pool['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return swap_pool


async def run():
    try:
        dex_pool_start = json.load(open(filename))
        print('本地池子', dex_pool_start)
    except:
        dex_pool_start = {}
        json.dump(dex_pool_start, open(filename, 'w'))
        print('获取初始池子数据')
        sys.exit()
    dex_pool_start.pop("timestamp", "")
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    dex_pool_now = await get_dex_pool()

    if not dex_pool_now:
        return
    Rate = await get_rate()

    dex_pool_symbol_add = set(dex_pool_now) - set(dex_pool_start)
    dex_pool_symbol_out = set(dex_pool_start) - set(dex_pool_now)

    dex_pool_start_copy = copy.deepcopy(dex_pool_start)
    msg_add, msg_out = "", ""
    for s in dex_pool_symbol_add:
        base, quote = s.split('-')
        msg_add += f"【{s}】池子大小:{int(dex_pool_now[s]['quoteamount'] * Rate.get(quote, 0)):,}U\n"
        dex_pool_start_copy[s] = dex_pool_now[s]

    for s in dex_pool_symbol_out:
        base, quote = s.split('-')
        msg_out += f"【{s}】池子大小:{int(dex_pool_start[s]['quoteamount'] * Rate.get(quote, 0)):,}U\n"
        dex_pool_start_copy.pop(s, '')
    msg = ""
    if msg_add:
        msg += f"增加池子监控:\n{msg_add}\n"
    if msg_out:
        msg += f"剔除池子监控:\n{msg_out}\n"
    msg_small, msg_reduce = "", ""

    symbols = set(dex_pool_start.keys()) & set(dex_pool_now.keys())
    for s in symbols:
        if s == 'timestamp':
            continue
        base, quote = s.split('-')
        if (base in infor.SYMBOLS_LIST and quote in BASE_COIN):

            amount_u = dex_pool_now[s]['quoteamount'] * Rate.get(quote, 0)
            amount_u_start = dex_pool_start[s]['quoteamount'] * Rate.get(quote, 0)
            if amount_u < AMOUNT_U:
                msg_small += f"【{s}】池子大小:{int(amount_u)}U\n"
            if amount_u_start and amount_u / amount_u_start <= AMOUNT_COEF:
                msg_reduce += f"【{s}】当前池子:{int(amount_u)}U 初始池子:{int(amount_u_start)}U \n"

    if msg_reduce:
        msg += f"池子量低于初始值监控的{int(AMOUNT_COEF * 100)}%:\n{msg_reduce}\n"
    if msg_small:
        msg += f"池子量低于{int(AMOUNT_U)}U:\n{msg_small}\n"

    if msg:
        msg = '链上池子监控\n' + msg
        sendmessage.send_telegram_msg(msg, 'spot_info')
        sendmessage.send_telegram_msg(msg, 'EmerWarning1')

    dex_pool_start_copy['timestamp'] = timestamp

    json.dump(dex_pool_start_copy, open(filename, 'w'))


async def spot_run():
    try:
        await run()
        await heartbeat.i_live_well(server='uni池子监控', frequency=60 * 60 * 2.5, index=29)
    except Exception as e:
        mess = f'error：uniswap池子监控-->{traceback.format_exc()}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())

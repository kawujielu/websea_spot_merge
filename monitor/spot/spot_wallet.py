# coding=utf-8
import pandas as pd
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor
from exchange.restful_api.abc_spot import AApi

# 不提示警告
pd.set_option('mode.chained_assignment', None)


async def get_wallet():
    currency = "RNDR"
    for k, v in infor.spot_account.items():
        ao = AApi(token=v['apikey']['token'], secret_key=v['apikey']['sk'])
        res = await ao.wallet()
        id = v['id']
        # print(k, v['id'], res)
        d = {i['currency']: float(i['available']) + float(i['frozen']) for i in res['result'] if float(i['available']) + float(i['frozen'])}
        if currency and d.get(currency):
            print(f"id:{id}, 账户:{k} 数量：", d.get(currency))
        if not currency:
            print(id, k, d)


if __name__ == "__main__":
    asyncio.run(get_wallet())

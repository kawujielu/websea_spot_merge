import sys
from pathlib import Path

_MERGE_ROOT = Path(__file__).resolve().parents[2]
if str(_MERGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MERGE_ROOT))

from abclibs import config as libs_config
from abclibs import price as libs_price
from abclibs import price_async as libs_price_async
from abclibs import account as _libs_account_mod
from abclibs import dex_config as libs_dex_config

# 兼容旧代码里偶发引用
REMOTE_INTERNAL_IP = "127.0.0.1"

if libs_config.DEBUG:
    libs_account = _libs_account_mod.account_test
else:
    libs_account = _libs_account_mod.account

s_dex_mappers = libs_dex_config.s_dex_mappers

eth_node_pools = libs_dex_config.eth_node_pools
bsc_node_pools = libs_dex_config.bsc_node_pools
heco_node_pools = libs_dex_config.heco_node_pools
matic_node_pools = libs_dex_config.matic_node_pools

price_dex_price_ex_symbols = libs_config.price_dex_price_ex_symbols
price_dex_price_ex_transfer_symbols = libs_config.price_dex_price_ex_transfer_symbols

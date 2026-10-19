import sys
from pathlib import Path

_MERGE_ROOT = Path(__file__).resolve().parents[2]
if str(_MERGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MERGE_ROOT))

from abclibs import config as libs_config
from abclibs import price_async as libs_price_async
from abclibs import account as libs_accounts
from abclibs import dex_config as libs_dex_config

REMOTE_INTERNAL_IP = "127.0.0.1"

if libs_config.DEBUG:
    libs_account = libs_accounts.account_test
else:
    libs_account = libs_accounts.account

libs_ex_account = libs_accounts.exchange_accounts

s_dex_mappers = libs_dex_config.s_dex_mappers

eth_node_pools = libs_dex_config.eth_node_pools
bsc_node_pools = libs_dex_config.bsc_node_pools
heco_node_pools = libs_dex_config.heco_node_pools
matic_node_pools = libs_dex_config.matic_node_pools

price_dex_price_ex_symbols = libs_config.price_dex_price_ex_symbols
price_dex_price_ex_transfer_symbols = libs_config.price_dex_price_ex_transfer_symbols

spec_symbol_rate_map = libs_config.SPEC_SYMBOL_RATE_MAPPING
spec_symbol_rate_mapping = {}
for ex, v in spec_symbol_rate_map.items():
    spec_symbol_rate_mapping[ex] = {}
    for symbol, j in v.items():
        spec_symbol_rate_mapping[ex][j[0]] = j[1]

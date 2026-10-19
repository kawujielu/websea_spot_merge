import sys
from pathlib import Path

_MERGE_ROOT = Path(__file__).resolve().parents[2]
if str(_MERGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MERGE_ROOT))

from abclibs import config as libs_config
from abclibs import price as libs_price
from abclibs import price_async as libs_price_async
from abclibs import account as libs_account
from abclibs import dex_config as libs_dex_config

REMOTE_INTERNAL_IP = "127.0.0.1"

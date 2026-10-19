import os
from load import load_remote

# 单机整合默认本机；过渡期 export ABCLIBS_HOST=10.0.209.181
REMOTE_IP = os.environ.get("ABCLIBS_HOST", "127.0.0.1")
REMOTE_INTERNAL_IP = REMOTE_IP

libs_config = load_remote.urllib_model("server@{}".format(REMOTE_IP), "/home/server/abclibs/config.py")
libs_price = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price.py")
libs_price_async = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/price_async.py")
libs_account = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/account.py")
libs_dex_config = load_remote.urllib_model("server@{}".format(REMOTE_IP, ), "/home/server/abclibs/dex_config.py")
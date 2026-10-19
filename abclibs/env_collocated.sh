#!/bin/bash
# 单机整合环境变量：在各项目启动前 source，或写入 ~/.bashrc / systemd Environment=
# 用法: source /home/server/abclibs/env_collocated.sh
#
# 前置条件（AWS Ubuntu 8C16G）:
# 1) abclibs 部署于 /home/server/abclibs，本机可 ssh server@127.0.0.1 免密
# 2) 各项目 conda env 仍独立: trading / spot_market_maker / spot_paddington / monitor
# 3) 8C16G 请盯 CPU/内存；做市可先只起 SERVER=1,2，再视情况开 SERVER=3
#
# 若未配好 server@127.0.0.1，会出现 Permission denied (publickey)，
# 过渡期可临时: export ABCLIBS_HOST=10.0.209.181

export ABCLIBS_HOST="${ABCLIBS_HOST:-127.0.0.1}"

# 推荐二选一：
# A) 把本机 hostname 写进白名单
if [ -n "$(hostname)" ]; then
  export WEBSEA_ONLINE_HOST="${WEBSEA_ONLINE_HOST:-$(hostname)}"
fi
# B) 或强制线上: export WEBSEA_FORCE_ONLINE=1

echo "ABCLIBS_HOST=$ABCLIBS_HOST WEBSEA_ONLINE_HOST=$WEBSEA_ONLINE_HOST WEBSEA_FORCE_ONLINE=${WEBSEA_FORCE_ONLINE:-}"

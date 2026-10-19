#!/bin/bash
# 单机整合环境变量：在各项目启动前 source，或写入 ~/.bashrc / systemd Environment=
# 用法: source /home/ubuntu/code/websea_spot_merge/abclibs/env_collocated.sh
#
# 前置条件（AWS Ubuntu 单机）:
# 1) 代码在 /home/ubuntu/code/websea_spot_merge，同级含 abclibs 与各业务目录
# 2) 各项目通过本地 import abclibs，无需 SSH / load_remote
# 3) 各项目 conda env 仍独立: trading / spot_market_maker / spot_paddington / monitor
# 4) 8C16G 请盯 CPU/内存；做市可先只起 SERVER=1,2，再视情况开 SERVER=3

# 推荐二选一：
# A) 把本机 hostname 写进白名单
if [ -n "$(hostname)" ]; then
  export WEBSEA_ONLINE_HOST="${WEBSEA_ONLINE_HOST:-$(hostname)}"
fi
# B) 或强制线上: export WEBSEA_FORCE_ONLINE=1

echo "WEBSEA_ONLINE_HOST=$WEBSEA_ONLINE_HOST WEBSEA_FORCE_ONLINE=${WEBSEA_FORCE_ONLINE:-}"

#!/bin/bash
# 单机整合：同一台机器起 SERVER=1/2/3 覆盖原多机分片
# 资源紧张时可只起 SERVER=1+2（USDT），BTC 视负载再开 SERVER=3

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MERGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -f "$MERGE_ROOT/abclibs/env_collocated.sh" ]; then
  # shellcheck disable=SC1091
  . "$MERGE_ROOT/abclibs/env_collocated.sh"
fi
export WEBSEA_FORCE_ONLINE="${WEBSEA_FORCE_ONLINE:-1}"

PYTHON_DIR="${PYTHON_DIR:-/home/ubuntu/miniconda3/envs/spot_market_maker/bin}"

pkill -f 'manage.py run SERVER=' || true
sleep 1

nohup "$PYTHON_DIR/python3.11" manage.py run SERVER=1 >> nohup.out 2>&1 &
sleep 1
nohup "$PYTHON_DIR/python3.11" manage.py run SERVER=2 >> nohup.out 2>&1 &
sleep 1
nohup "$PYTHON_DIR/python3.11" manage.py run SERVER=3 >> nohup.out 2>&1 &
sleep 1

ps aux | grep -E 'manage.py run SERVER=' | grep -v grep || true
echo '---------success -----------'
echo "Logs: tail -f $SCRIPT_DIR/nohup.out"

#!/bin/bash
# 单机整合：同一台机器起 SERVER=1/2/3 覆盖原多机分片
# 8C16G 资源紧张时可只起 SERVER=1+2（USDT），BTC 视负载再开 SERVER=3

pkill -f 'spot_market_maker/bin/python3.11 manage.py run SERVER='

PYTHON_DIR=/home/ubuntu/miniconda3/envs/spot_market_maker/bin

nohup $PYTHON_DIR/python3.11 manage.py run SERVER=1 >> nohup.out 2>&1 &
sleep 1
nohup $PYTHON_DIR/python3.11 manage.py run SERVER=2 >> nohup.out 2>&1 &
sleep 1
nohup $PYTHON_DIR/python3.11 manage.py run SERVER=3 >> nohup.out 2>&1 &
sleep 1
exec ps aux | grep -E 'manage.py run SERVER=' | grep -v grep
echo '---------success -----------'
echo 'Logs CMD :'
echo 'tail -f nohup.out'

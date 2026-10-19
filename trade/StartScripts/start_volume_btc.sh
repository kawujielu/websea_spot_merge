export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

# 只重启 BTC 对标刷量；不要 pkill volume_maker_self（与 start_volume.sh 共用一个 self）
pkill -f "launcher_volume_maker/volume_maker_center.py run BTC"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_volume_maker/volume_maker_center.py run BTC >> $CODE_DIR/StartScripts/log/volume_btc.log &

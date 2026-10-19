export PYTHONPATH=..
PYTHON_DIR=/home/ubuntu/miniconda3/envs/trading/bin
CODE_DIR=/home/ubuntu/code/trade

pkill -f "launcher_volume_maker/volume_maker_center.py run USDT"
# 自刷量全局唯一进程，仅由本脚本管理；start_volume_btc.sh 不再杀/启 self
pkill -f "launcher_volume_maker/volume_maker_self.py"

nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_volume_maker/volume_maker_center.py run USDT >> $CODE_DIR/StartScripts/log/volume_usdt.log &
nohup $PYTHON_DIR/python3.11 $CODE_DIR/launcher_volume_maker/volume_maker_self.py >> $CODE_DIR/StartScripts/log/volume_self.log &

#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_volume_maker/volume_maker_center.py run USDT" || true
# 自刷量全局唯一进程，仅由本脚本管理；start_volume_btc.sh 不再杀/�?self
pkill -f "launcher_volume_maker/volume_maker_self.py" || true

nohup "$PYTHON_BIN" "$CODE_DIR/launcher_volume_maker/volume_maker_center.py" run USDT \
  >> "$LOG_DIR/volume_usdt.log" 2>&1 &
nohup "$PYTHON_BIN" "$CODE_DIR/launcher_volume_maker/volume_maker_self.py" \
  >> "$LOG_DIR/volume_self.log" 2>&1 &
echo "started volume USDT+self -> $LOG_DIR/volume_usdt.log / volume_self.log"

#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

# 只重启 BTC 对标刷量；不要 pkill volume_maker_self（与 start_volume.sh 共用一个 self）
pkill -f "launcher_volume_maker/volume_maker_center.py run BTC" || true

nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_volume_maker/volume_maker_center.py" run BTC \
  >> "$LOG_DIR/volume_btc.log" 2>&1 &
echo "started volume BTC -> $LOG_DIR/volume_btc.log"

#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_volume_maker/volume_maker_ws_source.py" || true

nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_volume_maker/volume_maker_ws_source.py" \
  >> "$LOG_DIR/volume_maker_ws_source.log" 2>&1 &
echo "started volume_ws_source -> $LOG_DIR/volume_maker_ws_source.log"

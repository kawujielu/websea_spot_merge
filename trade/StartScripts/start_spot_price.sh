#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_spot_price_server/spot_price.py" || true

nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_spot_price_server/spot_price.py" \
  >> "$LOG_DIR/spot_price.log" 2>&1 &
echo "started spot_price -> $LOG_DIR/spot_price.log"

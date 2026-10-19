#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_dex_server/price_dex_server.py" || true

nohup "$PYTHON_BIN" "$CODE_DIR/launcher_dex_server/price_dex_server.py" \
  >> "$LOG_DIR/price_dex_server.log" 2>&1 &
echo "started dex_price -> $LOG_DIR/price_dex_server.log"

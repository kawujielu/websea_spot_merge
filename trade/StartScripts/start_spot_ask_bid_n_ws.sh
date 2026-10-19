#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_spot_price_server/spot_ask_bid_center.py run bn" || true
pkill -f "launcher_spot_price_server/spot_ask_bid_center.py run hb,okex,gate,mxc,bitget,kraken" || true

nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_spot_price_server/spot_ask_bid_center.py" run bn \
  >> "$LOG_DIR/spot_ask_bid_center_1.log" 2>&1 &
nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_spot_price_server/spot_ask_bid_center.py" run hb,okex,gate,mxc,bitget,kraken \
  >> "$LOG_DIR/spot_ask_bid_center_2.log" 2>&1 &
echo "started spot_ask_bid -> $LOG_DIR/spot_ask_bid_center_*.log"

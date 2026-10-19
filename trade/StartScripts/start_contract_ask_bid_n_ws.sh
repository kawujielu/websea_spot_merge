#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_contract/contract_price_from_contract_ask_bid.py" || true

nohup "$PYTHON_DIR/python3.11" "$CODE_DIR/launcher_contract/contract_price_from_contract_ask_bid.py" \
  >> "$LOG_DIR/contract_price_from_contract_ask_bid.log" 2>&1 &
echo "started contract_ask_bid -> $LOG_DIR/contract_price_from_contract_ask_bid.log"

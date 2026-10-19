#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_env.sh"

pkill -f "launcher_contract/contract_close.py" || true

nohup "$PYTHON_BIN" "$CODE_DIR/launcher_contract/contract_close.py" \
  >> "$LOG_DIR/contract_close.log" 2>&1 &
echo "started contract_close -> $LOG_DIR/contract_close.log"

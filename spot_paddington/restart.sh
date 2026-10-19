#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MERGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -f "$MERGE_ROOT/abclibs/env_collocated.sh" ]; then
  # shellcheck disable=SC1091
  . "$MERGE_ROOT/abclibs/env_collocated.sh"
fi
export WEBSEA_FORCE_ONLINE="${WEBSEA_FORCE_ONLINE:-1}"

PYTHON_DIR="${PYTHON_DIR:-/home/ubuntu/miniconda3/envs/spot_paddington/bin}"

pkill -f 'spot_paddington/bin/python3.11 launcher.py' || true
pkill -f "$SCRIPT_DIR/launcher.py" || true

nohup "$PYTHON_DIR/python3.11" launcher.py >> nohup.out 2>&1 &
sleep 1
ps aux | grep -E 'launcher.py' | grep -v grep || true
echo '---------success -----------'
echo "Logs: tail -f $SCRIPT_DIR/nohup.out"

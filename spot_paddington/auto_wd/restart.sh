#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PAD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MERGE_ROOT="$(cd "$PAD_ROOT/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

export PYTHONPATH="$PAD_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [ -f "$MERGE_ROOT/abclibs/env_collocated.sh" ]; then
  # shellcheck disable=SC1091
  . "$MERGE_ROOT/abclibs/env_collocated.sh"
fi
export WEBSEA_FORCE_ONLINE="${WEBSEA_FORCE_ONLINE:-1}"

PYTHON_DIR="${PYTHON_DIR:-/home/ubuntu/miniconda3/envs/spot_paddington/bin}"

pkill -f 'auto_wd/wd.py' || true

nohup "$PYTHON_DIR/python3.11" "$SCRIPT_DIR/wd.py" >> "$SCRIPT_DIR/nohup.out" 2>&1 &
echo "started wd.py -> $SCRIPT_DIR/nohup.out"

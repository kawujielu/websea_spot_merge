# 由同目录 start_*.sh source；勿单独执行
# 依赖调用方已设置 SCRIPT_DIR，或根据 $0 推断（bash 下 source 时 $0 仍为调用脚本）

if [ -z "${SCRIPT_DIR:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MERGE_ROOT="$(cd "$CODE_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

export PYTHONPATH="$CODE_DIR${PYTHONPATH:+:$PYTHONPATH}"
PYTHON_DIR="${PYTHON_DIR:-/home/ubuntu/miniconda3/envs/trading/bin}"

if [ -f "$MERGE_ROOT/abclibs/env_collocated.sh" ]; then
  # shellcheck disable=SC1091
  . "$MERGE_ROOT/abclibs/env_collocated.sh"
fi
export WEBSEA_FORCE_ONLINE="${WEBSEA_FORCE_ONLINE:-1}"

# 由同目录 start_*.sh source；勿单独执行
# 依赖调用方已设置 SCRIPT_DIR，或根据 $0 推断（bash 下 source 时 $0 仍为调用脚本）
#
# 需要 conda 环境 trading（Python 3.11）：
#   conda create -y -n trading python=3.11
#   conda activate trading && pip install -r ../requirements.txt
# 或: conda env create -f ../trading_env.yml

if [ -z "${SCRIPT_DIR:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MERGE_ROOT="$(cd "$CODE_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

export PYTHONPATH="$CODE_DIR${PYTHONPATH:+:$PYTHONPATH}"
PYTHON_DIR="${PYTHON_DIR:-/home/ubuntu/miniconda3/envs/trading/bin}"
PYTHON_BIN="$PYTHON_DIR/python3.11"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: 找不到 $PYTHON_BIN" >&2
  echo "请先创建 trading 环境，例如:" >&2
  echo "  conda create -y -n trading python=3.11" >&2
  echo "  conda activate trading" >&2
  echo "  pip install -U pip setuptools wheel" >&2
  echo "  pip install -r $CODE_DIR/requirements.txt" >&2
  echo "或: conda env create -f $CODE_DIR/trading_env.yml" >&2
  exit 1
fi

if [ -f "$MERGE_ROOT/abclibs/env_collocated.sh" ]; then
  # shellcheck disable=SC1091
  . "$MERGE_ROOT/abclibs/env_collocated.sh"
fi
export WEBSEA_FORCE_ONLINE="${WEBSEA_FORCE_ONLINE:-1}"

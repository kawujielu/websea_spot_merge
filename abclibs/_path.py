"""把 merge 根目录加入 sys.path，供各业务项目本地导入 abclibs。"""
import sys
from pathlib import Path


def ensure_merge_root_on_path(caller_file: str, parents_up: int = 2) -> Path:
    """
    caller_file: 调用方 __file__
    parents_up: 相对调用方文件上溯到 merge 根的层数
      - project/libs/__init__.py -> 2
      - project/config/infor_load.py -> 2
    """
    merge_root = Path(caller_file).resolve().parents[parents_up]
    root = str(merge_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    return merge_root

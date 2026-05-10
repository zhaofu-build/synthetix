"""
文件路径安全工具

校验用户提供的文件路径是否在允许的目录内，防止路径遍历攻击。
"""
import os
from typing import Optional

from src import config

# 允许的根目录列表
_ALLOWED_ROOTS: Optional[list] = None


def _get_allowed_roots() -> list:
    global _ALLOWED_ROOTS
    if _ALLOWED_ROOTS is None:
        root = str(config.ROOT_DIR_WIN)
        _ALLOWED_ROOTS = [
            os.path.normcase(os.path.realpath(root)),
            os.path.normcase(os.path.realpath(os.path.join(root, "static"))),
        ]
    return _ALLOWED_ROOTS


def validate_path_in_allowed_dir(path: str) -> str:
    """
    校验路径在允许的目录内。

    Args:
        path: 待校验的文件或目录路径

    Returns:
        校验通过的绝对路径

    Raises:
        ValueError: 路径不在允许的目录内
    """
    if not path:
        raise ValueError("路径不能为空")

    abs_path = os.path.normcase(os.path.realpath(path))

    for allowed in _get_allowed_roots():
        if abs_path.startswith(allowed + os.sep) or abs_path == allowed:
            return abs_path

    raise ValueError(f"路径不在允许的目录内: {path}")

"""
分析结果缓存 — ASR/VL/ffprobe 结果按文件哈希+参数缓存到本地 JSON 文件。

缓存结构: ~/.synthetix/cache/<hash>.json
键: file_path + 参数 → SHA256 hash
值: { "result": ..., "cached_at": timestamp, "file_mtime": mtime }
"""
import hashlib
import json
import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".synthetix", "cache")
DEFAULT_TTL = 3600 * 24  # 24 hours


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(file_path: str, prefix: str, **kwargs) -> str:
    h = hashlib.sha256()
    h.update(str(file_path).encode())
    h.update(prefix.encode())
    if kwargs:
        h.update(json.dumps(kwargs, sort_keys=True, default=str).encode())
    return h.hexdigest()


def get_cached(file_path: str, prefix: str, ttl: int = DEFAULT_TTL, **kwargs) -> Optional[Any]:
    _ensure_dir()
    key = _cache_key(file_path, prefix, **kwargs)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() - entry.get("cached_at", 0) > ttl:
            return None
        if os.path.exists(file_path):
            if abs(os.path.getmtime(file_path) - entry.get("file_mtime", 0)) > 1:
                return None
        return entry.get("result")
    except Exception:
        return None


def set_cached(file_path: str, prefix: str, result: Any, **kwargs):
    _ensure_dir()
    key = _cache_key(file_path, prefix, **kwargs)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"result": result, "cached_at": time.time(), "file_mtime": mtime}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"缓存写入失败: {e}")


def cached_result(prefix: str, ttl: int = DEFAULT_TTL, key_args: tuple = ()):
    """Decorator that caches function results by first arg (file_path) + key_args."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            file_path = str(args[0]) if args else ""
            cache_kwargs = {k: kwargs.get(k) for k in key_args if k in kwargs}
            cached = get_cached(file_path, prefix, ttl=ttl, **cache_kwargs)
            if cached is not None:
                logger.debug(f"[Cache] hit: {prefix} {os.path.basename(file_path)}")
                return cached
            result = func(*args, **kwargs)
            if result is not None:
                set_cached(file_path, prefix, result, **cache_kwargs)
            return result
        return wrapper
    return decorator


def clear_cache(prefix: Optional[str] = None):
    _ensure_dir()
    removed = 0
    for f in os.listdir(CACHE_DIR):
        if prefix and not f.startswith(hashlib.sha256(b"").hexdigest()):
            continue
        try:
            os.remove(os.path.join(CACHE_DIR, f))
            removed += 1
        except Exception:
            pass
    logger.info(f"[Cache] cleared {removed} entries")


def cache_stats() -> dict:
    _ensure_dir()
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {"count": len(files), "total_size_mb": round(total_size / 1024 / 1024, 2)}

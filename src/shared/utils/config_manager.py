"""
配置层级管理模块

合并顺序: .env 环境变量 > DB 用户覆盖 > 内嵌默认值
支持热更新：通过 API 触发 reload 从 DB 重新读取。
"""
import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

# 内嵌默认值（原 config/default.json）
_DEFAULTS: Dict[str, Any] = {
    "api": {
        "port": 9527,
        "cors_origins": [
            "http://localhost:9528",
            "http://127.0.0.1:9528",
            "http://localhost:9527",
            "http://127.0.0.1:9527",
        ],
    },
    "llm": {
        "model": "deepseek-chat",
        "fast_model": "",
        "mid_model": "",
        "slow_model": "",
        "fast_model_threshold": 100,
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "core_nexus": {
        "base_url": "http://127.0.0.1:9666",
        "api_key": "",
        "fallback_urls": {},
        "llm_model": "",
        "tts_model": "",
        "asr_model": "",
        "vl_model": "",
        "music_model": "",
        "image_model": "",
        "video_model": "",
        "image_to_video_model": "",
    },
    "agent": {
        "max_iterations": 5,
        "max_history": 50,
        "session_cleanup_interval": 600,
        "session_db_ttl": 86400,
    },
    "ffmpeg": {
        "default_crf": 23,
        "default_preset": "medium",
        "gpu_acceleration": True,
        "standardize_on_ingest": True,
    },
    "video": {
        "source_type": "pexels",
        "max_upload_size_mb": 500,
    },
    "web_search": {
        "enabled": False,
    },
    "ui": {
        "theme": "dark",
        "language": "zh-CN",
    },
}

_merged: Dict[str, Any] = {}
_lock = threading.Lock()

# 配置值校验规则: key_path → (type, min, max)
_VALIDATORS = {
    "api.port": (int, 1, 65535),
    "llm.fast_model_threshold": (int, 0, 100000),
    "agent.max_iterations": (int, 1, 50),
    "agent.max_history": (int, 10, 500),
    "agent.session_cleanup_interval": (int, 60, 86400),
    "agent.session_db_ttl": (int, 60, 604800),
    "ffmpeg.default_crf": (int, 0, 51),
    "video.max_upload_size_mb": (int, 1, 2048),
}


def _validate_value(key_path: str, value: Any) -> Any:
    """校验配置值，不合法则抛出 ValueError"""
    if key_path not in _VALIDATORS:
        return value
    expected_type, min_val, max_val = _VALIDATORS[key_path]
    if not isinstance(value, expected_type):
        raise ValueError(f"配置 {key_path} 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}")
    if value < min_val or value > max_val:
        raise ValueError(f"配置 {key_path} 范围错误: {min_val} ~ {max_val}, 实际 {value}")
    return value


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并字典，override 覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key.startswith('_'):
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """将嵌套字典展平为点分隔键值对"""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep))
        else:
            items[new_key] = v
    return items


def _unflatten_dict(flat: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
    """将点分隔键值对还原为嵌套字典"""
    result: Dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def _load_user_overrides() -> Dict[str, Any]:
    """从 DB config_store 表读取用户覆盖"""
    try:
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.config_store_repository import ConfigStoreRepository

        with get_db_context() as db:
            repo = ConfigStoreRepository(db)
            return repo.get_all_as_dict()
    except Exception as e:
        logger.debug(f"DB 配置读取失败（使用默认值）: {e}")
        return {}


def _migrate_from_settings_json():
    """一次性迁移: settings.json → DB"""
    if not _SETTINGS_FILE.is_file():
        return

    try:
        with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
    except Exception as e:
        logger.warning(f"读取 settings.json 失败，跳过迁移: {e}")
        return

    # 展平并过滤空值
    flat = _flatten_dict(user_data)
    non_empty = {k: v for k, v in flat.items() if v != "" and v != {} and v != []}

    if not non_empty:
        _rename_settings_backup()
        return

    # 检查 DB 是否已有数据
    try:
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.config_store_repository import ConfigStoreRepository

        with get_db_context(commit=True) as db:
            repo = ConfigStoreRepository(db)
            existing = repo.get_all_as_dict()
            if existing:
                logger.info("DB 已有配置，跳过 settings.json 迁移")
                _rename_settings_backup()
                return

            for key, value in non_empty.items():
                repo.upsert(key, value)

        logger.info(f"settings.json 迁移完成: {len(non_empty)} 项配置已写入 DB")
        _rename_settings_backup()
    except Exception as e:
        logger.warning(f"settings.json → DB 迁移失败: {e}")


def _rename_settings_backup():
    """重命名 settings.json 为 .bak"""
    try:
        bak_path = _SETTINGS_FILE.with_suffix('.json.bak')
        if bak_path.exists():
            bak_path.unlink()
        shutil.move(str(_SETTINGS_FILE), str(bak_path))
        logger.info(f"settings.json 已重命名为 {bak_path.name}")
    except Exception as e:
        logger.warning(f"重命名 settings.json 失败: {e}")


def load_config() -> Dict[str, Any]:
    """加载并合并配置"""
    global _merged

    with _lock:
        # 一次性迁移 settings.json（仅首次）
        _migrate_from_settings_json()

        # 从 DB 读取用户覆盖
        db_overrides = _load_user_overrides()

        # 将 DB 扁平键值还原为嵌套字典
        if db_overrides:
            nested_overrides = _unflatten_dict(db_overrides)
            _merged = _deep_merge(_DEFAULTS, nested_overrides)
        else:
            _merged = _DEFAULTS.copy()

    logger.info("配置加载完成（DB + 内嵌默认值）")
    return _merged


def reload_config() -> Dict[str, Any]:
    """热更新：重新加载配置"""
    return load_config()


def get(key_path: str, default: Any = None) -> Any:
    """
    按路径获取配置值

    Args:
        key_path: 点分隔的配置路径，如 "llm.model"
        default: 默认值

    Returns:
        配置值
    """
    if not _merged:
        load_config()

    keys = key_path.split('.')
    current = _merged
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def set_value(key_path: str, value: Any) -> None:
    """设置配置值并持久化到 DB"""
    _validate_value(key_path, value)

    if not _merged:
        load_config()

    with _lock:
        # 更新内存中的合并配置
        keys = key_path.split('.')
        current = _merged
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    # 持久化到 DB
    try:
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.config_store_repository import ConfigStoreRepository

        with get_db_context(commit=True) as db:
            repo = ConfigStoreRepository(db)
            repo.upsert(key_path, value)
        logger.info(f"配置已持久化到 DB: {key_path}")
    except Exception as e:
        logger.error(f"持久化配置到 DB 失败: {e}")


def get_all() -> Dict[str, Any]:
    """获取完整合并配置"""
    if not _merged:
        load_config()
    return _merged.copy()


# 启动时加载
load_config()

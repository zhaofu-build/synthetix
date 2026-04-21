"""
配置层级管理模块

合并顺序: .env 环境变量 > settings.json 用户覆盖 > default.json 默认值
支持热更新：修改 settings.json 后自动生效（通过 API 触发 reload）
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
_DEFAULT_FILE = _CONFIG_DIR / "default.json"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_merged: Dict[str, Any] = {}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 移除 _comment 等元数据
            data.pop('_comment', None)
            return data
    except Exception as e:
        logger.warning(f"加载配置文件失败 {path}: {e}")
        return {}


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


def load_config() -> Dict[str, Any]:
    """加载并合并配置"""
    global _merged
    default = _load_json(_DEFAULT_FILE)
    user = _load_json(_SETTINGS_FILE)
    _merged = _deep_merge(default, user)
    logger.info(f"配置加载完成: {_merged.get('llm', {}).get('model', 'default')}")
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
    """设置配置值并持久化到 settings.json"""
    if not _merged:
        load_config()

    keys = key_path.split('.')
    # 更新内存中的合并配置
    current = _merged
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value

    # 持久化到 settings.json
    user = _load_json(_SETTINGS_FILE)
    settings_current = user
    for k in keys[:-1]:
        if k not in settings_current or not isinstance(settings_current[k], dict):
            settings_current[k] = {}
        settings_current = settings_current[k]
    settings_current[keys[-1]] = value

    try:
        with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user, f, indent=2, ensure_ascii=False)
        logger.info(f"配置已持久化: {key_path} = {value}")
    except Exception as e:
        logger.error(f"持久化配置失败: {e}")


def get_all() -> Dict[str, Any]:
    """获取完整合并配置"""
    if not _merged:
        load_config()
    return _merged.copy()


# 启动时加载
load_config()

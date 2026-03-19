"""配置工具模块

提供高效的配置访问方式
"""
import logging
import importlib
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 配置模块缓存
_config_module = None
_config_mtime: float = 0


def get_config_module():
    """获取配置模块（带缓存）

    Returns:
        config 模块对象
    """
    global _config_module, _config_mtime

    try:
        import os
        current_mtime = os.path.getmtime('config.py')
        if _config_module is not None and current_mtime == _config_mtime:
            return _config_module
    except FileNotFoundError:
        pass

    try:
        _config_module = importlib.import_module('config')
        try:
            _config_mtime = os.path.getmtime('config.py')
        except FileNotFoundError:
            _config_mtime = 0

        return _config_module
    except ImportError as e:
        logger.error(f"无法导入 config 模块: {e}")
        raise


def get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        配置值
    """
    try:
        config = get_config_module()
        return getattr(config, key, default)
    except Exception as e:
        logger.error(f"获取配置 {key} 失败: {e}")
        return default


def reload_config() -> bool:
    """重新加载配置

    Returns:
        是否成功
    """
    global _config_module, _config_mtime

    try:
        if _config_module:
            importlib.reload(_config_module)

        try:
            _config_mtime = os.path.getmtime('config.py')
        except FileNotFoundError:
            _config_mtime = 0

        logger.info("配置已重新加载")
        return True
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        return False


# 便捷函数：快速访问常用配置
def get_upload_dir() -> str:
    """获取上传目录"""
    from src.util.file_util import clear_config_cache
    clear_config_cache()  # 确保获取最新配置
    return get_config_value('UPLOAD_DIR', 'static/uploads/')


def get_source_videos_dir() -> str:
    """获取视频素材目录"""
    from src.util.file_util import clear_config_cache
    clear_config_cache()
    return get_config_value('source_videos_dir', 'static/source_videos/')


def get_source_audios_dir() -> str:
    """获取音频素材目录"""
    from src.util.file_util import clear_config_cache
    clear_config_cache()
    return get_config_value('source_audios_dir', 'static/source_timbre/')


def get_model_cache_dir() -> str:
    """获取模型缓存目录"""
    return get_config_value('MODEL_CACHE_DIR', 'D:/hf-model')


def get_api_host() -> int:
    """获取API端口"""
    return get_config_value('api_host', 9527)


def get_web_host() -> int:
    """获取Web端口"""
    return get_config_value('web_host', 9528)

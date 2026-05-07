import sys
import os
from pathlib import Path
from enum import Enum
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入常量
from src.shared.constants import APIConfig, DirectoryConfig


# 获取程序执行目录
def _get_executable_path():
    if getattr(sys, 'frozen', False):
        # 如果程序是被"冻结"打包的，使用这个路径
        return Path(sys.executable).parent.as_posix()
    else:
        return Path(__file__).parent.parent.resolve()


ROOT_DIR_WIN = Path(__file__).parent.parent.resolve()

# 程序根目录
ROOT_DIR = _get_executable_path()
_root_path = Path(ROOT_DIR)


# API 端口配置
api_host = int(os.getenv('API_PORT', str(APIConfig.DEFAULT_API_PORT)))
web_host = int(os.getenv('WEB_PORT', str(APIConfig.DEFAULT_WEB_PORT)))
listenport = 9529

# 目录配置
UPLOAD_DIR = DirectoryConfig.UPLOAD_DIR
source_videos_dir = DirectoryConfig.SOURCE_VIDEOS_DIR
source_bgm_dir = DirectoryConfig.SOURCE_BGM_DIR
source_audios_dir = DirectoryConfig.SOURCE_AUDIOS_DIR

# 数据库配置
database_path = ROOT_DIR_WIN / "src" / "db" / "synthetix.db"
# alembic配置
alembic_path = ROOT_DIR_WIN / "alembic" / "versions"

# LLM 配置（保留用于兼容，实际使用 core-nexus-ai）
llm_model = os.getenv('LLM_MODEL', 'deepseek')
model_name = os.getenv('MODEL_NAME', 'deepseek-chat')
llm_key = os.getenv('LLM_KEY', '')

# 快慢双脑模型路由
FAST_MODEL = os.getenv('FAST_MODEL', '')       # 快速模型名（如 deepseek-chat），为空则不启用
SLOW_MODEL = os.getenv('SLOW_MODEL', model_name)  # 主模型名，默认使用 MODEL_NAME
FAST_MODEL_THRESHOLD = int(os.getenv('FAST_MODEL_THRESHOLD', '100'))  # 快速模型阈值（字符数）

# core-nexus-ai 配置
CORE_NEXUS_BASE_URL = os.getenv('CORE_NEXUS_BASE_URL', '')

# 视频API配置
video_type = os.getenv('VIDEO_TYPE', 'pexels')
video_api_keys = os.getenv('VIDEO_API_KEYS', '')
pixabay_api_key = os.getenv('PIXABAY_API_KEY', '')
coverr_api_key = os.getenv('COVERR_API_KEY', '')

# CORS配置 - 允许的来源，逗号分隔
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:9528,http://127.0.0.1:9528,http://localhost:9527,http://127.0.0.1:9527').split(',')

# 代理配置
proxy = os.getenv('PROXY', '')


# 模型配置
MODEL_CACHE_DIR = DirectoryConfig.MODEL_CACHE_DIR


class ModelType(Enum):
    """模型类型枚举"""
    VL = "vl"  # 视觉语言模型，如Qwen-VL系列


# ==================== 统一配置同步 ====================

# config_manager key → 本模块变量名 的映射
_CONFIG_KEY_MAP = {
    "core_nexus.api_key": "llm_key",
    "core_nexus.base_url": "CORE_NEXUS_BASE_URL",
    "core_nexus.llm_model": "llm_model",
    "core_nexus.fast_model": "FAST_MODEL",
    "core_nexus.slow_model": "SLOW_MODEL",
    "video_api_keys": "video_api_keys",
    "pixabay_api_key": "pixabay_api_key",
    "coverr_api_key": "coverr_api_key",
}


def sync_from_config_manager():
    """从 config_manager 同步所有已知 key 到模块级变量"""
    try:
        from src.shared.utils.config_manager import get as cfg_get
        import src.config as _self

        for cfg_key, var_name in _CONFIG_KEY_MAP.items():
            val = cfg_get(cfg_key, None)
            if val:
                setattr(_self, var_name, val)

        # 同步 fallback keys（core_nexus key 也设置到 TTS/ASR/VL）
        cn_key = cfg_get('core_nexus.api_key', '')
        if cn_key:
            if not getattr(_self, 'TTS_KEY', ''):
                _self.TTS_KEY = cn_key
            if not getattr(_self, 'ASR_KEY', ''):
                _self.ASR_KEY = cn_key
            if not getattr(_self, 'VL_KEY', ''):
                _self.VL_KEY = cn_key
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"配置同步失败: {e}")

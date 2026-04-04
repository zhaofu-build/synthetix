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

# core-nexus-ai 配置
CORE_NEXUS_BASE_URL = os.getenv('CORE_NEXUS_BASE_URL', '')

# 视频API配置
video_type = os.getenv('VIDEO_TYPE', 'pexels')
video_api_keys = os.getenv('VIDEO_API_KEYS', '')

# CORS配置 - 允许的来源，逗号分隔
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:9528,http://127.0.0.1:9528').split(',')

# 代理配置
proxy = os.getenv('PROXY', '')


# 模型配置
MODEL_CACHE_DIR = DirectoryConfig.MODEL_CACHE_DIR


class ModelType(Enum):
    """模型类型枚举"""
    VL = "vl"  # 视觉语言模型，如Qwen-VL系列

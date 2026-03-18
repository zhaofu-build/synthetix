import sys
import os
from pathlib import Path
from enum import Enum
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# 获取程序执行目录
def _get_executable_path():
    if getattr(sys, 'frozen', False):
        # 如果程序是被“冻结”打包的，使用这个路径
        return Path(sys.executable).parent.as_posix()
    else:
        return Path(__file__).parent.parent.parent.as_posix()


ROOT_DIR_WIN = Path(__file__).parent.resolve()

# 程序根目录
ROOT_DIR = _get_executable_path()
_root_path = Path(ROOT_DIR)


api_host = 9527
web_host = 9528
listenport = 9529

UPLOAD_DIR = "static/uploads/"
source_videos_dir = "static/source_videos/"
source_bgm_dir = "static/source_bgm/"
source_audios_dir = "static/source_timbre/"

# 数据库配置
database_path = ROOT_DIR_WIN / "src" / "db" / "we_library.db"
# alembic配置
alembic_path = ROOT_DIR_WIN / "alembic" / "versions"

# LLM 配置
llm_model = os.getenv('LLM_MODEL', 'deepseek')
model_name = os.getenv('MODEL_NAME', 'deepseek-chat')
llm_key = os.getenv('LLM_KEY', '')

# 视频API配置
video_type = os.getenv('VIDEO_TYPE', 'pexels')
video_api_keys = os.getenv('VIDEO_API_KEYS', '')

# CORS配置 - 允许的来源，逗号分隔
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:9528,http://127.0.0.1:9528').split(',')

# 代理配置
proxy = os.getenv('PROXY', '')


# 模型配置
MODEL_CACHE_DIR = "D:/hf-model"


class ModelType(Enum):
    """模型类型枚举"""
    VL = "vl"  # 视觉语言模型，如Qwen-VL系列
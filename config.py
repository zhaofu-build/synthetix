import sys
from pathlib import Path
from enum import Enum


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

llm_model = 'deepseek'
model_name = 'deepseek-chat'
llm_key = 'sk-'

video_type = 'pexels'
video_api_keys = 'AQanz5J1ptLpe8EzANVz4fFN9R0friFxQLnvzpTjTLFbwKjpR3eL6XLA'


# 模型配置
MODEL_CACHE_DIR = "D:/hf-model"


class ModelType(Enum):
    """模型类型枚举"""
    VL = "vl"  # 视觉语言模型，如Qwen-VL系列
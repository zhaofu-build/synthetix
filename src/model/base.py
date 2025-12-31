"""数据库操作和Pydantic模型"""
from pydantic import BaseModel
from typing import Optional
# 延迟导入以避免循环导入
from src.model.entity.video_source import VideoSource as VideoSourceModel
from src.model.entity.audio_source import AudioSource as AudioSourceModel

# 将CRUD实例创建延迟到函数内部，避免在模块加载时创建
def get_video_source_crud():
    from src.db.crud import CRUDBase
    return CRUDBase(VideoSourceModel)

def get_audio_source_crud():
    from src.db.crud import CRUDBase
    return CRUDBase(AudioSourceModel)


# pydantic基类
class BaseReq(BaseModel):
    class Config:
        extra = 'allow'  # 允许额外的字段


class VideoSource(BaseModel):
    table_name: str = "video_source"
    id: Optional[int] = None
    video_name: Optional[str] = None
    web_path: Optional[str] = None
    local_path: Optional[str] = None
    duration: Optional[float] = None
    duration_hms: Optional[str] = None
    description: Optional[str] = None
    video_type: Optional[bool] = 0

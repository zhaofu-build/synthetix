from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

# SQLAlchemy Base
Base = declarative_base()

# Pydantic 基础请求模型（用于API请求）
# 注意：此模型保留用于向后兼容，新API应使用 request.py 中的专用模型
class BaseReq(BaseModel):
    """基础请求模型（已废弃，请使用 src/model/request.py 中的专用模型）"""
    table_name: Optional[str] = Field(default="contents", description="表名")
    current: int = Field(default=1, ge=1, le=10000, description="当前页码")
    size: int = Field(default=10, ge=-1, le=1000, description="每页大小")
    id: Optional[int] = Field(None, description="记录ID")
    video_type: Optional[int] = Field(None, description="视频类型")
    video_url: Optional[str] = Field(None, description="视频URL")
    video_input: Optional[str] = Field(None, description="输入视频路径")
    video_path: Optional[str] = Field(None, description="视频路径")
    audio_path: Optional[str] = Field(None, description="音频路径")
    subtitle_content: Optional[str] = Field(None, description="字幕内容")
    is_soft: Optional[bool] = Field(None, description="是否软字幕")
    fontname: Optional[str] = Field(None, description="字体名称")
    fontsize: Optional[int] = Field(None, description="字体大小")
    fontcolor: Optional[str] = Field(None, description="字体颜色")
    subtitle_bottom: Optional[int] = Field(None, description="字幕底部距离")
    input_dir: Optional[str] = Field(None, description="输入目录")
    backup_dir: Optional[str] = Field(None, description="备份目录")
    crf: Optional[int] = Field(None, description="CRF值")
    max_bitrate: Optional[str] = Field(None, description="最大比特率")
    time_ss: Optional[str] = Field(None, description="时间点(秒)")
    time_str: Optional[str] = Field(None, description="时间字符串")

    class Config:
        extra = 'allow'  # 允许额外字段，保持向后兼容


# Fish Voice TTS请求模型（已迁移到 request.py，此处保留用于向后兼容）
class FishVoiceTTSReq(BaseModel):
    """Fish Speech TTS 请求（已废弃，请使用 src/model/request.py 中的 FishVoiceTTSRequest）"""
    text: str = Field(default="", max_length=5000, description="要合成的文本")
    audio_source_id: int = Field(default=-1, ge=-1, description="音色ID")
    seed: int = Field(default=-1, ge=-1, le=100000, description="随机种子")
    speed_factor: float = Field(default=1.0, ge=0.1, le=5.0, description="语速因子")
    top_p: float = Field(default=0.5, ge=0.0, le=1.0, description="采样概率阈值")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="温度参数")
    repetition_penalty: float = Field(default=1.35, ge=0.0, le=5.0, description="重复惩罚因子")
    references_audio: Optional[str] = Field(None, description="参考音频(base64)")
    references_text: str = Field(default="", max_length=500, description="参考文本")

    class Config:
        extra = 'forbid'
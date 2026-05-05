"""视频相关 API Schema"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from src.shared.constants import VideoProcessing, Subtitle


class VideoDownloadRequest(BaseModel):
    """视频下载请求"""
    video_url: str = Field(..., min_length=10, max_length=2048, description="视频URL")
    tags: Optional[str] = Field(default=None, description="标签，逗号分隔")

    @field_validator('video_url')
    @classmethod
    def validate_video_url(cls, v):
        """验证视频URL格式"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('视频URL必须以 http:// 或 https:// 开头')
        return v

    class Config:
        extra = 'forbid'


class VideoProcessRequest(BaseModel):
    """视频处理请求"""
    input_path: str = Field(..., min_length=1, description="输入文件路径")
    output_format: str = Field(
        default=VideoProcessing.DEFAULT_OUTPUT_FORMAT,
        pattern=f"^({'|'.join(VideoProcessing.SUPPORTED_FORMATS)})$",
        description="输出格式"
    )
    start_time: Optional[str] = Field(None, description="开始时间 (HH:MM:SS 或秒数)")
    end_time: Optional[str] = Field(None, description="结束时间 (HH:MM:SS 或秒数)")
    duration: Optional[str] = Field(None, description="时长")
    speed: Optional[float] = Field(
        None,
        ge=VideoProcessing.MIN_SPEED_FACTOR,
        le=VideoProcessing.MAX_SPEED_FACTOR,
        description="变速倍数"
    )
    volume: Optional[float] = Field(
        None,
        ge=VideoProcessing.MIN_VOLUME_FACTOR,
        le=VideoProcessing.MAX_VOLUME_FACTOR,
        description="音量倍数"
    )
    width: Optional[int] = Field(None, ge=100, le=7680, description="输出宽度")
    height: Optional[int] = Field(None, ge=100, le=4320, description="输出高度")
    cover_image: Optional[str] = Field(None, description="封面图路径")

    class Config:
        extra = 'forbid'


class VideoExtractFrameRequest(BaseModel):
    """提取视频帧请求"""
    video_input: str = Field(..., min_length=1, description="视频路径")
    time_ss: str = Field(..., description="提取时间点(秒数或HH:MM:SS)")

    class Config:
        extra = 'forbid'


class VideoExtractAudioRequest(BaseModel):
    """从视频提取音频请求"""
    video_url: str = Field(..., min_length=1, description="视频路径")

    class Config:
        extra = 'forbid'


class VideoAddAudioRequest(BaseModel):
    """添加音频到视频请求"""
    video_path: str = Field(..., min_length=1, description="视频路径")
    audio_path: str = Field(..., min_length=1, description="音频路径")

    class Config:
        extra = 'forbid'


class VideoAddSubtitleRequest(BaseModel):
    """添加字幕请求"""
    video_input: str = Field(..., min_length=1, description="视频路径")
    subtitle_content: str = Field(..., min_length=1, description="字幕内容")
    is_soft: bool = Field(default=False, description="是否软字幕")
    fontname: str = Field(default="楷体", description="字体名称")
    fontsize: int = Field(default=16, ge=8, le=72, description="字体大小")
    fontcolor: str = Field(default="&Hffffff", description="字体颜色")
    fontbordercolor: str = Field(default="&H000000", description="描边颜色")
    subtitle_bottom: int = Field(default=20, ge=0, le=500, description="字幕底部距离")
    bold: bool = Field(default=False, description="粗体")
    outline_width: float = Field(default=1, ge=0, le=6, description="描边宽度")
    shadow: float = Field(default=0, ge=0, le=4, description="阴影深度")
    alignment: int = Field(default=2, description="位置: 2=底部居中 5=上方居中 8=居中")
    bg_color: str = Field(default=None, description="背景颜色(ASS格式&HBBGGRR)")
    margin_l: int = Field(default=10, ge=0, le=200, description="左边距")
    margin_r: int = Field(default=10, ge=0, le=200, description="右边距")

    class Config:
        extra = 'forbid'


class BatchCompressRequest(BaseModel):
    """批量压缩请求"""
    input_dir: str = Field(..., min_length=1, description="输入目录")
    backup_dir: str = Field(..., min_length=1, description="备份目录")
    crf: Optional[int] = Field(default=23, ge=18, le=35, description="CRF值")
    max_bitrate: Optional[str] = Field(default="8000k", description="最大比特率")

    class Config:
        extra = 'forbid'

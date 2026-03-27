"""API 请求模型"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from src.shared.constants import (
    FileSize,
    Pagination,
    VideoProcessing,
    TTSConfig,
    Subtitle,
    VideoProcessing
)


class BaseQueryRequest(BaseModel):
    """基础查询请求模型"""
    current: int = Field(default=Pagination.DEFAULT_PAGE, ge=1, description="当前页码")
    size: int = Field(default=Pagination.DEFAULT_PAGE_SIZE, ge=Pagination.MIN_PAGE_SIZE, le=Pagination.MAX_PAGE_SIZE, description="每页大小")

    class Config:
        extra = 'forbid'  # 禁止额外字段


class VideoQueryRequest(BaseQueryRequest):
    """视频查询请求"""
    video_type: Optional[int] = Field(None, ge=0, le=10, description="视频类型")


class AudioQueryRequest(BaseQueryRequest):
    """音频查询请求"""
    audio_name: Optional[str] = Field(None, min_length=1, max_length=255, description="音频名称")


class DeleteRequest(BaseModel):
    """删除请求"""
    id: int = Field(..., ge=1, description="要删除的记录ID")

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


class TranscribeRequest(BaseModel):
    """转录请求"""
    input_path: str = Field(..., min_length=1, description="输入文件路径")
    model: str = Field(
        default=Subtitle.DEFAULT_MODEL,
        pattern=f"^({'|'.join(Subtitle.WHISPER_MODELS)})$",
        description="模型大小"
    )
    output_format: str = Field(
        default=Subtitle.DEFAULT_FORMAT,
        pattern=f"^({'|'.join(Subtitle.SUPPORTED_FORMATS)})$",
        description="输出格式"
    )
    is_translate: bool = Field(default=False, description="是否翻译")
    subtitle_double: bool = Field(default=False, description="字幕双语")
    translator_engine: str = Field(default="google", pattern="^(google|baidu|deepl)$", description="翻译引擎")
    subtitle_language: str = Field(
        default="zh",
        pattern=f"^({'|'.join(Subtitle.SUPPORTED_LANGUAGES)})$",
        description="字幕语言"
    )

    class Config:
        extra = 'forbid'


class DownloadVideoRequest(BaseModel):
    """视频下载请求"""
    video_url: str = Field(..., min_length=10, max_length=2048, description="视频URL")

    @field_validator('video_url')
    @classmethod
    def validate_video_url(cls, v):
        """验证视频URL格式"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('视频URL必须以 http:// 或 https:// 开头')
        return v

    class Config:
        extra = 'forbid'


class VideoUpdateRequest(BaseModel):
    """视频信息更新请求"""
    id: int = Field(..., ge=1, description="视频ID")
    video_name: Optional[str] = Field(None, min_length=1, max_length=255, description="视频名称")
    web_path: Optional[str] = Field(None, max_length=500, description="Web路径")
    local_path: Optional[str] = Field(None, max_length=500, description="本地路径")
    duration: Optional[str] = Field(None, max_length=50, description="时长")
    duration_hms: Optional[str] = Field(None, pattern="^\\d{2}:\\d{2}:\\d{2}$", description="时长(HH:MM:SS)")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    video_type: Optional[int] = Field(None, ge=0, le=10, description="视频类型")
    del_flag: Optional[bool] = Field(None, description="删除标志")

    class Config:
        extra = 'forbid'


class FishVoiceTTSRequest(BaseModel):
    """Fish Speech TTS 请求"""
    text: str = Field(..., min_length=1, max_length=5000, description="要合成的文本")
    audio_source_id: int = Field(default=-1, ge=-1, description="音色ID，-1表示使用自定义参考音频")
    seed: int = Field(default=42, ge=TTSConfig.SEED_MIN, le=TTSConfig.SEED_MAX, description="随机种子（仅当audio_source_id=-1时使用）")
    speed_factor: float = Field(default=TTSConfig.DEFAULT_SPEED, ge=TTSConfig.MIN_SPEED, le=TTSConfig.MAX_SPEED, description="语速因子")
    top_p: float = Field(default=TTSConfig.DEFAULT_TOP_P, ge=TTSConfig.MIN_TOP_P, le=TTSConfig.MAX_TOP_P, description="采样概率阈值")
    temperature: float = Field(default=TTSConfig.DEFAULT_TEMPERATURE, ge=TTSConfig.MIN_TEMPERATURE, le=TTSConfig.MAX_TEMPERATURE, description="温度参数")
    repetition_penalty: float = Field(default=TTSConfig.DEFAULT_REPETITION_PENALTY, ge=TTSConfig.MIN_REPETITION_PENALTY, le=TTSConfig.MAX_REPETITION_PENALTY, description="重复惩罚因子")
    references_audio: Optional[str] = Field(None, description="参考音频(base64编码)")
    references_text: str = Field(default="", max_length=500, description="参考音频文本")

    class Config:
        extra = 'forbid'


class SaveTimbreRequest(BaseModel):
    """保存音色请求"""
    audio_name: str = Field(..., min_length=1, max_length=255, description="音色名称")
    prompt_text: str = Field(..., min_length=1, max_length=1000, description="参考文本")
    seed: int = Field(..., ge=TTSConfig.SEED_MIN, le=TTSConfig.SEED_MAX, description="随机种子")
    speed: float = Field(..., ge=TTSConfig.MIN_SPEED, le=TTSConfig.MAX_SPEED, description="语速因子")
    top_p: float = Field(..., ge=TTSConfig.MIN_TOP_P, le=TTSConfig.MAX_TOP_P, description="采样概率阈值")
    temperature: float = Field(..., ge=TTSConfig.MIN_TEMPERATURE, le=TTSConfig.MAX_TEMPERATURE, description="温度参数")
    repetition_penalty: float = Field(..., ge=TTSConfig.MIN_REPETITION_PENALTY, le=TTSConfig.MAX_REPETITION_PENALTY, description="重复惩罚因子")
    output_format: str = Field(default="wav", pattern="^(wav|mp3|flac)$", description="输出格式")

    class Config:
        extra = 'forbid'


# 别名，保持向后兼容
FishVoiceTTSReq = FishVoiceTTSRequest

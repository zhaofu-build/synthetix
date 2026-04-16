"""音频相关 API Schema"""
from pydantic import BaseModel, Field
from typing import Optional
from src.shared.constants import TTSConfig


class FishSpeechTTSRequest(BaseModel):
    """Fish Speech TTS 请求"""
    text: str = Field(..., min_length=1, max_length=5000, description="要合成的文本")
    audio_source_id: int = Field(default=-1, ge=-1, description="音色ID，-1表示使用自定义参考音频")
    seed: int = Field(default=42, ge=TTSConfig.SEED_MIN, le=TTSConfig.SEED_MAX, description="随机种子")
    speed_factor: float = Field(default=TTSConfig.DEFAULT_SPEED, ge=TTSConfig.MIN_SPEED, le=TTSConfig.MAX_SPEED, description="语速因子")
    top_p: float = Field(default=TTSConfig.DEFAULT_TOP_P, ge=TTSConfig.MIN_TOP_P, le=TTSConfig.MAX_TOP_P, description="采样概率阈值")
    temperature: float = Field(default=TTSConfig.DEFAULT_TEMPERATURE, ge=TTSConfig.MIN_TEMPERATURE, le=TTSConfig.MAX_TEMPERATURE, description="温度参数")
    repetition_penalty: float = Field(default=TTSConfig.DEFAULT_REPETITION_PENALTY, ge=TTSConfig.MIN_REPETITION_PENALTY, le=TTSConfig.MAX_REPETITION_PENALTY, description="重复惩罚因子")
    references_audio: Optional[str] = Field(None, description="参考音频(base64编码)")
    references_text: str = Field(default="", max_length=500, description="参考音频文本")

    class Config:
        extra = 'forbid'


class AudioSeparateRequest(BaseModel):
    """音频分离请求"""
    audio_path: str = Field(..., min_length=1, description="音频文件路径")

    class Config:
        extra = 'forbid'


class AudioMergeRequest(BaseModel):
    """音频合并请求"""
    source_audio_path: str = Field(..., min_length=1, description="人声文件路径")
    accompaniment_url: str = Field(..., min_length=1, description="伴奏文件路径")

    class Config:
        extra = 'forbid'

"""API Schema 模块

包含所有 API 请求和响应的 Pydantic 模型
"""
from src.interfaces.api.schemas.video_schemas import (
    VideoDownloadRequest,
    VideoProcessRequest,
    VideoExtractFrameRequest,
    VideoExtractAudioRequest,
    VideoAddAudioRequest,
    VideoAddSubtitleRequest,
    BatchCompressRequest,
)
from src.interfaces.api.schemas.audio_schemas import (
    FishSpeechTTSRequest,
    SovitsTTSRequest,
    AudioSeparateRequest,
    AudioMergeRequest,
)
from src.interfaces.api.schemas.common_schemas import (
    PaginationRequest,
    DeleteRequest,
)

__all__ = [
    # Video schemas
    "VideoDownloadRequest",
    "VideoProcessRequest",
    "VideoExtractFrameRequest",
    "VideoExtractAudioRequest",
    "VideoAddAudioRequest",
    "VideoAddSubtitleRequest",
    "BatchCompressRequest",
    # Audio schemas
    "FishSpeechTTSRequest",
    "SovitsTTSRequest",
    "AudioSeparateRequest",
    "AudioMergeRequest",
    # Common schemas
    "PaginationRequest",
    "DeleteRequest",
]

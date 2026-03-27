"""应用服务模块

提供业务逻辑服务和外部适配器
"""
# Services
from src.application.services.video_service import VideoService
from src.application.services.audio_service import AudioService
from src.application.services.creative_service import CreativeService

# Adapters (重命名后的模块)
from src.application.services import ffmpeg_adapter
from src.application.services import whisper_adapter
from src.application.services import translation_adapter
from src.application.services import llm_adapter
from src.application.services import qwen_vl_adapter
from src.application.services import fish_speech_adapter
from src.application.services import video_downloader_adapter
from src.application.services import dh_live_adapter

# 向后兼容别名
use_ffmpeg = ffmpeg_adapter
use_fast_whisper = whisper_adapter
use_translation = translation_adapter
use_langchain_llm = llm_adapter
use_qwen_vl = qwen_vl_adapter
fish_voice = fish_speech_adapter
video_downloader = video_downloader_adapter
dh_live = dh_live_adapter

__all__ = [
    # Services
    'VideoService',
    'AudioService',
    'CreativeService',
    # Adapters (新名称)
    'ffmpeg_adapter',
    'whisper_adapter',
    'translation_adapter',
    'llm_adapter',
    'qwen_vl_adapter',
    'fish_speech_adapter',
    'video_downloader_adapter',
    'dh_live_adapter',
    # 向后兼容别名
    'use_ffmpeg',
    'use_fast_whisper',
    'use_translation',
    'use_langchain_llm',
    'use_qwen_vl',
    'fish_voice',
    'video_downloader',
    'dh_live',
]

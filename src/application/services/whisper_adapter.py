"""
ASR 语音识别服务

通过 core-nexus-ai API 进行语音转文字
"""
import os
import logging
from typing import Optional

# 设置translators库的区域环境变量，避免SSL证书验证问题
os.environ["translators_default_region"] = "EN"

from src.shared.utils.core_nexus_client import get_client
from src.shared.utils.config_manager import get as cfg_get
from src.application.services import translation_adapter as use_translation

logger = logging.getLogger(__name__)


def transcribe(
    audio_path: str,
    output_format_type: str = "srt",
    is_translate: bool = False,
    subtitle_double: bool = False,
    translator_engine: str = "google",
    subtitle_language: str = "zh"
) -> str:
    """
    语音转文字

    Args:
        audio_path: 音频文件路径
        output_format_type: 输出格式 (txt/srt)
        is_translate: 是否翻译
        subtitle_double: 是否双语字幕
        translator_engine: 翻译引擎
        subtitle_language: 字幕语言

    Returns:
        字幕内容字符串
    """
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

    try:
        client = get_client()
        asr_model = cfg_get("core_nexus.asr_model") or None
        result = client.asr_transcribe(
            audio=audio_path,
            language=subtitle_language,
            model=asr_model
        )

        text = result.get('text', '')
        segments = result.get('segments', [])

        # 如果没有 segments 信息，按句子拆分生成伪 segments
        if not segments and text:
            segments = _split_text_to_segments(text)

        if not segments:
            if is_translate:
                return use_translation.translator_response(text, subtitle_language, translator_engine)
            return text

        # 根据 output_format_type 生成输出
        segments_txt = ""

        if output_format_type == "txt":
            for segment in segments:
                segment_text = segment.get('text', '').strip()
                if is_translate:
                    if subtitle_double:
                        segments_txt += segment_text + "\n"
                    segments_txt += use_translation.translator_response(
                        segment_text, subtitle_language, translator_engine
                    ) + "\n"
                else:
                    segments_txt += segment_text + "\n"

        elif output_format_type == "srt":
            for i, segment in enumerate(segments, start=1):
                start_time = segment.get('start', 0)
                end_time = segment.get('end', 0)
                subtitle_text = segment.get('text', '').strip()

                start_str = _format_srt_time(start_time)
                end_str = _format_srt_time(end_time)

                segments_txt += f"{i}\n"
                segments_txt += f"{start_str} --> {end_str}\n"

                if is_translate:
                    if subtitle_double:
                        segments_txt += f"{subtitle_text}\n"
                    translated = use_translation.translator_build(
                        subtitle_text, subtitle_language, translator_engine
                    )
                    segments_txt += translated + "\n\n"
                else:
                    segments_txt += f"{subtitle_text}\n\n"

        return segments_txt

    except Exception as e:
        logger.error(f"ASR 转录失败: {e}")
        raise ValueError(f"ASR 转录失败: {e}")


def _split_text_to_segments(text: str, chars_per_second: float = 4.0) -> list:
    """将纯文本按句子拆分为带估算时间戳的 segments"""
    import re
    sentences = re.split(r'(?<=[，。！？；、\n])', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [{"text": text, "start": 0, "end": len(text) / max(chars_per_second, 1)}]

    segments = []
    current_time = 0.0
    for s in sentences:
        duration = max(len(s) / chars_per_second, 1.0)
        segments.append({
            "text": s,
            "start": round(current_time, 3),
            "end": round(current_time + duration, 3),
        })
        current_time += duration
    return segments


def _format_srt_time(seconds: float) -> str:
    """
    将秒数格式化为 SRT 时间格式

    Args:
        seconds: 秒数

    Returns:
        SRT 时间格式字符串 (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        result = transcribe(audio_file, "srt")
        print(result)
    else:
        print("用法: python whisper_adapter.py <audio_file>")

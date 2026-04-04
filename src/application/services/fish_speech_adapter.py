"""
TTS 文本转语音服务

通过 core-nexus-ai API 进行语音合成
"""
import logging
from typing import Optional, List

from src.shared.utils.core_nexus_client import get_client

logger = logging.getLogger(__name__)


def fish_voice(
    text: str,
    output_format: str = "wav",
    references: Optional[List[dict]] = None,
    seed: int = 42,
    speed_factor: float = 1.0,
    top_p: float = 0.7,
    temperature: float = 0.7,
    repetition_penalty: float = 1.2,
) -> bytes:
    """
    使用 core-nexus-ai API 进行语音合成

    Args:
        text: 要合成的文本
        output_format: 输出格式 (wav/mp3)
        references: 参考音频列表 [{"audio": base64, "text": str}]
        seed: 随机种子（保留参数，API 可能不使用）
        speed_factor: 语速因子
        top_p: 采样概率阈值
        temperature: 温度参数
        repetition_penalty: 重复惩罚因子

    Returns:
        音频二进制数据
    """
    logger.info(f"🔊 开始语音合成 | 文本长度: {len(text)} 字符")

    try:
        client = get_client()

        # 处理参考音频
        ref_audio = None
        ref_text = None
        if references and len(references) > 0:
            ref = references[0]
            ref_audio = ref.get("audio")
            ref_text = ref.get("text")

        # 调用 API（使用简化的参数格式）
        audio_data = client.tts_generate(
            text=text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            language="Auto",
        )

        logger.info(f"✅ 语音合成完成 | 数据大小: {len(audio_data)} bytes")
        return audio_data

    except Exception as e:
        logger.error(f"❌ 语音合成失败: {e}")
        raise ValueError(f"语音合成失败: {e}")


# 保留 TTSGenerator 类的兼容性别名
class TTSGenerator:
    """
    TTS 生成器类（兼容层）

    注意: 此类现在是通过 core-nexus-ai API 实现的兼容层
    """

    def __init__(self, *args, **kwargs):
        """初始化（参数保留用于兼容，实际不使用）"""
        logger.info("TTSGenerator 初始化（通过 core-nexus-ai API）")

    def generate_speech(
        self,
        text: str,
        seed: int = 42,
        speed_factor: float = 1.0,
        output_format: str = "wav",
        top_p: float = 0.7,
        temperature: float = 0.7,
        repetition_penalty: float = 1.2,
        references: Optional[List[dict]] = None,
        **kwargs
    ) -> bytes:
        """
        生成语音

        Args:
            text: 要合成的文本
            seed: 随机种子
            speed_factor: 语速因子
            output_format: 输出格式
            top_p: 采样概率阈值
            temperature: 温度参数
            repetition_penalty: 重复惩罚因子
            references: 参考音频列表
            **kwargs: 其他参数

        Returns:
            音频二进制数据
        """
        return fish_voice(
            text=text,
            output_format=output_format,
            references=references,
            seed=seed,
            speed_factor=speed_factor,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
        )


def clear_tts_cache():
    """清理缓存（兼容函数，API 模式无需缓存）"""
    logger.info("🧹 TTS 缓存清理（API 模式无需缓存）")


if __name__ == '__main__':
    # 测试代码
    import os
    import uuid
    from src import config

    text = "欢迎使用语音合成服务"
    output_format = "wav"

    audio_data = fish_voice(text, output_format)

    filename = f"{uuid.uuid4().hex}.{output_format}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(audio_data)

    logger.info(f"✅ 音频已保存到: {file_path}")

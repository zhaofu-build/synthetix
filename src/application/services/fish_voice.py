import io
import time
import threading
import librosa
import numpy as np
import soundfile as sf
import torch
from loguru import logger
from modelscope import snapshot_download
from pathlib import Path
from fish_speech.inference_engine import TTSInferenceEngine
from fish_speech.models.dac.inference import load_model as load_decoder_model
from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio
from tools.server.inference import inference_wrapper as inference


class TTSGenerator:
    # 添加类变量用于缓存实例
    _instances = {}
    _lock = threading.Lock()

    def __new__(
            cls,
            llama_checkpoint_path: str,
            decoder_checkpoint_path: str,
            decoder_config_name: str = "modded_dac_vq",
            device: str = "auto",
            half: bool = False,
            compile_model: bool = True,
            max_text_length: int = 200
    ):
        # 创建唯一的缓存键
        cache_key = (llama_checkpoint_path, decoder_checkpoint_path, decoder_config_name,
                     device, half, compile_model, max_text_length)

        # 双检锁确保线程安全
        if cache_key not in cls._instances:
            with cls._lock:
                if cache_key not in cls._instances:
                    logger.info(f"🚀 创建新的TTS生成器实例 | 缓存键: {cache_key[:2]}")
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instances[cache_key] = instance
        return cls._instances[cache_key]

    def __init__(
            self,
            llama_checkpoint_path: str,
            decoder_checkpoint_path: str,
            decoder_config_name: str = "modded_dac_vq",
            device: str = "auto",
            half: bool = False,
            compile_model: bool = True,
            max_text_length: int = 200
    ):
        # 防止重复初始化
        if self._initialized:
            return

        self._initialized = True
        self.cache_key = (llama_checkpoint_path, decoder_checkpoint_path)

        # 自动检测最佳设备
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        self.device = device
        self.half = half
        self.compile_model = compile_model
        self.max_text_length = max_text_length
        self.precision = torch.half if half else torch.bfloat16

        logger.info(f"🚀 初始化TTS生成器 | 设备: {device} | 半精度: {half} | 编译模型: {compile_model}")

        # 加载LLAMA模型 (文本转语义token)
        logger.info("⏳ 加载LLAMA模型...")
        self.llama_queue = launch_thread_safe_queue(
            checkpoint_path=llama_checkpoint_path,
            device=self.device,
            precision=self.precision,
            compile=self.compile_model,
        )

        # 加载解码器模型 (语义token转音频)
        logger.info("⏳ 加载解码器模型...")
        self.decoder_model = load_decoder_model(
            config_name=decoder_config_name,
            checkpoint_path=decoder_checkpoint_path,
            device=self.device,
        )

        # 创建TTS推理引擎
        self.tts_engine = TTSInferenceEngine(
            llama_queue=self.llama_queue,
            decoder_model=self.decoder_model,
            precision=self.precision,
            compile=self.compile_model,
        )

        # 预热模型
        self.warm_up()
        logger.success(f"✅ TTS生成器初始化完成 | 缓存键: {self.cache_key[:2]}")

    def warm_up(self):
        """预热模型以确保首次推理速度"""
        logger.info("🔥 预热模型...")
        request = ServeTTSRequest(
            text="欢迎使用语音合成服务",
            max_new_tokens=0,
            chunk_length=200,
            top_p=0.7,
            repetition_penalty=1.2,
            temperature=0.7,
            format="wav",
            references=[]
        )
        # 执行一次推理但不保存结果
        list(inference(request, self.tts_engine))
        logger.info("🔥 模型预热完成")


    def generate_speech(
            self,
            text: str,
            seed: int,
            speed_factor: float = 1.0,
            output_format: str = "wav",
            top_p: float = 0.7,
            temperature: float = 0.7,
            repetition_penalty: float = 1.2,
            references: list[dict] = None,  # 添加参考音频支持
            max_new_tokens: int = 1024,  # 添加max_new_tokens参数
            chunk_length: int = 200,  # 添加chunk_length参数
    ) -> bytes:
        """
        生成语音

        :param text: 要合成的文本
        :param seed: 随机种子
        :param speed_factor: 语速因子 (1.0为正常语速)
        :param output_format: 输出格式 (wav/pcm/mp3)
        :param top_p: 采样概率阈值 (控制生成多样性)
        :param temperature: 温度参数 (控制随机性)
        :param repetition_penalty: 重复惩罚因子 (避免重复)
        :param references: 参考音频列表 [{"audio": base64, "text": str}]
        :param max_new_tokens: 最大新token数
        :param chunk_length: 分块长度
        :return: 音频二进制数据
        """
        # 检查文本长度
        if self.max_text_length > 0 and len(text) > self.max_text_length:
            raise ValueError(f"文本过长 (最大长度: {self.max_text_length})")

        # 转换参考音频格式
        serve_references = []
        if references:
            for ref in references:
                serve_references.append(
                    ServeReferenceAudio(audio=ref["audio"], text=ref["text"])
                )

        # 创建TTS请求
        request = ServeTTSRequest(
            text=text,
            format=output_format,
            seed=seed,
            max_new_tokens=max_new_tokens,
            chunk_length=chunk_length,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            streaming=False,
            references=serve_references,  # 添加参考音频
        )

        # 执行TTS推理
        logger.info(f"🔊 合成语音 | 长度: {len(text)}字符 | 语速: {speed_factor}x")
        start_time = time.time()

        # 获取生成的音频数据
        fake_audios = next(inference(request, self.tts_engine))

        # 应用语速调整
        if speed_factor != 1.0:
            fake_audios = self.adjust_speech_speed(fake_audios, speed_factor)

        # 转换为音频文件格式
        audio_data = self.save_audio(fake_audios, output_format)

        logger.info(f"⏱️ 合成完成 | 耗时: {time.time() - start_time:.2f}秒")
        return audio_data

    def adjust_speech_speed(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """
        调整语音速度

        :param audio: 原始音频数据
        :param factor: 速度因子 (>1加速, <1减速)
        :return: 调整后的音频
        """
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # 单声道处理
        if audio.ndim == 1:
            return librosa.effects.time_stretch(audio, rate=factor)

        # 多声道处理
        processed_channels = []
        for channel in range(audio.shape[1]):
            processed_channels.append(
                librosa.effects.time_stretch(audio[:, channel], rate=factor)
            )

        # 对齐所有声道长度
        min_length = min(len(ch) for ch in processed_channels)
        return np.stack([ch[:min_length] for ch in processed_channels], axis=1)

    def save_audio(self, audio: np.ndarray, format: str) -> bytes:
        """
        将音频数据保存为指定格式

        :param audio: 音频numpy数组
        :param format: 音频格式 (wav/pcm/mp3)
        :return: 二进制音频数据
        """
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.decoder_model.sample_rate, format=format)
        buffer.seek(0)
        return buffer.read()


# 全局缓存字典
_TTS_CACHE = {}
_TTS_CACHE_LOCK = threading.Lock()


def fish_voice(text, output_format, references,seed,speed_factor,top_p,temperature,repetition_penalty):
    # 下载模型（使用缓存避免重复下载）
    logger.info("📥 检查并下载模型...")
    model_dir = snapshot_download('fishaudio/openaudio-s1-mini', cache_dir='D:/hf-model')
    logger.info(f"✅ 模型路径: {model_dir}")
    
    llama_model_path = model_dir
    decoder_model_path = str(Path(model_dir) / "codec.pth")
    # 使用缓存键
    cache_key = (llama_model_path, decoder_model_path)

    # 检查缓存
    with _TTS_CACHE_LOCK:
        if cache_key in _TTS_CACHE:
            logger.info(f"♻️ 复用已加载的TTS模型 | 缓存键: {cache_key}")
            tts = _TTS_CACHE[cache_key]
        else:
            logger.info(f"🆕 初始化TTS模型 | 缓存键: {cache_key}")
            start_time = time.time()
            tts = TTSGenerator(
                llama_checkpoint_path=llama_model_path,
                decoder_checkpoint_path=decoder_model_path,
                device="auto",
                half=False,
                compile_model=False,
                max_text_length=200
            )
            logger.info(f"🕒 初始化耗时: {time.time() - start_time:.2f}秒")
            _TTS_CACHE[cache_key] = tts

    # 生成语音
    audio_data = tts.generate_speech(
        text=text,
        seed=seed,
        speed_factor=speed_factor,
        output_format=output_format,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        references=references,
        max_new_tokens=1024,
        chunk_length=200
    )
    return audio_data



# 清理缓存的函数
def clear_tts_cache():
    global _TTS_CACHE
    with _TTS_CACHE_LOCK:
        logger.info("🧹 清理TTS模型缓存")
        _TTS_CACHE = {}
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("🧹 已清理GPU缓存")


if __name__ == '__main__':
    import os
    import uuid
    import config
    # clear_tts_cache()
    """主函数示例"""
    # ===== 配置参数 =====
    # 生成参数
    text = "欢迎使用高质量语音合成服务，本服务提供自然流畅的语音输出"
    output_file = "output.wav"

    references  = []
    # references = [{
    #     "audio": file_util.audio_to_base64("E:/aupi/sound/hutao/39.胡桃的爱好…_天清海阔，皓月凌空，此情此景，正适合作诗一首。.mp3"),
    #     # 实际使用base64编码的音频字符串
    #     "text": "天清海阔，皓月凌空，此情此景，正适合作诗一首。"
    # }]
    seed = 876888
    speed_factor = 1.0
    top_p = 0.8
    temperature = 0.7
    repetition_penalty=1.1
    output_format = "wav"
    audio_data = fish_voice(text, output_format, references, seed, speed_factor, top_p,
                                       temperature, repetition_penalty)

    filename = f"{uuid.uuid4().hex}.{output_format}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)
    # 保存结果
    with open(file_path, "wb") as f:
        f.write(audio_data)
    
    logger.info(f"✅ 音频已保存到: {file_path}")
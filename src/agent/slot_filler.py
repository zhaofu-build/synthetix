"""
槽位填充模块

从用户输入中提取信息填充槽位
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.application.services.llm_adapter import generate_response
from src.agent.prompts import AgentPrompts

logger = logging.getLogger(__name__)


@dataclass
class SlotDefinition:
    """槽位定义"""
    name: str
    description: str
    required: bool = True
    default: Any = None
    prompt: str = ""  # 缺失时的追问


# 常用槽位定义
SLOT_DEFINITIONS = {
    "video_id": SlotDefinition(
        name="video_id",
        description="视频 ID 或文件名",
        required=True,
        prompt="请告诉我您要操作哪个视频？"
    ),
    "video_ids": SlotDefinition(
        name="video_ids",
        description="视频 ID 列表",
        required=True,
        prompt="请告诉我需要合并哪些视频？"
    ),
    "start_time": SlotDefinition(
        name="start_time",
        description="开始时间 (HH:MM:SS 或秒数)",
        required=False,
        default="00:00:00",
        prompt="从什么时间开始？"
    ),
    "end_time": SlotDefinition(
        name="end_time",
        description="结束时间 (HH:MM:SS 或秒数)",
        required=False,
        prompt="到什么时间结束？"
    ),
    "duration": SlotDefinition(
        name="duration",
        description="时长（秒）",
        required=False,
        default=30,
        prompt="需要多长？"
    ),
    "speed_factor": SlotDefinition(
        name="speed_factor",
        description="速度倍数 (0.5=慢放, 2.0=快放)",
        required=True,
        prompt="调整到多少倍速？（如 0.5 慢放, 2.0 快放）"
    ),
    "description": SlotDefinition(
        name="description",
        description="描述内容",
        required=True,
        prompt="请描述您想要的效果。"
    ),
    "style": SlotDefinition(
        name="style",
        description="风格偏好",
        required=False,
        default="动感"
    ),
    "subtitle_content": SlotDefinition(
        name="subtitle_content",
        description="字幕内容",
        required=False,
        prompt="请提供字幕内容。"
    ),
    "audio_source": SlotDefinition(
        name="audio_source",
        description="音频来源",
        required=False,
        prompt="请提供音频文件或选择语音合成。"
    ),
    "text": SlotDefinition(
        name="text",
        description="要合成的文本",
        required=True,
        prompt="请输入要合成语音的文本。"
    ),
    "speaker_id": SlotDefinition(
        name="speaker_id",
        description="说话人 ID",
        required=False
    ),
    "keywords": SlotDefinition(
        name="keywords",
        description="搜索关键词",
        required=True,
        prompt="请告诉我您要搜索什么类型的素材？"
    ),
    "audio_path": SlotDefinition(
        name="audio_path",
        description="音频文件路径",
        required=True,
        prompt="请提供音频文件路径。"
    ),
    "audio_type": SlotDefinition(
        name="audio_type",
        description="音频类型: dubbing(配音)/bgm(背景音乐)",
        required=False,
        default="bgm"
    ),
    "url": SlotDefinition(
        name="url",
        description="视频 URL 地址",
        required=True,
        prompt="请提供视频的 URL 地址。"
    ),
    "prompt": SlotDefinition(
        name="prompt",
        description="提示词/分析提示",
        required=True,
        prompt="请描述您想要的效果或分析方向。"
    ),
    "quality": SlotDefinition(
        name="quality",
        description="质量: low/medium/high",
        required=False,
        default="medium"
    ),
    "timestamps": SlotDefinition(
        name="timestamps",
        description="时间点列表 (HH:MM:SS)，逗号分隔",
        required=False,
        prompt="请提供要截取的时间点，如 00:00:05,00:00:10"
    ),
    "target_lang": SlotDefinition(
        name="target_lang",
        description="目标语言",
        required=False,
        default="zh"
    ),
    "language": SlotDefinition(
        name="language",
        description="语言代码",
        required=False
    ),
    "file_type": SlotDefinition(
        name="file_type",
        description="文件类型: video/audio/image/all",
        required=False,
        default="all"
    ),
    "path": SlotDefinition(
        name="path",
        description="目录路径",
        required=False
    ),
    "pattern": SlotDefinition(
        name="pattern",
        description="文件名过滤",
        required=False
    ),
    "interval": SlotDefinition(
        name="interval",
        description="间隔时长（秒）",
        required=True,
        prompt="每段多少秒？"
    ),
    "cover_image": SlotDefinition(
        name="cover_image",
        description="封面图片路径",
        required=True,
        prompt="请提供封面图片路径。"
    ),
    "tts_path": SlotDefinition(
        name="tts_path",
        description="配音文件路径",
        required=False
    ),
    "bgm_path": SlotDefinition(
        name="bgm_path",
        description="背景音乐文件路径",
        required=False
    ),
    "bgm_volume": SlotDefinition(
        name="bgm_volume",
        description="背景音乐音量 (0.0-1.0)",
        required=False,
        default=0.3
    ),
    "mood": SlotDefinition(
        name="mood",
        description="情绪/风格描述",
        required=True,
        prompt="请描述视频的情绪或风格。"
    ),
    "prompt_type": SlotDefinition(
        name="prompt_type",
        description="提示词类型: 1=文生图 2=图生图 3=文生视频",
        required=False,
        default=1
    ),
    "video_type": SlotDefinition(
        name="video_type",
        description="视频类型",
        required=False
    ),
    "directory": SlotDefinition(
        name="directory",
        description="目录路径",
        required=True,
        prompt="请提供视频目录路径。"
    ),
    "srt_path": SlotDefinition(
        name="srt_path",
        description="SRT 字幕文件路径",
        required=True,
        prompt="请提供 SRT 字幕文件路径。"
    ),
    "fontname": SlotDefinition(
        name="fontname",
        description="字体名称",
        required=False,
        default="Arial"
    ),
    "fontsize": SlotDefinition(
        name="fontsize",
        description="字体大小",
        required=False,
        default=24
    ),
    "fontcolor": SlotDefinition(
        name="fontcolor",
        description="字体颜色",
        required=False,
        default="&H00FFFFFF"
    ),
    "value": SlotDefinition(
        name="value",
        description="时间值",
        required=True,
        prompt="请输入时间值。"
    ),
    "direction": SlotDefinition(
        name="direction",
        description="转换方向: to_hms/to_seconds",
        required=False,
        default="to_hms"
    ),
    "task_id": SlotDefinition(
        name="task_id",
        description="任务 ID",
        required=True,
        prompt="请提供任务 ID。"
    ),
    "description": SlotDefinition(
        name="description",
        description="描述内容",
        required=True,
        prompt="请输入描述内容。"
    ),
    # ==================== FFmpeg 滤镜相关槽位 ====================
    "brightness": SlotDefinition(
        name="brightness",
        description="亮度 (-1.0~1.0)",
        required=False,
        default=0
    ),
    "contrast": SlotDefinition(
        name="contrast",
        description="对比度 (0.1~10.0)",
        required=False,
        default=1.0
    ),
    "saturation": SlotDefinition(
        name="saturation",
        description="饱和度 (0.0~3.0)",
        required=False,
        default=1.0
    ),
    "gamma": SlotDefinition(
        name="gamma",
        description="伽马值 (0.1~3.0)",
        required=False,
        default=1.0
    ),
    "sigma": SlotDefinition(
        name="sigma",
        description="模糊强度 (0.1~20.0)",
        required=False,
        default=5.0
    ),
    "amount": SlotDefinition(
        name="amount",
        description="锐化强度 (0.0~3.0)",
        required=False,
        default=1.5
    ),
    "angle": SlotDefinition(
        name="angle",
        description="旋转角度: 90/180/270",
        required=True,
        prompt="请输入旋转角度（90/180/270）。"
    ),
    "width": SlotDefinition(
        name="width",
        description="裁剪宽度（像素）",
        required=True,
        prompt="请输入裁剪宽度。"
    ),
    "height": SlotDefinition(
        name="height",
        description="裁剪高度（像素）",
        required=True,
        prompt="请输入裁剪高度。"
    ),
    "x": SlotDefinition(
        name="x",
        description="起始X坐标",
        required=False
    ),
    "y": SlotDefinition(
        name="y",
        description="起始Y坐标",
        required=False
    ),
    "fade_in": SlotDefinition(
        name="fade_in",
        description="淡入时长（秒）",
        required=False,
        default=2.0
    ),
    "fade_out": SlotDefinition(
        name="fade_out",
        description="淡出时长（秒）",
        required=False,
        default=2.0
    ),
    "overlay_video_id": SlotDefinition(
        name="overlay_video_id",
        description="叠加视频 ID",
        required=True,
        prompt="请提供要叠加的视频 ID。"
    ),
    "scale": SlotDefinition(
        name="scale",
        description="缩放比例",
        required=False,
        default=0.25
    ),
    "watermark_path": SlotDefinition(
        name="watermark_path",
        description="水印图片路径",
        required=True,
        prompt="请提供水印图片路径。"
    ),
    "position": SlotDefinition(
        name="position",
        description="位置: top-left/top-right/bottom-left/bottom-right",
        required=False,
        default="bottom-right"
    ),
    "opacity": SlotDefinition(
        name="opacity",
        description="透明度 (0.0~1.0)",
        required=False,
        default=1.0
    ),
    "text": SlotDefinition(
        name="text",
        description="文字内容",
        required=True,
        prompt="请输入要叠加的文字。"
    ),
    "fontcolor": SlotDefinition(
        name="fontcolor",
        description="字体颜色",
        required=False,
        default="white"
    ),
    "smoothing": SlotDefinition(
        name="smoothing",
        description="防抖平滑强度",
        required=False,
        default=10
    ),
    "threshold": SlotDefinition(
        name="threshold",
        description="场景变化阈值 (0.0~1.0)",
        required=False,
        default=0.4
    ),
    "factor": SlotDefinition(
        name="factor",
        description="慢放倍数 (2~8)",
        required=False,
        default=4.0
    ),
    "target_format": SlotDefinition(
        name="target_format",
        description="目标格式: mp4/mkv/avi/mov/webm",
        required=True,
        prompt="请输入目标格式（mp4/mkv/avi/mov/webm）。"
    ),
    "target_loudness": SlotDefinition(
        name="target_loudness",
        description="目标响度 LUFS",
        required=False,
        default=-16.0
    ),
    "frequency": SlotDefinition(
        name="frequency",
        description="频率 Hz",
        required=False,
        default=1000
    ),
    "gain": SlotDefinition(
        name="gain",
        description="增益 dB",
        required=False,
        default=2.0
    ),
    "delay": SlotDefinition(
        name="delay",
        description="延迟毫秒",
        required=False,
        default=60
    ),
    "decay": SlotDefinition(
        name="decay",
        description="衰减系数 (0.0~1.0)",
        required=False,
        default=0.4
    ),
    "noise_level": SlotDefinition(
        name="noise_level",
        description="降噪强度 dB",
        required=False,
        default=-25.0
    ),
    "semitones": SlotDefinition(
        name="semitones",
        description="半音变化 (-12~12)",
        required=True,
        prompt="请输入变调半音数（负数降低，正数升高）。"
    ),
}


class SlotFiller:
    """槽位填充器"""

    def __init__(self):
        """初始化槽位填充器"""
        self.prompts = AgentPrompts()

    async def fill(
        self,
        user_input: str,
        slot_names: List[str],
        filled_slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从用户输入中提取槽位值

        Args:
            user_input: 用户输入
            slot_names: 需要提取的槽位名列表
            filled_slots: 已填充的槽位

        Returns:
            Dict: 新提取的槽位值
        """
        # 过滤掉已填充的槽位
        unfilled = [name for name in slot_names if name not in filled_slots]
        if not unfilled:
            return {}

        # 先尝试规则提取
        rule_result = self._rule_extract(user_input, unfilled)
        if rule_result:
            return rule_result

        # 使用 LLM 提取
        return await self._llm_extract(user_input, unfilled, filled_slots)

    def _rule_extract(self, user_input: str, slot_names: List[str]) -> Optional[Dict]:
        """规则提取"""
        result = {}

        for name in slot_names:
            if name == "start_time":
                # 匹配 "前30秒" "从第5秒" "从00:01:30"
                match = re.search(r"前\s*(\d+)\s*秒", user_input)
                if match:
                    result["start_time"] = "00:00:00"
                    result["end_time"] = self._seconds_to_hms(int(match.group(1)))
                    continue

                match = re.search(r"从\s*(\d+)", user_input)
                if match:
                    result["start_time"] = self._seconds_to_hms(int(match.group(1)))

            elif name == "end_time":
                match = re.search(r"到\s*(\d+)\s*秒", user_input)
                if match:
                    result["end_time"] = self._seconds_to_hms(int(match.group(1)))

            elif name == "duration":
                match = re.search(r"(\d+)\s*秒", user_input)
                if match:
                    result["duration"] = int(match.group(1))

            elif name == "speed_factor":
                if "慢放" in user_input or "减速" in user_input:
                    result["speed_factor"] = 0.5
                elif "快放" in user_input or "加速" in user_input:
                    result["speed_factor"] = 2.0
                else:
                    match = re.search(r"(\d+\.?\d*)\s*倍", user_input)
                    if match:
                        result["speed_factor"] = float(match.group(1))

            elif name == "description":
                # 描述通常是整句话
                if len(user_input) > 10:
                    result["description"] = user_input

            elif name == "keywords":
                # 从"下载XXX素材"中提取
                match = re.search(r"(?:下载|搜索|找)(.+?)(?:素材|视频)", user_input)
                if match:
                    result["keywords"] = match.group(1).strip()
                # 从"搜索XXX文件"中提取
                elif "搜索" in user_input or "查找" in user_input or "找" in user_input:
                    match = re.search(r"(?:搜索|查找|找)(.+?)(?:文件|$)", user_input)
                    if match:
                        result["keywords"] = match.group(1).strip()

            elif name == "url":
                # 提取 URL
                match = re.search(r'(https?://[^\s]+)', user_input)
                if match:
                    result["url"] = match.group(1)

            elif name == "target_lang":
                if "英文" in user_input or "英语" in user_input or "English" in user_input.lower():
                    result["target_lang"] = "en"
                elif "日文" in user_input or "日语" in user_input or "Japanese" in user_input.lower():
                    result["target_lang"] = "ja"
                elif "韩文" in user_input or "韩语" in user_input:
                    result["target_lang"] = "ko"

            elif name == "quality":
                if "高质量" in user_input or "高清" in user_input:
                    result["quality"] = "high"
                elif "低质量" in user_input or "最小" in user_input:
                    result["quality"] = "low"

            elif name == "audio_type":
                if "配音" in user_input or "旁白" in user_input:
                    result["audio_type"] = "dubbing"
                elif "背景音乐" in user_input or "BGM" in user_input.upper() or "背景音" in user_input:
                    result["audio_type"] = "bgm"

            elif name == "interval":
                match = re.search(r"每\s*(\d+)\s*秒", user_input)
                if match:
                    result["interval"] = int(match.group(1))

            elif name == "direction":
                if "秒" in user_input and ("时" in user_input or "分" in user_input or "hms" in user_input.lower()):
                    result["direction"] = "to_hms"
                elif ":" in user_input:
                    result["direction"] = "to_seconds"

            elif name == "prompt_type":
                if "图生图" in user_input:
                    result["prompt_type"] = 2
                elif "视频" in user_input or "文生视频" in user_input:
                    result["prompt_type"] = 3
                elif "图" in user_input or "画" in user_input:
                    result["prompt_type"] = 1

            elif name == "mood":
                if len(user_input) > 5:
                    result["mood"] = user_input

            # ===== FFmpeg 滤镜参数提取 =====
            elif name == "brightness":
                if "亮" in user_input or "调亮" in user_input:
                    result["brightness"] = 0.2
                elif "暗" in user_input or "调暗" in user_input:
                    result["brightness"] = -0.2
                match = re.search(r"亮度\s*([+-]?\d+\.?\d*)", user_input)
                if match:
                    result["brightness"] = float(match.group(1))

            elif name == "contrast":
                if "高对比" in user_input or "增加对比" in user_input:
                    result["contrast"] = 1.5
                elif "低对比" in user_input or "降低对比" in user_input:
                    result["contrast"] = 0.7

            elif name == "saturation":
                if "高饱和" in user_input or "增加饱和" in user_input:
                    result["saturation"] = 1.5
                elif "黑白" in user_input or "去色" in user_input or "低饱和" in user_input:
                    result["saturation"] = 0.0

            elif name == "gamma":
                match = re.search(r"伽马\s*(\d+\.?\d*)", user_input)
                if match:
                    result["gamma"] = float(match.group(1))

            elif name == "angle":
                match = re.search(r"(\d+)\s*度", user_input)
                if match and int(match.group(1)) in (90, 180, 270):
                    result["angle"] = int(match.group(1))
                elif "左转" in user_input:
                    result["angle"] = 270
                elif "右转" in user_input:
                    result["angle"] = 90
                elif "倒过来" in user_input or "翻过来" in user_input:
                    result["angle"] = 180

            elif name == "direction":
                if "水平" in user_input or "左右" in user_input:
                    result["direction"] = "horizontal"
                elif "垂直" in user_input or "上下" in user_input:
                    result["direction"] = "vertical"

            elif name == "target_format":
                fmt_map = {"mp4": "mp4", "mkv": "mkv", "avi": "avi", "mov": "mov",
                           "webm": "webm", "flv": "flv", "wmv": "wmv"}
                for fmt_name, fmt_val in fmt_map.items():
                    if fmt_name in user_input.lower():
                        result["target_format"] = fmt_val
                        break

            elif name == "position":
                if "左上" in user_input:
                    result["position"] = "top-left"
                elif "右上" in user_input:
                    result["position"] = "top-right"
                elif "左下" in user_input:
                    result["position"] = "bottom-left"
                elif "右下" in user_input:
                    result["position"] = "bottom-right"
                elif "中间" in user_input or "居中" in user_input:
                    result["position"] = "center"

            elif name == "semitones":
                if "低沉" in user_input or "低音" in user_input:
                    result["semitones"] = -3
                elif "高音" in user_input or "尖细" in user_input:
                    result["semitones"] = 3

            elif name == "factor":
                match = re.search(r"(\d+)\s*倍.*慢", user_input)
                if match:
                    result["factor"] = float(match.group(1))
                elif "超级慢" in user_input:
                    result["factor"] = 8.0
                elif "慢动作" in user_input or "慢放" in user_input:
                    result["factor"] = 4.0

        return result if result else None

    async def _llm_extract(
        self,
        user_input: str,
        slot_names: List[str],
        filled_slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 LLM 提取槽位（带重试）"""
        from src.shared.constants import AgentConfig
        from src.shared.utils.string_util import safe_parse_llm_json

        prompt = self.prompts.format_slot_prompt(
            user_input=user_input,
            slot_names=slot_names,
            filled_slots=filled_slots
        )

        messages = [{"role": "user", "content": prompt}]

        for attempt in range(AgentConfig.MAX_LLM_PARSE_RETRIES + 1):
            try:
                response = generate_response(messages)

                result = safe_parse_llm_json(response)

                if result is None:
                    if attempt < AgentConfig.MAX_LLM_PARSE_RETRIES:
                        logger.warning(f"槽位提取 JSON 解析失败，重试 ({attempt + 1})")
                        messages.append({"role": "assistant", "content": response})
                        messages.append({"role": "user", "content": "请只返回纯JSON字典，不要包含任何其他内容或markdown标记。"})
                        continue
                    raise json.JSONDecodeError("解析失败", response, 0)

                return result

            except json.JSONDecodeError:
                if attempt == AgentConfig.MAX_LLM_PARSE_RETRIES:
                    logger.error(f"槽位提取失败（已重试）")
                    return {}
            except Exception as e:
                logger.error(f"槽位提取失败: {e}")
                return {}

        return {}

    def get_missing_slots(
        self,
        required_slots: List[str],
        filled_slots: Dict[str, Any]
    ) -> List[SlotDefinition]:
        """获取缺失的必填槽位"""
        missing = []
        for name in required_slots:
            if name not in filled_slots or filled_slots[name] is None:
                if name in SLOT_DEFINITIONS:
                    missing.append(SLOT_DEFINITIONS[name])
                else:
                    missing.append(SlotDefinition(
                        name=name,
                        description=name,
                        required=True,
                        prompt=f"请提供 {name}"
                    ))
        return missing

    def get_slot_prompt(self, slot_name: str) -> str:
        """获取槽位的追问提示"""
        if slot_name in SLOT_DEFINITIONS:
            return SLOT_DEFINITIONS[slot_name].prompt
        return f"请提供 {slot_name}"

    @staticmethod
    def _seconds_to_hms(seconds: int) -> str:
        """秒数转 HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# 全局槽位填充器实例
_filler: Optional[SlotFiller] = None


def get_slot_filler() -> SlotFiller:
    """获取全局槽位填充器实例"""
    global _filler
    if _filler is None:
        _filler = SlotFiller()
    return _filler

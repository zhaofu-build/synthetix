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
    )
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

        return result if result else None

    async def _llm_extract(
        self,
        user_input: str,
        slot_names: List[str],
        filled_slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 LLM 提取槽位"""
        prompt = self.prompts.format_slot_prompt(
            user_input=user_input,
            slot_names=slot_names,
            filled_slots=filled_slots
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = generate_response(messages)

            # 清理响应
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]

            return json.loads(response)

        except Exception as e:
            logger.error(f"槽位提取失败: {e}")
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

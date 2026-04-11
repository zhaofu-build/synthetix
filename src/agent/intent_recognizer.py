"""
意图识别模块

使用 LLM 识别用户意图
"""
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.application.services.llm_adapter import generate_response
from src.agent.prompts import AgentPrompts

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str
    confidence: float
    entities: Dict[str, Any]
    need_clarification: bool
    clarification_question: str

    @classmethod
    def from_dict(cls, data: Dict) -> "IntentResult":
        """从字典创建"""
        return cls(
            intent=data.get("intent", "unknown"),
            confidence=data.get("confidence", 0.0),
            entities=data.get("entities", {}),
            need_clarification=data.get("need_clarification", False),
            clarification_question=data.get("clarification_question", "")
        )


# 意图定义
INTENTS = {
    "cut_video": {
        "name": "剪切视频",
        "description": "从视频中剪切指定片段",
        "slots": ["video_id", "start_time", "end_time"],
        "required_slots": ["video_id"]
    },
    "merge_videos": {
        "name": "合并视频",
        "description": "合并多个视频为一个",
        "slots": ["video_ids"],
        "required_slots": ["video_ids"]
    },
    "add_subtitle": {
        "name": "添加字幕",
        "description": "为视频添加字幕",
        "slots": ["video_id", "subtitle_content", "subtitle_type"],
        "required_slots": ["video_id"]
    },
    "add_audio": {
        "name": "添加音频",
        "description": "为视频添加背景音乐或配音",
        "slots": ["video_id", "audio_source", "audio_type"],
        "required_slots": ["video_id"]
    },
    "change_speed": {
        "name": "调整速度",
        "description": "调整视频播放速度",
        "slots": ["video_id", "speed_factor"],
        "required_slots": ["video_id", "speed_factor"]
    },
    "smart_clip": {
        "name": "智能剪辑",
        "description": "根据描述自动规划并生成视频",
        "slots": ["description", "duration", "style"],
        "required_slots": ["description"]
    },
    "analyze_video": {
        "name": "分析视频",
        "description": "分析视频内容",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "generate_tts": {
        "name": "生成语音",
        "description": "根据文本生成语音",
        "slots": ["text", "speaker_id"],
        "required_slots": ["text"]
    },
    "list_videos": {
        "name": "查看素材",
        "description": "列出可用的视频素材",
        "slots": [],
        "required_slots": []
    },
    "search_material": {
        "name": "搜索素材",
        "description": "搜索或下载视频素材",
        "slots": ["keywords"],
        "required_slots": ["keywords"]
    },
    "help": {
        "name": "获取帮助",
        "description": "显示帮助信息",
        "slots": [],
        "required_slots": []
    },
    "confirm": {
        "name": "确认操作",
        "description": "用户确认执行",
        "slots": [],
        "required_slots": []
    },
    "cancel": {
        "name": "取消操作",
        "description": "用户取消操作",
        "slots": [],
        "required_slots": []
    },
    "unknown": {
        "name": "未知意图",
        "description": "无法识别的意图",
        "slots": [],
        "required_slots": []
    }
}


class IntentRecognizer:
    """意图识别器"""

    def __init__(self):
        """初始化意图识别器"""
        self.prompts = AgentPrompts()

    async def recognize(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        current_video: Optional[str] = None
    ) -> IntentResult:
        """
        识别用户意图

        Args:
            user_input: 用户输入
            history: 对话历史
            current_video: 当前视频信息

        Returns:
            IntentResult: 意图识别结果
        """
        # 快速规则匹配
        quick_result = self._quick_match(user_input)
        if quick_result:
            return quick_result

        # LLM 意图识别
        return await self._llm_recognize(user_input, history, current_video)

    def _quick_match(self, user_input: str) -> Optional[IntentResult]:
        """快速规则匹配"""
        text = user_input.lower().strip()

        # 确认/取消
        if text in ["确认", "好的", "可以", "是", "执行", "确定"]:
            return IntentResult(
                intent="confirm",
                confidence=1.0,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        if text in ["取消", "不要", "不行", "否", "算了"]:
            return IntentResult(
                intent="cancel",
                confidence=1.0,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        # 帮助
        if text in ["帮助", "help", "怎么用", "你能做什么"]:
            return IntentResult(
                intent="help",
                confidence=1.0,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        # 查看素材
        if any(kw in text for kw in ["素材", "视频列表", "有什么视频"]):
            return IntentResult(
                intent="list_videos",
                confidence=0.9,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        return None

    async def _llm_recognize(
        self,
        user_input: str,
        history: List[Dict[str, str]],
        current_video: Optional[str]
    ) -> IntentResult:
        """使用 LLM 识别意图（带重试）"""
        from src.shared.constants import AgentConfig
        from src.shared.utils.string_util import safe_parse_llm_json

        prompt = self.prompts.format_intent_prompt(
            user_input=user_input,
            history=history,
            current_video=current_video or "无"
        )

        messages = [{"role": "user", "content": prompt}]

        for attempt in range(AgentConfig.MAX_LLM_PARSE_RETRIES + 1):
            try:
                response = generate_response(messages)

                result = safe_parse_llm_json(response)

                if result is None:
                    if attempt < AgentConfig.MAX_LLM_PARSE_RETRIES:
                        logger.warning(f"意图识别 JSON 解析失败，重试 ({attempt + 1})")
                        messages.append({"role": "assistant", "content": response})
                        messages.append({"role": "user", "content": "请只返回纯JSON，不要包含任何其他内容或markdown标记。"})
                        continue
                    raise json.JSONDecodeError("解析失败", response, 0)

                return IntentResult.from_dict(result)

            except json.JSONDecodeError as e:
                if attempt == AgentConfig.MAX_LLM_PARSE_RETRIES:
                    logger.warning(f"JSON 解析失败（已重试）: {e}, 原始响应: {response}")
                    return IntentResult(
                        intent="unknown",
                        confidence=0.0,
                        entities={},
                        need_clarification=True,
                        clarification_question="抱歉，我没理解您的意思。您可以描述得更具体一些吗？"
                    )
            except Exception as e:
                logger.error(f"意图识别失败: {e}")
                return IntentResult(
                    intent="unknown",
                    confidence=0.0,
                    entities={},
                    need_clarification=True,
                    clarification_question="处理时出现错误，请重试。"
                )

        return IntentResult(
            intent="unknown",
            confidence=0.0,
            entities={},
            need_clarification=True,
            clarification_question="抱歉，我没理解您的意思。"
        )

    def get_intent_info(self, intent: str) -> Dict:
        """获取意图信息"""
        return INTENTS.get(intent, INTENTS["unknown"])

    def get_required_slots(self, intent: str) -> List[str]:
        """获取意图的必填槽位"""
        info = self.get_intent_info(intent)
        return info.get("required_slots", [])


# 全局意图识别器实例
_recognizer: Optional[IntentRecognizer] = None


def get_intent_recognizer() -> IntentRecognizer:
    """获取全局意图识别器实例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = IntentRecognizer()
    return _recognizer

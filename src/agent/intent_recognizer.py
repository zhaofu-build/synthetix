"""
意图识别模块

使用 LLM 识别用户意图
"""
import json
import logging
import re
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
        "slots": ["video_id", "audio_path", "audio_type"],
        "required_slots": ["video_id", "audio_path"]
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
    "analyze_video_vl": {
        "name": "AI 视频理解",
        "description": "使用 AI 深度分析视频内容，理解场景、人物、动作、风格等",
        "slots": ["video_id", "prompt"],
        "required_slots": ["video_id"]
    },
    "transcribe_video": {
        "name": "提取字幕",
        "description": "从视频中提取字幕，进行语音识别",
        "slots": ["video_id", "language"],
        "required_slots": ["video_id"]
    },
    "generate_tts": {
        "name": "生成语音",
        "description": "根据文本生成语音",
        "slots": ["text", "speaker_id"],
        "required_slots": ["text"]
    },
    "generate_music": {
        "name": "生成音乐",
        "description": "根据文字描述生成背景音乐",
        "slots": ["prompt", "duration", "style"],
        "required_slots": ["prompt"]
    },
    "download_video": {
        "name": "下载视频",
        "description": "从 URL 下载视频到素材库",
        "slots": ["url"],
        "required_slots": ["url"]
    },
    "compress_video": {
        "name": "压缩视频",
        "description": "压缩视频文件大小",
        "slots": ["video_id", "quality"],
        "required_slots": ["video_id"]
    },
    "extract_frames": {
        "name": "提取帧",
        "description": "从视频中提取关键帧或截图",
        "slots": ["video_id", "timestamps"],
        "required_slots": ["video_id"]
    },
    "convert_to_gif": {
        "name": "转GIF",
        "description": "将视频片段转换为 GIF 动图",
        "slots": ["video_id", "start_time", "end_time"],
        "required_slots": ["video_id"]
    },
    "separate_vocal": {
        "name": "人声分离",
        "description": "分离视频中的人声和伴奏",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "translate_text": {
        "name": "翻译",
        "description": "翻译文本内容",
        "slots": ["text", "target_lang"],
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
    "search_files": {
        "name": "搜索文件",
        "description": "在素材目录中模糊搜索文件",
        "slots": ["keywords", "file_type"],
        "required_slots": ["keywords"]
    },
    "list_directory": {
        "name": "列出目录",
        "description": "列出指定目录下的文件和文件夹",
        "slots": ["path", "pattern"],
        "required_slots": []
    },
    "get_current_time": {
        "name": "查询时间",
        "description": "获取当前日期和时间",
        "slots": [],
        "required_slots": []
    },
    "extract_audio": {
        "name": "提取音频",
        "description": "从视频中提取音频轨道",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "mix_audio_to_video": {
        "name": "混合音频",
        "description": "将配音和背景音乐同时混入视频",
        "slots": ["video_id", "tts_path", "bgm_path", "bgm_volume"],
        "required_slots": ["video_id"]
    },
    "get_video_detail": {
        "name": "视频详情",
        "description": "获取视频详细信息（编码、分辨率、帧率等）",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "split_video": {
        "name": "拆分视频",
        "description": "按固定间隔将视频拆分成多个片段",
        "slots": ["video_id", "interval"],
        "required_slots": ["video_id"]
    },
    "list_audios": {
        "name": "列出音色",
        "description": "列出可用的音色/语音列表",
        "slots": [],
        "required_slots": []
    },
    "set_cover": {
        "name": "设置封面",
        "description": "设置视频封面/缩略图",
        "slots": ["video_id", "cover_image"],
        "required_slots": ["video_id", "cover_image"]
    },
    "get_system_info": {
        "name": "系统信息",
        "description": "获取系统信息（GPU、磁盘空间等）",
        "slots": [],
        "required_slots": []
    },
    "open_folder": {
        "name": "打开目录",
        "description": "在文件管理器中打开目录",
        "slots": ["path"],
        "required_slots": []
    },
    "delete_material": {
        "name": "删除素材",
        "description": "删除素材文件和记录",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "detect_language": {
        "name": "检测语言",
        "description": "检测文本的语言类型",
        "slots": ["text"],
        "required_slots": ["text"]
    },
    "suggest_music": {
        "name": "推荐音乐",
        "description": "根据风格推荐背景音乐",
        "slots": ["mood", "duration"],
        "required_slots": ["mood"]
    },
    "optimize_prompt": {
        "name": "优化提示词",
        "description": "优化 AI 提示词",
        "slots": ["prompt", "prompt_type"],
        "required_slots": ["prompt"]
    },
    "random_video": {
        "name": "随机素材",
        "description": "随机选择一个视频素材",
        "slots": ["video_type"],
        "required_slots": []
    },
    "batch_compress": {
        "name": "批量压缩",
        "description": "批量压缩目录下所有视频",
        "slots": ["directory", "quality"],
        "required_slots": ["directory"]
    },
    "update_description": {
        "name": "更新描述",
        "description": "更新视频描述/标签",
        "slots": ["video_id", "description"],
        "required_slots": ["video_id", "description"]
    },
    "srt_to_ass": {
        "name": "字幕转换",
        "description": "将 SRT 字幕转换为 ASS 格式",
        "slots": ["srt_path", "fontname", "fontsize", "fontcolor"],
        "required_slots": ["srt_path"]
    },
    "time_convert": {
        "name": "时间转换",
        "description": "时间格式转换（秒 ↔ HH:MM:SS）",
        "slots": ["value", "direction"],
        "required_slots": ["value"]
    },
    "task_status": {
        "name": "任务进度",
        "description": "查询后台任务执行进度",
        "slots": ["task_id"],
        "required_slots": ["task_id"]
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
    # ==================== FFmpeg 视频滤镜意图 ====================
    "adjust_brightness": {
        "name": "调整亮度对比度",
        "description": "调整视频亮度、对比度、饱和度",
        "slots": ["video_id", "brightness", "contrast", "saturation"],
        "required_slots": ["video_id"]
    },
    "blur_video": {
        "name": "模糊视频",
        "description": "对视频应用模糊效果",
        "slots": ["video_id", "sigma"],
        "required_slots": ["video_id"]
    },
    "sharpen_video": {
        "name": "锐化视频",
        "description": "对视频应用锐化效果",
        "slots": ["video_id", "amount"],
        "required_slots": ["video_id"]
    },
    "rotate_video": {
        "name": "旋转视频",
        "description": "旋转视频（90/180/270度）",
        "slots": ["video_id", "angle"],
        "required_slots": ["video_id", "angle"]
    },
    "flip_video": {
        "name": "翻转视频",
        "description": "水平或垂直翻转视频",
        "slots": ["video_id", "direction"],
        "required_slots": ["video_id"]
    },
    "crop_video": {
        "name": "裁剪视频",
        "description": "裁剪视频画面区域",
        "slots": ["video_id", "width", "height", "x", "y"],
        "required_slots": ["video_id", "width", "height"]
    },
    "fade_video": {
        "name": "淡入淡出",
        "description": "为视频添加淡入淡出效果",
        "slots": ["video_id", "fade_in", "fade_out"],
        "required_slots": ["video_id"]
    },
    "picture_in_picture": {
        "name": "画中画",
        "description": "将一个视频叠加到另一个视频上",
        "slots": ["video_id", "overlay_video_id", "x", "y", "scale"],
        "required_slots": ["video_id", "overlay_video_id"]
    },
    "add_watermark": {
        "name": "添加水印",
        "description": "为视频添加图片水印",
        "slots": ["video_id", "watermark_path", "position", "opacity"],
        "required_slots": ["video_id", "watermark_path"]
    },
    "add_text_overlay": {
        "name": "文字叠加",
        "description": "在视频上叠加文字",
        "slots": ["video_id", "text", "fontsize", "fontcolor", "x", "y"],
        "required_slots": ["video_id", "text"]
    },
    "reverse_video": {
        "name": "视频倒放",
        "description": "视频画面和音频同时反转播放",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
    },
    "stabilize_video": {
        "name": "视频防抖",
        "description": "稳定抖动的视频画面",
        "slots": ["video_id", "smoothing"],
        "required_slots": ["video_id"]
    },
    # ==================== 高级视频意图 ====================
    "scene_detect": {
        "name": "场景检测",
        "description": "检测视频中的场景切换点",
        "slots": ["video_id", "threshold"],
        "required_slots": ["video_id"]
    },
    "slow_motion": {
        "name": "慢动作",
        "description": "慢动作效果（插帧+降速）",
        "slots": ["video_id", "factor"],
        "required_slots": ["video_id"]
    },
    "color_adjust": {
        "name": "色彩调整",
        "description": "高级色彩调整（亮度/对比度/饱和度/伽马）",
        "slots": ["video_id", "brightness", "contrast", "saturation", "gamma"],
        "required_slots": ["video_id"]
    },
    "convert_format": {
        "name": "格式转换",
        "description": "视频格式转换（MP4/MKV/AVI/MOV/WEBM等）",
        "slots": ["video_id", "target_format"],
        "required_slots": ["video_id", "target_format"]
    },
    # ==================== 音频滤镜意图 ====================
    "normalize_audio": {
        "name": "音频标准化",
        "description": "音频标准化，统一音量",
        "slots": ["video_id", "target_loudness"],
        "required_slots": ["video_id"]
    },
    "equalize_audio": {
        "name": "均衡器",
        "description": "音频均衡器调节",
        "slots": ["video_id", "frequency", "gain", "width"],
        "required_slots": ["video_id"]
    },
    "fade_audio": {
        "name": "音频淡入淡出",
        "description": "音频淡入淡出效果",
        "slots": ["video_id", "fade_in", "fade_out"],
        "required_slots": ["video_id"]
    },
    "add_echo": {
        "name": "回声效果",
        "description": "为音频添加回声/混响",
        "slots": ["video_id", "delay", "decay"],
        "required_slots": ["video_id"]
    },
    "denoise_audio": {
        "name": "音频降噪",
        "description": "音频降噪处理",
        "slots": ["video_id", "noise_level"],
        "required_slots": ["video_id"]
    },
    "pitch_shift": {
        "name": "变调",
        "description": "音频变调（改变音高）",
        "slots": ["video_id", "semitones"],
        "required_slots": ["video_id", "semitones"]
    },
    "reverse_audio": {
        "name": "音频倒放",
        "description": "音频倒放（画面不变）",
        "slots": ["video_id"],
        "required_slots": ["video_id"]
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

        # URL 下载 — 包含链接的"下载"请求直接路由到 download_video
        if re.search(r'(https?://[^\s]+)', user_input):
            url_match = re.search(r'(https?://[^\s]+)', user_input)
            return IntentResult(
                intent="download_video",
                confidence=0.98,
                entities={"url": url_match.group(1)},
                need_clarification=False,
                clarification_question=""
            )

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

        # 查询时间
        if any(kw in text for kw in ["几点", "现在时间", "当前时间", "今天几号", "星期几"]):
            return IntentResult(
                intent="get_current_time",
                confidence=1.0,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        # 列出目录
        if any(kw in text for kw in ["目录", "文件夹", "看看有什么文件"]):
            return IntentResult(
                intent="list_directory",
                confidence=0.9,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        # 系统信息
        if any(kw in text for kw in ["系统信息", "gpu", "磁盘", "显卡"]):
            return IntentResult(
                intent="get_system_info",
                confidence=0.9,
                entities={},
                need_clarification=False,
                clarification_question=""
            )

        # 列出音色
        if any(kw in text for kw in ["音色", "声音列表", "有什么声音", "有哪些音色"]):
            return IntentResult(
                intent="list_audios",
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

"""
项目级记忆/偏好模块

从对话交互中自动提取用户偏好，跨会话持久化。
新会话开始时自动注入项目偏好到系统提示词。
"""
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 偏好存储路径
_MEMORY_DIR = Path(__file__).parent.parent.parent / "src" / "db" / "memories"


def _memory_path(project_id: int) -> Path:
    return _MEMORY_DIR / f"project_{project_id}.json"


def _ensure_dir():
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class ProjectMemory:
    """项目级偏好存储"""

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.preferences: Dict[str, str] = {}
        self.notes: List[str] = []
        self.load()

    def load(self):
        """从文件加载偏好"""
        path = _memory_path(self.project_id)
        if path.is_file():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.preferences = data.get("preferences", {})
                self.notes = data.get("notes", [])
            except Exception as e:
                logger.warning(f"加载项目记忆失败 (project={self.project_id}): {e}")

    def save(self):
        """持久化到文件"""
        _ensure_dir()
        path = _memory_path(self.project_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    "project_id": self.project_id,
                    "preferences": self.preferences,
                    "notes": self.notes,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存项目记忆失败: {e}")

    def set_preference(self, key: str, value: str):
        """设置偏好"""
        self.preferences[key] = value
        self.save()

    def add_note(self, note: str):
        """添加笔记"""
        self.notes.append(note)
        if len(self.notes) > 50:
            self.notes = self.notes[-50:]
        self.save()

    def get_preferences_summary(self) -> str:
        """获取偏好摘要，用于注入系统提示词"""
        if not self.preferences and not self.notes:
            return ""
        parts = []
        if self.preferences:
            items = [f"- {k}: {v}" for k, v in self.preferences.items()]
            parts.append("用户偏好:\n" + "\n".join(items))
        if self.notes:
            parts.append("项目备注:\n" + "\n".join(f"- {n}" for n in self.notes[-10:]))
        return "\n".join(parts)

    def clear(self):
        """清除所有偏好"""
        self.preferences = {}
        self.notes = []
        self.save()


# 内存缓存
_memories: Dict[int, ProjectMemory] = {}


def get_project_memory(project_id: int) -> ProjectMemory:
    """获取项目记忆实例"""
    if project_id not in _memories:
        _memories[project_id] = ProjectMemory(project_id)
    return _memories[project_id]


async def extract_preferences_from_messages(messages: List[Dict]) -> Dict[str, str]:
    """
    从最近消息中提取用户偏好（轻量级规则匹配，不调用 LLM）

    识别模式：
    - "用 XX 风格" → style
    - "字幕用 XX" → subtitle_style
    - "背景音乐要 XX" → bgm_preference
    - "语速 XX" → speech_speed
    - "我喜欢/我偏好/以后都 XX" → 从上下文提取
    """
    prefs = {}
    style_keywords = ["动感", "温馨", "简约", "复古", "科技", "文艺", "暗黑", "清新"]

    for msg in messages[-10:]:
        content = msg.get("content", "")
        if msg.get("role") != "user":
            continue

        # 风格偏好
        for kw in style_keywords:
            if kw in content and ("风格" in content or "用" in content):
                prefs["style"] = kw

        # 字幕偏好
        if "字幕" in content:
            if "白色" in content or "白边" in content:
                prefs["subtitle_color"] = "white"
            elif "黄色" in content:
                prefs["subtitle_color"] = "yellow"

        # BGM 偏好
        if "bgm" in content.lower() or "背景音乐" in content or "配乐" in content:
            if "小声" in content or "轻" in content:
                prefs["bgm_volume"] = "low"
            elif "大声" in content or "重" in content:
                prefs["bgm_volume"] = "high"

        # 明确偏好声明
        if "以后都" in content or "我都喜欢" in content or "默认都" in content:
            prefs["general_note"] = content[:100]

    return prefs

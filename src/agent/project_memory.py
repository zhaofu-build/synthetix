"""
项目级记忆/偏好模块

从对话交互中自动提取用户偏好，跨会话持久化。
新会话开始时自动注入项目偏好到系统提示词。
"""
import json
import logging
import time
import math
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
        self.edit_history: List[Dict] = []
        self.quality_feedback: List[Dict] = []
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
                self.edit_history = data.get("edit_history", [])
                self.quality_feedback = data.get("quality_feedback", [])
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
                    "edit_history": self.edit_history[-100:],
                    "quality_feedback": self.quality_feedback[-50:],
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
        if not self.preferences and not self.notes and not self.edit_history:
            return ""
        parts = []
        if self.preferences:
            items = [f"- {k}: {v}" for k, v in self.preferences.items()]
            parts.append("用户偏好:\n" + "\n".join(items))
        if self.notes:
            parts.append("项目备注:\n" + "\n".join(f"- {n}" for n in self.notes[-10:]))
        if self.edit_history:
            recent = self.edit_history[-5:]
            ops = [f"- {e.get('tool', '?')}({e.get('summary', '')})" for e in recent]
            parts.append("近期操作:\n" + "\n".join(ops))
        return "\n".join(parts)

    def get_relevant_summary(self, query: str = "", max_chars: int = 500) -> str:
        """根据当前查询相关性返回偏好摘要（带评分 + 时间衰减）"""
        if not self.preferences and not self.notes and not self.edit_history:
            return ""

        now = time.time()
        half_life = 30 * 86400  # 30 天半衰期（秒）

        # 评分并排序偏好
        scored_prefs = []
        for k, v in self.preferences.items():
            # 关键词匹配评分
            score = 0
            query_lower = query.lower()
            for word in k.replace("_", " ").split():
                if word in query_lower:
                    score += 2
            for word in v.split():
                if len(word) > 1 and word in query_lower:
                    score += 1
            # 基础分（通用偏好如 style, bgm 等总是有用的）
            if k in ("style", "bgm_volume", "subtitle_color", "general_note"):
                score += 1
            scored_prefs.append((score, k, v))

        scored_prefs.sort(key=lambda x: x[0], reverse=True)

        parts = []
        char_count = 0

        # 偏好
        if scored_prefs:
            pref_lines = []
            for score, k, v in scored_prefs:
                line = f"- {k}: {v}"
                if char_count + len(line) > max_chars:
                    break
                pref_lines.append(line)
                char_count += len(line)
            if pref_lines:
                parts.append("用户偏好:\n" + "\n".join(pref_lines))

        # 近期操作（最近 3 条）
        if self.edit_history:
            recent = self.edit_history[-3:]
            ops = [f"- {e.get('tool', '?')}({e.get('summary', '')})" for e in recent]
            op_text = "近期操作:\n" + "\n".join(ops)
            if char_count + len(op_text) <= max_chars:
                parts.append(op_text)
                char_count += len(op_text)

        # 笔记（最近 3 条）
        if self.notes:
            note_lines = [f"- {n}" for n in self.notes[-3:]]
            note_text = "项目备注:\n" + "\n".join(note_lines)
            if char_count + len(note_text) <= max_chars:
                parts.append(note_text)

        return "\n".join(parts)

    def record_edit(self, tool: str, summary: str, params: Dict = None):
        """记录编辑操作"""
        import time
        self.edit_history.append({
            "tool": tool, "summary": summary,
            "params": params or {}, "time": time.time(),
        })
        if len(self.edit_history) > 100:
            self.edit_history = self.edit_history[-100:]
        self.save()

    def record_quality_feedback(self, score: float, issues: List[str] = None):
        """记录质量反馈"""
        import time
        self.quality_feedback.append({
            "score": score, "issues": issues or [], "time": time.time(),
        })
        if len(self.quality_feedback) > 50:
            self.quality_feedback = self.quality_feedback[-50:]
        # Auto-adjust preferences based on feedback
        if score < 0.5 and issues:
            for issue in issues:
                if "音频" in issue:
                    self.preferences["audio_quality_note"] = "用户反馈音频问题，优先高质量音频"
                if "黑帧" in issue:
                    self.preferences["black_frame_aware"] = "true"
        self.save()

    def clear(self):
        """清除所有偏好"""
        self.preferences = {}
        self.notes = []
        self.edit_history = []
        self.quality_feedback = []
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


# ── 跨项目共享偏好 ──

_GLOBAL_PREFS_PATH = _MEMORY_DIR / "_global.json"


def get_global_preferences() -> Dict[str, str]:
    """获取跨项目共享偏好"""
    if _GLOBAL_PREFS_PATH.is_file():
        try:
            with open(_GLOBAL_PREFS_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("preferences", {})
        except Exception:
            pass
    return {}


def set_global_preference(key: str, value: str):
    """设置跨项目共享偏好"""
    _ensure_dir()
    prefs = get_global_preferences()
    prefs[key] = value
    try:
        with open(_GLOBAL_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump({"preferences": prefs}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存全局偏好失败: {e}")


def get_merged_preferences(project_id: int) -> Dict[str, str]:
    """合并全局偏好 + 项目偏好（项目偏好优先）"""
    merged = get_global_preferences()
    project_mem = get_project_memory(project_id)
    merged.update(project_mem.preferences)
    return merged

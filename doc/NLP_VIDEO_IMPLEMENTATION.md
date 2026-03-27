# 自然语言视频剪辑/生成系统实现方案

## 一、系统概述

本方案实现一个基于自然语言交互的智能视频剪辑与生成系统，用户可以通过对话方式完成视频编辑任务。

### 核心能力
- **自然语言理解**：解析用户的剪辑意图和需求
- **多轮对话交互**：支持上下文记忆和追问澄清
- **视频内容理解**：通过多模态模型分析视频内容
- **智能剪辑执行**：自动生成剪辑方案并执行

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Web UI    │  │  CLI 接口   │  │     REST API           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       对话管理层 (Agent)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ 会话管理器  │  │ 意图识别器  │  │     槽位填充器          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       核心能力层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ 视频理解    │  │ 剪辑规划    │  │     效果生成            │  │
│  │ (多模态LLM) │  │ (策略引擎)  │  │     (FFmpeg/AI)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       工具执行层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FFmpeg工具  │  │ 视频下载    │  │     素材管理            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ TTS/语音    │  │ 字幕处理    │  │     AI生成              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       数据存储层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ SQLite      │  │ 文件存储    │  │     会话缓存            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块设计

### 3.1 对话管理 Agent

```python
# src/agent/video_agent.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import json

class IntentType(Enum):
    """用户意图类型"""
    # 视频剪辑类
    CUT_VIDEO = "cut_video"           # 剪切视频
    MERGE_VIDEOS = "merge_videos"     # 合并视频
    ADD_SUBTITLE = "add_subtitle"     # 添加字幕
    ADD_AUDIO = "add_audio"           # 添加音频
    ADD_EFFECT = "add_effect"         # 添加特效
    CHANGE_SPEED = "change_speed"     # 调整速度
    CROP_VIDEO = "crop_video"         # 裁剪画面
    COMPRESS_VIDEO = "compress_video" # 压缩视频

    # 视频生成类
    GENERATE_VIDEO = "generate_video" # AI生成视频
    TEXT_TO_VIDEO = "text_to_video"   # 文本生成视频
    IMAGE_TO_VIDEO = "image_to_video" # 图片生成视频

    # 视频分析类
    ANALYZE_VIDEO = "analyze_video"   # 分析视频内容
    EXTRACT_AUDIO = "extract_audio"   # 提取音频
    EXTRACT_FRAMES = "extract_frames" # 提取帧

    # 素材管理类
    UPLOAD_VIDEO = "upload_video"     # 上传视频
    LIST_VIDEOS = "list_videos"       # 列出视频
    SEARCH_VIDEO = "search_video"     # 搜索视频

    # 会话类
    CONFIRM = "confirm"               # 确认操作
    CANCEL = "cancel"                 # 取消操作
    HELP = "help"                     # 获取帮助
    UNKNOWN = "unknown"               # 未知意图


@dataclass
class Slot:
    """槽位定义"""
    name: str
    value: Any = None
    required: bool = True
    description: str = ""
    prompt: str = ""  # 缺失时的追问


@dataclass
class DialogState:
    """对话状态"""
    session_id: str
    intent: Optional[IntentType] = None
    slots: Dict[str, Slot] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    current_video: Optional[str] = None
    pending_action: Optional[Dict] = None
    status: str = "idle"  # idle, collecting, confirming, executing


class VideoDialogAgent:
    """视频对话代理"""

    # 意图对应的槽位定义
    INTENT_SLOTS = {
        IntentType.CUT_VIDEO: [
            Slot("video_id", required=True, description="视频ID或路径",
                 prompt="请告诉我您要剪辑哪个视频？"),
            Slot("start_time", required=False, description="开始时间",
                 prompt="从什么时间开始剪辑？（如：00:01:30）"),
            Slot("end_time", required=False, description="结束时间",
                 prompt="到什么时间结束？"),
            Slot("duration", required=False, description="持续时长",
                 prompt="需要剪辑多长时间？"),
        ],
        IntentType.MERGE_VIDEOS: [
            Slot("video_ids", required=True, description="视频ID列表",
                 prompt="请告诉我需要合并哪些视频？（可以按顺序列出）"),
            Slot("transition", required=False, description="转场效果",
                 prompt="需要添加转场效果吗？（如：dissolve渐变、cut硬切）"),
        ],
        IntentType.ADD_SUBTITLE: [
            Slot("video_id", required=True, description="视频ID",
                 prompt="请告诉我要给哪个视频添加字幕？"),
            Slot("subtitle_type", required=False, description="字幕类型",
                 prompt="需要硬字幕还是软字幕？"),
            Slot("subtitle_content", required=False, description="字幕内容",
                 prompt="请提供字幕内容或字幕文件"),
        ],
        IntentType.ADD_AUDIO: [
            Slot("video_id", required=True, description="视频ID",
                 prompt="要给哪个视频添加音频？"),
            Slot("audio_source", required=True, description="音频来源",
                 prompt="请提供音频文件或选择语音合成"),
        ],
        IntentType.GENERATE_VIDEO: [
            Slot("prompt", required=True, description="生成提示词",
                 prompt="请描述您想生成的视频内容"),
            Slot("duration", required=False, description="视频时长",
                 prompt="视频需要多长？"),
            Slot("style", required=False, description="视频风格",
                 prompt="希望什么风格？（如：电影感、动漫、写实等）"),
        ],
    }

    def __init__(self, llm_service, tool_registry):
        self.llm = llm_service
        self.tools = tool_registry
        self.sessions: Dict[str, DialogState] = {}

    async def process_message(self, session_id: str, user_input: str) -> Dict:
        """处理用户消息"""
        state = self._get_or_create_session(session_id)
        state.history.append({"role": "user", "content": user_input})

        # 1. 意图识别
        if state.status == "idle":
            intent = await self._recognize_intent(user_input, state)
            state.intent = intent

            if intent == IntentType.UNKNOWN:
                return self._response("抱歉，我没理解您的意思。您可以尝试说：\n"
                                     "- 帮我剪辑视频的前30秒\n"
                                     "- 把这两个视频合并\n"
                                     "- 生成一段日落风景的视频")

            # 初始化槽位
            state.slots = {
                name: Slot(name, **config)
                for name, config in self.INTENT_SLOTS.get(intent, {}).items()
            }
            state.status = "collecting"

        # 2. 槽位填充
        if state.status == "collecting":
            await self._fill_slots(user_input, state)

            # 检查是否所有必填槽位都已填充
            missing = self._get_missing_slots(state)
            if missing:
                return self._response(missing[0].prompt)

            # 所有槽位已填充，请求确认
            state.status = "confirming"
            state.pending_action = self._build_action(state)
            return self._response(
                self._format_confirmation(state.pending_action)
            )

        # 3. 确认执行
        if state.status == "confirming":
            if self._is_confirmation(user_input):
                state.status = "executing"
                result = await self._execute_action(state.pending_action)
                state.status = "idle"
                state.history.append({"role": "assistant", "content": result["message"]})
                return result
            elif self._is_cancellation(user_input):
                state.status = "idle"
                return self._response("操作已取消。")
            else:
                # 用户可能有修改请求
                await self._handle_modification(user_input, state)
                state.status = "collecting"
                return self._response("好的，请告诉我您想修改什么？")

        return self._response("处理中...")

    async def _recognize_intent(self, text: str, state: DialogState) -> IntentType:
        """使用LLM识别用户意图"""
        prompt = f"""
        分析用户意图并返回JSON格式结果。

        用户输入: {text}

        当前上下文:
        - 当前视频: {state.current_video or '无'}
        - 最近操作: {state.history[-3:] if state.history else '无'}

        可选意图:
        - cut_video: 剪切/裁剪视频片段
        - merge_videos: 合并多个视频
        - add_subtitle: 添加字幕
        - add_audio: 添加背景音乐或配音
        - add_effect: 添加特效/滤镜
        - change_speed: 调整播放速度
        - generate_video: AI生成视频
        - analyze_video: 分析视频内容
        - list_videos: 查看可用视频列表
        - help: 获取帮助

        返回格式:
        {{"intent": "意图名称", "confidence": 0.9, "entities": {{"时间": "...", "时长": "..."}}}}
        """

        response = await self.llm.generate(prompt)
        try:
            result = json.loads(response)
            return IntentType(result.get("intent", "unknown"))
        except:
            return IntentType.UNKNOWN

    async def _fill_slots(self, text: str, state: DialogState):
        """从用户输入中提取槽位值"""
        slot_names = list(state.slots.keys())
        prompt = f"""
        从用户输入中提取信息。

        用户输入: {text}
        需要提取的字段: {slot_names}

        当前已填充: {dict((k, v.value) for k, v in state.slots.items() if v.value)}

        返回JSON格式:
        {{"字段名": "提取的值", ...}}
        """

        response = await self.llm.generate(prompt)
        try:
            extracted = json.loads(response)
            for key, value in extracted.items():
                if key in state.slots and value:
                    state.slots[key].value = value
        except:
            pass

    def _get_missing_slots(self, state: DialogState) -> List[Slot]:
        """获取缺失的必填槽位"""
        return [slot for slot in state.slots.values()
                if slot.required and slot.value is None]

    async def _execute_action(self, action: Dict) -> Dict:
        """执行剪辑动作"""
        tool_name = action["tool"]
        params = action["params"]

        if tool_name in self.tools:
            return await self.tools[tool_name].execute(**params)

        return {"success": False, "message": f"未知工具: {tool_name}"}
```

### 3.2 视频理解模块

```python
# src/agent/video_understanding.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import base64
from pathlib import Path

@dataclass
class VideoSegment:
    """视频片段信息"""
    start_time: float
    end_time: float
    description: str
    key_frames: List[str]  # 关键帧路径
    objects: List[str]     # 检测到的对象
    actions: List[str]     # 检测到的动作
    mood: str              # 情感基调


@dataclass
class VideoAnalysis:
    """视频分析结果"""
    duration: float
    resolution: tuple
    fps: float
    segments: List[VideoSegment]
    overall_description: str
    suggested_highlights: List[Dict]  # 建议的精彩片段
    transcript: Optional[str] = None  # 语音转写


class VideoUnderstanding:
    """视频内容理解模块"""

    def __init__(self, vision_model, whisper_model):
        self.vision_model = vision_model  # 多模态视觉模型
        self.whisper = whisper_model      # 语音识别模型

    async def analyze(self, video_path: str) -> VideoAnalysis:
        """全面分析视频内容"""
        # 1. 获取视频基础信息
        basic_info = await self._get_basic_info(video_path)

        # 2. 提取关键帧
        key_frames = await self._extract_key_frames(video_path)

        # 3. 多模态理解
        segments = await self._analyze_frames(key_frames, basic_info)

        # 4. 语音转写
        transcript = await self._transcribe(video_path)

        # 5. 生成整体描述和精彩片段建议
        highlights = await self._suggest_highlights(segments, transcript)

        return VideoAnalysis(
            duration=basic_info["duration"],
            resolution=(basic_info["width"], basic_info["height"]),
            fps=basic_info["fps"],
            segments=segments,
            overall_description=await self._generate_summary(segments, transcript),
            suggested_highlights=highlights,
            transcript=transcript
        )

    async def _extract_key_frames(self, video_path: str, interval: float = 2.0) -> List[Dict]:
        """按间隔提取关键帧"""
        # 使用FFmpeg提取帧
        from src.service.use_ffmpeg import extract_frames_at_times

        frames = extract_frames_at_times(video_path, interval=interval)
        return frames

    async def _analyze_frames(self, frames: List[Dict], video_info: Dict) -> List[VideoSegment]:
        """使用多模态模型分析帧内容"""
        segments = []

        for i, frame in enumerate(frames):
            # 调用视觉模型分析
            analysis = await self.vision_model.analyze_image(
                frame["path"],
                prompt="""
                分析这张图片，返回JSON格式：
                {
                    "description": "画面描述",
                    "objects": ["检测到的对象"],
                    "actions": ["可能的动作"],
                    "mood": "情感基调",
                    "quality_score": 0.8
                }
                """
            )

            segment = VideoSegment(
                start_time=frame["time"],
                end_time=frame["time"] + 2.0,
                description=analysis["description"],
                key_frames=[frame["path"]],
                objects=analysis["objects"],
                actions=analysis["actions"],
                mood=analysis["mood"]
            )
            segments.append(segment)

        return segments

    async def find_best_clips(self, video_path: str, query: str, duration: float = 30.0) -> List[Dict]:
        """根据自然语言描述找到最佳片段"""
        analysis = await self.analyze(video_path)

        # 使用LLM匹配查询和片段
        prompt = f"""
        视频信息:
        - 总时长: {analysis.duration}秒
        - 片段数量: {len(analysis.segments)}

        片段描述:
        {[f"[{s.start_time:.1f}-{s.end_time:.1f}] {s.description}" for s in analysis.segments]}

        用户想要: {query}

        请推荐最匹配的片段，返回JSON:
        {{
            "clips": [
                {{"start": 开始时间, "end": 结束时间, "reason": "选择原因"}}
            ]
        }}
        """

        result = await self.vision_model.generate(prompt)
        return result["clips"]


    async def smart_search(self, query: str, video_analyses: Dict[str, VideoAnalysis]) -> List[Dict]:
        """在多个视频中搜索匹配的内容"""
        results = []

        for video_id, analysis in video_analyses.items():
            for segment in analysis.segments:
                # 计算匹配分数
                score = await self._calculate_relevance(query, segment)
                if score > 0.5:
                    results.append({
                        "video_id": video_id,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "description": segment.description,
                        "score": score
                    })

        return sorted(results, key=lambda x: x["score"], reverse=True)
```

### 3.3 智能剪辑规划器

```python
# src/agent/clip_planner.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

@dataclass
class ClipPlan:
    """剪辑计划"""
    clips: List[Dict]
    transitions: List[Dict]
    effects: List[Dict]
    audio_tracks: List[Dict]
    subtitles: List[Dict]
    estimated_duration: float


class ClipPlanner:
    """智能剪辑规划器"""

    def __init__(self, llm_service):
        self.llm = llm_service

    async def plan_from_script(self, script: str, video_sources: List[Dict],
                                target_duration: float = 60.0) -> ClipPlan:
        """根据文案自动规划剪辑方案"""
        prompt = f"""
        你是一个专业的视频剪辑师。请根据以下信息规划剪辑方案。

        目标文案:
        {script}

        可用素材:
        {json.dumps(video_sources, ensure_ascii=False, indent=2)}

        目标时长: {target_duration}秒

        请返回JSON格式的剪辑方案:
        {{
            "clips": [
                {{
                    "source_id": "素材ID",
                    "start_time": "00:00:00",
                    "end_time": "00:00:10",
                    "purpose": "这段用于展示什么内容"
                }}
            ],
            "transitions": [
                {{"type": "dissolve/cut/wipe", "duration": 0.5}}
            ],
            "effects": [
                {{
                    "type": "效果类型",
                    "params": {{}},
                    "apply_to": "clip_index"
                }}
            ],
            "audio": {{
                "background_music": "音乐风格建议",
                "voice_over": "需要配音的部分"
            }},
            "subtitles": [
                {{
                    "text": "字幕内容",
                    "start": "00:00:00",
                    "end": "00:00:03"
                }}
            ]
        }}

        规划原则:
        1. 片段时长要合理，避免过长或过短
        2. 转场要与内容情感匹配
        3. 总时长要接近目标时长
        4. 素材选择要与文案内容呼应
        """

        response = await self.llm.generate(prompt)
        plan_data = json.loads(response)

        return ClipPlan(
            clips=plan_data["clips"],
            transitions=plan_data["transitions"],
            effects=plan_data["effects"],
            audio_tracks=plan_data["audio"],
            subtitles=plan_data["subtitles"],
            estimated_duration=target_duration
        )

    async def optimize_pacing(self, clips: List[Dict], style: str = "dynamic") -> List[Dict]:
        """优化剪辑节奏"""
        prompt = f"""
        优化以下剪辑片段的节奏，使其更加{style}。

        当前片段:
        {json.dumps(clips, ensure_ascii=False, indent=2)}

        风格要求:
        - dynamic: 快节奏，适合短视频，片段短促有力
        - cinematic: 电影感，节奏舒缓，留有呼吸空间
        - documentary: 纪录片风格，稳重，信息密集

        返回优化后的片段列表，可以:
        1. 调整片段顺序
        2. 调整开始/结束时间
        3. 添加或删除片段
        4. 调整转场效果
        """

        response = await self.llm.generate(prompt)
        return json.loads(response)

    async def suggest_music(self, video_mood: str, duration: float) -> Dict:
        """推荐背景音乐"""
        prompt = f"""
        根据视频情感基调推荐背景音乐。

        视频情感: {video_mood}
        视频时长: {duration}秒

        返回:
        {{
            "genre": "音乐类型",
            "tempo": "节奏(bpm)",
            "mood": "情感描述",
            "search_keywords": ["搜索关键词"],
            "volume_curve": [
                {{"time": 0, "volume": 0.3}},
                {{"time": 10, "volume": 0.8}}
            ]
        }}
        """

        response = await self.llm.generate(prompt)
        return json.loads(response)
```

### 3.4 工具注册表

```python
# src/agent/tool_registry.py

from typing import Dict, Callable, Any
from dataclasses import dataclass
import asyncio

@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: Dict
    execute: Callable


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, parameters: Dict):
        """注册工具装饰器"""
        def decorator(func: Callable):
            self._tools[name] = Tool(
                name=name,
                description=description,
                parameters=parameters,
                execute=func
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        """获取所有工具的描述（供LLM使用）"""
        descriptions = []
        for tool in self._tools.values():
            descriptions.append(f"""
            {tool.name}:
            描述: {tool.description}
            参数: {json.dumps(tool.parameters, ensure_ascii=False)}
            """)
        return "\n".join(descriptions)


# 全局工具注册表
registry = ToolRegistry()


# 注册视频处理工具
@registry.register(
    name="cut_video",
    description="剪切视频片段，指定开始和结束时间",
    parameters={
        "video_path": {"type": "string", "description": "视频文件路径"},
        "start_time": {"type": "string", "description": "开始时间 (HH:MM:SS)"},
        "end_time": {"type": "string", "description": "结束时间 (HH:MM:SS)"},
        "output_path": {"type": "string", "description": "输出路径"}
    }
)
async def tool_cut_video(video_path: str, start_time: str, end_time: str, output_path: str):
    from src.service.use_ffmpeg import cut_video
    result = cut_video(video_path, start_time, end_time, output_path)
    return {"success": True, "output_path": result, "message": "剪切完成"}


@registry.register(
    name="merge_videos",
    description="合并多个视频文件",
    parameters={
        "video_paths": {"type": "array", "description": "视频路径列表"},
        "transitions": {"type": "array", "description": "转场效果列表"},
        "output_path": {"type": "string", "description": "输出路径"}
    }
)
async def tool_merge_videos(video_paths: List[str], transitions: List[Dict], output_path: str):
    from src.service.use_ffmpeg import concatenate_videos_with_transitions
    result = concatenate_videos_with_transitions(video_paths, output_path)
    return {"success": True, "output_path": output_path, "message": "合并完成"}


@registry.register(
    name="add_subtitle",
    description="为视频添加字幕",
    parameters={
        "video_path": {"type": "string"},
        "subtitle_content": {"type": "string"},
        "hard_subtitle": {"type": "boolean", "description": "是否硬字幕"}
    }
)
async def tool_add_subtitle(video_path: str, subtitle_content: str, hard_subtitle: bool = True):
    from src.service.use_ffmpeg import add_subtitle
    result = add_subtitle(video_path, subtitle_content, hard_subtitle)
    return {"success": True, "output_path": result, "message": "字幕添加完成"}


@registry.register(
    name="change_speed",
    description="调整视频播放速度",
    parameters={
        "video_path": {"type": "string"},
        "speed_factor": {"type": "number", "description": "速度倍数 (0.5=慢放, 2.0=快放)"}
    }
)
async def tool_change_speed(video_path: str, speed_factor: float):
    from src.service.use_ffmpeg import process_video
    output = process_video(video_path, speed_factor=speed_factor)
    return {"success": True, "output_path": output, "message": f"速度调整为{speed_factor}倍"}


@registry.register(
    name="analyze_video",
    description="分析视频内容，返回场景、对象、动作等信息",
    parameters={
        "video_path": {"type": "string"}
    }
)
async def tool_analyze_video(video_path: str):
    from src.agent.video_understanding import VideoUnderstanding
    analyzer = VideoUnderstanding(None, None)  # 需要注入模型
    result = await analyzer.analyze(video_path)
    return {
        "success": True,
        "analysis": {
            "duration": result.duration,
            "description": result.overall_description,
            "segments": len(result.segments),
            "highlights": result.suggested_highlights
        }
    }


@registry.register(
    name="generate_video",
    description="使用AI根据文本描述生成视频",
    parameters={
        "prompt": {"type": "string", "description": "视频内容描述"},
        "duration": {"type": "number", "description": "目标时长(秒)"},
        "style": {"type": "string", "description": "视频风格"}
    }
)
async def tool_generate_video(prompt: str, duration: float = 5.0, style: str = "realistic"):
    # 调用AI视频生成API (如Runway, Pika, Sora等)
    # 这里是示例实现
    return {
        "success": True,
        "message": "视频生成任务已提交",
        "task_id": "gen_123456",
        "estimated_time": duration * 10  # 预估时间
    }


@registry.register(
    name="add_audio",
    description="为视频添加背景音乐或配音",
    parameters={
        "video_path": {"type": "string"},
        "audio_path": {"type": "string", "description": "音频文件路径"},
        "volume": {"type": "number", "description": "音量 (0.0-1.0)"},
        "fade_in": {"type": "number", "description": "淡入时长(秒)"},
        "fade_out": {"type": "number", "description": "淡出时长(秒)"}
    }
)
async def tool_add_audio(video_path: str, audio_path: str, volume: float = 1.0,
                         fade_in: float = 0, fade_out: float = 0):
    from src.service.use_ffmpeg import add_audio_to_video
    output = add_audio_to_video(video_path, audio_path, "output_with_audio.mp4")
    return {"success": True, "output_path": output}
```

### 3.5 API 接口设计

```python
# src/api/chat_api.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid

router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: Optional[str] = None
    message: str
    context: Optional[Dict] = None


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    reply: str
    status: str  # idle, collecting, confirming, executing, completed
    action: Optional[Dict] = None
    result: Optional[Dict] = None
    suggestions: Optional[List[str]] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理对话请求"""
    session_id = request.session_id or str(uuid.uuid4())

    agent = get_video_agent()  # 获取全局Agent实例
    result = await agent.process_message(session_id, request.message)

    return ChatResponse(
        session_id=session_id,
        reply=result.get("message", ""),
        status=result.get("status", "idle"),
        action=result.get("action"),
        result=result.get("result"),
        suggestions=result.get("suggestions")
    )


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket实时对话"""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    agent = get_video_agent()

    try:
        while True:
            data = await websocket.receive_text()
            result = await agent.process_message(session_id, data)
            await websocket.send_json({
                "session_id": session_id,
                **result
            })
    except WebSocketDisconnect:
        pass


@router.post("/execute")
async def execute_action(action: Dict):
    """直接执行剪辑动作（跳过对话）"""
    tool_name = action.get("tool")
    params = action.get("params", {})

    tool = registry.get_tool(tool_name)
    if not tool:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    result = await tool.execute(**params)
    return result


@router.post("/analyze/{video_id}")
async def analyze_video_endpoint(video_id: int):
    """分析视频内容"""
    from src.repository import VideoRepository
    from src.db.session import get_db

    db = next(get_db())
    repo = VideoRepository(db)
    video = repo.get_by_id(video_id)

    if not video:
        return {"success": False, "error": "Video not found"}

    from src.agent.video_understanding import VideoUnderstanding
    analyzer = VideoUnderstanding(get_vision_model(), get_whisper_model())
    analysis = await analyzer.analyze(video.local_path)

    return {
        "success": True,
        "analysis": {
            "duration": analysis.duration,
            "description": analysis.overall_description,
            "highlights": analysis.suggested_highlights,
            "transcript": analysis.transcript
        }
    }
```

---

## 四、对话流程示例

### 示例 1：简单剪辑

```
用户: 帮我把视频的前30秒剪出来
助手: 好的，请告诉我您要剪辑哪个视频？

用户: 就是刚才上传的那个"旅行记录.mp4"
助手: 我找到了这个视频（时长5分钟）。请确认：
      - 视频：旅行记录.mp4
      - 时间：00:00:00 - 00:00:30
      - 输出：旅行记录_剪辑.mp4
      确认执行吗？

用户: 确认
助手: [执行中...] 剪切完成！
      输出文件：/static/uploads/旅行记录_剪辑.mp4
      [预览播放器]
```

### 示例 2：智能剪辑

```
用户: 帮我做一个30秒的旅行Vlog混剪，要那种很燃的感觉
助手: 好的，我来分析您的素材并规划剪辑方案...

      [分析中...找到5个旅行相关视频]

      我为您规划了以下方案：
      - 开场：海边日出的慢动作 (5秒)
      - 过渡：城市街景快切 (8秒)
      - 高潮：跳伞+冲浪的动感片段 (12秒)
      - 收尾：夕阳下的剪影 (5秒)

      背景音乐推荐：节奏感强的电子乐 (128bpm)

      确认按此方案执行吗？

用户: 把跳伞那段换成潜水吧
助手: 好的，已更新方案：
      - 高潮：潜水+冲浪的动感片段 (12秒)
      确认执行吗？

用户: 好的
助手: [执行中...]
      - 剪切片段 x4 ✓
      - 添加转场 x3 ✓
      - 添加背景音乐 ✓
      - 最终合成 ✓

      混剪完成！
      输出文件：/static/uploads/旅行混剪.mp4
```

### 示例 3：视频生成

```
用户: 帮我生成一段15秒的日落海滩视频
助手: 我来帮您生成。请补充一些细节：

      - 风格偏好：写实 / 动漫 / 电影感？
      - 时间段：黄金时刻 / 蓝调时刻？
      - 是否需要人物或动物？

用户: 电影感，黄金时刻，有一个人在遛狗
助手: 收到，生成参数：
      - 内容：日落海滩，黄金时刻，一人遛狗
      - 时长：15秒
      - 风格：电影感
      - 比例：16:9

      预计生成时间约2分钟，开始生成？

用户: 开始
助手: [生成中... 进度: 35%]
      ...
      [生成完成]

      视频已生成！
      输出文件：/static/generated/sunset_beach_15s.mp4
      [预览播放器]
```

---

## 五、技术选型

| 模块 | 推荐技术 | 说明 |
|------|----------|------|
| LLM | DeepSeek / Claude / GPT-4 | 意图识别、槽位提取、规划生成 |
| 多模态理解 | Qwen-VL / GPT-4V | 视频帧分析、内容理解 |
| 语音识别 | Faster Whisper | 语音转写 |
| 视频处理 | FFmpeg | 剪辑、转码、特效 |
| AI视频生成 | Runway/Pika/Sora API | 文本生成视频 |
| TTS | Fish Speech | 语音合成 |
| 向量检索 | ChromaDB / FAISS | 素材语义搜索 |
| 任务队列 | Celery / Redis | 异步任务处理 |

---

## 六、项目结构建议

```
src/
├── agent/                     # Agent核心模块
│   ├── __init__.py
│   ├── video_agent.py         # 视频对话Agent
│   ├── video_understanding.py # 视频理解
│   ├── clip_planner.py        # 剪辑规划
│   ├── tool_registry.py       # 工具注册
│   └── prompts.py             # 提示词模板
│
├── api/
│   ├── chat_api.py            # 对话接口
│   └── ...                    # 现有API
│
├── service/
│   ├── ai_video_generator.py  # AI视频生成
│   └── ...                    # 现有服务
│
└── model/
    ├── dialog_state.py        # 对话状态模型
    └── ...                    # 现有模型
```

---

## 七、实现路线图

### 第一阶段：基础对话 (1-2周)
- [ ] 实现 DialogState 和会话管理
- [ ] 实现意图识别（基于规则+LLM）
- [ ] 实现槽位填充
- [ ] 注册基础工具（cut, merge, add_subtitle）
- [ ] 实现 /chat API

### 第二阶段：视频理解 (2-3周)
- [ ] 集成多模态模型
- [ ] 实现关键帧提取和分析
- [ ] 实现视频内容描述生成
- [ ] 实现精彩片段推荐

### 第三阶段：智能剪辑 (2-3周)
- [ ] 实现 ClipPlanner
- [ ] 实现基于文案的自动剪辑
- [ ] 实现节奏优化
- [ ] 实现背景音乐推荐

### 第四阶段：AI生成 (1-2周)
- [ ] 集成视频生成API
- [ ] 实现文生视频
- [ ] 实现图生视频

### 第五阶段：优化完善 (持续)
- [ ] 多轮对话优化
- [ ] 错误处理和回退
- [ ] 性能优化
- [ ] 用户体验改进

---

## 八、关键提示词模板

```python
# src/agent/prompts.py

SYSTEM_PROMPT = """
你是一个专业的视频剪辑助手。你可以帮助用户：
1. 剪辑、合并、处理视频
2. 分析视频内容
3. 规划剪辑方案
4. 生成视频

交互原则：
- 简洁明了，避免冗余
- 必要时追问，避免猜测
- 提供具体选项，便于用户选择
- 执行前确认，避免误操作

工具列表：
{tools_description}
"""

INTENT_RECOGNITION_PROMPT = """
分析用户意图。

用户输入: {user_input}
对话历史: {history}

返回JSON:
{{
    "intent": "意图类型",
    "confidence": 0.95,
    "entities": {{"时间": "...", "时长": "..."}},
    "need_clarification": false,
    "clarification_question": ""
}}
"""

CLIP_PLANNING_PROMPT = """
你是专业视频剪辑师。根据以下信息规划剪辑方案：

文案: {script}
素材: {materials}
目标时长: {duration}秒
风格: {style}

返回剪辑方案JSON...
"""
```

---

这个方案提供了完整的自然语言视频剪辑/生成系统的实现思路，包括：
1. 对话管理和意图识别
2. 视频内容理解
3. 智能剪辑规划
4. 工具注册和执行
5. API接口设计

你可以根据实际需求逐步实现各个模块。

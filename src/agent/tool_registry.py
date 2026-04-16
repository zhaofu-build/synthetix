"""
工具注册表模块

管理所有可调用的剪辑工具
"""
import logging
import os
import re
import sys
import json
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import asyncio
from pydantic import BaseModel, Field, field_validator
from typing import Optional as Opt

logger = logging.getLogger(__name__)


# ==================== Pydantic 参数模型 ====================

class CutVideoParams(BaseModel):
    """剪切视频参数"""
    video_id: int = Field(..., description="视频 ID")
    start_time: str = Field(default="00:00:00", description="开始时间 (HH:MM:SS)")
    end_time: Opt[str] = Field(default=None, description="结束时间 (HH:MM:SS)")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v):
        if v and not re.match(r'^\d{2}:\d{2}:\d{2}(\.\d+)?$', v):
            raise ValueError(f"时间格式错误: {v}，需要 HH:MM:SS")
        return v


class MergeVideosParams(BaseModel):
    """合并视频参数"""
    video_ids: List[int] = Field(..., description="视频 ID 列表")
    transition: str = Field(default="cut", description="转场效果")


class AddSubtitleParams(BaseModel):
    """添加字幕参数"""
    video_id: int = Field(..., description="视频 ID")
    subtitle_content: str = Field(..., description="字幕内容或文件路径")
    hard_subtitle: bool = Field(default=True, description="是否硬字幕")


class ChangeSpeedParams(BaseModel):
    """调整速度参数"""
    video_id: int = Field(..., description="视频 ID")
    speed_factor: float = Field(..., gt=0, le=10, description="速度倍数")


class SmartClipParams(BaseModel):
    """智能剪辑参数"""
    description: str = Field(..., description="剪辑需求描述")
    duration: float = Field(default=30.0, description="目标时长（秒）")
    style: str = Field(default="动感", description="风格偏好")


class AnalyzeVideoParams(BaseModel):
    """分析视频参数"""
    video_id: int = Field(..., description="视频 ID")


class GenerateTtsParams(BaseModel):
    """生成语音参数"""
    text: str = Field(..., description="要合成的文本")
    speaker_id: Opt[int] = Field(default=None, description="说话人/音色 ID")


class SearchMaterialParams(BaseModel):
    """搜索素材参数"""
    keywords: str = Field(..., description="搜索关键词")


class TranscribeVideoParams(BaseModel):
    """字幕提取参数"""
    video_id: int = Field(..., description="视频 ID")
    language: Opt[str] = Field(default=None, description="语言（可选，默认自动检测）")


class AnalyzeVideoVlParams(BaseModel):
    """AI 视频理解参数"""
    video_id: int = Field(..., description="视频 ID")
    prompt: Opt[str] = Field(default="请详细描述这个视频的内容、场景和风格", description="分析提示")


class GenerateMusicParams(BaseModel):
    """音乐生成参数"""
    prompt: str = Field(..., description="音乐描述")
    duration: float = Field(default=10.0, ge=1, le=60, description="时长（秒）")
    style: Opt[str] = Field(default=None, description="风格: pop/classical/electronic/jazz/rock/ambient")


class AddAudioParams(BaseModel):
    """添加音频参数"""
    video_id: int = Field(..., description="视频 ID")
    audio_path: str = Field(..., description="音频文件路径")
    audio_type: str = Field(default="bgm", description="类型: dubbing(配音)/bgm(背景音乐)")


class DownloadVideoParams(BaseModel):
    """下载视频参数"""
    url: str = Field(..., description="视频 URL")


class SearchFilesParams(BaseModel):
    """搜索文件参数"""
    keywords: str = Field(..., description="搜索关键词")
    file_type: Opt[str] = Field(default="all", description="文件类型: video/audio/image/all")


class CompressVideoParams(BaseModel):
    """压缩视频参数"""
    video_id: int = Field(..., description="视频 ID")
    quality: Opt[str] = Field(default="medium", description="质量: low/medium/high")


class ExtractFramesParams(BaseModel):
    """提取帧参数"""
    video_id: int = Field(..., description="视频 ID")
    timestamps: Opt[str] = Field(default=None, description="时间点列表，逗号分隔 (HH:MM:SS)")


class ConvertToGifParams(BaseModel):
    """视频转 GIF 参数"""
    video_id: int = Field(..., description="视频 ID")
    start_time: Opt[str] = Field(default=None, description="开始时间 (HH:MM:SS)")
    end_time: Opt[str] = Field(default=None, description="结束时间 (HH:MM:SS)")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v):
        if v and not re.match(r'^\d{2}:\d{2}:\d{2}(\.\d+)?$', v):
            raise ValueError(f"时间格式错误: {v}，需要 HH:MM:SS")
        return v


class SeparateVocalParams(BaseModel):
    """人声分离参数"""
    video_id: int = Field(..., description="视频 ID")


class TranslateTextParams(BaseModel):
    """翻译参数"""
    text: str = Field(..., description="要翻译的文本")
    target_lang: Opt[str] = Field(default="zh", description="目标语言")


# 参数模型映射
PARAM_MODELS = {
    "cut_video": CutVideoParams,
    "merge_videos": MergeVideosParams,
    "add_subtitle": AddSubtitleParams,
    "change_speed": ChangeSpeedParams,
    "smart_clip": SmartClipParams,
    "analyze_video": AnalyzeVideoParams,
    "analyze_video_vl": AnalyzeVideoVlParams,
    "generate_tts": GenerateTtsParams,
    "generate_music": GenerateMusicParams,
    "search_material": SearchMaterialParams,
    "transcribe_video": TranscribeVideoParams,
    "add_audio": AddAudioParams,
    "download_video": DownloadVideoParams,
    "search_files": SearchFilesParams,
    "compress_video": CompressVideoParams,
    "extract_frames": ExtractFramesParams,
    "convert_to_gif": ConvertToGifParams,
    "separate_vocal": SeparateVocalParams,
    "translate_text": TranslateTextParams,
}


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    execute: Callable
    examples: List[str] = None
    param_model: Optional[type] = None
    before_execute: Optional[Callable] = None
    after_execute: Optional[Callable] = None

    def __post_init__(self):
        if self.examples is None:
            self.examples = []

    def validate_params(self, params: Dict) -> Dict:
        """校验并规范化参数"""
        if self.param_model is None:
            return params
        model = self.param_model(**params)
        return model.model_dump()


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        examples: List[str] = None,
        param_model: Optional[type] = None,
        before_execute: Optional[Callable] = None,
        after_execute: Optional[Callable] = None
    ) -> Callable:
        """
        注册工具装饰器

        Args:
            name: 工具名称
            description: 工具描述
            parameters: 参数定义
            examples: 使用示例
            param_model: Pydantic 参数校验模型
            before_execute: 执行前钩子（异步函数，接收 params dict，返回修改后的 params）
            after_execute: 执行后钩子（异步函数，接收 result dict，返回修改后的 result）

        Returns:
            装饰器函数
        """
        def decorator(func: Callable):
            self._tools[name] = Tool(
                name=name,
                description=description,
                parameters=parameters,
                execute=func,
                examples=examples or [],
                param_model=param_model,
                before_execute=before_execute,
                after_execute=after_execute
            )
            logger.info(f"注册工具: {name}")
            return func
        return decorator

    def register_tool(self, tool: Tool):
        """直接注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        """获取所有工具的描述（供 LLM 使用）"""
        descriptions = []
        for tool in self._tools.values():
            params_str = ", ".join(tool.parameters.keys())
            descriptions.append(
                f"- {tool.name}: {tool.description}\n"
                f"  参数: {params_str}"
            )
        return "\n".join(descriptions)

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools


# 全局工具注册表
registry = ToolRegistry()


# ==================== 通用 Hook 函数 ====================

def validate_video_exists(params: Dict) -> Dict:
    """校验视频是否存在的 before_execute hook"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    video_id = params.get("video_id")
    if video_id:
        with get_db_context() as db:
            repo = VideoRepository(db)
            if not repo.exists(video_id):
                raise ValueError(f"视频 {video_id} 不存在")
    return params


def validate_videos_exist(params: Dict) -> Dict:
    """校验多个视频是否存在的 before_execute hook"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    video_ids = params.get("video_ids", [])
    if video_ids:
        with get_db_context() as db:
            repo = VideoRepository(db)
            # Batch check instead of one-by-one
            existing_ids = set(
                row[0] for row in db.query(repo.model.id)
                .filter(repo.model.id.in_(video_ids))
                .all()
            )
            missing = [vid for vid in video_ids if vid not in existing_ids]
            if missing:
                raise ValueError(f"视频不存在: {missing}")
    return params


# ==================== 注册基础工具 ====================

@registry.register(
    name="cut_video",
    description="剪切视频片段，指定开始和结束时间",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "start_time": {"type": "string", "description": "开始时间 (HH:MM:SS)"},
        "end_time": {"type": "string", "description": "结束时间 (HH:MM:SS)"},
    },
    examples=["帮我把视频前30秒剪出来", "从第10秒到第30秒剪切"],
    param_model=CutVideoParams,
    before_execute=validate_video_exists
)
async def tool_cut_video(
    video_id: int,
    start_time: str = "00:00:00",
    end_time: str = None,
    **kwargs
) -> Dict[str, Any]:
    """剪切视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    import os

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {
                    "success": False,
                    "error": f"视频 {video_id} 不存在"
                }

            # 执行剪切
            output_path = ffmpeg.cut_video(
                input_path=video.local_path,
                start_time=start_time,
                end_time=end_time
            )

            # 获取剪切后视频的时长
            cut_info = ffmpeg.get_video_info(output_path) or {}
            cut_duration = float(cut_info.get("duration", 0)) or None

            # 入库：注册为新素材
            cut_name = f"{video.video_name or 'video'}_cut_{start_time.replace(':','')}"
            if end_time:
                cut_name += f"_{end_time.replace(':','')}"
            cut_name += os.path.splitext(video.video_name or '.mp4')[1] or '.mp4'

            new_video = repo.create(
                video_name=cut_name,
                local_path=output_path,
                duration=cut_duration,
            )

            return {
                "success": True,
                "video_id": new_video.id,
                "output_path": output_path,
                "duration": cut_duration,
                "message": f"剪切完成: {start_time} - {end_time or '结尾'}，新素材 ID={new_video.id}"
            }

    except Exception as e:
        logger.error(f"剪切视频失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="merge_videos",
    description="合并多个视频文件",
    parameters={
        "video_ids": {"type": "array", "description": "视频 ID 列表"},
        "transition": {"type": "string", "description": "转场效果 (dissolve/cut)"},
    },
    examples=["把这两个视频合并", "合并选中的视频"],
    param_model=MergeVideosParams,
    before_execute=validate_videos_exist
)
async def tool_merge_videos(
    video_ids: List[int],
    transition: str = "cut",
    **kwargs
) -> Dict[str, Any]:
    """合并视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video_paths = []

            for vid in video_ids:
                video = repo.get_by_id(vid)
                if video:
                    video_paths.append(video.local_path)

            if not video_paths:
                return {
                    "success": False,
                    "error": "没有找到有效的视频"
                }

            # 执行合并
            output_path = f"{config.UPLOAD_DIR}merged_{len(video_paths)}_videos.mp4"
            ffmpeg.concatenate_videos(video_paths, output_path)

            return {
                "success": True,
                "output_path": output_path,
                "message": f"成功合并 {len(video_paths)} 个视频"
            }

    except Exception as e:
        logger.error(f"合并视频失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="add_subtitle",
    description="为视频添加字幕",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "subtitle_content": {"type": "string", "description": "字幕内容或文件路径"},
        "hard_subtitle": {"type": "boolean", "description": "是否硬字幕"},
    },
    examples=["给视频添加字幕", "添加硬字幕"],
    param_model=AddSubtitleParams,
    before_execute=validate_video_exists
)
async def tool_add_subtitle(
    video_id: int,
    subtitle_content: str,
    hard_subtitle: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """添加字幕工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {
                    "success": False,
                    "error": f"视频 {video_id} 不存在"
                }

            # 添加字幕
            output_path = ffmpeg.add_subtitle(
                video_path=video.local_path,
                subtitle_content=subtitle_content,
                is_soft=not hard_subtitle
            )

            return {
                "success": True,
                "output_path": output_path,
                "message": "字幕添加完成"
            }

    except Exception as e:
        logger.error(f"添加字幕失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="change_speed",
    description="调整视频播放速度",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "speed_factor": {"type": "number", "description": "速度倍数 (0.5=慢放, 2.0=快放)"},
    },
    examples=["把视频放慢一点", "2倍速播放"],
    param_model=ChangeSpeedParams,
    before_execute=validate_video_exists
)
async def tool_change_speed(
    video_id: int,
    speed_factor: float,
    **kwargs
) -> Dict[str, Any]:
    """调整速度工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {
                    "success": False,
                    "error": f"视频 {video_id} 不存在"
                }

            # 调整速度
            output_path = ffmpeg.process_video(
                input_path=video.local_path,
                speed_factor=speed_factor
            )

            speed_desc = "慢放" if speed_factor < 1 else "快放"
            return {
                "success": True,
                "output_path": str(output_path),
                "message": f"已调整为 {speed_factor} 倍速{speed_desc}"
            }

    except Exception as e:
        logger.error(f"调整速度失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="smart_clip",
    description="智能剪辑，根据描述自动规划和生成视频",
    parameters={
        "description": {"type": "string", "description": "剪辑需求描述"},
        "duration": {"type": "number", "description": "目标时长（秒）"},
        "style": {"type": "string", "description": "风格偏好"},
    },
    examples=["帮我做一个30秒的旅行混剪", "做一个燃一点的短视频"],
    param_model=SmartClipParams
)
async def tool_smart_clip(
    description: str,
    duration: float = 30.0,
    style: str = "动感",
    **kwargs
) -> Dict[str, Any]:
    """智能剪辑工具"""
    from src.application.services.creative_service import CreativeService

    try:
        service = CreativeService()
        result = service.create_video_with_transitions(
            creative=description,
            audio_url=kwargs.get("audio_url")
        )

        return {
            "success": True,
            "output_path": result.get("concatenate_web_url"),
            "message": f"智能剪辑完成，时长约 {duration} 秒"
        }

    except Exception as e:
        logger.error(f"智能剪辑失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="analyze_video",
    description="分析视频内容，返回场景、对象、动作等信息",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["分析这个视频", "看看视频里有什么"],
    param_model=AnalyzeVideoParams,
    before_execute=validate_video_exists
)
async def tool_analyze_video(
    video_id: int,
    **kwargs
) -> Dict[str, Any]:
    """分析视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {
                    "success": False,
                    "error": f"视频 {video_id} 不存在"
                }

            # 获取基础信息
            info = ffmpeg.get_video_info(video.local_path)

            return {
                "success": True,
                "analysis": {
                    "video_id": video_id,
                    "video_name": video.video_name,
                    "duration": info.get("duration_hms", "00:00:00"),
                    "resolution": f"{info.get('width', 0)}x{info.get('height', 0)}",
                    "description": video.description or "暂无描述"
                },
                "message": "分析完成"
            }

    except Exception as e:
        logger.error(f"分析视频失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="generate_tts",
    description="文本转语音，生成配音",
    parameters={
        "text": {"type": "string", "description": "要合成的文本"},
        "speaker_id": {"type": "integer", "description": "说话人/音色 ID"},
    },
    examples=["生成配音", "把这个文案读出来"],
    param_model=GenerateTtsParams
)
async def tool_generate_tts(
    text: str,
    speaker_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """生成 TTS 工具"""
    from src.application.services.fish_speech_adapter import generate_audio
    from src import config

    try:
        # 生成语音
        output_path = generate_audio(
            text=text,
            audio_source_id=speaker_id
        )

        return {
            "success": True,
            "output_path": output_path,
            "web_path": config.UPLOAD_DIR + output_path.split("/")[-1],
            "message": "语音生成完成"
        }

    except Exception as e:
        logger.error(f"语音生成失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="list_videos",
    description="列出可用的视频素材",
    parameters={},
    examples=["有什么素材", "查看素材库"]
)
async def tool_list_videos(**kwargs) -> Dict[str, Any]:
    """列出视频工具，支持按项目筛选"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.domain.entities.video_project import VideoProject

    project_id = kwargs.get("project_id")

    try:
        with get_db_context() as db:
            if project_id:
                # 按项目查询：只返回项目关联的素材
                project = db.query(VideoProject).filter(VideoProject.id == int(project_id)).first()
                if project and project.material_ids:
                    repo = VideoRepository(db)
                    videos = repo.get_by_ids(project.material_ids)
                    label = f"项目 '{project.name}' 中"
                else:
                    return {
                        "success": True,
                        "videos": [],
                        "count": 0,
                        "message": "当前项目没有关联素材"
                    }
            else:
                repo = VideoRepository(db)
                videos = repo.get_all(limit=20)
                label = "素材库中"

            video_list = [
                {
                    "id": v.id,
                    "name": v.video_name,
                    "duration": v.duration_hms,
                    "description": v.description or "无描述"
                }
                for v in videos
            ]

            # 构建包含素材名称的详细消息
            lines = [f"{label}共 {len(video_list)} 个素材："]
            for i, v in enumerate(video_list):
                name = v.get("name") or "未命名"
                dur = v.get("duration") or ""
                lines.append(f"{i+1}. {name} ({dur})")

            return {
                "success": True,
                "videos": video_list,
                "count": len(video_list),
                "message": "\n".join(lines)
            }

    except Exception as e:
        logger.error(f"获取素材列表失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="get_video_description",
    description="查询视频素材的描述信息，如果无描述会提示用户使用 AI 分析",
    parameters={
        "video_id": {"type": "integer", "description": "视频素材 ID"},
    },
    examples=["第一个视频的描述", "这个视频讲了什么", "查看描述"],
)
async def tool_get_video_description(video_id: int, **kwargs) -> Dict[str, Any]:
    """查询视频素材的描述信息"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"找不到 ID 为 {video_id} 的素材"}

            name = video.video_name or "未命名"
            desc = video.description

            if desc:
                # 尝试解析 JSON segments 格式
                try:
                    obj = json.loads(desc)
                    if isinstance(obj, dict) and "segments" in obj:
                        segs = obj["segments"]
                        lines = [f"- **{s.get('start', '?')}s-{s.get('end', '?')}s**: {s.get('desc', '')}" for s in segs]
                        formatted = "\n".join(lines)
                        return {
                            "success": True,
                            "video_id": video_id,
                            "video_name": name,
                            "description": formatted,
                            "has_description": True,
                            "message": f"**{name}** 的描述：\n{formatted}",
                        }
                except (ValueError, TypeError):
                    pass

                return {
                    "success": True,
                    "video_id": video_id,
                    "video_name": name,
                    "description": desc,
                    "has_description": True,
                    "message": f"**{name}** 的描述：{desc}",
                }
            else:
                return {
                    "success": True,
                    "video_id": video_id,
                    "video_name": name,
                    "description": None,
                    "has_description": False,
                    "message": (
                        f"**{name}** 暂无描述。\n\n"
                        "您可以在素材库中点击「AI分析」按钮获取描述，"
                        "或者回复 **帮我AI分析** 我来帮您分析。"
                    ),
                }

    except Exception as e:
        logger.error(f"查询视频描述失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="search_material",
    description="搜索或下载视频素材",
    parameters={
        "keywords": {"type": "string", "description": "搜索关键词"},
    },
    examples=["下载一些海边素材", "搜索城市夜景"],
    param_model=SearchMaterialParams
)
async def tool_search_material(
    keywords: str,
    **kwargs
) -> Dict[str, Any]:
    """搜索素材工具"""
    from src.application.services.creative_service import CreativeService

    try:
        service = CreativeService()
        result = service.get_source_by_keywords(keywords)

        return {
            "success": True,
            "message": f"已下载与 '{keywords}' 相关的素材",
            "details": result
        }

    except Exception as e:
        logger.error(f"搜索素材失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== P0: 能力缺口工具 ====================

@registry.register(
    name="transcribe_video",
    description="从视频中提取字幕，进行语音识别生成 SRT 字幕文件",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "language": {"type": "string", "description": "语言（可选，默认自动检测）"},
    },
    examples=["帮我提取这个视频的字幕", "识别视频中的语音", "生成字幕文件"],
    param_model=TranscribeVideoParams,
    before_execute=validate_video_exists
)
async def tool_transcribe_video(
    video_id: int,
    language: str = None,
    **kwargs
) -> Dict[str, Any]:
    """字幕提取工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import whisper_adapter

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            subtitle_text = whisper_adapter.transcribe(
                audio_path=video.local_path,
                subtitle_language=language or "zh"
            )

            return {
                "success": True,
                "subtitle": subtitle_text,
                "message": "字幕提取完成"
            }

    except Exception as e:
        logger.error(f"字幕提取失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="analyze_video_vl",
    description="AI 深度分析视频内容，理解场景、人物、动作、风格等",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "prompt": {"type": "string", "description": "分析提示（可选）"},
    },
    examples=["这个视频讲了什么", "分析视频内容和风格", "详细描述一下这个视频"],
    param_model=AnalyzeVideoVlParams,
    before_execute=validate_video_exists
)
async def tool_analyze_video_vl(
    video_id: int,
    prompt: str = "请详细描述这个视频的内容、场景和风格",
    **kwargs
) -> Dict[str, Any]:
    """AI 视频理解工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import qwen_vl_adapter
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            # AI 视觉理解
            duration_sec = video.duration if video.duration else None
            analysis = qwen_vl_adapter.video_summary(
                tmp_path=video.local_path,
                prompt=prompt,
                duration=duration_sec
            )

            return {
                "success": True,
                "analysis": {
                    "video_id": video_id,
                    "video_name": video.video_name,
                    "duration": video.duration_hms or "未知",
                    "ai_summary": analysis
                },
                "message": "AI 视频分析完成"
            }

    except Exception as e:
        logger.error(f"AI 视频分析失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="generate_music",
    description="根据文字描述生成背景音乐",
    parameters={
        "prompt": {"type": "string", "description": "音乐描述"},
        "duration": {"type": "number", "description": "时长（秒，默认10）"},
        "style": {"type": "string", "description": "风格: pop/classical/electronic/jazz/rock/ambient"},
    },
    examples=["生成一段轻快的电子音乐", "做一个30秒的钢琴背景音乐", "来点爵士风格的 BGM"],
    param_model=GenerateMusicParams
)
async def tool_generate_music(
    prompt: str,
    duration: float = 10.0,
    style: str = None,
    **kwargs
) -> Dict[str, Any]:
    """音乐生成工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src import config
    import base64

    try:
        client = get_client()
        result = client.text_to_music(
            prompt=prompt,
            duration=duration,
            style=style
        )

        audio_data = result.get("audio", "")
        if audio_data:
            # 保存音频文件
            if audio_data.startswith("data:"):
                audio_data = audio_data.split(",", 1)[1]
            audio_bytes = base64.b64decode(audio_data)
            output_filename = f"music_{int(time.time())}.mp3"
            output_path = os.path.join(config.UPLOAD_DIR, output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            web_path = f"/static/uploads/{output_filename}"
        else:
            output_path = None
            web_path = None

        return {
            "success": True,
            "output_path": output_path,
            "web_path": web_path,
            "duration": result.get("duration", duration),
            "message": f"音乐生成完成，时长 {result.get('duration', duration)} 秒"
        }

    except Exception as e:
        logger.error(f"音乐生成失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_audio",
    description="为视频添加音频、配音或背景音乐",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "audio_path": {"type": "string", "description": "音频文件路径"},
        "audio_type": {"type": "string", "description": "类型: dubbing(配音)/bgm(背景音乐)"},
    },
    examples=["给视频加上背景音乐", "添加配音"],
    param_model=AddAudioParams,
    before_execute=validate_video_exists
)
async def tool_add_audio(
    video_id: int,
    audio_path: str,
    audio_type: str = "bgm",
    **kwargs
) -> Dict[str, Any]:
    """添加音频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services.video_service import VideoService

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            service = VideoService()
            result = service.add_audio_to_video(
                video_path=video.local_path,
                audio_path=audio_path
            )

            return {
                "success": True,
                "output_path": result.get("output_path") if isinstance(result, dict) else str(result),
                "message": f"已添加{'配音' if audio_type == 'dubbing' else '背景音乐'}"
            }

    except Exception as e:
        logger.error(f"添加音频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="download_video",
    description="从 URL 下载视频到素材库",
    parameters={
        "url": {"type": "string", "description": "视频 URL"},
    },
    examples=["下载这个视频 https://...", "帮我下载一个视频"],
    param_model=DownloadVideoParams
)
async def tool_download_video(
    url: str,
    **kwargs
) -> Dict[str, Any]:
    """下载视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.application.services.video_service import VideoService

    try:
        with get_db_context() as db:
            service = VideoService(db)
            result = service.download_video(url)

            return {
                "success": True,
                "video_id": result["id"],
                "filename": result["filename"],
                "output_path": result["local_path"],
                "message": f"视频下载完成，已入库 ID={result['id']}"
            }

    except Exception as e:
        logger.error(f"视频下载失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== P1: 基础系统工具 ====================

@registry.register(
    name="get_current_time",
    description="获取当前日期和时间",
    parameters={},
    examples=["现在几点了", "今天几号", "当前时间"]
)
async def tool_get_current_time(**kwargs) -> Dict[str, Any]:
    """查询当前时间"""
    from datetime import datetime

    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    return {
        "success": True,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": weekdays[now.weekday()],
        "message": f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} {weekdays[now.weekday()]}"
    }


@registry.register(
    name="list_directory",
    description="列出指定目录下的文件和文件夹",
    parameters={
        "path": {"type": "string", "description": "目录路径（默认素材目录）"},
        "pattern": {"type": "string", "description": "文件名过滤（可选）"},
    },
    examples=["看看素材目录里有什么", "列出 uploads 文件夹的内容"]
)
async def tool_list_directory(
    path: str = None,
    pattern: str = None,
    **kwargs
) -> Dict[str, Any]:
    """列出目录工具"""
    import os
    from pathlib import Path as FilePath
    from src import config

    try:
        target = path or config.UPLOAD_DIR

        # 防止目录穿越：只允许访问项目相关目录
        allowed_dirs = [
            FilePath(config.UPLOAD_DIR).resolve(),
            FilePath(config.source_videos_dir).resolve() if hasattr(config, 'source_videos_dir') else None,
            FilePath(config.source_audios_dir).resolve() if hasattr(config, 'source_audios_dir') else None,
            FilePath("static").resolve(),
        ]
        allowed_dirs = [d for d in allowed_dirs if d is not None]

        target_resolved = FilePath(target).resolve()
        if not any(str(target_resolved).startswith(str(d)) for d in allowed_dirs):
            return {"success": False, "error": f"不允许访问该目录: {target}"}

        if not os.path.isdir(target):
            return {"success": False, "error": f"目录不存在: {target}"}

        items = []
        for item in os.listdir(target):
            full_path = os.path.join(target, item)
            if pattern and pattern.lower() not in item.lower():
                continue
            items.append({
                "name": item,
                "type": "directory" if os.path.isdir(full_path) else "file",
                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None
            })

        return {
            "success": True,
            "path": target,
            "items": items,
            "count": len(items),
            "message": f"共 {len(items)} 个项目"
        }

    except Exception as e:
        logger.error(f"列出目录失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="search_files",
    description="在素材目录中模糊搜索文件",
    parameters={
        "keywords": {"type": "string", "description": "搜索关键词"},
        "file_type": {"type": "string", "description": "文件类型: video/audio/image/all"},
    },
    examples=["找一下海边的视频", "搜索 mp3 文件"],
    param_model=SearchFilesParams
)
async def tool_search_files(
    keywords: str,
    file_type: str = "all",
    **kwargs
) -> Dict[str, Any]:
    """搜索文件工具"""
    import os
    from src import config

    try:
        ext_map = {
            "video": {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"},
            "audio": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"},
            "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
        }
        allowed_ext = ext_map.get(file_type, None)

        results = []
        search_dirs = [config.UPLOAD_DIR, config.source_videos_dir, config.source_audios_dir]

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for root, dirs, files in os.walk(search_dir):
                for fname in files:
                    if keywords.lower() not in fname.lower():
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if allowed_ext and ext not in allowed_ext:
                        continue
                    full_path = os.path.join(root, fname)
                    results.append({
                        "name": fname,
                        "path": full_path,
                        "size": os.path.getsize(full_path),
                    })

        return {
            "success": True,
            "files": results[:20],
            "count": len(results),
            "message": f"找到 {len(results)} 个匹配文件" + (f"（显示前20个）" if len(results) > 20 else "")
        }

    except Exception as e:
        logger.error(f"搜索文件失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== P2: FFmpeg 高级工具 ====================

@registry.register(
    name="compress_video",
    description="压缩视频文件大小（H.265 编码）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "quality": {"type": "string", "description": "质量: low/medium/high"},
    },
    examples=["压缩这个视频", "把视频文件变小一点"],
    param_model=CompressVideoParams,
    before_execute=validate_video_exists
)
async def tool_compress_video(
    video_id: int,
    quality: str = "medium",
    **kwargs
) -> Dict[str, Any]:
    """视频压缩工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    quality_map = {"low": 28, "medium": 23, "high": 18}
    crf = quality_map.get(quality, 23)

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = ffmpeg.compress_video_h265(
                input_path=video.local_path,
                crf=crf
            )

            return {
                "success": True,
                "output_path": str(output_path),
                "message": f"视频压缩完成（质量: {quality}）"
            }

    except Exception as e:
        logger.error(f"视频压缩失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="extract_frames",
    description="从视频中提取关键帧或指定时间点的截图",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "timestamps": {"type": "string", "description": "时间点列表 (HH:MM:SS)，逗号分隔"},
    },
    examples=["截取视频第5秒的画面", "提取几个关键帧"],
    param_model=ExtractFramesParams,
    before_execute=validate_video_exists
)
async def tool_extract_frames(
    video_id: int,
    timestamps: str = None,
    **kwargs
) -> Dict[str, Any]:
    """提取帧工具"""
    import os
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = os.path.join(config.UPLOAD_DIR, f"frames_{video_id}")
            os.makedirs(output_dir, exist_ok=True)

            if timestamps:
                ts_list = [t.strip() for t in timestamps.split(",")]
            else:
                # 默认提取 5 帧（均匀分布）
                info = ffmpeg.get_video_info(video.local_path)
                duration = float(info.get("duration", 30)) if info else 30
                step = duration / 6
                ts_list = [f"{int(step * (i + 1)) // 3600:02d}:{(int(step * (i + 1)) % 3600) // 60:02d}:{int(step * (i + 1)) % 60:02d}" for i in range(5)]

            frame_paths = []
            for i, ts in enumerate(ts_list):
                output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
                ffmpeg.extract_frame(video.local_path, ts, output_path)
                frame_paths.append(output_path)

            return {
                "success": True,
                "frames": frame_paths,
                "count": len(frame_paths),
                "message": f"已提取 {len(frame_paths)} 帧"
            }

    except Exception as e:
        logger.error(f"提取帧失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="convert_to_gif",
    description="将视频片段转换为 GIF 动图",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "start_time": {"type": "string", "description": "开始时间 (HH:MM:SS)"},
        "end_time": {"type": "string", "description": "结束时间 (HH:MM:SS)"},
    },
    examples=["把前5秒转成GIF", "做个动图"],
    param_model=ConvertToGifParams,
    before_execute=validate_video_exists
)
async def tool_convert_to_gif(
    video_id: int,
    start_time: str = None,
    end_time: str = None,
    **kwargs
) -> Dict[str, Any]:
    """视频转 GIF 工具"""
    import os
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"gif_{video_id}_{int(time.time())}.gif")

            # 计算时长参数
            duration_param = None
            if start_time and end_time:
                from src.shared.utils import time_util
                start_sec = time_util.hms_to_seconds(start_time) if hasattr(time_util, 'hms_to_seconds') else 0
                end_sec = time_util.hms_to_seconds(end_time) if hasattr(time_util, 'hms_to_seconds') else 0
                duration_param = end_sec - start_sec

            ffmpeg.video_to_gif(
                input_video=video.local_path,
                start_time=start_time,
                duration=duration_param
            )

            return {
                "success": True,
                "output_path": output_path,
                "message": "GIF 生成完成"
            }

    except Exception as e:
        logger.error(f"GIF 生成失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="separate_vocal",
    description="分离视频中的人声和伴奏",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["分离人声和伴奏", "提取背景音乐"],
    param_model=SeparateVocalParams,
    before_execute=validate_video_exists
)
async def tool_separate_vocal(
    video_id: int,
    **kwargs
) -> Dict[str, Any]:
    """人声分离工具"""
    import os
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.application.services import dh_live_adapter
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            # 先提取音频
            output_dir = os.path.join(config.UPLOAD_DIR, f"separated_{video_id}")
            os.makedirs(output_dir, exist_ok=True)
            audio_path = os.path.join(output_dir, "original.wav")
            ffmpeg.extract_audio(video.local_path, audio_path)

            # 人声分离
            dh_live_adapter.do_s(audio_path, output_dir)

            return {
                "success": True,
                "output_dir": output_dir,
                "message": "人声分离完成，已生成人声和伴奏文件"
            }

    except Exception as e:
        logger.error(f"人声分离失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="translate_text",
    description="翻译文本内容",
    parameters={
        "text": {"type": "string", "description": "要翻译的文本"},
        "target_lang": {"type": "string", "description": "目标语言（默认中文）"},
    },
    examples=["把这段话翻译成英文", "翻译成日语"],
    param_model=TranslateTextParams
)
async def tool_translate_text(
    text: str,
    target_lang: str = "zh",
    **kwargs
) -> Dict[str, Any]:
    """翻译工具"""
    from src.application.services import translation_adapter

    try:
        result = translation_adapter.translator_response(
            messages=[{"role": "user", "content": text}],
            to_language=target_lang
        )

        return {
            "success": True,
            "translated_text": result,
            "message": "翻译完成"
        }

    except Exception as e:
        logger.error(f"翻译失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 第一梯队：高频实用工具 ====================

@registry.register(
    name="extract_audio",
    description="从视频中提取音频轨道，导出为音频文件",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["提取视频的音频", "把视频的声音导出来"],
    before_execute=validate_video_exists
)
async def tool_extract_audio(video_id: int, **kwargs) -> Dict[str, Any]:
    """提取音频工具"""
    import os
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"audio_{video_id}_{int(time.time())}.wav")
            ffmpeg.get_audio(video.local_path, output_path)

            return {"success": True, "output_path": output_path, "message": "音频提取完成"}

    except Exception as e:
        logger.error(f"提取音频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="mix_audio_to_video",
    description="将配音和背景音乐同时混入视频（自动混合多路音频）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "tts_path": {"type": "string", "description": "配音文件路径"},
        "bgm_path": {"type": "string", "description": "背景音乐文件路径"},
        "bgm_volume": {"type": "number", "description": "背景音乐音量 (0.0-1.0)"},
    },
    examples=["给视频加配音和背景音乐", "混合配音和 BGM"],
    before_execute=validate_video_exists
)
async def tool_mix_audio_to_video(
    video_id: int,
    tts_path: str = None,
    bgm_path: str = None,
    bgm_volume: float = 0.3,
    **kwargs
) -> Dict[str, Any]:
    """混合音频到视频"""
    import os
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"mixed_{video_id}_{int(time.time())}.mp4")
            ffmpeg.mix_audios_to_video(
                video_path=video.local_path,
                tts_path=tts_path,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                output_path=output_path
            )

            return {"success": True, "output_path": output_path, "message": "音频混合完成"}

    except Exception as e:
        logger.error(f"混合音频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="get_video_detail",
    description="获取视频详细信息（编码、分辨率、帧率、码率、时长等）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["查看视频详情", "这个视频是什么编码"],
    before_execute=validate_video_exists
)
async def tool_get_video_detail(video_id: int, **kwargs) -> Dict[str, Any]:
    """获取视频详情"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            info = ffmpeg.get_video_info(video.local_path)
            if not info:
                return {"success": False, "error": "无法获取视频信息"}

            return {
                "success": True,
                "detail": {
                    "video_id": video_id,
                    "name": video.video_name,
                    "codec": info.get("codec", "unknown"),
                    "width": info.get("width", 0),
                    "height": info.get("height", 0),
                    "resolution": f"{info.get('width', 0)}x{info.get('height', 0)}",
                    "fps": info.get("fps", "unknown"),
                    "duration": info.get("duration_hms", "unknown"),
                    "bit_rate": info.get("bit_rate", "unknown"),
                    "file_size": info.get("size", "unknown"),
                },
                "message": "视频信息获取完成"
            }

    except Exception as e:
        logger.error(f"获取视频详情失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="split_video",
    description="按固定间隔将视频拆分成多个片段",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "interval": {"type": "integer", "description": "每段时长（秒）"},
    },
    examples=["把视频每10秒切一段", "拆分成多个片段"],
    before_execute=validate_video_exists
)
async def tool_split_video(video_id: int, interval: int = 10, **kwargs) -> Dict[str, Any]:
    """拆分视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = os.path.join(config.UPLOAD_DIR, f"clips_{video_id}")
            os.makedirs(output_dir, exist_ok=True)

            ffmpeg.extract_video_clips(video.local_path, output_dir, interval)

            clips = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]

            return {
                "success": True,
                "output_dir": output_dir,
                "clips_count": len(clips),
                "message": f"已拆分为 {len(clips)} 个片段（每段 {interval} 秒）"
            }

    except Exception as e:
        logger.error(f"拆分视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="list_audios",
    description="列出可用的音色/语音列表",
    parameters={},
    examples=["有哪些音色", "列出可用的声音"]
)
async def tool_list_audios(**kwargs) -> Dict[str, Any]:
    """列出音色工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import AudioRepository

    try:
        with get_db_context() as db:
            repo = AudioRepository(db)
            audios = repo.get_active_audios(limit=50)

            audio_list = [
                {"id": a.id, "name": a.audio_name, "seed": a.seed}
                for a in audios
            ]

            return {
                "success": True,
                "audios": audio_list,
                "count": len(audio_list),
                "message": f"共 {len(audio_list)} 个可用音色"
            }

    except Exception as e:
        logger.error(f"获取音色列表失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="set_cover",
    description="设置视频封面/缩略图",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "cover_image": {"type": "string", "description": "封面图片路径"},
    },
    examples=["设置视频封面", "更换缩略图"],
    before_execute=validate_video_exists
)
async def tool_set_cover(video_id: int, cover_image: str, **kwargs) -> Dict[str, Any]:
    """设置封面工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ffmpeg.set_video_cover(video.local_path, cover_image)

            return {"success": True, "message": "封面设置完成"}

    except Exception as e:
        logger.error(f"设置封面失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 第二梯队：体验提升工具 ====================

@registry.register(
    name="get_system_info",
    description="获取系统信息（GPU、磁盘空间、系统类型）",
    parameters={},
    examples=["系统信息", "有 GPU 吗", "磁盘还剩多少"]
)
async def tool_get_system_info(**kwargs) -> Dict[str, Any]:
    """获取系统信息"""
    import shutil
    from src.shared.utils import ffmpeg_util

    try:
        gpu_info = "无 GPU"
        try:
            if ffmpeg_util.check_nvidia():
                gpu_info = "NVIDIA GPU 可用"
            else:
                gpu_info = "未检测到 NVIDIA GPU"
        except Exception:
            pass

        cuda = ffmpeg_util.check_cuda_support()

        # 磁盘空间
        upload_dir = config.UPLOAD_DIR
        if os.path.exists(upload_dir):
            usage = shutil.disk_usage(upload_dir)
            disk_info = f"总 {usage.total // (1024**3)}GB, 已用 {usage.used // (1024**3)}GB, 剩余 {usage.free // (1024**3)}GB"
        else:
            disk_info = "目录不存在"

        return {
            "success": True,
            "gpu": gpu_info,
            "cuda_support": cuda,
            "disk": disk_info,
            "platform": sys.platform,
            "message": f"GPU: {gpu_info} | CUDA: {'支持' if cuda else '不支持'} | 磁盘: {disk_info}"
        }

    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="open_folder",
    description="在文件管理器中打开指定目录",
    parameters={
        "path": {"type": "string", "description": "目录路径（默认输出目录）"},
    },
    examples=["打开输出目录", "打开素材文件夹"]
)
async def tool_open_folder(path: str = None, **kwargs) -> Dict[str, Any]:
    """打开文件夹"""
    from src.shared.utils.file_util import open_folder as _open_folder
    from src import config

    try:
        target = path or config.UPLOAD_DIR
        if not os.path.isdir(target):
            return {"success": False, "error": f"目录不存在: {target}"}

        _open_folder(target)
        return {"success": True, "message": f"已打开: {target}"}

    except Exception as e:
        logger.error(f"打开文件夹失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="delete_material",
    description="删除素材文件和数据库记录",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["删除这个素材", "清理视频"],
)
async def tool_delete_material(video_id: int, **kwargs) -> Dict[str, Any]:
    """删除素材工具"""
    from src.application.services.video_service import VideoService

    try:
        service = VideoService()
        service.delete_video(video_id)
        return {"success": True, "message": f"素材 {video_id} 已删除"}

    except Exception as e:
        logger.error(f"删除素材失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="detect_language",
    description="检测文本的语言类型",
    parameters={
        "text": {"type": "string", "description": "要检测的文本"},
    },
    examples=["这段话是什么语言", "检测语种"],
)
async def tool_detect_language(text: str, **kwargs) -> Dict[str, Any]:
    """语言检测工具"""
    from src.shared.utils.string_util import detect_prompt_language

    try:
        lang = detect_prompt_language(text)
        return {"success": True, "language": lang, "message": f"检测为: {lang}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="suggest_music",
    description="根据视频风格推荐背景音乐风格",
    parameters={
        "mood": {"type": "string", "description": "视频情绪/风格描述"},
        "duration": {"type": "number", "description": "视频时长（秒）"},
    },
    examples=["推荐背景音乐", "适合什么 BGM"],
)
async def tool_suggest_music(mood: str, duration: float = 30.0, **kwargs) -> Dict[str, Any]:
    """推荐音乐工具"""
    from src.application.services.clip_planner import ClipPlanner

    try:
        planner = ClipPlanner()
        suggestion = planner.suggest_music(mood, duration)

        return {
            "success": True,
            "suggestion": suggestion,
            "message": f"推荐音乐风格: {suggestion}"
        }

    except Exception as e:
        logger.error(f"推荐音乐失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="optimize_prompt",
    description="优化 AI 提示词（文生图/文生视频）",
    parameters={
        "prompt": {"type": "string", "description": "原始提示词"},
        "prompt_type": {"type": "integer", "description": "类型: 1=文生图, 2=图生图, 3=文生视频"},
    },
    examples=["优化一下提示词", "帮我把描述优化成 AI 绘画提示"],
)
async def tool_optimize_prompt(prompt: str, prompt_type: int = 1, **kwargs) -> Dict[str, Any]:
    """优化提示词工具"""
    from src.application.services.creative_service import CreativeService

    try:
        service = CreativeService()
        result = service.optimize_prompt(prompt, prompt_type)

        return {
            "success": True,
            "original": prompt,
            "optimized": result,
            "message": "提示词优化完成"
        }

    except Exception as e:
        logger.error(f"优化提示词失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="random_video",
    description="随机选择一个视频素材",
    parameters={
        "video_type": {"type": "string", "description": "视频类型（可选）"},
    },
    examples=["随机选一个素材", "挑个视频"],
)
async def tool_random_video(video_type: str = None, **kwargs) -> Dict[str, Any]:
    """随机视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_random_active(video_type=video_type)

            if not video:
                return {"success": False, "error": "没有可用的素材"}

            return {
                "success": True,
                "video": {
                    "id": video.id,
                    "name": video.video_name,
                    "duration": video.duration_hms,
                    "path": video.local_path,
                },
                "message": f"随机选中: {video.video_name}"
            }

    except Exception as e:
        logger.error(f"随机选素材失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 第三梯队：锦上添花工具 ====================

@registry.register(
    name="batch_compress",
    description="批量压缩目录下所有视频",
    parameters={
        "directory": {"type": "string", "description": "视频目录路径"},
        "quality": {"type": "string", "description": "质量: low/medium/high"},
    },
    examples=["批量压缩素材", "把目录里的视频都压缩一下"],
)
async def tool_batch_compress(directory: str, quality: str = "medium", **kwargs) -> Dict[str, Any]:
    """批量压缩工具"""
    from src.application.services import ffmpeg_adapter as ffmpeg

    quality_map = {"low": 28, "medium": 23, "high": 18}
    crf = quality_map.get(quality, 23)

    try:
        if not os.path.isdir(directory):
            return {"success": False, "error": f"目录不存在: {directory}"}

        result = ffmpeg.batch_compress_videos(input_dir=directory, crf=crf)

        return {"success": True, "message": f"批量压缩完成", "details": result}

    except Exception as e:
        logger.error(f"批量压缩失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="update_description",
    description="更新视频的描述/标签",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "description": {"type": "string", "description": "新描述内容"},
    },
    examples=["给视频加个描述", "更新素材备注"],
    before_execute=validate_video_exists
)
async def tool_update_description(video_id: int, description: str, **kwargs) -> Dict[str, Any]:
    """更新描述工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context(commit=True) as db:
            repo = VideoRepository(db)
            repo.update_description(video_id, description)

            return {"success": True, "message": f"描述已更新"}

    except Exception as e:
        logger.error(f"更新描述失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="srt_to_ass",
    description="将 SRT 字幕转换为 ASS 格式（支持设置字体样式）",
    parameters={
        "srt_path": {"type": "string", "description": "SRT 字幕文件路径"},
        "fontname": {"type": "string", "description": "字体名称"},
        "fontsize": {"type": "integer", "description": "字体大小"},
        "fontcolor": {"type": "string", "description": "字体颜色（如 &H00FFFFFF）"},
    },
    examples=["把字幕转成 ASS 格式", "转换字幕并设置字体"],
)
async def tool_srt_to_ass(
    srt_path: str,
    fontname: str = "Arial",
    fontsize: int = 24,
    fontcolor: str = "&H00FFFFFF",
    **kwargs
) -> Dict[str, Any]:
    """字幕格式转换工具"""
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.shared.utils import string_util

    try:
        if not os.path.exists(srt_path):
            return {"success": False, "error": f"文件不存在: {srt_path}"}

        ass_path = srt_path.rsplit(".", 1)[0] + ".ass"
        ffmpeg.str_to_ass(srt_path, ass_path)

        # 设置字体样式
        if fontname or fontsize or fontcolor:
            string_util.set_ass_font(ass_path, fontname, fontsize, fontcolor, "&H000000", 30)

        return {"success": True, "ass_path": ass_path, "message": "字幕格式转换完成"}

    except Exception as e:
        logger.error(f"字幕转换失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="time_convert",
    description="时间格式转换（秒 ↔ HH:MM:SS）",
    parameters={
        "value": {"type": "string", "description": "时间值（秒数或 HH:MM:SS）"},
        "direction": {"type": "string", "description": "转换方向: to_hms（秒→时分秒）/ to_seconds（时分秒→秒）"},
    },
    examples=["300秒是多少时间", "01:30:00 是多少秒"],
)
async def tool_time_convert(value: str, direction: str = "to_hms", **kwargs) -> Dict[str, Any]:
    """时间转换工具"""
    from src.shared.utils import time_util

    try:
        if direction == "to_hms":
            seconds = float(value)
            result = time_util.seconds_to_hms(seconds)
            return {"success": True, "result": result, "message": f"{seconds} 秒 = {result}"}
        else:
            result = time_util.parse_time(value)
            return {"success": True, "result": str(result), "message": f"{value} = {result} 秒"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="task_status",
    description="查询后台任务执行进度",
    parameters={
        "task_id": {"type": "string", "description": "任务 ID"},
    },
    examples=["查看任务进度", "任务执行到哪了"],
)
async def tool_task_status(task_id: str, **kwargs) -> Dict[str, Any]:
    """任务状态工具"""
    from src.shared.utils.task_manager import get_task

    try:
        task = get_task(task_id)
        if not task:
            return {"success": False, "error": f"任务 {task_id} 不存在"}

        return {
            "success": True,
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "message": f"任务状态: {task.get('status', 'unknown')}"
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 第四梯队：FFmpeg 视频滤镜工具 ====================

@registry.register(
    name="adjust_brightness",
    description="调整视频亮度、对比度、饱和度",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "brightness": {"type": "number", "description": "亮度 (-1.0~1.0，默认0)"},
        "contrast": {"type": "number", "description": "对比度 (0.1~10.0，默认1)"},
        "saturation": {"type": "number", "description": "饱和度 (0.0~3.0，默认1)"},
    },
    examples=["把视频调亮一点", "增加对比度", "提高饱和度"],
    before_execute=validate_video_exists
)
async def tool_adjust_brightness(
    video_id: int,
    brightness: float = 0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    **kwargs
) -> Dict[str, Any]:
    """调整亮度/对比度/饱和度"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    brightness = max(-1.0, min(1.0, float(brightness)))
    contrast = max(0.1, min(10.0, float(contrast)))
    saturation = max(0.0, min(3.0, float(saturation)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"adjusted_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"亮度={brightness} 对比度={contrast} 饱和度={saturation}"}

    except Exception as e:
        logger.error(f"调整亮度失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="blur_video",
    description="对视频应用模糊效果",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "sigma": {"type": "number", "description": "模糊强度 (0.1~20.0，默认5)"},
    },
    examples=["模糊视频", "加个模糊效果"],
    before_execute=validate_video_exists
)
async def tool_blur_video(video_id: int, sigma: float = 5.0, **kwargs) -> Dict[str, Any]:
    """模糊视频"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    sigma = max(0.1, min(20.0, float(sigma)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"blurred_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"gblur=sigma={sigma}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"模糊完成 (sigma={sigma})"}

    except Exception as e:
        logger.error(f"模糊视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="sharpen_video",
    description="对视频应用锐化效果",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "amount": {"type": "number", "description": "锐化强度 (0.0~3.0，默认1.5)"},
    },
    examples=["锐化视频", "让画面更清晰"],
    before_execute=validate_video_exists
)
async def tool_sharpen_video(video_id: int, amount: float = 1.5, **kwargs) -> Dict[str, Any]:
    """锐化视频"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    amount = max(0.0, min(3.0, float(amount)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"sharpened_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"unsharp=5:5:{amount}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"锐化完成 (强度={amount})"}

    except Exception as e:
        logger.error(f"锐化视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="rotate_video",
    description="旋转视频（90/180/270度）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "angle": {"type": "integer", "description": "旋转角度: 90/180/270"},
    },
    examples=["把视频旋转90度", "旋转180度"],
    before_execute=validate_video_exists
)
async def tool_rotate_video(video_id: int, angle: int = 90, **kwargs) -> Dict[str, Any]:
    """旋转视频"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    angle = int(angle)
    if angle == 90:
        vf = "transpose=1"
    elif angle == 180:
        vf = "hflip,vflip"
    elif angle == 270:
        vf = "transpose=2"
    else:
        return {"success": False, "error": "角度只支持 90/180/270"}

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"rotated_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"已旋转 {angle} 度"}

    except Exception as e:
        logger.error(f"旋转视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="flip_video",
    description="水平或垂直翻转视频",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "direction": {"type": "string", "description": "翻转方向: horizontal/vertical"},
    },
    examples=["水平翻转视频", "垂直翻转"],
    before_execute=validate_video_exists
)
async def tool_flip_video(video_id: int, direction: str = "horizontal", **kwargs) -> Dict[str, Any]:
    """翻转视频"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    vf = "hflip" if direction == "horizontal" else "vflip"

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"flipped_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            dir_desc = "水平" if direction == "horizontal" else "垂直"
            return {"success": True, "output_path": output_path, "message": f"已{dir_desc}翻转"}

    except Exception as e:
        logger.error(f"翻转视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="crop_video",
    description="裁剪视频画面区域",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "width": {"type": "integer", "description": "裁剪宽度"},
        "height": {"type": "integer", "description": "裁剪高度"},
        "x": {"type": "integer", "description": "起始X坐标（默认居中）"},
        "y": {"type": "integer", "description": "起始Y坐标（默认居中）"},
    },
    examples=["裁剪视频为640x480", "截取中间区域"],
    before_execute=validate_video_exists
)
async def tool_crop_video(
    video_id: int, width: int, height: int,
    x: int = None, y: int = None, **kwargs
) -> Dict[str, Any]:
    """裁剪视频"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            # 居中裁剪
            if x is None or y is None:
                info = ffmpeg.get_video_info(video.local_path)
                ow = info.get("width", 1920) if info else 1920
                oh = info.get("height", 1080) if info else 1080
                x = (ow - width) // 2 if x is None else x
                y = (oh - height) // 2 if y is None else y

            output_path = os.path.join(config.UPLOAD_DIR, f"cropped_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"crop={width}:{height}:{x}:{y}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"裁剪完成 {width}x{height}+{x}+{y}"}

    except Exception as e:
        logger.error(f"裁剪视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="fade_video",
    description="为视频添加淡入淡出效果",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "fade_in": {"type": "number", "description": "淡入时长（秒，默认2）"},
        "fade_out": {"type": "number", "description": "淡出时长（秒，默认2）"},
    },
    examples=["加个淡入淡出", "开头淡入3秒"],
    before_execute=validate_video_exists
)
async def tool_fade_video(
    video_id: int, fade_in: float = 2.0, fade_out: float = 2.0, **kwargs
) -> Dict[str, Any]:
    """淡入淡出"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            info = ffmpeg.get_video_info(video.local_path)
            duration = float(info.get("duration", 30)) if info else 30
            fade_out_start = max(0, duration - fade_out)

            vf = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start:.2f}:d={fade_out}"

            output_path = os.path.join(config.UPLOAD_DIR, f"faded_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"淡入{fade_in}秒 淡出{fade_out}秒"}

    except Exception as e:
        logger.error(f"淡入淡出失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="picture_in_picture",
    description="画中画效果，将一个视频叠加到另一个视频上",
    parameters={
        "video_id": {"type": "integer", "description": "主视频 ID"},
        "overlay_video_id": {"type": "integer", "description": "叠加视频 ID"},
        "x": {"type": "integer", "description": "叠加位置X（默认10）"},
        "y": {"type": "integer", "description": "叠加位置Y（默认10）"},
        "scale": {"type": "number", "description": "叠加视频缩放比例（默认0.25）"},
    },
    examples=["画中画效果", "把视频2叠加到视频1上"],
    before_execute=validate_video_exists
)
async def tool_picture_in_picture(
    video_id: int, overlay_video_id: int,
    x: int = 10, y: int = 10, scale: float = 0.25, **kwargs
) -> Dict[str, Any]:
    """画中画"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            main_video = repo.get_by_id(video_id)
            overlay_video = repo.get_by_id(overlay_video_id)
            if not main_video or not overlay_video:
                return {"success": False, "error": "视频不存在"}

            info = ffmpeg.get_video_info(main_video.local_path)
            ow = info.get("width", 1920) if info else 1920
            oh = info.get("height", 1080) if info else 1080
            sw = int(ow * scale)
            sh = int(oh * scale)

            output_path = os.path.join(config.UPLOAD_DIR, f"pip_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y',
                '-i', main_video.local_path,
                '-i', overlay_video.local_path,
                '-filter_complex', f"[1:v]scale={sw}:{sh}[pi];[0:v][pi]overlay={x}:{y}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"画中画完成 叠加大小{sw}x{sh}"}

    except Exception as e:
        logger.error(f"画中画失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_watermark",
    description="为视频添加图片水印",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "watermark_path": {"type": "string", "description": "水印图片路径"},
        "position": {"type": "string", "description": "位置: top-left/top-right/bottom-left/bottom-right（默认右下）"},
        "opacity": {"type": "number", "description": "透明度 (0.0~1.0，默认1.0)"},
    },
    examples=["添加水印", "加上logo"],
    before_execute=validate_video_exists
)
async def tool_add_watermark(
    video_id: int, watermark_path: str,
    position: str = "bottom-right", opacity: float = 1.0, **kwargs
) -> Dict[str, Any]:
    """添加水印"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    if not os.path.exists(watermark_path):
        return {"success": False, "error": f"水印文件不存在: {watermark_path}"}

    opacity = max(0.0, min(1.0, float(opacity)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            info = ffmpeg.get_video_info(video.local_path)
            w = info.get("width", 1920) if info else 1920
            h = info.get("height", 1080) if info else 1080

            pos_map = {
                "top-left": "10:10",
                "top-right": f"{w}-W-10:10",
                "bottom-left": f"10:{h}-H-10",
                "bottom-right": f"{w}-W-10:{h}-H-10"
            }
            pos = pos_map.get(position, pos_map["bottom-right"])

            filter_complex = f"[1:v]colorchannelmixer=aa={opacity}[wm];[0:v][wm]overlay={pos}"

            output_path = os.path.join(config.UPLOAD_DIR, f"watermarked_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y',
                '-i', video.local_path,
                '-i', watermark_path,
                '-filter_complex', filter_complex,
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"水印已添加 (位置: {position})"}

    except Exception as e:
        logger.error(f"添加水印失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_text_overlay",
    description="在视频上叠加文字",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "text": {"type": "string", "description": "文字内容"},
        "fontsize": {"type": "integer", "description": "字体大小（默认48）"},
        "fontcolor": {"type": "string", "description": "字体颜色（默认white）"},
        "x": {"type": "integer", "description": "X坐标（默认10）"},
        "y": {"type": "integer", "description": "Y坐标（默认10）"},
    },
    examples=["在视频上加文字", "添加标题"],
    before_execute=validate_video_exists
)
async def tool_add_text_overlay(
    video_id: int, text: str, fontsize: int = 48,
    fontcolor: str = "white", x: int = 10, y: int = 10, **kwargs
) -> Dict[str, Any]:
    """文字叠加"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    # 转义特殊字符防止命令注入
    safe_text = re.sub(r'[\'\"\\:;]', '', text)

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            drawtext = f"drawtext=text='{safe_text}':fontsize={fontsize}:fontcolor={fontcolor}:x={x}:y={y}"

            output_path = os.path.join(config.UPLOAD_DIR, f"text_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', drawtext,
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"文字已叠加: {text}"}

    except Exception as e:
        logger.error(f"文字叠加失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="reverse_video",
    description="视频倒放（画面和音频同时反转）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["倒放视频", "视频反过来播放"],
    before_execute=validate_video_exists
)
async def tool_reverse_video(video_id: int, **kwargs) -> Dict[str, Any]:
    """视频倒放"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"reversed_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-filter_complex', '[0:v]reverse[v];[0:a]areverse[a]',
                '-map', '[v]', '-map', '[a]', output_path
            ])

            return {"success": True, "output_path": output_path, "message": "倒放完成"}

    except Exception as e:
        logger.error(f"视频倒放失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="stabilize_video",
    description="视频防抖，稳定画面",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "smoothing": {"type": "integer", "description": "平滑强度（默认10）"},
    },
    examples=["防抖处理", "稳定画面"],
    before_execute=validate_video_exists
)
async def tool_stabilize_video(video_id: int, smoothing: int = 10, **kwargs) -> Dict[str, Any]:
    """视频防抖"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config
    import tempfile

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"stable_{video_id}_{int(time.time())}.mp4")

            # 第一步：检测抖动
            with tempfile.NamedTemporaryFile(suffix='.trf', delete=False) as tmp:
                trf_path = tmp.name

            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f'vidstabdetect=stepsize=6:shakiness=5:result={trf_path}',
                '-f', 'null', '-'
            ])

            # 第二步：应用稳定
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"vidstabtransform=input={trf_path}:smoothing={smoothing}",
                '-c:a', 'copy', output_path
            ])

            try:
                os.unlink(trf_path)
            except OSError:
                pass

            return {"success": True, "output_path": output_path, "message": "防抖处理完成"}

    except Exception as e:
        logger.error(f"视频防抖失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 第五梯队：高级视频工具 ====================

@registry.register(
    name="scene_detect",
    description="检测视频中的场景切换点",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "threshold": {"type": "number", "description": "场景变化阈值 (0.0~1.0，默认0.4)"},
    },
    examples=["检测场景切换", "找出视频中的转场点"],
    before_execute=validate_video_exists
)
async def tool_scene_detect(video_id: int, threshold: float = 0.4, **kwargs) -> Dict[str, Any]:
    """场景检测"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    threshold = max(0.01, min(1.0, float(threshold)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            result = ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-i', video.local_path,
                '-filter:v', f"select='gt(scene,{threshold})',showinfo",
                '-f', 'null', '-'
            ])

            scenes = []
            if result and result.stderr:
                for line in result.stderr.split('\n'):
                    if 'pts_time' in line:
                        match = re.search(r'pts_time:(\d+\.?\d*)', line)
                        if match:
                            scenes.append(float(match.group(1)))

            return {
                "success": True,
                "scenes": scenes,
                "count": len(scenes),
                "message": f"检测到 {len(scenes)} 个场景切换点"
            }

    except Exception as e:
        logger.error(f"场景检测失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="slow_motion",
    description="慢动作效果（插帧+降速）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "factor": {"type": "number", "description": "慢放倍数 (2~8，默认4)"},
    },
    examples=["慢动作效果", "超级慢放"],
    before_execute=validate_video_exists
)
async def tool_slow_motion(video_id: int, factor: float = 4.0, **kwargs) -> Dict[str, Any]:
    """慢动作"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    factor = max(2.0, min(8.0, float(factor)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"slowmo_{video_id}_{int(time.time())}.mp4")

            fps = min(60, int(30 * factor))

            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-filter_complex',
                f"[0:v]minterpolate='mi_mode=mci:mc_mode=aobmc:vsbmc=1:fps={fps}',setpts={factor}*PTS[v];"
                f"[0:a]atempo={1.0/factor}[a]",
                '-map', '[v]', '-map', '[a]', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"{factor}倍慢动作完成"}

    except Exception as e:
        logger.error(f"慢动作失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="color_adjust",
    description="高级色彩调整（色相/颜色通道混合）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "brightness": {"type": "number", "description": "亮度调整 (-1.0~1.0)"},
        "contrast": {"type": "number", "description": "对比度 (0.1~3.0)"},
        "saturation": {"type": "number", "description": "饱和度 (0.0~3.0)"},
        "gamma": {"type": "number", "description": "伽马值 (0.1~3.0)"},
    },
    examples=["调色", "调整色彩风格"],
    before_execute=validate_video_exists
)
async def tool_color_adjust(
    video_id: int, brightness: float = 0, contrast: float = 1.0,
    saturation: float = 1.0, gamma: float = 1.0, **kwargs
) -> Dict[str, Any]:
    """色彩调整"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    brightness = max(-1.0, min(1.0, float(brightness)))
    contrast = max(0.1, min(3.0, float(contrast)))
    saturation = max(0.0, min(3.0, float(saturation)))
    gamma = max(0.1, min(3.0, float(gamma)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"color_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-vf', f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma}",
                '-c:a', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": "色彩调整完成"}

    except Exception as e:
        logger.error(f"色彩调整失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="convert_format",
    description="视频格式转换（MP4/MKV/AVI/MOV/WEBM 等）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "target_format": {"type": "string", "description": "目标格式: mp4/mkv/avi/mov/webm"},
    },
    examples=["转成MKV格式", "把视频转为WEBM"],
    before_execute=validate_video_exists
)
async def tool_convert_format(video_id: int, target_format: str = "mp4", **kwargs) -> Dict[str, Any]:
    """格式转换"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    allowed = {"mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "ts"}
    target_format = target_format.lower().lstrip('.')
    if target_format not in allowed:
        return {"success": False, "error": f"不支持的格式: {target_format}"}

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(
                config.UPLOAD_DIR,
                f"converted_{video_id}_{int(time.time())}.{target_format}"
            )

            # 尝试流复制（无重编码），失败则重编码
            try:
                ffmpeg.run_ffmpeg_cmd([
                    'ffmpeg', '-y', '-i', video.local_path,
                    '-c', 'copy', output_path
                ])
            except Exception:
                ffmpeg.run_ffmpeg_cmd([
                    'ffmpeg', '-y', '-i', video.local_path,
                    '-c:v', 'libx264', '-c:a', 'aac', output_path
                ])

            return {"success": True, "output_path": output_path, "message": f"已转为 {target_format} 格式"}

    except Exception as e:
        logger.error(f"格式转换失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 第六梯队：音频滤镜工具 ====================

@registry.register(
    name="normalize_audio",
    description="音频标准化（统一音量到目标响度）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "target_loudness": {"type": "number", "description": "目标响度 LUFS（默认-16）"},
    },
    examples=["标准化音频", "统一音量"],
    before_execute=validate_video_exists
)
async def tool_normalize_audio(video_id: int, target_loudness: float = -16.0, **kwargs) -> Dict[str, Any]:
    """音频标准化"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"normalized_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11",
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"音频标准化完成 (目标 {target_loudness} LUFS)"}

    except Exception as e:
        logger.error(f"音频标准化失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="equalize_audio",
    description="音频均衡器调节",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "frequency": {"type": "number", "description": "频率 Hz（默认1000）"},
        "gain": {"type": "number", "description": "增益 dB（默认2）"},
        "width": {"type": "number", "description": "带宽（默认1）"},
    },
    examples=["调节均衡器", "增强低频"],
    before_execute=validate_video_exists
)
async def tool_equalize_audio(
    video_id: int, frequency: float = 1000, gain: float = 2.0, width: float = 1.0, **kwargs
) -> Dict[str, Any]:
    """均衡器"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"eq_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', f"equalizer=f={frequency}:t=q:w={width}:g={gain}",
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"均衡器调节 {frequency}Hz +{gain}dB"}

    except Exception as e:
        logger.error(f"均衡器调节失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="fade_audio",
    description="音频淡入淡出",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "fade_in": {"type": "number", "description": "淡入时长（秒，默认3）"},
        "fade_out": {"type": "number", "description": "淡出时长（秒，默认3）"},
    },
    examples=["音频淡入淡出", "声音渐渐变大"],
    before_execute=validate_video_exists
)
async def tool_fade_audio(
    video_id: int, fade_in: float = 3.0, fade_out: float = 3.0, **kwargs
) -> Dict[str, Any]:
    """音频淡入淡出"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            info = ffmpeg.get_video_info(video.local_path)
            duration = float(info.get("duration", 30)) if info else 30
            fade_out_start = max(0, duration - fade_out)

            af = f"afade=t=in:ss=0:d={fade_in},afade=t=out:st={fade_out_start:.2f}:d={fade_out}"

            output_path = os.path.join(config.UPLOAD_DIR, f"afaded_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', af,
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"音频淡入{fade_in}秒 淡出{fade_out}秒"}

    except Exception as e:
        logger.error(f"音频淡入淡出失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_echo",
    description="为音频添加回声/混响效果",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "delay": {"type": "integer", "description": "回声延迟毫秒（默认60）"},
        "decay": {"type": "number", "description": "衰减系数 (0.0~1.0，默认0.4)"},
    },
    examples=["加回声效果", "加混响"],
    before_execute=validate_video_exists
)
async def tool_add_echo(
    video_id: int, delay: int = 60, decay: float = 0.4, **kwargs
) -> Dict[str, Any]:
    """回声效果"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    decay = max(0.0, min(1.0, float(decay)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"echo_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', f"aecho=0.8:0.88:{delay}:{decay}",
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"回声效果已添加 (延迟{delay}ms)"}

    except Exception as e:
        logger.error(f"回声效果失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="denoise_audio",
    description="音频降噪",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "noise_level": {"type": "number", "description": "降噪强度 (-80~-20 dB，默认-25)"},
    },
    examples=["降噪", "去掉背景噪音"],
    before_execute=validate_video_exists
)
async def tool_denoise_audio(video_id: int, noise_level: float = -25.0, **kwargs) -> Dict[str, Any]:
    """音频降噪"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    noise_level = max(-80.0, min(-20.0, float(noise_level)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"denoised_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', f"afftdn=nf={noise_level}",
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": f"降噪完成 (强度 {noise_level} dB)"}

    except Exception as e:
        logger.error(f"音频降噪失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="pitch_shift",
    description="音频变调（改变音高而不改变速度）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "semitones": {"type": "integer", "description": "半音变化 (负=降低, 正=升高, 范围 -12~12)"},
    },
    examples=["变调", "声音变低沉"],
    before_execute=validate_video_exists
)
async def tool_pitch_shift(video_id: int, semitones: int = 0, **kwargs) -> Dict[str, Any]:
    """变调"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    semitones = max(-12, min(12, int(semitones)))
    # 半音 → 频率比率: 2^(semitones/12)
    import math
    ratio = 2 ** (semitones / 12.0)

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"pitch_{video_id}_{int(time.time())}.mp4")
            # asetrate 改变采样率实现变调，aresample 恢复原始采样率
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', f"asetrate=44100*{ratio},aresample=44100,atempo={1.0/ratio}",
                '-c:v', 'copy', output_path
            ])

            dir_desc = "升高" if semitones > 0 else "降低"
            return {"success": True, "output_path": output_path, "message": f"音调{dir_desc}{abs(semitones)}个半音"}

    except Exception as e:
        logger.error(f"变调失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="reverse_audio",
    description="音频倒放（仅反转音频，画面不变）",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
    },
    examples=["音频倒放", "声音反过来"],
    before_execute=validate_video_exists
)
async def tool_reverse_audio(video_id: int, **kwargs) -> Dict[str, Any]:
    """音频倒放"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = os.path.join(config.UPLOAD_DIR, f"areversed_{video_id}_{int(time.time())}.mp4")
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video.local_path,
                '-af', 'areverse',
                '-c:v', 'copy', output_path
            ])

            return {"success": True, "output_path": output_path, "message": "音频倒放完成"}

    except Exception as e:
        logger.error(f"音频倒放失败: {e}")
        return {"success": False, "error": str(e)}

"""
工具注册表模块

管理所有可调用的剪辑工具
"""
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import asyncio
from pydantic import BaseModel, Field
from typing import Optional as Opt

logger = logging.getLogger(__name__)


# ==================== Pydantic 参数模型 ====================

class CutVideoParams(BaseModel):
    """剪切视频参数"""
    video_id: int = Field(..., description="视频 ID")
    start_time: str = Field(default="00:00:00", description="开始时间 (HH:MM:SS)")
    end_time: Opt[str] = Field(default=None, description="结束时间 (HH:MM:SS)")


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


# 参数模型映射
PARAM_MODELS = {
    "cut_video": CutVideoParams,
    "merge_videos": MergeVideosParams,
    "add_subtitle": AddSubtitleParams,
    "change_speed": ChangeSpeedParams,
    "smart_clip": SmartClipParams,
    "analyze_video": AnalyzeVideoParams,
    "generate_tts": GenerateTtsParams,
    "search_material": SearchMaterialParams,
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

    def __post_init__(self):
        if self.examples is None:
            self.examples = []

    def validate_params(self, params: Dict) -> Dict:
        """校验并规范化参数"""
        if self.param_model is None:
            return params
        try:
            model = self.param_model(**params)
            return model.model_dump()
        except Exception as e:
            logger.warning(f"工具 {self.name} 参数校验失败: {e}")
            return params  # 校验失败时返回原始参数，不阻断执行


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
        param_model: Optional[type] = None
    ) -> Callable:
        """
        注册工具装饰器

        Args:
            name: 工具名称
            description: 工具描述
            parameters: 参数定义
            examples: 使用示例
            param_model: Pydantic 参数校验模型

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
                param_model=param_model
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
    param_model=CutVideoParams
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

            return {
                "success": True,
                "output_path": output_path,
                "message": f"剪切完成: {start_time} - {end_time or '结尾'}"
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
    param_model=MergeVideosParams
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
    param_model=AddSubtitleParams
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
    param_model=ChangeSpeedParams
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
    param_model=AnalyzeVideoParams
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
    """列出视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            videos = repo.get_all(limit=20)

            video_list = [
                {
                    "id": v.id,
                    "name": v.video_name,
                    "duration": v.duration_hms,
                    "description": v.description or "无描述"
                }
                for v in videos
            ]

            return {
                "success": True,
                "videos": video_list,
                "count": len(video_list),
                "message": f"共 {len(video_list)} 个素材"
            }

    except Exception as e:
        logger.error(f"获取素材列表失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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

"""
工具注册表模块

管理所有可调用的剪辑工具
"""
import logging
import os
import re
import sys
import json
import shutil
from src import config
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import asyncio
from pydantic import BaseModel, Field, field_validator
from typing import Optional as Opt

logger = logging.getLogger(__name__)


def _add_material_to_project(project_id: int, video_id: int):
    """将素材关联到项目的 material_ids 列表"""
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.video_project import VideoProject
    with get_db_context() as db:
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if project:
            ids = project.material_ids or []
            if video_id not in ids:
                ids.append(video_id)
                project.material_ids = ids
                db.commit()


def _save_temp_file(src_path: str, project_id: int, file_type: str, source: str,
                    session_id: str = None, file_name: str = None, duration: float = None) -> Dict[str, Any]:
    """将工具产出的文件移到项目临时目录，创建 ProjectTempFile 记录。

    返回兼容旧 is_temp_asset 格式的 dict（temp_file_id 替代 video_id）。
    """
    import shutil
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories.temp_file_repository import TempFileRepository

    if not project_id:
        # 无 project_id 时回退到素材库
        return None

    temp_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "temp", str(project_id))
    os.makedirs(temp_dir, exist_ok=True)

    filename = file_name or f"{source}_{int(time.time())}_{os.path.basename(src_path)}"
    dest_path = os.path.join(temp_dir, filename)
    shutil.move(src_path, dest_path)

    # 视频入库时统一编码标准化
    if file_type == "video":
        from src.application.services import ffmpeg_adapter as _ffmpeg
        _ffmpeg.standardize_video(dest_path)

    file_size = os.path.getsize(dest_path) if os.path.isfile(dest_path) else 0
    web_path = f"/static/temp/{project_id}/{filename}"

    with get_db_context() as db:
        repo = TempFileRepository(db)
        record = repo.create(
            project_id=project_id,
            session_id=session_id,
            file_name=filename,
            file_path=dest_path,
            web_path=web_path,
            file_type=file_type,
            source=source,
            file_size=file_size,
        )
        # 同时创建 VideoSource（is_temp=True），供工具通过 video_id 引用
        from src.infrastructure.repositories import VideoRepository
        video_repo = VideoRepository(db)
        vs = video_repo.create(
            video_name=filename,
            local_path=dest_path,
            web_path=web_path,
            is_temp=True,
            file_type=file_type,
        )
        db.commit()
        temp_file_id = record.id
        video_id = vs.id

    result = {
        "success": True,
        "temp_file_id": temp_file_id,
        "video_id": video_id,
        "web_path": web_path,
        "local_path": dest_path,
        "output_type": file_type,
        "is_temp_asset": True,
    }
    if duration is not None:
        result["duration"] = duration
    return result


def _make_temp_output(suffix: str, video_id: int) -> str:
    """创建临时文件路径供 FFmpeg 输出，避免写入素材库目录。"""
    import tempfile
    tmp_dir = tempfile.gettempdir()
    return os.path.join(tmp_dir, f"synthetix_{video_id}_{int(time.time())}_{os.getpid()}{suffix}")


_font_cache = None

def _prepare_font_for_file(file_path: str) -> str:
    """返回供 FFmpeg drawtext 使用的字体路径。

    优先使用 static/fonts/ 下的集中字体，计算相对路径给 FFmpeg
    （避免 Windows 绝对路径含盘符冒号导致 drawtext 解析失败）。
    回退到系统字体目录。
    """
    global _font_cache

    if not _font_cache:
        # 优先使用项目 static/fonts/ 集中存放的字体
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_font = os.path.join(_project_root, 'static', 'fonts', 'simhei.ttf')
        if os.path.exists(project_font):
            _font_cache = project_font
        else:
            import platform
            candidates = []
            if platform.system() == 'Windows':
                fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
                candidates = [
                    os.path.join(fonts_dir, 'simhei.ttf'),
                    os.path.join(fonts_dir, 'simkai.ttf'),
                ]
            elif platform.system() == 'Darwin':
                candidates = [
                    '/System/Library/Fonts/PingFang.ttc',
                    '/Library/Fonts/Arial Unicode.ttf',
                ]
            else:
                candidates = [
                    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
                ]
            for path in candidates:
                if os.path.exists(path):
                    _font_cache = path
                    break

    if not _font_cache:
        return ''

    # 使用相对路径（从输入文件目录到字体文件），避免 Windows 盘符冒号问题
    try:
        input_dir = os.path.dirname(os.path.abspath(file_path))
        rel = os.path.relpath(_font_cache, input_dir).replace('\\', '/')
    except Exception:
        return os.path.basename(_font_cache)
    return rel


def _save_tool_output(output_path: str, video_id: int, source: str,
                      project_id, file_type: str = "video",
                      file_name: str = None, message: str = None) -> Dict[str, Any]:
    """工具产出保存：优先存入项目临时目录（聊天框展示），无 project_id 时原样返回。"""
    if project_id:
        result = _save_temp_file(output_path, project_id, file_type, source,
                                 file_name=file_name)
        if result:
            if message:
                result["message"] = message
            return result
    if message:
        return {"success": True, "output_path": output_path, "message": message}
    return {"success": True, "output_path": output_path}


# ==================== Pydantic 参数模型 ====================

class CutVideoParams(BaseModel):
    """剪切视频参数"""
    video_id: int = Field(..., description="视频 ID")
    start_time: str = Field(default="00:00:00", description="开始时间 (HH:MM:SS 或秒数)")
    end_time: Opt[str] = Field(default=None, description="结束时间 (HH:MM:SS 或秒数)")
    margin_before: float = Field(default=0.3, ge=0, le=5.0, description="开始前缓冲（秒）")
    margin_after: float = Field(default=0.3, ge=0, le=5.0, description="结束后缓冲（秒）")
    smart_margin: bool = Field(default=False, description="启用智能缓冲（基于语音停顿）")

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def validate_time_format(cls, v):
        if v is None:
            return v
        if isinstance(v, (int, float)):
            total = int(v)
            h, remainder = divmod(abs(total), 3600)
            m, s = divmod(remainder, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        v = str(v)
        if v.isdigit():
            total = int(v)
            h, remainder = divmod(abs(total), 3600)
            m, s = divmod(remainder, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        if not re.match(r'^\d{2}:\d{2}:\d{2}(\.\d+)?$', v):
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
    project_id: Opt[int] = Field(default=None, description="项目 ID")
    fontname: str = Field(default="楷体", description="字体名称，如: 楷体, Microsoft YaHei, SimHei, SimSun, FangSong")
    fontsize: int = Field(default=24, ge=8, le=72, description="字体大小")
    fontcolor: str = Field(default="&Hffffff", description="字体颜色(ASS格式&HBBGGRR)")
    fontbordercolor: str = Field(default="&H000000", description="描边颜色(ASS格式)")
    bold: bool = Field(default=False, description="粗体")
    outline_width: float = Field(default=2, ge=0, le=6, description="描边宽度")
    shadow: float = Field(default=0, ge=0, le=4, description="阴影深度")
    alignment: int = Field(default=2, description="位置: 2=底部居中 5=上方居中 8=居中")
    bg_color: str = Field(default=None, description="背景颜色(ASS格式&HBBGGRR)，空则无背景")


class ChangeSpeedParams(BaseModel):
    """调整速度参数"""
    video_id: int = Field(..., description="视频 ID")
    speed_factor: float = Field(..., gt=0, le=10, description="速度倍数")


class SmartClipParams(BaseModel):
    """智能剪辑参数"""
    description: str = Field(..., description="剪辑需求描述")
    duration: float = Field(default=30.0, description="目标时长（秒）")
    style: str = Field(default="动感", description="风格偏好")
    margin_before: float = Field(default=0.3, ge=0, le=5.0, description="片段开始前缓冲（秒）")
    margin_after: float = Field(default=0.3, ge=0, le=5.0, description="片段结束后缓冲（秒）")
    smart_margin: bool = Field(default=False, description="启用智能缓冲")
    text_first: bool = Field(default=True, description="启用文本优先模式（先 ASR 再 LLM 分析）")


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
    video_id: Opt[int] = Field(default=None, description="视频 ID")
    file_path: Opt[str] = Field(default=None, description="直接传入文件路径（与 video_id 二选一）")
    language: Opt[str] = Field(default=None, description="语言（可选，默认自动检测）")


class AnalyzeVideoVlParams(BaseModel):
    """AI 视频理解参数"""
    video_id: Opt[int] = Field(default=None, description="视频 ID")
    file_path: Opt[str] = Field(default=None, description="直接传入文件路径（与 video_id 二选一）")
    prompt: Opt[str] = Field(default="请详细描述这个视频的内容、场景和风格", description="分析提示")


class GenerateMusicParams(BaseModel):
    """音乐生成参数"""
    prompt: str = Field(..., description="音乐描述")
    duration: float = Field(default=10.0, ge=1, le=240, description="时长（秒）")
    style: Opt[str] = Field(default=None, description="风格: pop/classical/electronic/jazz/rock/ambient")
    lyrics: Opt[str] = Field(default=None, description="歌词（支持 [verse]/[chorus] 结构标签，不传则纯音乐）")


class RetakeMusicParams(BaseModel):
    """音乐变奏参数"""
    prompt: str = Field(..., description="音乐描述")
    duration: float = Field(default=10.0, ge=1, le=240, description="时长（秒）")
    style: Opt[str] = Field(default=None, description="风格")
    lyrics: Opt[str] = Field(default=None, description="歌词")
    variance: float = Field(default=0.5, ge=0, le=1, description="变化程度 0-1，越大差异越大")


class RepaintMusicParams(BaseModel):
    """音乐局部重绘参数"""
    bgm_id: int = Field(..., description="BGM ID（从曲库中选择需要重绘的音乐）")
    prompt: str = Field(..., description="重绘部分的音乐描述")
    start_time: float = Field(..., ge=0, description="重绘起始时间（秒）")
    end_time: float = Field(..., ge=0, description="重绘结束时间（秒）")
    duration: Opt[float] = Field(default=None, ge=1, le=240, description="输出总时长（秒）")


class EditMusicLyricsParams(BaseModel):
    """音乐歌词编辑参数"""
    bgm_id: int = Field(..., description="BGM ID")
    lyrics: str = Field(..., description="新歌词（支持 [verse]/[chorus] 结构标签）")
    prompt: Opt[str] = Field(default=None, description="编辑指导")


class ExtendMusicParams(BaseModel):
    """音乐扩展参数"""
    bgm_id: int = Field(..., description="BGM ID")
    prompt: Opt[str] = Field(default=None, description="音乐描述")
    extend_left: float = Field(default=0, ge=0, le=60, description="向前延长秒数")
    extend_right: float = Field(default=10, ge=0, le=60, description="向后延长秒数")


class CoverMusicParams(BaseModel):
    """音乐翻唱参数"""
    bgm_id: int = Field(..., description="要翻唱的 BGM ID")
    prompt: Opt[str] = Field(default=None, description="翻唱风格描述")
    lyrics: Opt[str] = Field(default=None, description="歌词")


class StyleTransferMusicParams(BaseModel):
    """音乐风格迁移参数"""
    bgm_id: int = Field(..., description="BGM ID")
    prompt: str = Field(..., description="目标风格描述")
    edit_strength: float = Field(default=0.5, ge=0, le=1, description="风格修改强度 0-1")


class AddAudioParams(BaseModel):
    """添加音频参数"""
    video_id: int = Field(..., description="视频 ID")
    audio_path: str = Field(..., description="音频文件路径")
    audio_type: str = Field(default="bgm", description="类型: dubbing(配音)/bgm(背景音乐)")
    project_id: Opt[int] = Field(default=None, description="项目 ID")


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


# --- 本机文件操作参数模型 ---

class RenameItem(BaseModel):
    old_path: str = Field(..., description="原文件完整路径")
    new_path: str = Field(..., description="新文件完整路径")


class MoveItem(BaseModel):
    src: str = Field(..., description="源文件完整路径")
    dst: str = Field(..., description="目标文件完整路径")


class CopyItem(BaseModel):
    src: str = Field(..., description="源文件完整路径")
    dst: str = Field(..., description="目标文件完整路径")


class RenameFilesParams(BaseModel):
    renames: List[RenameItem] = Field(..., description="重命名列表")

    @field_validator("renames")
    @classmethod
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError("单次最多重命名 50 个文件")
        return v


class DeleteFilesParams(BaseModel):
    file_paths: List[str] = Field(..., description="要删除的文件完整路径列表")

    @field_validator("file_paths")
    @classmethod
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError("单次最多删除 50 个文件")
        return v


class MoveFilesParams(BaseModel):
    moves: List[MoveItem] = Field(..., description="移动列表")

    @field_validator("moves")
    @classmethod
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError("单次最多移动 50 个文件")
        return v


class CopyFilesParams(BaseModel):
    copies: List[CopyItem] = Field(..., description="复制列表")

    @field_validator("copies")
    @classmethod
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError("单次最多复制 50 个文件")
        return v


class GenerateImageParams(BaseModel):
    prompt: str = Field(..., description="图片描述")
    negative_prompt: Optional[str] = Field(default=None, description="反向提示词（排除元素）")
    width: int = Field(default=1024, ge=256, le=2048, description="图片宽度")
    height: int = Field(default=1024, ge=256, le=2048, description="图片高度")


class EditImageParams(BaseModel):
    prompt: str = Field(..., description="编辑指令")
    video_id: int = Field(..., description="原始图片素材 ID")
    mask_video_id: Optional[int] = Field(default=None, description="蒙版图片素材 ID（可选，用于局部编辑）")


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
    "retake_music": RetakeMusicParams,
    "repaint_music": RepaintMusicParams,
    "edit_music_lyrics": EditMusicLyricsParams,
    "extend_music": ExtendMusicParams,
    "cover_music": CoverMusicParams,
    "style_transfer_music": StyleTransferMusicParams,
    "search_material": SearchMaterialParams,
    "transcribe_video": TranscribeVideoParams,
    "add_audio": AddAudioParams,
    "download_video": DownloadVideoParams,
    "search_files": SearchFilesParams,
    "compress_video": CompressVideoParams,
    "extract_frames": ExtractFramesParams,
    "convert_to_gif": ConvertToGifParams,
    "separate_vocal": SeparateVocalParams,
    "rename_files": RenameFilesParams,
    "delete_files": DeleteFilesParams,
    "move_files": MoveFilesParams,
    "copy_files": CopyFilesParams,
    "generate_image": GenerateImageParams,
    "edit_image": EditImageParams,
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
    permission: str = "modify"  # read_only / modify / destructive
    category: str = "video"     # "common" | "video" | "comic"

    def __post_init__(self):
        if self.examples is None:
            self.examples = []

    def validate_params(self, params: Dict) -> Dict:
        """校验并规范化参数，保留 Pydantic 模型未声明的额外字段（如 project_id）"""
        if self.param_model is None:
            return params
        model = self.param_model(**params)
        validated = model.model_dump()
        # 保留 Pydantic 未处理的额外字段（如 react_agent 注入的 project_id）
        for k, v in params.items():
            if k not in validated:
                validated[k] = v
        return validated


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Tool] = {}
        self._pre_interceptors: List[Callable] = []
        self._post_interceptors: List[Callable] = []

    def add_pre_interceptor(self, fn: Callable):
        """添加全局前置拦截器。fn(params, tool_name) -> params"""
        self._pre_interceptors.append(fn)

    def add_post_interceptor(self, fn: Callable):
        """添加全局后置拦截器。fn(result, tool_name) -> result"""
        self._post_interceptors.append(fn)

    def run_pre_interceptors(self, params: Dict, tool_name: str) -> Dict:
        for fn in self._pre_interceptors:
            try:
                result = fn(params, tool_name)
                if result is not None:
                    params = result
            except Exception as e:
                logger.warning(f"前置拦截器 {fn.__name__} 异常: {e}")
        return params

    def run_post_interceptors(self, result: Dict, tool_name: str) -> Dict:
        for fn in self._post_interceptors:
            try:
                r = fn(result, tool_name)
                if r is not None:
                    result = r
            except Exception as e:
                logger.warning(f"后置拦截器 {fn.__name__} 异常: {e}")
        return result

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        examples: List[str] = None,
        param_model: Optional[type] = None,
        before_execute: Optional[Callable] = None,
        after_execute: Optional[Callable] = None,
        permission: str = "modify",
        category: str = "video"
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
                after_execute=after_execute,
                permission=permission,
                category=category
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

    def get_tools_description_by_category(self, mode: str = "video") -> str:
        """按模式过滤工具描述：common 工具 + 当前模式的工具"""
        descriptions = []
        for tool in self._tools.values():
            if tool.category == "common" or tool.category == mode:
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
    description="剪切视频片段，指定开始和结束时间。支持缓冲区(margin)避免截断句子",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "start_time": {"type": "string", "description": "开始时间 (HH:MM:SS)"},
        "end_time": {"type": "string", "description": "结束时间 (HH:MM:SS)"},
        "margin_before": {"type": "number", "description": "开始前缓冲（秒，默认0.3）"},
        "margin_after": {"type": "number", "description": "结束后缓冲（秒，默认0.3）"},
        "smart_margin": {"type": "boolean", "description": "启用智能缓冲（基于语音停顿）"},
    },
    examples=["帮我把视频前30秒剪出来", "从第10秒到第30秒剪切"],
    param_model=CutVideoParams,
    before_execute=validate_video_exists
)
async def tool_cut_video(
    video_id: int,
    start_time: str = "00:00:00",
    end_time: str = None,
    margin_before: float = 0.3,
    margin_after: float = 0.3,
    smart_margin: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """剪切视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.application.services.whisper_adapter import get_speech_pauses, find_nearest_pause
    from src.shared.utils import time_util
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

            actual_margin_before = margin_before
            actual_margin_after = margin_after

            # 智能缓冲：基于 ASR 停顿点调整剪切位置
            if smart_margin:
                try:
                    pauses = get_speech_pauses(video.local_path)
                    if pauses:
                        start_sec = time_util.parse_time(start_time)
                        adjusted_start = find_nearest_pause(pauses, start_sec, "before")
                        if adjusted_start is not None:
                            actual_margin_before = start_sec - adjusted_start

                        if end_time:
                            end_sec = time_util.parse_time(end_time)
                            adjusted_end = find_nearest_pause(pauses, end_sec, "after")
                            if adjusted_end is not None:
                                actual_margin_after = adjusted_end - end_sec
                except Exception as e:
                    logger.warning(f"智能缓冲计算失败，使用固定缓冲: {e}")

            # 执行剪切
            output_path = str(ffmpeg.cut_video(
                input_path=video.local_path,
                start_time=start_time,
                end_time=end_time,
                margin_before=actual_margin_before,
                margin_after=actual_margin_after,
            ))

            # 获取剪切后视频的时长
            cut_info = ffmpeg.get_video_info(output_path) or {}
            cut_duration = float(cut_info.get("duration", 0)) or None

            project_id = kwargs.get("project_id")

            # 优先保存到项目临时目录
            if project_id:
                cut_filename = f"cut_{video_id}_{start_time.replace(':','')}{('_' + end_time.replace(':','')) if end_time else ''}{os.path.splitext(video.video_name or '.mp4')[1] or '.mp4'}"
                result = _save_temp_file(output_path, project_id, "video", "cut",
                                        file_name=cut_filename, duration=cut_duration)
                if result:
                    result["message"] = f"剪切完成: {start_time} - {end_time or '结尾'}"
                    return result

            # 回退：保存到素材库
            import shutil
            cut_filename = os.path.basename(str(output_path))
            dest_dir = config.source_videos_dir
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, cut_filename)
            shutil.move(output_path, dest_path)

            new_video = repo.create(
                video_name=f"{video.video_name or 'video'}_cut_{start_time.replace(':','')}{('_' + end_time.replace(':','')) if end_time else ''}{os.path.splitext(video.video_name or '.mp4')[1] or '.mp4'}",
                local_path=dest_path,
                web_path=f"/static/source_videos/{cut_filename}",
                duration=str(cut_duration) if cut_duration else None,
                is_temp=True,
                file_type="video",
            )

            if project_id:
                _add_material_to_project(project_id, new_video.id)

            return {
                "success": True,
                "video_id": new_video.id,
                "output_path": dest_path,
                "web_path": f"/static/source_videos/{cut_filename}",
                "output_type": "video",
                "duration": cut_duration,
                "is_temp_asset": True,
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
            output_path = _make_temp_output("_merged.mp4", video_ids[0])
            if transition == "dissolve":
                clip_infos = [{"path": p} for p in video_paths]
                ffmpeg.concatenate_videos_with_transitions(clip_infos, output_path)
            else:
                ffmpeg.concatenate_videos_with_filter(video_paths, output_path)

            project_id = kwargs.get("project_id")

            # 优先保存到项目临时目录
            if project_id:
                merge_filename = f"merge_{len(video_paths)}_{int(time.time())}.mp4"
                result = _save_temp_file(output_path, project_id, "video", "merge", file_name=merge_filename)
                if result:
                    result["message"] = f"成功合并 {len(video_paths)} 个视频（转场: {transition}）"
                    return result

            # 回退：保存到素材库
            import shutil
            output_filename = os.path.basename(str(output_path))
            dest_dir = config.source_videos_dir
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, output_filename)
            shutil.move(output_path, dest_path)

            new_video = repo.create(
                video_name=f"合并视频_{len(video_paths)}段.mp4",
                local_path=dest_path,
                web_path=f"/static/source_videos/{output_filename}",
                is_temp=True,
                file_type="video",
            )

            if project_id:
                _add_material_to_project(project_id, new_video.id)

            return {
                "success": True,
                "video_id": new_video.id,
                "output_path": dest_path,
                "web_path": f"/static/source_videos/{output_filename}",
                "output_type": "video",
                "is_temp_asset": True,
                "message": f"成功合并 {len(video_paths)} 个视频（转场: {transition}）"
            }

    except Exception as e:
        logger.error(f"合并视频失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="image_to_video",
    description="将图片转换为视频片段（静态展示或带缩放/平移效果），可用于 merge_videos 拼接到视频时间线",
    parameters={
        "image_path": {"type": "string", "description": "图片文件路径（本地路径或 web_path）"},
        "duration": {"type": "number", "description": "持续时长（秒，默认5）"},
        "effect": {"type": "string", "description": "效果: static(静态)/zoom_in(缓慢放大)/zoom_out(缩小)/pan_left(左移)/pan_right(右移)，默认 static"},
        "resolution": {"type": "string", "description": "分辨率 如 1920x1080，默认 1920x1080"},
        "project_id": {"type": "integer", "description": "项目 ID"},
    },
    examples=["把这张图做成5秒视频", "图片转视频带放大效果"],
    permission="modify",
)
async def tool_image_to_video(
    image_path: str,
    duration: float = 5.0,
    effect: str = "static",
    resolution: str = "1920x1080",
    project_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """图片转视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        # 解析图片路径
        abs_path = image_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(str(config.ROOT_DIR_WIN), abs_path.lstrip('/'))
            if not os.path.isfile(abs_path):
                abs_path = os.path.abspath(image_path.lstrip('/'))

        if not os.path.isfile(abs_path):
            return {"success": False, "error": f"图片文件不存在: {image_path}"}

        # 获取图片尺寸
        info = ffmpeg.get_video_info(abs_path)
        img_w = int(info.get('width', 0)) if info else 0
        img_h = int(info.get('height', 0)) if info else 0

        # 解析目标分辨率
        try:
            w, h = resolution.lower().split('x')
            out_w, out_h = int(w), int(h)
        except Exception:
            out_w, out_h = 1920, 1080

        output_path = _make_temp_output(".mp4", 0)

        # 构建 FFmpeg 滤镜
        if effect == "static" or not effect:
            vf = f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black"
            cmd = ['-loop', '1', '-t', str(duration), '-i', abs_path,
                   '-vf', vf,
                   '-c:v', 'libx264', '-tune', 'stillimage',
                   '-pix_fmt', 'yuv420p', '-r', '30',
                   '-an', output_path]
        else:
            # 动态效果：用 zoompan 滤镜
            fps = 30
            frames = int(duration * fps)
            if effect == "zoom_in":
                zp = f"zoompan=z='min(zoom+0.001,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={out_w}x{out_h}:fps={fps}"
            elif effect == "zoom_out":
                zp = f"zoompan=z='if(eq(on,1),1.5,max(zoom-0.001,1))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={out_w}x{out_h}:fps={fps}"
            elif effect == "pan_left":
                zp = f"zoompan=z='1.2':x='iw*(1-1/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={out_w}x{out_h}:fps={fps}"
            elif effect == "pan_right":
                zp = f"zoompan=z='1.2':x='iw*(1-1/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={out_w}x{out_h}:fps={fps}"
            else:
                zp = f"zoompan=z='1':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={out_w}x{out_h}:fps={fps}"
            cmd = ['-loop', '1', '-t', str(duration), '-i', abs_path,
                   '-vf', zp,
                   '-c:v', 'libx264', '-tune', 'stillimage',
                   '-pix_fmt', 'yuv420p',
                   '-an', output_path]

        ffmpeg.run_ffmpeg_cmd(cmd)

        output_info = ffmpeg.get_video_info(output_path)
        output_duration = float(output_info.get('duration', duration)) if output_info else duration

        result = _save_tool_output(
            output_path, 0, "image_to_video",
            project_id,
            file_type="video",
            file_name=f"img2vid_{int(time.time())}.mp4",
            message=f"图片已转为 {duration} 秒视频（效果: {effect}）",
            duration=output_duration,
        )
        if result.get("success"):
            result["duration"] = output_duration
        return result

    except Exception as e:
        logger.error(f"图片转视频失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_subtitle",
    description="为视频添加字幕，支持多种字体、粗体、描边、阴影、背景色、位置等样式",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "subtitle_content": {"type": "string", "description": "字幕内容或文件路径"},
        "hard_subtitle": {"type": "boolean", "description": "是否硬字幕"},
        "project_id": {"type": "integer", "description": "项目 ID"},
        "fontname": {"type": "string", "description": "字体名称(楷体/Microsoft YaHei/SimHei/SimSun/FangSong/Arial等)"},
        "fontsize": {"type": "integer", "description": "字体大小(8-72)"},
        "fontcolor": {"type": "string", "description": "字体颜色(ASS格式&HBBGGRR，如&Hffffff白色)"},
        "fontbordercolor": {"type": "string", "description": "描边颜色(ASS格式)"},
        "bold": {"type": "boolean", "description": "粗体"},
        "outline_width": {"type": "number", "description": "描边宽度(0-6)"},
        "shadow": {"type": "number", "description": "阴影深度(0-4)"},
        "alignment": {"type": "integer", "description": "位置: 2=底部居中 5=上方居中 8=居中"},
        "bg_color": {"type": "string", "description": "背景颜色(ASS格式)，空则透明"},
    },
    examples=["给视频添加字幕", "添加粗体字幕", "添加带描边和阴影的字幕"],
    param_model=AddSubtitleParams,
    before_execute=validate_video_exists
)
async def tool_add_subtitle(
    video_id: int,
    subtitle_content: str,
    hard_subtitle: bool = True,
    project_id: int = None,
    fontname: str = "楷体",
    fontsize: int = 24,
    fontcolor: str = "&Hffffff",
    fontbordercolor: str = "&H000000",
    bold: bool = False,
    outline_width: float = 2,
    shadow: float = 0,
    alignment: int = 2,
    bg_color: str = None,
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

            # subtitle_type: True=软字幕, False=硬字幕
            output_name = ffmpeg.add_subtitle(
                video_path=video.local_path,
                subtitle_content=subtitle_content,
                subtitle_type=not hard_subtitle,
                fontname=fontname,
                fontsize=fontsize,
                fontcolor=fontcolor,
                fontbordercolor=fontbordercolor,
                bold=bold,
                outline_width=outline_width,
                shadow=shadow,
                alignment=alignment,
                bg_color=bg_color,
            )

            return _save_tool_output(
                output_name, video_id, "add_subtitle",
                project_id,
                file_type="video",
                file_name=f"subtitle_{video_id}_{int(time.time())}{os.path.splitext(output_name)[1]}",
                message="字幕添加完成",
            )

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
            return _save_tool_output(
                str(output_path), video_id, "change_speed",
                kwargs.get("project_id"),
                file_type="video",
                file_name=f"speed_{video_id}_{speed_factor}{os.path.splitext(str(output_path))[1]}",
                message=f"已调整为 {speed_factor} 倍速{speed_desc}",
            )

    except Exception as e:
        logger.error(f"调整速度失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@registry.register(
    name="smart_clip",
    description="智能剪辑，根据描述自动规划和生成视频。支持文本优先模式（先 ASR 再 LLM 分析）",
    parameters={
        "description": {"type": "string", "description": "剪辑需求描述"},
        "duration": {"type": "number", "description": "目标时长（秒）"},
        "style": {"type": "string", "description": "风格偏好"},
        "text_first": {"type": "boolean", "description": "启用文本优先模式（默认 true，先 ASR 再分析）"},
        "margin_before": {"type": "number", "description": "片段开始前缓冲（秒）"},
        "margin_after": {"type": "number", "description": "片段结束后缓冲（秒）"},
    },
    examples=["帮我做一个30秒的旅行混剪", "做一个燃一点的短视频"],
    param_model=SmartClipParams
)
async def tool_smart_clip(
    description: str,
    duration: float = 30.0,
    style: str = "动感",
    margin_before: float = 0.3,
    margin_after: float = 0.3,
    **kwargs
) -> Dict[str, Any]:
    """智能剪辑工具"""
    from src.application.services.creative_service import CreativeService

    try:
        service = CreativeService()

        # 文本优先模式：先通过 ASR 获取字幕，再基于字幕做剪辑规划
        text_first = kwargs.get("text_first", True)
        if text_first:
            try:
                from src.application.services import whisper_adapter, ffmpeg_adapter
                from src.infrastructure.db.session import get_db_context
                from src.domain.entities.video_source import VideoSource

                with get_db_context() as db:
                    videos = db.query(VideoSource).filter(VideoSource.video_type == 1).all()

                transcripts = []
                for v in videos[:2]:  # 最多处理 2 个素材，防止内存溢出
                    try:
                        proxy_path = ffmpeg_adapter.generate_proxy(v.local_path)
                        srt = whisper_adapter.transcribe(
                            audio_path=v.local_path,
                            output_format_type="srt",
                            proxy_path=proxy_path,
                        )
                        if srt and len(srt.strip()) > 10:
                            transcripts.append(f"[视频 {v.id}: {v.video_name or '未命名'}]\n{srt[:2000]}")
                    except Exception as te:
                        logger.warning(f"视频 {v.id} 转录失败，跳过: {te}")

                if transcripts:
                    combined_transcript = "\n\n".join(transcripts)
                    # 将转录文本注入创意描述
                    description = f"{description}\n\n[以下是素材的转录文本，请基于文本定位高光片段：]\n{combined_transcript[:6000]}"
                    logger.info(f"文本优先模式：注入了 {len(transcripts)} 段转录文本")
            except Exception as e:
                logger.warning(f"文本优先模式失败，回退到标准模式: {e}")

        result = service.create_video_with_transitions(
            creative=description,
            audio_url=kwargs.get("audio_url"),
            duration=duration,
            style=style
        )

        return {
            "success": True,
            "output_path": result.get("concatenate_web_url"),
            "message": f"智能剪辑完成（text_first={text_first}），时长约 {duration} 秒"
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
    before_execute=validate_video_exists,
    permission="read_only"
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
    description="文本转语音，生成配音。不需要先查询音色列表，系统会自动使用默认音色。仅在需要指定特定音色时才传 speaker_id",
    parameters={
        "text": {"type": "string", "description": "要合成的文本"},
        "speaker_id": {"type": "integer", "description": "音色 ID（可选，不传则使用默认音色）"},
    },
    examples=["生成配音", "把这个文案读出来", "用1号音色生成语音"],
    param_model=GenerateTtsParams,
    category="common",
)
async def tool_generate_tts(
    text: str,
    speaker_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """生成 TTS 工具"""
    from src.application.services.audio_service import AudioService
    from src.infrastructure.db.session import get_db_context

    # 未指定 speaker_id 时自动使用默认音色
    resolved_speaker_id = speaker_id
    if resolved_speaker_id is None:
        from src.domain.entities.audio_source import AudioSource
        with get_db_context() as db:
            default_voice = db.query(AudioSource).filter(
                AudioSource.is_default == 1, AudioSource.del_flag == 0
            ).first()
            if default_voice:
                resolved_speaker_id = default_voice.id

    try:
        with get_db_context() as db:
            audio_service = AudioService(db)
            result = audio_service.generate_fish_speech_tts(
                text=text,
                audio_source_id=resolved_speaker_id or -1,
            )

        project_id = kwargs.get("project_id")
        local_path = result.get("local_path")
        if local_path and os.path.isfile(local_path):
            save_result = _save_tool_output(
                local_path, resolved_speaker_id or 0, "tts",
                project_id, file_type="audio",
                file_name=f"tts_{int(time.time())}.wav",
                message="语音生成完成",
            )
            if save_result.get("is_temp_asset"):
                return save_result

        return {
            "success": True,
            "web_path": result.get("web_path"),
            "local_path": result.get("local_path"),
            "message": "语音生成完成",
        }

    except Exception as e:
        logger.error(f"语音生成失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="list_videos",
    description="列出当前项目已使用的素材（仅项目关联的正式素材和临时文件，不包含素材库中未使用的素材）",
    parameters={
        "project_id": {"type": "integer", "description": "项目 ID（自动注入）"},
    },
    examples=["有什么素材", "查看素材库"],
    permission="read_only",
    category="common",
)
async def tool_list_videos(**kwargs) -> Dict[str, Any]:
    """列出视频工具，支持按项目筛选"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.domain.entities.video_project import VideoProject
    from src.domain.entities.video_source import VideoSource

    project_id = kwargs.get("project_id")

    try:
        with get_db_context() as db:
            if not project_id:
                return {
                    "success": True,
                    "videos": [],
                    "count": 0,
                    "message": "当前无项目，无法查看素材"
                }

            project = db.query(VideoProject).filter(VideoProject.id == int(project_id)).first()
            project_name = project.name if project else str(project_id)

            # 项目关联的正式素材
            videos = []
            if project and project.material_ids:
                repo = VideoRepository(db)
                videos.extend(repo.get_by_ids(project.material_ids))

            # 项目临时文件对应的 VideoSource 记录
            from src.domain.entities.project_temp_file import ProjectTempFile
            temp_files = db.query(ProjectTempFile).filter(
                ProjectTempFile.project_id == int(project_id)
            ).all()
            if temp_files:
                temp_paths = [tf.file_path for tf in temp_files]
                temp_vs = db.query(VideoSource).filter(
                    VideoSource.local_path.in_(temp_paths),
                    VideoSource.is_temp == True,
                ).all()
                existing_ids = {v.id for v in videos}
                for v in temp_vs:
                    if v.id not in existing_ids:
                        videos.append(v)

            if not videos:
                return {
                    "success": True,
                    "videos": [],
                    "count": 0,
                    "message": f"项目 '{project_name}' 暂无素材"
                }

            video_list = [
                {
                    "id": v.id,
                    "name": v.video_name,
                    "duration": v.duration_hms,
                    "description": v.description or "无描述",
                    "is_temp": v.is_temp if v.is_temp is not None else False,
                    "file_type": v.file_type or "video",
                }
                for v in videos
            ]

            lines = [f"项目 '{project_name}' 共 {len(video_list)} 个素材："]
            for i, v in enumerate(video_list):
                name = v.get("name") or "未命名"
                dur = v.get("duration") or ""
                temp_tag = " [临时]" if v.get("is_temp") else ""
                ft_tag = f" ({v.get('file_type')})" if v.get("file_type") != "video" else ""
                lines.append(f"{i+1}. {name}{temp_tag}{ft_tag} ({dur}) [ID: {v['id']}]")

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
    permission="read_only",
    category="common",
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
                result = {"success": True, "video_id": video_id, "video_name": name, "has_description": True}
                parts = []

                # 尝试解析结构化 JSON（VL + ASR 组合格式）
                try:
                    obj = json.loads(desc)
                    if isinstance(obj, dict):
                        if "segments" in obj:
                            segs = obj["segments"]
                            lines = [f"- **{s.get('start', '?')}s-{s.get('end', '?')}s**: {s.get('desc', '')}" for s in segs]
                            parts.append("画面分析：\n" + "\n".join(lines))
                            result["segments"] = segs
                        if "vl_text" in obj:
                            parts.append("画面分析：" + obj["vl_text"])
                        if "transcription" in obj:
                            parts.append("字幕/语音：\n" + obj["transcription"])
                            result["transcription"] = obj["transcription"]
                        if not parts:
                            parts.append(desc)
                    else:
                        parts.append(desc)
                except (ValueError, TypeError):
                    # 旧格式：纯 segments JSON 或纯文本
                    try:
                        obj = json.loads(desc)
                        if isinstance(obj, dict) and "segments" in obj:
                            segs = obj["segments"]
                            lines = [f"- **{s.get('start', '?')}s-{s.get('end', '?')}s**: {s.get('desc', '')}" for s in segs]
                            parts.append("画面分析：\n" + "\n".join(lines))
                            result["segments"] = segs
                        else:
                            parts.append(desc)
                    except (ValueError, TypeError):
                        parts.append(desc)

                formatted = "\n\n".join(parts)
                result["description"] = formatted
                result["message"] = f"**{name}** 的描述：\n{formatted}"
                return result
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
    description="搜索或下载视频素材（注意：使用前请先调用 list_videos 检查项目已有素材，优先使用已有素材，不够时再搜索下载）",
    parameters={
        "keywords": {"type": "string", "description": "搜索关键词"},
    },
    examples=["下载一些海边素材", "搜索城市夜景"],
    param_model=SearchMaterialParams,
    permission="read_only"
)
async def tool_search_material(
    keywords: str,
    **kwargs
) -> Dict[str, Any]:
    """搜索素材工具"""
    from src.application.services import video_downloader_adapter
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        project_id = kwargs.get("project_id")
        keyword_list = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]
        tags = ",".join(keyword_list)
        logger.info(f"[search_material] 开始搜索下载: {keyword_list}")

        def _do_search():
            results = []
            for kw in keyword_list:
                videos = video_downloader_adapter.search_videos(kw, minimum_duration=0, source="pexels")
                if not videos:
                    videos = video_downloader_adapter.search_videos(kw, minimum_duration=0, source="pixabay")
                if not videos:
                    videos = video_downloader_adapter.search_videos(kw, minimum_duration=0, source="coverr")
                for v in videos[:2]:
                    try:
                        dl_result = video_downloader_adapter.download_video(
                            v, project_id=project_id, tags=tags,
                        )
                        vid = dl_result.get("video_id") if isinstance(dl_result, dict) else None
                        results.append({"keyword": kw, "url": v.get("url", ""), "status": "downloaded", "video_id": vid})
                    except Exception as e:
                        results.append({"keyword": kw, "url": v.get("url", ""), "status": "failed", "error": str(e)})
            return results

        results = await asyncio.to_thread(_do_search)
        downloaded = [r for r in results if r["status"] == "downloaded"]
        logger.info(f"[search_material] 完成: 下载 {len(downloaded)}/{len(results)} 个素材")

        # 自动分析下载的视频（获取描述 + ASR 转录，供后续剪辑使用）
        analyzed_ids = []
        transcribed_ids = []
        for r in downloaded:
            vid = r.get("video_id")
            if not vid:
                continue
            try:
                with get_db_context() as db:
                    repo = VideoRepository(db)
                    video = repo.get_by_id(vid)
                    if not video or video.description:
                        continue
                    # 基础视频信息分析
                    desc = await asyncio.to_thread(ffmpeg.get_video_info, video.local_path)
                    if desc:
                        w, h = desc.get('width', 0), desc.get('height', 0)
                        dur = desc.get('duration_hms', '')
                        fps = desc.get('fps', 0)
                        video.description = (
                            f"自动分析: {w}x{h} {fps}fps 时长{dur}。"
                            f"搜索关键词: {tags}"
                        )
                        analyzed_ids.append(vid)
                    db.commit()
            except Exception as e:
                logger.warning(f"[search_material] 分析视频 {vid} 失败: {e}")
                continue

            # 有音频轨时自动 ASR 转录
            try:
                has_audio = ffmpeg._has_audio_stream(video.local_path if vid else "")
            except Exception:
                continue
            if not has_audio:
                continue
            try:
                from src.application.services import whisper_adapter
                subtitle_text = await asyncio.to_thread(
                    whisper_adapter.transcribe,
                    video.local_path,
                    "txt",
                    subtitle_language="zh",
                )
                if subtitle_text and subtitle_text.strip():
                    with get_db_context() as db:
                        v = db.query(VideoSource).filter(VideoSource.id == vid).first()
                        if v:
                            existing = v.description or ""
                            v.description = existing + f"\n语音内容: {subtitle_text.strip()}"
                            db.commit()
                            transcribed_ids.append(vid)
            except Exception as e:
                logger.warning(f"[search_material] ASR 转录视频 {vid} 失败: {e}")

        summary = f"搜索 '{keywords}' 完成，下载了 {len(downloaded)} 个素材"
        if analyzed_ids:
            summary += f"，已分析 {len(analyzed_ids)} 个"
        if transcribed_ids:
            summary += f"，已转录 {len(transcribed_ids)} 个"

        return {
            "success": True,
            "message": summary,
            "details": results,
        }

    except Exception as e:
        logger.error(f"搜索素材失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# ==================== P0: 能力缺口工具 ====================

@registry.register(
    name="transcribe_video",
    description="从视频/音频中提取字幕，进行语音识别生成 SRT 字幕文件",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID（与 file_path 二选一）"},
        "file_path": {"type": "string", "description": "文件路径（与 video_id 二选一，支持视频和音频）"},
        "language": {"type": "string", "description": "语言（可选，默认自动检测）"},
    },
    examples=["帮我提取这个视频的字幕", "识别视频中的语音", "生成字幕文件"],
    param_model=TranscribeVideoParams,
    permission="read_only"
)
async def tool_transcribe_video(
    video_id: int = None,
    file_path: str = None,
    language: str = None,
    **kwargs
) -> Dict[str, Any]:
    """字幕提取工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import whisper_adapter, ffmpeg_adapter
    import os

    try:
        local_path = file_path

        if video_id and not file_path:
            with get_db_context() as db:
                repo = VideoRepository(db)
                video = repo.get_by_id(video_id)
                if not video:
                    return {"success": False, "error": f"视频 {video_id} 不存在"}
                local_path = video.local_path

        if not local_path or not os.path.exists(local_path):
            return {"success": False, "error": f"文件不存在: {local_path}"}

        # 对于视频/WAV/FLAC 文件，先提取为 MP3 再送 ASR（避免 WAV 过大导致 413）
        ext = os.path.splitext(local_path)[1].lower()
        asr_input = local_path
        if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.ts', '.m4v', '.wav', '.flac'):
            audio_tmp = _make_temp_output(".mp3", video_id or 0)
            try:
                ffmpeg_adapter.run_ffmpeg_cmd([
                    '-y', '-i', local_path,
                    '-vn', '-acodec', 'libmp3lame', '-q:a', '4',
                    audio_tmp
                ])
                asr_input = audio_tmp
            except Exception as audio_err:
                logger.warning(f"提取音频失败，直接使用原始文件: {audio_err}")

        subtitle_text = whisper_adapter.transcribe(
            audio_path=asr_input,
            subtitle_language=language or "zh",
        )

        # 清理临时音频文件
        if asr_input != local_path and os.path.exists(asr_input):
            try:
                os.remove(asr_input)
            except OSError:
                pass

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
    description="AI 深度分析视频/图片内容，理解场景、人物、动作、风格等",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID（与 file_path 二选一）"},
        "file_path": {"type": "string", "description": "文件路径（与 video_id 二选一，支持图片和视频）"},
        "prompt": {"type": "string", "description": "分析提示（可选）"},
    },
    examples=["这个视频讲了什么", "分析视频内容和风格", "详细描述一下这个视频"],
    param_model=AnalyzeVideoVlParams,
    permission="read_only"
)
async def tool_analyze_video_vl(
    video_id: int = None,
    file_path: str = None,
    prompt: str = "请详细描述这个视频的内容、场景和风格",
    **kwargs
) -> Dict[str, Any]:
    """AI 视觉理解工具（优化版：优先使用镜头索引 + 文本 LLM，降级到 VL）"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import qwen_vl_adapter
    from src.application.services import ffmpeg_adapter as ffmpeg
    import os

    try:
        local_path = file_path
        video_name = os.path.basename(file_path) if file_path else None
        duration_sec = None

        # 优先使用 video_id 从数据库获取
        if video_id and not file_path:
            with get_db_context() as db:
                repo = VideoRepository(db)
                video = repo.get_by_id(video_id)
                if not video:
                    return {"success": False, "error": f"视频 {video_id} 不存在"}
                local_path = video.local_path
                video_name = video.video_name
                duration_sec = float(video.duration) if video.duration else None

        if not local_path or not os.path.exists(local_path):
            return {"success": False, "error": f"文件不存在: {local_path}"}

        # 图片文件直接调用 image_summary
        ext = os.path.splitext(local_path)[1].lower()
        if ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}:
            analysis = qwen_vl_adapter.image_summary(tmp_path=local_path, prompt=prompt)
        elif video_id:
            # 视频文件 + 有 video_id → 优先尝试索引分析
            try:
                from src.application.services.video_indexer import VideoIndexer
                from src.application.services.llm_adapter import generate_response_async

                indexer = VideoIndexer()
                context = indexer.build_structured_context(video_id, prompt)
                if context:
                    messages = [
                        {"role": "system", "content": "你是一个视频分析专家。根据以下视频的镜头级索引数据回答用户问题，给出详细、准确的分析。"},
                        {"role": "user", "content": f"以下是视频的结构化分析数据：\n\n{context}\n\n用户提问：{prompt}"}
                    ]
                    analysis = await generate_response_async(
                        messages, temperature=0.5, max_tokens=2048
                    )
                    # 将分析结果写入素材描述
                    if video_id and analysis:
                        try:
                            with get_db_context() as db:
                                repo = VideoRepository(db)
                                v = repo.get_by_id(video_id)
                                if v:
                                    v.description = analysis[:500]
                                    db.commit()
                        except Exception:
                            pass
                    return {
                        "success": True,
                        "analysis": {
                            "video_id": video_id,
                            "video_name": video_name,
                            "ai_summary": analysis,
                            "index_based": True
                        },
                        "message": "AI 分析完成（基于镜头索引）"
                    }
            except Exception as e:
                logger.warning(f"[VL] 索引分析失败，降级到 VL 直接分析: {e}")

            # 降级：原 VL 流程
            proxy_path = ffmpeg.generate_proxy(local_path)
            analysis = qwen_vl_adapter.video_summary(
                tmp_path=local_path,
                prompt=prompt,
                duration=duration_sec,
                proxy_path=proxy_path
            )
        else:
            # 无 video_id（直接文件路径），走原 VL 流程
            proxy_path = ffmpeg.generate_proxy(local_path)
            analysis = qwen_vl_adapter.video_summary(
                tmp_path=local_path,
                prompt=prompt,
                duration=duration_sec,
                proxy_path=proxy_path
            )

        # 将分析结果写入素材描述
        if video_id and analysis:
            try:
                with get_db_context() as db:
                    repo = VideoRepository(db)
                    v = repo.get_by_id(video_id)
                    if v:
                        v.description = analysis[:500]
                        db.commit()
            except Exception:
                pass

        return {
            "success": True,
            "analysis": {
                "video_id": video_id,
                "video_name": video_name,
                "ai_summary": analysis,
                "index_based": False
            },
            "message": "AI 分析完成"
        }

    except Exception as e:
        logger.error(f"AI 视频分析失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="analyze_transcript",
    description="基于视频的字幕/转录文本进行内容分析，识别高光片段、主题边界和情感峰值。比 VL 分析快 10 倍且成本低",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "analysis_type": {"type": "string", "description": "分析类型: highlights(高光)/topics(主题)/sentiment(情感)/summary(摘要)，默认 highlights"},
    },
    examples=["分析这个视频的高光片段", "提取视频的主题结构", "分析字幕内容"],
    param_model=None,
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_analyze_transcript(
    video_id: int,
    analysis_type: str = "highlights",
    **kwargs
) -> Dict[str, Any]:
    """基于转录文本的视频分析工具（文本优先模式）"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import whisper_adapter, ffmpeg_adapter
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            # 生成代理文件加速 ASR
            proxy_path = ffmpeg_adapter.generate_proxy(video.local_path)

            # ASR 转录
            subtitle_text = whisper_adapter.transcribe(
                audio_path=video.local_path,
                output_format_type="srt",
                proxy_path=proxy_path
            )

            if not subtitle_text or len(subtitle_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "转录文本为空或过短，建议使用 analyze_video_vl 进行视觉分析",
                    "fallback_tool": "analyze_video_vl"
                }

            # 构建 LLM 分析提示
            analysis_prompts = {
                "highlights": f"""分析以下视频字幕文本，识别最精彩、最有价值的片段。
返回 JSON 格式的高光片段列表：
{{"highlights": [{{"start": 秒数, "end": 秒数, "reason": "高光原因", "score": 1-10}}]}}

字幕内容：
{subtitle_text[:4000]}""",
                "topics": f"""分析以下视频字幕文本，按主题/话题进行分段。
返回 JSON 格式的主题列表：
{{"topics": [{{"start": 秒数, "end": 秒数, "topic": "主题名称", "summary": "简要描述"}}]}}

字幕内容：
{subtitle_text[:4000]}""",
                "sentiment": f"""分析以下视频字幕文本，识别情感变化。
返回 JSON 格式的情感分析：
{{"segments": [{{"start": 秒数, "end": 秒数, "sentiment": "积极/中性/消极", "intensity": 1-5}}]}}

字幕内容：
{subtitle_text[:4000]}""",
                "summary": f"""总结以下视频字幕文本的内容。
返回 JSON 格式：
{{"title": "视频标题", "summary": "整体摘要(100字内)", "key_points": ["要点1", "要点2", ...]}}

字幕内容：
{subtitle_text[:4000]}""",
            }

            prompt = analysis_prompts.get(analysis_type, analysis_prompts["highlights"])

            # 调用 LLM 分析
            client = get_client()
            model = cfg_get("core_nexus.fast_model") or cfg_get("core_nexus.model") or None
            response = client.llm_generate(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )

            analysis_result = response.get("text", "")

            return {
                "success": True,
                "video_id": video_id,
                "analysis_type": analysis_type,
                "subtitle_length": len(subtitle_text),
                "analysis": analysis_result,
                "message": f"文本分析完成（类型: {analysis_type}，基于 {len(subtitle_text)} 字符的转录文本）"
            }

    except Exception as e:
        logger.error(f"转录文本分析失败: {e}")
        return {"success": False, "error": str(e)}


def _resolve_bgm_audio(bgm_id: int) -> tuple:
    """从 BGM 曲库解析音频，返回 (local_path, audio_base64, bgm_dict)"""
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.bgm_item import BGMItem

    with get_db_context() as db:
        bgm = db.query(BGMItem).filter(BGMItem.id == bgm_id).first()
        if not bgm:
            raise ValueError(f"BGM ID {bgm_id} 不存在")
        bgm_data = bgm.to_dict()
        local_path = bgm.local_path

    if not local_path or not os.path.exists(local_path):
        raise ValueError(f"BGM 文件不存在: {local_path}")

    with open(local_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return local_path, audio_b64, bgm_data


def _extract_audio_bytes(result: dict) -> bytes:
    """从 API 结果中提取音频字节，兼容多种返回格式"""
    import base64 as _b64
    result = result or {}
    audio_data = ""

    if isinstance(result, dict):
        audio_data = result.get("audio", "") or result.get("output", "") or result.get("data", "")
        if not audio_data and any(result.values()):
            for v in result.values():
                if isinstance(v, str) and len(v) > 100:
                    audio_data = v
                    break
    elif isinstance(result, str) and len(result) > 100:
        audio_data = result

    if not audio_data:
        raise ValueError("音乐生成服务未返回音频数据")

    if audio_data.startswith("data:"):
        audio_data = audio_data.split(",", 1)[1]
    return _b64.b64decode(audio_data)


def _save_audio_to_bgm(audio_bytes: bytes, name: str, style: str = "",
                       duration: float = 10.0, description: str = "") -> dict:
    """将音频字节保存到 BGM 曲库，返回 bgm_dict"""
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.bgm_item import BGMItem

    bgm_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "bgm")
    os.makedirs(bgm_dir, exist_ok=True)
    save_name = f"ai_music_{int(time.time())}.mp3"
    file_path = os.path.join(bgm_dir, save_name)
    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    with get_db_context(commit=True) as db:
        bgm = BGMItem(
            name=name[:255],
            web_path=f"static/bgm/{save_name}",
            local_path=file_path,
            style=style or "",
            duration=duration,
            description=description[:500]
        )
        db.add(bgm)
        db.commit()
        db.refresh(bgm)
        return bgm.to_dict()


@registry.register(
    name="generate_music",
    description="根据文字描述生成背景音乐。不传 lyrics 生成纯音乐，传入歌词生成带人声的歌曲。支持 [verse]/[chorus] 结构标签",
    parameters={
        "prompt": {"type": "string", "description": "音乐描述"},
        "duration": {"type": "number", "description": "时长（秒，默认10，最大240）"},
        "style": {"type": "string", "description": "风格: pop/classical/electronic/jazz/rock/ambient"},
        "lyrics": {"type": "string", "description": "歌词（支持 [verse]/[chorus] 结构标签，不传则纯音乐）"},
    },
    examples=["生成一段30秒的钢琴纯音乐", "做一个轻快的电子BGM", "写一首温暖的流行歌，歌词：[verse]星空下的夜晚[chorus]我想要飞翔"],
    param_model=GenerateMusicParams,
    category="common",
)
async def tool_generate_music(
    prompt: str,
    duration: float = 10.0,
    style: str = None,
    lyrics: str = None,
    **kwargs
) -> Dict[str, Any]:
    """音乐生成工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get
    from src import config

    try:
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.text_to_music(
            prompt=prompt, duration=duration, style=style,
            model=music_model, mode="generate", lyrics=lyrics,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        name_prefix = "AI歌曲" if lyrics else "AI纯音乐"
        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"{name_prefix}-{prompt[:20]}",
            style=style or "",
            duration=duration,
            description=f"提示词: {prompt[:100]}"
        )
        return {
            "success": True,
            "message": f"音乐生成完成，已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"音乐生成失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="generate_image",
    description="AI 图片生成：根据文字描述生成图片。可用于生成封面、背景、配图等。生成后自动保存到项目临时文件",
    parameters={
        "prompt": {"type": "string", "description": "图片描述（越详细效果越好，包含主体、风格、光影、构图等）"},
        "negative_prompt": {"type": "string", "description": "反向提示词（排除不想要的元素，如 '模糊, 变形, 水印'）"},
        "width": {"type": "integer", "description": "图片宽度（默认1024，范围256-2048）"},
        "height": {"type": "integer", "description": "图片高度（默认1024，范围256-2048）"},
    },
    examples=["生成一张动漫风格的女孩头像", "画一个赛博朋克城市夜景，霓虹灯光", "生成一张1024x576的横版风景图"],
    param_model=GenerateImageParams,
    category="common",
)
async def tool_generate_image(
    prompt: str,
    negative_prompt: str = None,
    width: int = 1024,
    height: int = 1024,
    **kwargs
) -> Dict[str, Any]:
    """AI 图片生成工具"""
    from src.shared.utils.core_nexus_client import get_client

    try:
        client = get_client()
        result = await client.text_to_image_async(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
        )

        image_bytes = result.get("image_bytes")
        if not image_bytes or len(image_bytes) < 1000:
            return {"success": False, "error": "图片生成失败，返回数据异常，请重试"}

        project_id = kwargs.get("project_id")

        # 保存到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(image_bytes)
            temp_path = f.name

        if project_id:
            saved = _save_temp_file(
                temp_path, project_id, "image", "generate_image",
                file_name=f"ai_image_{int(time.time())}.png",
            )
            if saved:
                return {
                    "success": True,
                    "message": f"图片生成完成 ({width}x{height})",
                    **saved,
                }

        # 无 project_id 时保存到 static/source_videos/
        import uuid
        from src import config
        save_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "source_videos")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"ai_image_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(save_dir, filename)
        shutil.move(temp_path, save_path)
        web_path = f"static/source_videos/{filename}"
        return {
            "success": True,
            "message": f"图片生成完成 ({width}x{height})",
            "web_path": web_path,
            "local_path": save_path,
        }
    except Exception as e:
        logger.error(f"图片生成失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="edit_image",
    description="AI 图片编辑：根据文字指令修改现有图片（改风格、加元素、去元素、局部重绘等）。需要提供原始图片的素材 ID",
    parameters={
        "prompt": {"type": "string", "description": "编辑指令（描述想要的效果，如 '把背景换成星空' '去掉水印' '改成水彩风格'）"},
        "video_id": {"type": "integer", "description": "原始图片素材 ID"},
        "mask_video_id": {"type": "integer", "description": "蒙版图片素材 ID（可选，用于局部编辑，白色区域会被重新生成）"},
    },
    examples=["把这张图的背景换成海边", "把这个图片改成卡通风格", "去掉图片上的水印"],
    param_model=EditImageParams,
    category="common",
)
async def tool_edit_image(
    prompt: str,
    video_id: int,
    mask_video_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """AI 图片编辑工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.video_source import VideoSource

    try:
        # 查找原图
        with get_db_context() as db:
            source = db.query(VideoSource).filter(VideoSource.id == video_id).first()
            if not source:
                return {"success": False, "error": f"素材 ID {video_id} 不存在"}
            image_path = source.local_path or source.web_path
            if image_path and not os.path.isabs(image_path):
                image_path = os.path.join(str(config.ROOT_DIR_WIN), image_path.lstrip('/'))
            if not image_path or not os.path.isfile(image_path):
                return {"success": False, "error": f"素材文件不存在: {image_path}"}

            mask_path = None
            if mask_video_id:
                mask_source = db.query(VideoSource).filter(VideoSource.id == mask_video_id).first()
                if mask_source:
                    mask_path = mask_source.local_path or mask_source.web_path
                    if mask_path and not os.path.isabs(mask_path):
                        mask_path = os.path.join(str(config.ROOT_DIR_WIN), mask_path.lstrip('/'))

        client = get_client()
        result = await client.image_to_image_async(
            prompt=prompt,
            image=image_path,
            mask=mask_path if mask_path and os.path.isfile(mask_path) else None,
        )

        image_bytes = result.get("image_bytes")
        if not image_bytes or len(image_bytes) < 1000:
            return {"success": False, "error": "图片编辑失败，返回数据异常，请重试"}

        project_id = kwargs.get("project_id")

        # 保存结果
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(image_bytes)
            temp_path = f.name

        if project_id:
            saved = _save_temp_file(
                temp_path, project_id, "image", "edit_image",
                file_name=f"edited_{int(time.time())}.png",
            )
            if saved:
                return {
                    "success": True,
                    "message": "图片编辑完成",
                    **saved,
                }

        import uuid
        save_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "source_videos")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"edited_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(save_dir, filename)
        shutil.move(temp_path, save_path)
        web_path = f"static/source_videos/{filename}"
        return {
            "success": True,
            "message": "图片编辑完成",
            "web_path": web_path,
            "local_path": save_path,
        }
    except Exception as e:
        logger.error(f"图片编辑失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="retake_music",
    description="音乐变奏：基于相同描述生成不同变体。variance 越大差异越大",
    parameters={
        "prompt": {"type": "string", "description": "音乐描述"},
        "duration": {"type": "number", "description": "时长（秒）"},
        "style": {"type": "string", "description": "风格"},
        "lyrics": {"type": "string", "description": "歌词"},
        "variance": {"type": "number", "description": "变化程度 0-1（默认0.5）"},
    },
    examples=["换一个版本的音乐", "再来一个变体，变化大一点"],
    param_model=RetakeMusicParams,
    category="common",
)
async def tool_retake_music(
    prompt: str, duration: float = 10.0, style: str = None,
    lyrics: str = None, variance: float = 0.5, **kwargs
) -> Dict[str, Any]:
    """音乐变奏工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.text_to_music(
            prompt=prompt, duration=duration, style=style,
            model=music_model, mode="retake", lyrics=lyrics,
            variance=variance,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI变奏-{prompt[:20]}",
            style=style or "", duration=duration,
            description=f"变奏(variance={variance}): {prompt[:100]}"
        )
        return {
            "success": True,
            "message": f"音乐变奏完成，已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"音乐变奏失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="repaint_music",
    description="音乐局部重绘：对 BGM 曲库中指定时间段重新生成。需要指定 bgm_id、起止时间",
    parameters={
        "bgm_id": {"type": "integer", "description": "BGM ID（从曲库中选择）"},
        "prompt": {"type": "string", "description": "重绘部分的音乐描述"},
        "start_time": {"type": "number", "description": "重绘起始时间（秒）"},
        "end_time": {"type": "number", "description": "重绘结束时间（秒）"},
        "duration": {"type": "number", "description": "输出总时长（秒）"},
    },
    examples=["把第5到10秒重绘一下，加点鼓点", "重绘BGM的前15秒，改成钢琴"],
    param_model=RepaintMusicParams,
    category="common",
)
async def tool_repaint_music(
    bgm_id: int, prompt: str, start_time: float, end_time: float,
    duration: float = None, **kwargs
) -> Dict[str, Any]:
    """音乐局部重绘工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        _, audio_b64, bgm_info = _resolve_bgm_audio(bgm_id)
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.text_to_music(
            prompt=prompt, duration=duration or bgm_info.get("duration", 10.0),
            model=music_model, mode="repaint",
            audio=audio_b64, start_time=start_time, end_time=end_time,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI重绘-{bgm_info.get('name', '')[:20]}",
            style=bgm_info.get("style", ""),
            duration=duration or bgm_info.get("duration", 10.0),
            description=f"重绘 {start_time}-{end_time}s: {prompt[:100]}"
        )
        return {
            "success": True,
            "message": f"音乐重绘完成（{start_time}-{end_time}s），已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"音乐重绘失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="edit_music_lyrics",
    description="音乐歌词编辑：替换 BGM 曲库中音乐的歌词并重新生成，保持原曲风格",
    parameters={
        "bgm_id": {"type": "integer", "description": "BGM ID"},
        "lyrics": {"type": "string", "description": "新歌词（支持 [verse]/[chorus] 结构标签）"},
        "prompt": {"type": "string", "description": "编辑指导（可选）"},
    },
    examples=["把这首歌的歌词改成关于春天的", "替换歌词：[verse]春风吹过[chorus]花开满园"],
    param_model=EditMusicLyricsParams,
    category="common",
)
async def tool_edit_music_lyrics(
    bgm_id: int, lyrics: str, prompt: str = None, **kwargs
) -> Dict[str, Any]:
    """音乐歌词编辑工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        _, audio_b64, bgm_info = _resolve_bgm_audio(bgm_id)
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.text_to_music(
            prompt=prompt or "保持原曲风格",
            duration=bgm_info.get("duration", 10.0),
            model=music_model, mode="edit",
            audio=audio_b64, lyrics=lyrics,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI歌词编辑-{bgm_info.get('name', '')[:20]}",
            style=bgm_info.get("style", ""),
            duration=bgm_info.get("duration", 10.0),
            description=f"歌词编辑: {lyrics[:100]}"
        )
        return {
            "success": True,
            "message": f"歌词编辑完成，已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"歌词编辑失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="extend_music",
    description="音乐扩展：在 BGM 曲库中的音乐前后扩展时长",
    parameters={
        "bgm_id": {"type": "integer", "description": "BGM ID"},
        "prompt": {"type": "string", "description": "音乐描述"},
        "extend_left": {"type": "number", "description": "向前延长秒数（默认0）"},
        "extend_right": {"type": "number", "description": "向后延长秒数（默认10）"},
    },
    examples=["把这段BGM往后延长15秒", "在前面加10秒的引子"],
    param_model=ExtendMusicParams,
    category="common",
)
async def tool_extend_music(
    bgm_id: int, prompt: str = None, extend_left: float = 0,
    extend_right: float = 10, **kwargs
) -> Dict[str, Any]:
    """音乐扩展工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        _, audio_b64, bgm_info = _resolve_bgm_audio(bgm_id)
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        orig_duration = bgm_info.get("duration", 10.0)
        result = client.text_to_music(
            prompt=prompt or "延续前面的旋律风格",
            duration=orig_duration + extend_left + extend_right,
            model=music_model, mode="extend",
            audio=audio_b64,
            extend_left=extend_left, extend_right=extend_right,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        new_duration = orig_duration + extend_left + extend_right
        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI扩展-{bgm_info.get('name', '')[:20]}",
            style=bgm_info.get("style", ""),
            duration=new_duration,
            description=f"扩展(左+{extend_left}s 右+{extend_right}s): {bgm_info.get('name', '')}"
        )
        return {
            "success": True,
            "message": f"音乐扩展完成（+左{extend_left}s +右{extend_right}s），已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"音乐扩展失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="cover_music",
    description="音乐翻唱：基于 BGM 曲库中的参考音频进行翻唱，可指定风格",
    parameters={
        "bgm_id": {"type": "integer", "description": "要翻唱的 BGM ID"},
        "prompt": {"type": "string", "description": "翻唱风格描述"},
        "lyrics": {"type": "string", "description": "翻唱歌词（可选）"},
    },
    examples=["用爵士风格翻唱这段BGM", "把这首歌翻唱成摇滚版"],
    param_model=CoverMusicParams,
    category="common",
)
async def tool_cover_music(
    bgm_id: int, prompt: str = None, lyrics: str = None, **kwargs
) -> Dict[str, Any]:
    """音乐翻唱工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        _, audio_b64, bgm_info = _resolve_bgm_audio(bgm_id)
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.text_to_music(
            prompt=prompt or "翻唱",
            duration=bgm_info.get("duration", 10.0),
            model=music_model, mode="cover",
            audio=audio_b64, lyrics=lyrics,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI翻唱-{bgm_info.get('name', '')[:20]}",
            style=prompt or bgm_info.get("style", ""),
            duration=bgm_info.get("duration", 10.0),
            description=f"翻唱: {prompt or '默认风格'} | 原曲: {bgm_info.get('name', '')}"
        )
        return {
            "success": True,
            "message": f"音乐翻唱完成，已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"音乐翻唱失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="style_transfer_music",
    description="音乐风格迁移：将 BGM 曲库中的音乐转换为新的风格",
    parameters={
        "bgm_id": {"type": "integer", "description": "BGM ID"},
        "prompt": {"type": "string", "description": "目标风格描述"},
        "edit_strength": {"type": "number", "description": "风格修改强度 0-1（默认0.5）"},
    },
    examples=["把这段BGM改成电子风格", "转换成古典风格，强度0.8"],
    param_model=StyleTransferMusicParams,
    category="common",
)
async def tool_style_transfer_music(
    bgm_id: int, prompt: str, edit_strength: float = 0.5, **kwargs
) -> Dict[str, Any]:
    """音乐风格迁移工具"""
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    try:
        _, audio_b64, bgm_info = _resolve_bgm_audio(bgm_id)
        client = get_client()
        music_model = cfg_get("core_nexus.music_model") or None
        result = client.music_to_music(
            audio=audio_b64,
            prompt=prompt,
            style=prompt,
            model=music_model,
            edit_strength=edit_strength,
        )

        audio_bytes = _extract_audio_bytes(result)
        if len(audio_bytes) < 1000:
            return {"success": False, "error": f"生成的音频数据异常（仅 {len(audio_bytes)} 字节），请重试"}

        bgm_data = _save_audio_to_bgm(
            audio_bytes,
            name=f"AI风格迁移-{prompt[:20]}",
            style=prompt,
            duration=bgm_info.get("duration", 10.0),
            description=f"风格迁移({prompt}): {bgm_info.get('name', '')}"
        )
        return {
            "success": True,
            "message": f"风格迁移完成，已添加到BGM曲库: {bgm_data.get('name', '')}",
            "bgm": bgm_data,
            "web_path": bgm_data.get("web_path"),
        }
    except Exception as e:
        logger.error(f"风格迁移失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="add_audio",
    description="为视频添加音频、配音或背景音乐",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "audio_path": {"type": "string", "description": "音频文件路径"},
        "audio_type": {"type": "string", "description": "类型: dubbing(配音)/bgm(背景音乐)"},
        "project_id": {"type": "integer", "description": "项目 ID"},
    },
    examples=["给视频加上背景音乐", "添加配音"],
    param_model=AddAudioParams,
    before_execute=validate_video_exists
)
async def tool_add_audio(
    video_id: int,
    audio_path: str,
    audio_type: str = "bgm",
    project_id: int = None,
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

            # 将 web_path 或相对路径转为绝对文件系统路径
            abs_audio = audio_path
            if not os.path.isabs(abs_audio):
                # web_path 如 "static/uploads/xxx.wav" 或 "/static/temp/7/tts_xxx.wav"
                abs_audio = abs_audio.lstrip('/')
                abs_audio = os.path.join(str(config.ROOT_DIR_WIN), abs_audio)
            if not os.path.isfile(abs_audio):
                # 回退：基于 CWD 解析
                abs_audio = os.path.abspath(audio_path.lstrip('/'))


            service = VideoService(db)
            result = service.add_audio_to_video(
                video_path=video.local_path,
                audio_path=abs_audio
            )

            output_path = result.get("local_path") or result.get("output_path") if isinstance(result, dict) else str(result)
            if output_path:
                try:
                    return _save_tool_output(
                        str(output_path), video_id, "add_audio",
                        project_id,
                        file_type="video",
                        file_name=f"audio_{video_id}_{int(time.time())}{os.path.splitext(str(output_path))[1]}",
                        message=f"已添加{'配音' if audio_type == 'dubbing' else '背景音乐'}",
                    )
                except Exception as e:
                    print(f"[add_audio] _save_tool_output 失败: {e}", flush=True)

            return {
                "success": True,
                "output_path": str(output_path) if output_path else None,
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
    param_model=DownloadVideoParams,
    category="common",
)
async def tool_download_video(
    url: str,
    _progress_dict: dict = None,
    **kwargs
) -> Dict[str, Any]:
    """下载视频工具"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import video_downloader_adapter as video_downloader
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src import config

    try:
        import tempfile
        with get_db_context() as db:
            repo = VideoRepository(db)

            # 下载到临时目录
            tmp_dir = tempfile.mkdtemp(prefix="synthetix_dl_")
            title, duration = video_downloader.download_videos_from_url(url, tmp_dir, progress_dict=_progress_dict)

            file_path = os.path.join(tmp_dir, title)
            if not os.path.exists(file_path):
                return {"success": False, "error": f"视频下载失败：文件未生成。可能是需要登录 Cookie 才能下载该视频。"}

            # 获取视频信息
            try:
                video_info = ffmpeg.get_video_info(file_path) or {}
                duration_hms = video_info.get("duration_hms", str(duration) if duration else "0")
            except Exception:
                video_info = {}
                duration_hms = str(duration) if duration else "0"

            project_id = kwargs.get("project_id")

            if project_id:
                dl_filename = f"download_{int(time.time())}_{title}"
                temp_result = _save_temp_file(file_path, project_id, "video", "download",
                                              file_name=dl_filename, duration=duration)
                if temp_result:
                    temp_result["filename"] = title
                    temp_result["message"] = f"视频下载完成"
                    return temp_result

            # 回退：无 project_id，保存到素材库
            import shutil
            dest_dir = config.source_videos_dir
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, title)
            shutil.move(file_path, dest_path)

            new_video = repo.create(
                video_name=title,
                local_path=dest_path,
                web_path=f"/static/source_videos/{title}",
                duration=video_info.get("duration", str(duration) if duration else "0"),
                duration_hms=duration_hms,
                is_temp=True,
                file_type="video",
            )

            return {
                "success": True,
                "video_id": new_video.id,
                "filename": title,
                "output_path": dest_path,
                "web_path": f"/static/source_videos/{title}",
                "output_type": "video",
                "duration": duration,
                "is_temp_asset": True,
                "message": f"视频下载完成 ID={new_video.id}"
            }

    except Exception as e:
        logger.error(f"视频下载失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== P1: 基础系统工具 ====================

@registry.register(
    name="get_current_time",
    description="获取当前日期和时间",
    parameters={},
    examples=["现在几点了", "今天几号", "当前时间"],
    permission="read_only",
    category="common",
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
    examples=["看看素材目录里有什么", "列出 uploads 文件夹的内容"],
    permission="read_only",
    category="common",
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
    param_model=SearchFilesParams,
    permission="read_only",
    category="common",
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

            out_path = _make_temp_output("_compressed.mp4", video_id)
            output_path = ffmpeg.compress_video_h265(
                input_path=video.local_path,
                output_path=out_path,
                crf=crf
            )

            if not output_path:
                return {"success": False, "error": "视频不需要压缩或压缩失败"}

            return _save_tool_output(
                str(output_path), video_id, "compress",
                kwargs.get("project_id"),
                file_type="video",
                file_name=f"compressed_{video_id}_{int(time.time())}.mp4",
                message=f"视频压缩完成（质量: {quality}）"
            )

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
    import os, tempfile
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = tempfile.mkdtemp(prefix="synthetix_frames_")

            if timestamps:
                ts_list = [t.strip() for t in timestamps.split(",")]
            else:
                info = ffmpeg.get_video_info(video.local_path)
                duration = float(info.get("duration", 30)) if info else 30
                step = duration / 6
                ts_list = [f"{int(step * (i + 1)) // 3600:02d}:{(int(step * (i + 1)) % 3600) // 60:02d}:{int(step * (i + 1)) % 60:02d}" for i in range(5)]

            frame_paths = []
            project_id = kwargs.get("project_id")
            for i, ts in enumerate(ts_list):
                output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
                ffmpeg.extract_frame(video.local_path, ts, output_path)
                if project_id and os.path.exists(output_path):
                    saved = _save_temp_file(output_path, project_id, "image", "extract_frame",
                                            file_name=f"frame_{i}_{video_id}_{int(time.time())}.jpg")
                    frame_paths.append(saved.get("web_path", output_path) if saved else output_path)
                else:
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


class ExtractKeyframesParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    mode: str = Field(default="smart", description="提取模式: fixed(固定间隔)/scene(场景切换)/smart(智能混合)")
    interval: float = Field(default=2.0, ge=0.5, le=30.0, description="fixed 模式的间隔秒数")
    scene_threshold: float = Field(default=0.3, ge=0.05, le=1.0, description="scene 模式的场景切换阈值")
    max_frames: int = Field(default=50, ge=1, le=200, description="最大提取帧数")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        if v not in ("fixed", "scene", "smart"):
            raise ValueError(f"模式必须是 fixed/scene/smart，收到: {v}")
        return v


@registry.register(
    name="extract_keyframes",
    description="分层关键帧提取，支持固定间隔、场景切换、智能混合三种模式",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "mode": {"type": "string", "description": "提取模式: fixed/scene/smart"},
        "interval": {"type": "number", "description": "固定间隔秒数 (0.5-30)"},
        "scene_threshold": {"type": "number", "description": "场景切换阈值 (0.05-1.0)"},
        "max_frames": {"type": "integer", "description": "最大提取帧数 (1-200)"},
    },
    param_model=ExtractKeyframesParams,
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_extract_keyframes(
    video_id: int,
    mode: str = "smart",
    interval: float = 2.0,
    scene_threshold: float = 0.3,
    max_frames: int = 50,
    **kwargs,
) -> Dict[str, Any]:
    import os, tempfile
    from src.application.services import ffmpeg_adapter
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = tempfile.mkdtemp(prefix="synthetix_keyframes_")
            frames = ffmpeg_adapter.extract_keyframes(
                input_path=video.local_path,
                output_dir=output_dir,
                mode=mode,
                interval=interval,
                scene_threshold=scene_threshold,
                max_frames=max_frames,
            )
            project_id = kwargs.get("project_id")
            if project_id and frames:
                saved_frames = []
                for fp in frames:
                    if os.path.exists(fp):
                        saved = _save_temp_file(fp, project_id, "image", "extract_keyframe",
                                                file_name=os.path.basename(fp))
                        saved_frames.append(saved.get("web_path", fp) if saved else fp)
                    else:
                        saved_frames.append(fp)
                frames = saved_frames
            return {
                "success": True,
                "frames": frames,
                "count": len(frames),
                "mode": mode,
                "message": f"使用 {mode} 模式提取了 {len(frames)} 个关键帧",
            }
    except Exception as e:
        logger.error(f"关键帧提取失败: {e}")
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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = _make_temp_output(".gif", video_id)

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
                duration=duration_param,
                output_path=output_path
            )

            return _save_tool_output(output_path, video_id, "gif",
                                     kwargs.get("project_id"),
                                     file_type="image",
                                     file_name=f"gif_{video_id}_{int(time.time())}.gif",
                                     message="GIF 生成完成")

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
    import os, tempfile
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.application.services import dh_live_adapter

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)

            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = tempfile.mkdtemp(prefix="synthetix_separated_")
            audio_path = os.path.join(output_dir, "original.wav")
            ffmpeg.extract_audio(video.local_path, audio_path)

            dh_live_adapter.do_s(audio_path, output_dir)

            project_id = kwargs.get("project_id")
            saved_files = []
            for f in os.listdir(output_dir):
                if f == "original.wav":
                    continue
                fp = os.path.join(output_dir, f)
                if os.path.isfile(fp):
                    if project_id:
                        saved = _save_temp_file(fp, project_id, "audio", "separate_vocal",
                                                file_name=f)
                        if saved:
                            saved_files.append(saved)
                    else:
                        saved_files.append({"path": fp, "file_name": f})

            if project_id and saved_files:
                return {
                    "success": True,
                    "files": saved_files,
                    "message": "人声分离完成，已生成人声和伴奏文件"
                }
            return {
                "success": True,
                "output_dir": output_dir,
                "message": "人声分离完成，已生成人声和伴奏文件"
            }

    except Exception as e:
        logger.error(f"人声分离失败: {e}")
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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_path = _make_temp_output(".wav", video_id)
            ffmpeg.get_audio(video.local_path, output_path)

            return _save_tool_output(output_path, video_id, "extract_audio",
                                     kwargs.get("project_id"),
                                     file_type="audio",
                                     file_name=f"audio_{video_id}_{int(time.time())}.wav",
                                     message="音频提取完成")

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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            # 将 web_path 或相对路径转为绝对文件系统路径
            def _resolve_audio_path(p):
                if not p:
                    return p
                if os.path.isabs(p):
                    return p
                abs_p = os.path.join(str(config.ROOT_DIR_WIN), p.lstrip('/'))
                if os.path.isfile(abs_p):
                    return abs_p
                return os.path.abspath(p.lstrip('/'))

            abs_tts = _resolve_audio_path(tts_path)
            abs_bgm = _resolve_audio_path(bgm_path)

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.mix_audios_to_video(
                video_path=video.local_path,
                tts_path=abs_tts,
                bgm_path=abs_bgm,
                bgm_volume=bgm_volume,
                output_path=output_path
            )

            return _save_tool_output(output_path, video_id, "mix_audio",
                                     kwargs.get("project_id"),
                                     file_name=f"mixed_{video_id}_{int(time.time())}{ext}",
                                     message="音频混合完成")

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
    before_execute=validate_video_exists,
    permission="read_only"
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
    import os, tempfile
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            output_dir = tempfile.mkdtemp(prefix="synthetix_clips_")

            ffmpeg.extract_video_clips(video.local_path, output_dir, interval)

            clips = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]
            project_id = kwargs.get("project_id")
            if project_id and clips:
                saved_clips = []
                for clip_name in clips:
                    clip_path = os.path.join(output_dir, clip_name)
                    saved = _save_temp_file(clip_path, project_id, "video", "split_video",
                                            file_name=clip_name)
                    if saved:
                        saved_clips.append(saved)
                return {
                    "success": True,
                    "clips": saved_clips,
                    "clips_count": len(saved_clips),
                    "message": f"已拆分为 {len(saved_clips)} 个片段（每段 {interval} 秒）"
                }

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
    examples=["有哪些音色", "列出可用的声音"],
    permission="read_only",
    category="common",
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
    examples=["系统信息", "有 GPU 吗", "磁盘还剩多少"],
    permission="read_only",
    category="common",
)
async def tool_get_system_info(**kwargs) -> Dict[str, Any]:
    """获取系统信息"""
    import shutil
    import platform
    import psutil
    from src.shared.utils import ffmpeg_util
    from src import config

    try:
        # GPU 信息
        gpu_name = "无 GPU"
        gpu_vram = ""
        cuda = False
        try:
            if ffmpeg_util.check_nvidia():
                cuda = ffmpeg_util.check_cuda_support()
                # 尝试获取 GPU 型号
                import subprocess as sp
                result = sp.run(
                    ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split(',')
                    gpu_name = parts[0].strip()
                    total_vram = float(parts[1].strip())
                    used_vram = float(parts[2].strip())
                    free_vram = float(parts[3].strip())
                    gpu_vram = f"{total_vram:.0f}MB (已用 {used_vram:.0f}MB, 空闲 {free_vram:.0f}MB)"
                else:
                    gpu_name = "NVIDIA GPU 可用"
        except Exception:
            pass

        # CPU
        cpu_count = os.cpu_count() or 0
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # 内存
        mem = psutil.virtual_memory()
        mem_total_gb = mem.total / (1024 ** 3)
        mem_used_gb = mem.used / (1024 ** 3)
        mem_avail_gb = mem.available / (1024 ** 3)

        # 磁盘
        upload_dir = config.UPLOAD_DIR
        disk_parts = []
        try:
            usage = shutil.disk_usage(upload_dir)
            disk_parts.append(f"系统盘: 总 {usage.total // (1024**3)}GB, 已用 {usage.used // (1024**3)}GB, 剩余 {usage.free // (1024**3)}GB")
        except Exception:
            disk_parts.append("系统盘: 无法读取")

        # 所有磁盘概览
        for part in psutil.disk_partitions():
            try:
                du = shutil.disk_usage(part.mountpoint)
                disk_parts.append(f"{part.mountpoint} {du.free // (1024**3)}GB 可用 / {du.total // (1024**3)}GB")
            except Exception:
                pass

        # 操作系统
        os_name = platform.platform()
        python_ver = platform.python_version()

        return {
            "success": True,
            "os": os_name,
            "python": python_ver,
            "cpu": f"{cpu_count} 核, 使用率 {cpu_percent}%",
            "memory": f"总 {mem_total_gb:.1f}GB, 已用 {mem_used_gb:.1f}GB ({mem.percent}%), 可用 {mem_avail_gb:.1f}GB",
            "gpu": gpu_name,
            "gpu_vram": gpu_vram or None,
            "cuda": "支持" if cuda else "不支持",
            "disk": disk_parts,
            "message": (
                f"OS: {os_name} | Python {python_ver}\n"
                f"CPU: {cpu_count} 核 ({cpu_percent}%)\n"
                f"内存: {mem_used_gb:.1f}/{mem_total_gb:.1f}GB ({mem.percent}%)\n"
                f"GPU: {gpu_name}" + (f" | VRAM: {gpu_vram}" if gpu_vram else "") + f"\n"
                f"CUDA: {'支持' if cuda else '不支持'}\n"
                f"磁盘: {disk_parts[0]}"
            )
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
    examples=["打开输出目录", "打开素材文件夹"],
    category="common",
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
    permission="destructive",
    category="common",
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
    permission="read_only",
    category="common",
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
    permission="read_only"
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
    permission="read_only",
    category="common",
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
    permission="read_only"
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
    permission="read_only",
    category="common",
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

    brightness = max(-1.0, min(1.0, float(brightness)))
    contrast = max(0.1, min(10.0, float(contrast)))
    saturation = max(0.0, min(3.0, float(saturation)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "adjust",
                                     kwargs.get("project_id"),
                                     file_name=f"adjusted_{video_id}_{int(time.time())}{ext}",
                                     message=f"亮度={brightness} 对比度={contrast} 饱和度={saturation}")

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

    sigma = max(0.1, min(20.0, float(sigma)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"gblur=sigma={sigma}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "blur",
                                     kwargs.get("project_id"),
                                     file_name=f"blurred_{video_id}_{int(time.time())}{ext}",
                                     message=f"模糊完成 (sigma={sigma})")

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

    amount = max(0.0, min(3.0, float(amount)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"unsharp=5:5:{amount}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "sharpen",
                                     kwargs.get("project_id"),
                                     file_name=f"sharpened_{video_id}_{int(time.time())}{ext}",
                                     message=f"锐化完成 (强度={amount})")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "rotate",
                                     kwargs.get("project_id"),
                                     file_name=f"rotated_{video_id}_{int(time.time())}{ext}",
                                     message=f"已旋转 {angle} 度")

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

    vf = "hflip" if direction == "horizontal" else "vflip"

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            dir_desc = "水平" if direction == "horizontal" else "垂直"
            return _save_tool_output(output_path, video_id, "flip",
                                     kwargs.get("project_id"),
                                     file_name=f"flipped_{video_id}_{int(time.time())}{ext}",
                                     message=f"已{dir_desc}翻转")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"crop={width}:{height}:{x}:{y}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "crop",
                                     kwargs.get("project_id"),
                                     file_name=f"cropped_{video_id}_{int(time.time())}{ext}",
                                     message=f"裁剪完成 {width}x{height}+{x}+{y}")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', vf,
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "fade",
                                     kwargs.get("project_id"),
                                     file_name=f"faded_{video_id}_{int(time.time())}{ext}",
                                     message=f"淡入{fade_in}秒 淡出{fade_out}秒")

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

            ext = os.path.splitext(main_video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y',
                '-i', main_video.local_path,
                '-i', overlay_video.local_path,
                '-filter_complex', f"[1:v]scale={sw}:{sh}[pi];[0:v][pi]overlay={x}:{y}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "pip",
                                     kwargs.get("project_id"),
                                     file_name=f"pip_{video_id}_{int(time.time())}{ext}",
                                     message=f"画中画完成 叠加大小{sw}x{sh}")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y',
                '-i', video.local_path,
                '-i', watermark_path,
                '-filter_complex', filter_complex,
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "watermark",
                                     kwargs.get("project_id"),
                                     file_name=f"watermarked_{video_id}_{int(time.time())}{ext}",
                                     message=f"水印已添加 (位置: {position})")

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

    # 转义特殊字符防止命令注入
    safe_text = re.sub(r'[\'\"\\:;]', '', text)

    try:
        # 防护空值参数
        if not isinstance(x, (int, float)) or not x:
            x = 10
        if not isinstance(y, (int, float)) or not y:
            y = 10
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            vf_parts = f"text='{safe_text}':fontsize={fontsize}:fontcolor={fontcolor}:x={x}:y={y}"

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            font_file = _prepare_font_for_file(video.local_path)
            if font_file:
                vf_parts = f"fontfile={font_file}:" + vf_parts
            drawtext = f"drawtext={vf_parts}"

            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', drawtext,
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "text_overlay",
                                     kwargs.get("project_id"),
                                     file_name=f"text_{video_id}_{int(time.time())}{ext}",
                                     message=f"文字已叠加: {text}")

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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)

            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-filter_complex', '[0:v]reverse[v];[0:a]areverse[a]',
                '-map', '[v]', '-map', '[a]', output_path
            ])

            return _save_tool_output(output_path, video_id, "reverse",
                                     kwargs.get("project_id"),
                                     file_name=f"reversed_{video_id}_{int(time.time())}{ext}",
                                     message="倒放完成")

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
    import tempfile

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)

            # 第一步：检测抖动
            with tempfile.NamedTemporaryFile(suffix='.trf', delete=False) as tmp:
                trf_path = tmp.name

            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f'vidstabdetect=stepsize=6:shakiness=5:result={trf_path}',
                '-f', 'null', '-'
            ])

            # 第二步：应用稳定
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"vidstabtransform=input={trf_path}:smoothing={smoothing}",
                '-c:a', 'copy', output_path
            ])

            try:
                os.unlink(trf_path)
            except OSError:
                pass

            return _save_tool_output(output_path, video_id, "stabilize",
                                     kwargs.get("project_id"),
                                     file_name=f"stable_{video_id}_{int(time.time())}{ext}",
                                     message="防抖处理完成")

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
    before_execute=validate_video_exists,
    permission="read_only"
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
                '-i', video.local_path,
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

    factor = max(2.0, min(8.0, float(factor)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)

            fps = min(60, int(30 * factor))

            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-filter_complex',
                f"[0:v]minterpolate='mi_mode=mci:mc_mode=aobmc:vsbmc=1:fps={fps}',setpts={factor}*PTS[v];"
                f"[0:a]atempo={1.0/factor}[a]",
                '-map', '[v]', '-map', '[a]', output_path
            ])

            return _save_tool_output(output_path, video_id, "slowmo",
                                     kwargs.get("project_id"),
                                     file_name=f"slowmo_{video_id}_{int(time.time())}{ext}",
                                     message=f"{factor}倍慢动作完成")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-vf', f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}:gamma={gamma}",
                '-c:a', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "color",
                                     kwargs.get("project_id"),
                                     file_name=f"color_{video_id}_{int(time.time())}{ext}",
                                     message="色彩调整完成")

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

            output_path = _make_temp_output(f".{target_format}", video_id)

            # 尝试流复制（无重编码），失败则重编码
            try:
                ffmpeg.run_ffmpeg_cmd([
                    '-y', '-i', video.local_path,
                    '-c', 'copy', output_path
                ])
            except Exception:
                ffmpeg.run_ffmpeg_cmd([
                    '-y', '-i', video.local_path,
                    '-c:v', 'libx264', '-c:a', 'aac', output_path
                ])

            return _save_tool_output(output_path, video_id, "convert_format",
                                     kwargs.get("project_id"),
                                     file_name=f"converted_{video_id}_{int(time.time())}.{target_format}",
                                     message=f"已转为 {target_format} 格式")

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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', f"loudnorm=I={target_loudness}:TP=-1.5:LRA=11",
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "normalize",
                                     kwargs.get("project_id"),
                                     file_name=f"normalized_{video_id}_{int(time.time())}{ext}",
                                     message=f"音频标准化完成 (目标 {target_loudness} LUFS)")

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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', f"equalizer=f={frequency}:t=q:w={width}:g={gain}",
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "equalize",
                                     kwargs.get("project_id"),
                                     file_name=f"eq_{video_id}_{int(time.time())}{ext}",
                                     message=f"均衡器调节 {frequency}Hz +{gain}dB")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', af,
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "audio_fade",
                                     kwargs.get("project_id"),
                                     file_name=f"afaded_{video_id}_{int(time.time())}{ext}",
                                     message=f"音频淡入{fade_in}秒 淡出{fade_out}秒")

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

    decay = max(0.0, min(1.0, float(decay)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', f"aecho=0.8:0.88:{delay}:{decay}",
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "echo",
                                     kwargs.get("project_id"),
                                     file_name=f"echo_{video_id}_{int(time.time())}{ext}",
                                     message=f"回声效果已添加 (延迟{delay}ms)")

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

    noise_level = max(-80.0, min(-20.0, float(noise_level)))

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', f"afftdn=nf={noise_level}",
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "denoise",
                                     kwargs.get("project_id"),
                                     file_name=f"denoised_{video_id}_{int(time.time())}{ext}",
                                     message=f"降噪完成 (强度 {noise_level} dB)")

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

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            # asetrate 改变采样率实现变调，aresample 恢复原始采样率
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', f"asetrate=44100*{ratio},aresample=44100,atempo={1.0/ratio}",
                '-c:v', 'copy', output_path
            ])

            dir_desc = "升高" if semitones > 0 else "降低"
            return _save_tool_output(output_path, video_id, "pitch",
                                     kwargs.get("project_id"),
                                     file_name=f"pitch_{video_id}_{int(time.time())}{ext}",
                                     message=f"音调{dir_desc}{abs(semitones)}个半音")

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

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            ext = os.path.splitext(video.local_path)[1] or '.mp4'
            output_path = _make_temp_output(ext, video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video.local_path,
                '-af', 'areverse',
                '-c:v', 'copy', output_path
            ])

            return _save_tool_output(output_path, video_id, "audio_reverse",
                                     kwargs.get("project_id"),
                                     file_name=f"areversed_{video_id}_{int(time.time())}{ext}",
                                     message="音频倒放完成")

    except Exception as e:
        logger.error(f"音频倒放失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 多 Agent 协作工具 ====================

@registry.register(
    name="plan_clip",
    description="调用规划 Agent 制定专业剪辑方案（分镜、音频、时长规划）",
    parameters={
        "requirement": {"type": "string", "description": "剪辑需求描述"},
    },
    examples=["帮我规划一个30秒的产品宣传视频方案"],
    permission="read_only"
)
async def tool_plan_clip(requirement: str, **kwargs) -> Dict[str, Any]:
    """调用规划子 Agent"""
    from src.agent.multi_agent import run_sub_agent, AgentRole
    result = await run_sub_agent(AgentRole.PLANNER, task=requirement, project_id=kwargs.get("project_id"))
    return {"success": True, "plan": result}


@registry.register(
    name="review_result",
    description="调用审查 Agent 检查剪辑结果质量（技术、连贯性、同步、观感）",
    parameters={
        "content": {"type": "string", "description": "要审查的内容描述或结果"},
        "original_requirement": {"type": "string", "description": "原始需求（可选）"},
    },
    examples=["审查一下刚才的剪辑结果"],
    permission="read_only"
)
async def tool_review_result(content: str, original_requirement: str = "", **kwargs) -> Dict[str, Any]:
    """调用审查子 Agent"""
    from src.agent.multi_agent import run_sub_agent, AgentRole
    result = await run_sub_agent(
        AgentRole.REVIEWER, task=content,
        context=f"原始需求: {original_requirement}" if original_requirement else "",
        project_id=kwargs.get("project_id"),
    )
    return {"success": True, "review": result}


# ==================== 知识库 RAG 工具 ====================

@registry.register(
    name="knowledge_search",
    description="搜索项目知识库，查找相关的素材分析、文档记录等",
    parameters={
        "query": {"type": "string", "description": "搜索关键词"},
        "top_k": {"type": "integer", "description": "返回结果数量（默认5）"},
    },
    examples=["搜索关于海边素材的分析记录"],
    permission="read_only",
    category="common",
)
async def tool_knowledge_search(query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
    """搜索知识库"""
    from src.agent.knowledge_base import get_knowledge_base
    pid = kwargs.get("project_id")
    if not pid:
        return {"success": False, "error": "缺少 project_id"}
    kb = get_knowledge_base(pid)
    results = kb.search(query, top_k)
    return {"success": True, "results": results, "count": len(results)}


@registry.register(
    name="knowledge_add",
    description="向项目知识库添加文档记录（素材分析结果、备注等）",
    parameters={
        "content": {"type": "string", "description": "文档内容"},
        "source": {"type": "string", "description": "来源说明（可选）"},
        "tags": {"type": "array", "description": "标签（可选）", "items": {"type": "string"}},
    },
    examples=["记录一下这个视频的分析结果"],
    category="common",
)
async def tool_knowledge_add(content: str, source: str = "", tags: list = None, **kwargs) -> Dict[str, Any]:
    """添加文档到知识库"""
    from src.agent.knowledge_base import get_knowledge_base
    pid = kwargs.get("project_id")
    if not pid:
        return {"success": False, "error": "缺少 project_id"}
    kb = get_knowledge_base(pid)
    kb.add(content, source, tags)
    return {"success": True, "message": "已添加到知识库"}


# ==================== 联网搜索工具（通过 core-nexus-ai） ====================

@registry.register(
    name="search_online",
    description="联网搜索互联网信息（通过 AI 服务端搜索）。支持实时新闻、百科、科技等各类信息查询。",
    parameters={
        "query": {"type": "string", "description": "搜索关键词或问题"},
    },
    examples=["搜索今天的新闻", "查一下 xxx 是什么", "2026年5月科技热点"],
    permission="read_only",
    category="common",
)
async def tool_search_online(query: str, **kwargs) -> Dict[str, Any]:
    """联网搜索（通过 core-nexus-ai 的 enable_search 能力）"""
    from src.shared.utils.config_manager import get as cfg_get

    if not cfg_get("web_search.enabled"):
        return {"success": False, "error": "联网搜索未启用，请在设置中开启"}

    try:
        from src.application.services.llm_adapter import generate_response_async
        answer = await generate_response_async(
            messages=[{"role": "user", "content": query}],
            enable_search=True,
        )
        # 从 last_response 获取搜索引用
        from src.shared.utils.core_nexus_client import get_client
        client = get_client()
        last = client.last_response or {}
        output = last.get("output", {})
        search_results = output.get("search_results", [])

        result = {
            "success": True,
            "query": query,
            "answer": answer,
            "search_results": search_results,
            "message": f"搜索完成，找到 {len(search_results)} 条引用" if search_results else "搜索完成",
        }
        return result
    except Exception as e:
        logger.error(f"联网搜索失败: {e}")
        return {"success": False, "error": f"搜索失败: {e}"}


# ==================== CDP 浏览器自动化工具 ====================

@registry.register(
    name="browser_navigate",
    description="在浏览器中打开指定 URL（需要 Chrome 开启远程调试端口）。可用于搜索素材、浏览网页。",
    parameters={
        "url": {"type": "string", "description": "要打开的网页 URL"},
        "wait_ms": {"type": "integer", "description": "等待页面加载时间（毫秒），默认 2000"},
    },
    examples=[
        "帮我打开 Pexels 搜索猫咪视频",
        "在浏览器里打开这个网页",
    ],
    permission="read_only"
)
async def tool_browser_navigate(url: str, wait_ms: int = 2000, **kwargs) -> Dict[str, Any]:
    """浏览器导航"""
    from src.shared.utils.cdp_browser import get_cdp_browser
    try:
        browser = get_cdp_browser()
        return await browser.navigate(url, wait_ms)
    except Exception as e:
        return {"success": False, "error": f"浏览器操作失败: {e}。请确保 Chrome 以 --remote-debugging-port=9222 启动。"}


@registry.register(
    name="browser_screenshot",
    description="截取当前浏览器页面截图。可用于查看网页内容、确认页面状态。",
    parameters={
        "save_path": {"type": "string", "description": "截图保存路径（可选，默认保存到 static/ 目录）"},
        "full_page": {"type": "boolean", "description": "是否截取完整页面，默认 false"},
    },
    examples=["截个图看看当前页面"],
    permission="read_only"
)
async def tool_browser_screenshot(save_path: str = None, full_page: bool = False, **kwargs) -> Dict[str, Any]:
    """浏览器截图"""
    from src.shared.utils.cdp_browser import get_cdp_browser
    try:
        browser = get_cdp_browser()
        if not save_path:
            import time
            import os
            save_path = _make_temp_output(".png", 0)
        result = await browser.screenshot(save_path, full_page)
        # If screenshot was successful, try to save to project temp dir
        if isinstance(result, dict) and result.get("success") and kwargs.get("project_id"):
            saved = _save_tool_output(save_path, 0, "screenshot",
                                     kwargs.get("project_id"),
                                     file_type="image",
                                     file_name=f"browser_screenshot_{int(time.time())}.png")
            if saved.get("web_path"):
                result["web_path"] = saved["web_path"]
                result["temp_file_id"] = saved.get("temp_file_id")
        return result
    except Exception as e:
        return {"success": False, "error": f"截图失败: {e}"}


@registry.register(
    name="browser_get_content",
    description="获取当前浏览器页面的文本内容。可用于提取网页信息、搜索结果。",
    parameters={},
    examples=["读取当前页面内容", "提取网页文字"],
    permission="read_only"
)
async def tool_browser_get_content(**kwargs) -> Dict[str, Any]:
    """获取页面内容"""
    from src.shared.utils.cdp_browser import get_cdp_browser
    try:
        browser = get_cdp_browser()
        return await browser.get_content()
    except Exception as e:
        return {"success": False, "error": f"获取内容失败: {e}"}


@registry.register(
    name="browser_get_links",
    description="提取当前浏览器页面所有链接。可用于查找下载资源、相关页面。",
    parameters={},
    examples=["列出页面上的所有链接"],
    permission="read_only"
)
async def tool_browser_get_links(**kwargs) -> Dict[str, Any]:
    """获取页面链接"""
    from src.shared.utils.cdp_browser import get_cdp_browser
    try:
        browser = get_cdp_browser()
        return await browser.get_page_links()
    except Exception as e:
        return {"success": False, "error": f"获取链接失败: {e}"}


@registry.register(
    name="browser_execute_js",
    description="在浏览器页面中执行 JavaScript 代码。高级操作，可用于自定义页面交互。",
    parameters={
        "expression": {"type": "string", "description": "要执行的 JavaScript 代码"},
    },
    examples=["在页面上执行一段 JS"],
    permission="modify"
)
async def tool_browser_execute_js(expression: str, **kwargs) -> Dict[str, Any]:
    """执行 JS"""
    from src.shared.utils.cdp_browser import get_cdp_browser
    try:
        browser = get_cdp_browser()
        return await browser.execute_js(expression)
    except Exception as e:
        return {"success": False, "error": f"JS 执行失败: {e}"}


# ==================== Comic Drama Tools ====================

@registry.register(
    name="comic_generate_script",
    description="根据创意描述生成漫剧脚本，包含角色定义、分镜列表、对白和旁白。返回完整的脚本结构。",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "description": {"type": "string", "description": "故事设定/大纲，如'3分钟校园恋爱故事'"},
        "genre": {"type": "string", "description": "类型: drama/comedy/action/romance/mystery/fantasy", "default": "drama"},
        "num_panels": {"type": "integer", "description": "分镜数量 (3-50)", "default": 10},
        "characters": {"type": "array", "description": "角色定义列表（可选）", "default": None},
    },
    examples=["帮我生成一个10个分镜的校园恋爱漫剧脚本", "创建一个悬疑漫剧，8个分镜"],
    permission="modify",
    category="comic",
)
async def tool_comic_generate_script(
    project_id: int, description: str, genre: str = "drama",
    num_panels: int = 10, characters: list = None, **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.application.services.llm_adapter import generate_response
    from src.shared.utils.string_util import remove_think_tags
    import json, re
    try:
        characters_str = "未指定"
        if characters:
            characters_str = "\n".join([
                f"- {c.get('name', '?')}: {c.get('appearance', '?')}"
                for c in characters
            ])

        prompt = f"""你是一个专业的漫剧编剧。请根据以下信息生成漫剧脚本。

故事设定: {description}
类型: {genre}
分镜数量: {num_panels}
角色: {characters_str}

请严格按照以下 JSON 格式输出（不要用 ```json 标记）:
{{
  "title": "标题",
  "synopsis": "简介",
  "genre": "{genre}",
  "scenes": [
    {{
      "sequence": 0,
      "scene_description": "详细场景视觉描述（用于AI图片生成）",
      "background_description": "背景描述",
      "characters": ["角色名"],
      "dialogues": [{{"character_id": "角色名", "text": "台词", "emotion": "开心"}}],
      "narration": null,
      "emotion": "neutral",
      "duration": 3.0,
      "transition": "cut",
      "camera": "中景"
    }}
  ],
  "bgm_prompt": "BGM风格描述"
}}"""

        result_text = generate_response([{"role": "user", "content": prompt}])
        result_text = remove_think_tags(result_text).strip()

        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if not json_match:
            return {"success": False, "error": "AI 返回格式异常"}

        script_data = json.loads(json_match.group())

        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            project.script_data = script_data
            if script_data.get("scenes"):
                project.panels = script_data["scenes"]
            if not project.genre and script_data.get("genre"):
                project.genre = script_data["genre"]
            project.current_step = 1
            db.commit()

        return {
            "success": True,
            "title": script_data.get("title", ""),
            "num_panels": len(script_data.get("scenes", [])),
            "message": f"脚本生成成功: {script_data.get('title', '')}, 共 {len(script_data.get('scenes', []))} 个分镜",
        }
    except json.JSONDecodeError:
        return {"success": False, "error": "AI 返回 JSON 解析失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_edit_panel",
    description="编辑指定分镜的内容（场景描述、对白、时长、转场等）",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "panel_index": {"type": "integer", "description": "分镜索引（从0开始）"},
        "scene_description": {"type": "string", "description": "新的场景描述", "default": None},
        "dialogues": {"type": "array", "description": "新的对白列表", "default": None},
        "duration": {"type": "number", "description": "持续秒数", "default": None},
        "transition": {"type": "string", "description": "转场类型", "default": None},
        "emotion": {"type": "string", "description": "情绪", "default": None},
    },
    examples=["修改第3个分镜的场景描述", "把分镜5的时长改为5秒"],
    permission="modify",
    category="comic",
)
async def tool_comic_edit_panel(
    project_id: int, panel_index: int, scene_description: str = None,
    dialogues: list = None, duration: float = None, transition: str = None,
    emotion: str = None, **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    try:
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if panel_index < 0 or panel_index >= len(panels):
                return {"success": False, "error": f"分镜索引 {panel_index} 越界"}
            panel = panels[panel_index]
            if scene_description is not None:
                panel["scene_description"] = scene_description
            if dialogues is not None:
                panel["dialogues"] = dialogues
            if duration is not None:
                panel["duration"] = duration
            if transition is not None:
                panel["transition"] = transition
            if emotion is not None:
                panel["emotion"] = emotion
            project.panels = panels
            db.commit()
        return {"success": True, "message": f"分镜 {panel_index} 已更新"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_generate_image",
    description="为指定分镜生成画面图片（通过 AI 文生图）",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "panel_index": {"type": "integer", "description": "分镜索引（从0开始）"},
    },
    examples=["生成分镜1的画面图片", "为第3个分镜生成图片"],
    permission="modify",
    category="comic",
)
async def tool_comic_generate_image(project_id: int, panel_index: int, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.shared.utils.core_nexus_client import get_client
    try:
        client = get_client()
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if panel_index < 0 or panel_index >= len(panels):
                return {"success": False, "error": f"分镜索引 {panel_index} 越界"}
            panel = panels[panel_index]
            prompt = panel.get("scene_description", "")
            style = project.style or "动漫"
            style_map = {
                "动漫": "anime style, high quality, detailed",
                "写实": "photorealistic, cinematic lighting, 8k",
                "水墨": "chinese ink painting style, elegant",
                "像素": "pixel art style, retro game aesthetic",
                "美漫": "western comic style, bold lines, vibrant colors",
            }
            full_prompt = f"{style_map.get(style, 'anime style')}, {prompt}"
            result = await client.text_to_image_async(prompt=full_prompt)
            if result.get("status") == "stub":
                return {"success": False, "error": "图片生成服务尚未就绪"}
            image_path = result.get("image_url") or result.get("image_path")
            if image_path:
                panel["generated_image_path"] = image_path
                project.panels = panels
                db.commit()
        return {"success": True, "image_path": image_path, "message": f"分镜 {panel_index} 图片已生成"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_generate_video",
    description="为指定分镜生成动态视频（通过 AI 图/文生视频）",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "panel_index": {"type": "integer", "description": "分镜索引（从0开始）"},
        "duration": {"type": "number", "description": "视频时长（秒）", "default": 3.0},
    },
    examples=["为分镜2生成3秒动态视频"],
    permission="modify",
    category="comic",
)
async def tool_comic_generate_video(
    project_id: int, panel_index: int, duration: float = 3.0, **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.shared.utils.core_nexus_client import get_client
    try:
        client = get_client()
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if panel_index < 0 or panel_index >= len(panels):
                return {"success": False, "error": f"分镜索引 {panel_index} 越界"}
            panel = panels[panel_index]
            prompt = panel.get("scene_description", "")
            ref_image = panel.get("generated_image_path")
            result = await client.text_to_video_async(
                prompt=prompt, duration=duration, ref_image=ref_image
            )
            if result.get("status") == "stub":
                return {"success": False, "error": "视频生成服务尚未就绪"}
            video_path = result.get("video_url") or result.get("video_path")
            if video_path:
                panel["generated_video_path"] = video_path
                project.panels = panels
                db.commit()
        return {"success": True, "video_path": video_path, "message": f"分镜 {panel_index} 视频已生成"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_generate_audio",
    description="为指定分镜的对白生成 TTS 语音",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "panel_index": {"type": "integer", "description": "分镜索引（从0开始）"},
        "text": {"type": "string", "description": "要合成语音的文本", "default": None},
        "voice_id": {"type": "string", "description": "TTS speaker ID", "default": None},
    },
    examples=["为分镜1的对白生成语音", "生成分镜3的旁白音频"],
    permission="modify",
    category="comic",
)
async def tool_comic_generate_audio(
    project_id: int, panel_index: int, text: str = None,
    voice_id: str = None, **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.shared.utils.core_nexus_client import get_client
    import base64, uuid, os
    from src import config
    try:
        client = get_client()
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if panel_index < 0 or panel_index >= len(panels):
                return {"success": False, "error": f"分镜索引 {panel_index} 越界"}
            panel = panels[panel_index]
            if not text:
                dialogues = panel.get("dialogues") or []
                text = " ".join([d.get("text", "") for d in dialogues])
            if not text:
                return {"success": False, "error": "没有可用的文本内容"}

            audio_bytes = await client.tts_generate_async(text=text, speaker=voice_id)
            if audio_bytes:
                upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
                os.makedirs(upload_dir, exist_ok=True)
                save_name = f"panel_{panel_index}_{uuid.uuid4().hex[:8]}.wav"
                file_path = os.path.join(upload_dir, save_name)
                with open(file_path, "wb") as f:
                    f.write(audio_bytes if isinstance(audio_bytes, bytes) else base64.b64decode(audio_bytes))
                audio_paths = panel.get("generated_audio_paths") or []
                audio_paths.append(f"static/projects/{project_id}/{save_name}")
                panel["generated_audio_paths"] = audio_paths
                project.panels = panels
                db.commit()
            return {"success": True, "message": f"分镜 {panel_index} 语音已生成"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_add_character",
    description="为漫剧项目添加角色定义",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "name": {"type": "string", "description": "角色名称"},
        "appearance": {"type": "string", "description": "外貌描述", "default": ""},
        "gender": {"type": "string", "description": "性别", "default": None},
        "personality": {"type": "string", "description": "性格特点", "default": ""},
    },
    examples=["添加一个角色：小红，活泼的女生"],
    permission="modify",
    category="comic",
)
async def tool_comic_add_character(
    project_id: int, name: str, appearance: str = "", gender: str = None,
    personality: str = "", **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    import uuid
    try:
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            characters = project.characters or []
            characters.append({
                "id": str(uuid.uuid4())[:8],
                "name": name,
                "appearance": appearance,
                "gender": gender,
                "personality": personality,
            })
            project.characters = characters
            db.commit()
        return {"success": True, "message": f"角色 '{name}' 已添加"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_remove_panel",
    description="删除指定分镜",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "panel_index": {"type": "integer", "description": "要删除的分镜索引（从0开始）"},
    },
    examples=["删除第3个分镜"],
    permission="modify",
    category="comic",
)
async def tool_comic_remove_panel(project_id: int, panel_index: int, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    try:
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if panel_index < 0 or panel_index >= len(panels):
                return {"success": False, "error": f"分镜索引 {panel_index} 越界"}
            removed = panels.pop(panel_index)
            for i, p in enumerate(panels):
                p["sequence"] = i
            project.panels = panels
            db.commit()
        return {"success": True, "message": f"分镜 {panel_index} 已删除，剩余 {len(panels)} 个分镜"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_reorder_panels",
    description="重新排列分镜顺序",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "new_order": {"type": "array", "description": "新的分镜索引顺序，如 [2,0,1] 表示原第3个分镜排第一"},
    },
    examples=["把分镜顺序调整为 [2,0,1]"],
    permission="modify",
    category="comic",
)
async def tool_comic_reorder_panels(project_id: int, new_order: list, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    try:
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            panels = project.panels or []
            if len(new_order) != len(panels):
                return {"success": False, "error": "新顺序长度与分镜数不匹配"}
            reordered = [panels[i] for i in new_order]
            for i, p in enumerate(reordered):
                p["sequence"] = i
            project.panels = reordered
            db.commit()
        return {"success": True, "message": f"分镜顺序已调整为 {new_order}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_compose",
    description="将所有分镜素材合成最终漫剧视频（图片序列+音频+BGM+字幕）",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
    },
    examples=["合成漫剧视频"],
    permission="destructive",
    category="comic",
)
async def tool_comic_compose(project_id: int, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.application.services.comic_composer import ComicComposer
    from datetime import datetime as dt
    try:
        with get_db_context() as db:
            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            project.status = "compositing"
            db.commit()

            composer = ComicComposer()
            result = composer.compose(
                panels=project.panels or [],
                bgm_config=project.bgm_config or {},
                project_id=project_id,
            )

            if not result.get("success"):
                project.status = "draft"
                db.commit()
                return {"success": False, "error": result.get("error", "合成失败")}

            video_entry = {"path": result["output_path"], "created_at": dt.utcnow().isoformat()}
            output_videos = project.output_videos or []
            output_videos.append(video_entry)
            project.output_videos = output_videos
            project.status = "completed"
            db.commit()

        return {"success": True, "output_path": result["output_path"], "message": "漫剧视频合成完成"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="comic_select_bgm",
    description="为漫剧项目选择或生成 BGM",
    parameters={
        "project_id": {"type": "integer", "description": "漫剧项目 ID"},
        "bgm_id": {"type": "integer", "description": "已有 BGM 的 ID（可选）", "default": None},
        "bgm_description": {"type": "string", "description": "BGM 风格描述（用于 AI 生成）", "default": None},
        "volume": {"type": "number", "description": "音量 (0-1)", "default": 0.3},
    },
    examples=["为漫剧选择轻快的 BGM", "AI 生成一段紧张的背景音乐"],
    permission="modify",
    category="comic",
)
async def tool_comic_select_bgm(
    project_id: int, bgm_id: int = None, bgm_description: str = None,
    volume: float = 0.3, **kwargs
) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.comic_project import ComicProject
    from src.domain.entities.bgm_item import BGMItem
    try:
        bgm_path = None
        with get_db_context() as db:
            if bgm_id:
                bgm = db.query(BGMItem).filter(BGMItem.id == bgm_id).first()
                if bgm:
                    bgm_path = bgm.web_path

            bgm_config = {"volume": volume}
            if bgm_path:
                bgm_config["path"] = bgm_path
            if bgm_description:
                bgm_config["description"] = bgm_description

            project = db.query(ComicProject).get(project_id)
            if not project:
                return {"success": False, "error": f"项目 {project_id} 不存在"}
            project.bgm_config = bgm_config
            db.commit()

        return {"success": True, "message": "BGM 配置已更新"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 质量检测工具 ──

class QualityCheckParams(BaseModel):
    video_id: Opt[int] = Field(default=None, description="视频 ID（用于黑屏/爆音检测）")
    project_id: Opt[int] = Field(default=None, description="项目 ID（用于时长合规检测）")


@registry.register(
    name="quality_check",
    description="视频质量检测：检查黑屏、爆音、跳切、时长合规等问题",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID（可选）"},
        "project_id": {"type": "integer", "description": "项目 ID（可选，检测方案片段时长合规）"},
    },
    examples=["检查视频质量", "检测这个视频有没有黑屏或爆音", "质量评分"],
    param_model=QualityCheckParams,
    permission="read_only"
)
async def tool_quality_check(
    video_id: int = None,
    project_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """视频质量检测工具"""
    from src.application.services.quality_service import run_quality_check
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.domain.entities.video_project import VideoProject

    try:
        video_path = None
        clips = None
        target_duration = None

        with get_db_context() as db:
            if video_id:
                repo = VideoRepository(db)
                video = repo.get_by_id(video_id)
                if video:
                    video_path = video.local_path

            if project_id:
                proj = db.query(VideoProject).filter(VideoProject.id == project_id).first()
                if proj:
                    target_duration = proj.target_duration
                    if proj.plan_data and proj.plan_data.get("clips"):
                        clips = proj.plan_data["clips"]

        result = run_quality_check(
            video_path=video_path,
            clips=clips,
            target_duration=target_duration,
        )

        return {
            "success": True,
            "quality": result,
            "message": result["summary"],
        }
    except Exception as e:
        logger.error(f"质量检测失败: {e}")
        return {"success": False, "error": str(e)}


# ── 多信号高光检测工具 ──

class DiarizeSpeakersParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    num_speakers: Opt[int] = Field(default=None, ge=1, le=20, description="预期说话人数量（可选）")


@registry.register(
    name="diarize_speakers",
    description="对视频音频进行说话人分离，返回每段语音的说话人 ID + 时间范围",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "num_speakers": {"type": "integer", "description": "预期说话人数量（可选）"},
    },
    examples=["识别这个视频有几个说话人", "分离说话人", "谁在说话"],
    param_model=DiarizeSpeakersParams,
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_diarize_speakers(
    video_id: int,
    num_speakers: int = None,
    **kwargs
) -> Dict[str, Any]:
    """说话人分离工具"""
    from src.application.services import whisper_adapter, ffmpeg_adapter
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.shared.utils.result_cache import get_cached, set_cached

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            audio_path = video.local_path
            cache_key = {"num": num_speakers or 0}
            cached = get_cached(audio_path, "diarize", ttl=3600 * 4, **cache_key)
            if cached is not None:
                return {"success": True, "segments": cached, "message": f"检测到 {len(set(s['speaker'] for s in cached))} 个说话人（缓存）"}

            # Use ASR to get segments, then cluster by timing gaps
            proxy_path = ffmpeg_adapter.generate_proxy(audio_path)
            srt_text = whisper_adapter.transcribe(
                audio_path=audio_path, output_format_type="srt", proxy_path=proxy_path,
            )

            if not srt_text:
                return {"success": False, "error": "ASR 转录失败，无法进行说话人分离"}

            # Parse SRT and assign speakers based on pause patterns
            import re
            segments = []
            blocks = re.split(r'\n\n+', srt_text.strip())
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    time_match = re.match(r'(\d{2}:\d{2}:\d{2}),\d{3}\s*-->\s*(\d{2}:\d{2}:\d{2}),\d{3}', lines[1])
                    if time_match:
                        start = whisper_adapter._parse_srt_time(time_match.group(1))
                        end = whisper_adapter._parse_srt_time(time_match.group(2))
                        text = ' '.join(lines[2:])
                        segments.append({"start": round(start, 2), "end": round(end, 2), "text": text})

            # Simple speaker diarization: assign speaker based on pause gaps
            speaker_segments = _assign_speakers(segments, num_speakers)
            set_cached(audio_path, "diarize", speaker_segments, **cache_key)

            unique_speakers = len(set(s["speaker"] for s in speaker_segments))
            return {
                "success": True,
                "segments": speaker_segments,
                "num_speakers": unique_speakers,
                "message": f"检测到 {unique_speakers} 个说话人，{len(speaker_segments)} 个片段",
            }
    except Exception as e:
        logger.error(f"说话人分离失败: {e}")
        return {"success": False, "error": str(e)}


def _assign_speakers(segments: list, num_speakers: int = None) -> list:
    """基于停顿间隔的简单说话人分配"""
    if not segments:
        return []

    PAUSE_THRESHOLD = 1.5  # seconds — long pause likely means speaker change
    speakers = ["spk0"]
    results = []
    current_speaker = "spk0"

    for i, seg in enumerate(segments):
        if i > 0:
            gap = seg["start"] - segments[i - 1]["end"]
            if gap >= PAUSE_THRESHOLD:
                # Speaker change
                idx = len(speakers)
                if num_speakers and idx >= num_speakers:
                    current_speaker = speakers[idx % len(speakers)]
                else:
                    current_speaker = f"spk{idx}"
                    speakers.append(current_speaker)

        results.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "speaker": current_speaker,
        })

    return results


class DetectSilenceParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    min_duration: float = Field(default=0.5, ge=0.1, le=10.0, description="最短静音时长(秒)")
    noise_db: int = Field(default=-30, ge=-60, le=0, description="噪声阈值(dB)")


@registry.register(
    name="detect_silence",
    description="检测视频中的静音段，返回静音开始/结束时间",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "min_duration": {"type": "number", "description": "最短静音时长(秒)，默认 0.5"},
        "noise_db": {"type": "integer", "description": "噪声阈值(dB)，默认 -30"},
    },
    examples=["检测这个视频的静音段", "找出没有声音的部分"],
    param_model=DetectSilenceParams,
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_detect_silence(
    video_id: int,
    min_duration: float = 0.5,
    noise_db: int = -30,
    **kwargs
) -> Dict[str, Any]:
    """静音检测工具"""
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}
            silences = ffmpeg.detect_silence_segments(video.local_path, min_duration, noise_db)
            return {
                "success": True,
                "silences": silences,
                "count": len(silences),
                "message": f"检测到 {len(silences)} 段静音"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


class DetectSceneChangeParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    threshold: float = Field(default=0.3, ge=0.01, le=1.0, description="场景切换敏感度(0-1)")


@registry.register(
    name="detect_scene_change",
    description="检测视频中的场景切换点，返回切换时间列表",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "threshold": {"type": "number", "description": "敏感度(0-1)，默认 0.3"},
    },
    examples=["检测场景切换", "找出画面变化的点"],
    param_model=DetectSceneChangeParams,
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_detect_scene_change(
    video_id: int,
    threshold: float = 0.3,
    **kwargs
) -> Dict[str, Any]:
    """场景切换检测工具"""
    from src.application.services import ffmpeg_adapter as ffmpeg
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}
            changes = ffmpeg.detect_scene_changes(video.local_path, threshold)
            return {
                "success": True,
                "changes": changes,
                "count": len(changes),
                "message": f"检测到 {len(changes)} 个场景切换点"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 缓存管理工具 ──

@registry.register(
    name="manage_cache",
    description="管理分析结果缓存（查看统计、清除缓存）",
    parameters={
        "action": {"type": "string", "description": "操作: stats/clear", "enum": ["stats", "clear"]},
        "prefix": {"type": "string", "description": "缓存类型: ffprobe/asr/vl（clear 时可选，不指定则全部清除）"},
    },
    examples=["查看缓存统计", "清除所有缓存", "清除 ASR 缓存"],
    permission="destructive"
)
async def tool_manage_cache(
    action: str = "stats",
    prefix: str = None,
    **kwargs
) -> Dict[str, Any]:
    """缓存管理工具"""
    from src.shared.utils.result_cache import cache_stats, clear_cache

    try:
        if action == "stats":
            stats = cache_stats()
            return {
                "success": True,
                "stats": stats,
                "message": f"缓存统计: {stats['count']} 条, {stats['total_size_mb']} MB"
            }
        elif action == "clear":
            clear_cache(prefix)
            label = f"{prefix} 缓存" if prefix else "所有缓存"
            return {"success": True, "message": f"{label}已清除"}
        else:
            return {"success": False, "error": f"未知操作: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 批量处理工具 ──

class BatchCutParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    segments: list = Field(..., description="剪切片段列表 [{start_time, end_time}]")


@registry.register(
    name="batch_cut",
    description="批量剪切视频片段，一次性提取多个时间段",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "segments": {"type": "array", "description": "片段列表 [{start_time, end_time}]"},
    },
    param_model=BatchCutParams,
    before_execute=validate_video_exists,
    permission="modify"
)
async def tool_batch_cut(
    video_id: int,
    segments: list,
    **kwargs,
) -> Dict[str, Any]:
    """批量剪切"""
    from src.application.services import ffmpeg_adapter
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    if not segments:
        return {"success": False, "error": "未提供剪切片段"}

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            project_id = kwargs.get("project_id")
            results = []
            for i, seg in enumerate(segments):
                start = seg.get("start_time", "00:00:00")
                end = seg.get("end_time")
                if not end:
                    continue
                try:
                    out_path = _make_temp_output(f"_cut{i}.mp4", video_id)
                    output = ffmpeg_adapter.cut_video(
                        input_path=video.local_path,
                        start_time=start,
                        end_time=end,
                        output_path=out_path,
                    )
                    if project_id:
                        saved = _save_tool_output(
                            str(output), video_id, f"batch_cut_{i}",
                            project_id,
                            file_type="video",
                            file_name=f"cut_{i}_{video_id}_{int(time.time())}.mp4",
                        )
                        results.append({
                            "index": i, "start": start, "end": end,
                            "path": saved.get("local_path", str(output)),
                            "web_path": saved.get("web_path"),
                            "temp_file_id": saved.get("temp_file_id"),
                            "is_temp_asset": saved.get("is_temp_asset", False),
                            "success": True,
                        })
                    else:
                        results.append({"index": i, "start": start, "end": end, "path": output, "success": True})
                except Exception as e:
                    results.append({"index": i, "start": start, "end": end, "error": str(e), "success": False})

            success_count = sum(1 for r in results if r["success"])
            return {
                "success": True,
                "results": results,
                "total": len(segments),
                "success_count": success_count,
                "message": f"批量剪切完成: {success_count}/{len(segments)} 成功",
            }
    except Exception as e:
        logger.error(f"批量剪切失败: {e}")
        return {"success": False, "error": str(e)}


class BatchAnalyzeParams(BaseModel):
    video_ids: list = Field(..., description="视频 ID 列表")
    analyze_type: str = Field(default="basic", description="分析类型: basic/transcribe")


@registry.register(
    name="batch_analyze",
    description="批量分析多个视频，支持基础信息获取和转录",
    parameters={
        "video_ids": {"type": "array", "description": "视频 ID 列表"},
        "analyze_type": {"type": "string", "description": "分析类型: basic/transcribe"},
    },
    param_model=BatchAnalyzeParams,
    permission="read_only"
)
async def tool_batch_analyze(
    video_ids: list,
    analyze_type: str = "basic",
    **kwargs,
) -> Dict[str, Any]:
    """批量分析"""
    from src.application.services import ffmpeg_adapter, whisper_adapter
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository

    results = []
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            for vid in video_ids:
                video = repo.get_by_id(vid)
                if not video:
                    results.append({"video_id": vid, "success": False, "error": "不存在"})
                    continue

                if analyze_type == "transcribe":
                    try:
                        proxy = ffmpeg_adapter.generate_proxy(video.local_path)
                        srt = whisper_adapter.transcribe(video.local_path, output_format_type="srt", proxy_path=proxy)
                        results.append({"video_id": vid, "name": video.name, "subtitle": srt, "success": True})
                    except Exception as e:
                        results.append({"video_id": vid, "success": False, "error": str(e)})
                else:
                    info = ffmpeg_adapter.get_video_info(video.local_path)
                    results.append({"video_id": vid, "name": video.name, "info": info, "success": True})

        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": True,
            "results": results,
            "total": len(video_ids),
            "success_count": success_count,
            "message": f"批量分析完成: {success_count}/{len(video_ids)} 成功",
        }
    except Exception as e:
        logger.error(f"批量分析失败: {e}")
        return {"success": False, "error": str(e)}


# ── AI 元数据生成 ──

@registry.register(
    name="generate_metadata",
    description="根据视频内容 AI 生成标题、标签、描述、推荐封面帧等平台发布元数据",
    parameters={
        "video_id": {"type": "integer", "description": "视频 ID"},
        "platform": {"type": "string", "description": "目标平台: douyin/bilibili/youtube/xiaohongshu (可选)"},
    },
    before_execute=validate_video_exists,
    permission="read_only"
)
async def tool_generate_metadata(
    video_id: int,
    platform: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """AI 生成视频发布元数据"""
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import whisper_adapter
    from src.application.services.llm_adapter import generate_response_async
    import json as _json

    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return {"success": False, "error": f"视频 {video_id} 不存在"}

            context_parts = []
            if video.description:
                context_parts.append(f"视频描述: {video.description}")
            if video.name:
                context_parts.append(f"文件名: {video.name}")

            try:
                srt = whisper_adapter.transcribe(video.local_path, output_format_type="srt")
                if srt:
                    context_parts.append(f"转录内容摘要: {srt[:1000]}")
            except Exception:
                pass

            context = "\n".join(context_parts) if context_parts else "无额外信息"
            platform_hint = f"\n目标平台: {platform}" if platform else ""

            prompt = f"""基于以下视频信息，生成适合社交媒体发布的元数据。
请以 JSON 格式返回，包含以下字段：
- title: 吸引人的标题（15-30字）
- description: 详细描述（50-150字）
- tags: 标签列表（5-10个）
- category: 内容分类
- cover_frame_second: 推荐封面帧的时间点（秒数）
{platform_hint}

视频信息：
{context}

请直接返回 JSON，不要包含其他文本。"""

            response = await generate_response_async(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=1024,
            )

            try:
                cleaned = response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
                metadata = _json.loads(cleaned)
            except (_json.JSONDecodeError, IndexError):
                metadata = {
                    "title": video.name or "未命名视频",
                    "description": response[:200],
                    "tags": [], "category": "其他", "cover_frame_second": 0,
                }

            return {
                "success": True,
                "metadata": metadata,
                "video_id": video_id,
                "message": f"已生成元数据: {metadata.get('title', '未知')}",
            }
    except Exception as e:
        logger.error(f"元数据生成失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 图片处理工具 ====================

def _get_image_info(video):
    """验证素材是图片并返回 (local_path, ext, error)"""
    if not video:
        return None, None, "素材不存在"
    ft = getattr(video, 'file_type', None) or 'video'
    if ft != 'image':
        return None, None, f"该素材不是图片（类型: {ft}），请选择图片素材"
    local = video.local_path
    if not local or not os.path.isfile(local):
        return None, None, f"图片文件不存在: {local}"
    ext = os.path.splitext(local)[1].lower()
    return local, ext, None


def _save_image_result(src_path, video_id, suffix, ext, project_id=None):
    """将处理后的图片保存（优先项目临时目录，回退素材库）"""
    if project_id:
        filename = f"img_{suffix}_{video_id}_{int(time.time())}{ext}"
        result = _save_temp_file(src_path, project_id, "image", suffix, file_name=filename)
        if result:
            result["message"] = f"图片{suffix}完成"
            return result
    # 回退：保存到素材库
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    filename = f"img_{suffix}_{video_id}_{int(time.time())}{ext}"
    dest_dir = str(config.source_videos_dir)
    dest_path = os.path.join(dest_dir, filename)
    import shutil
    shutil.move(src_path, dest_path)
    with get_db_context() as db:
        repo = VideoRepository(db)
        new_img = repo.create(
            video_name=f"图片处理_{suffix}_{video_id}",
            local_path=dest_path,
            web_path=f"/static/source_videos/{filename}",
            is_temp=True,
            file_type="image",
        )
        db.commit()
    if project_id:
        _add_material_to_project(project_id, new_img.id)
    return {
        "success": True,
        "video_id": new_img.id,
        "web_path": f"/static/source_videos/{filename}",
        "local_path": dest_path,
        "output_type": "image",
        "message": f"图片{suffix}完成",
    }


@registry.register(
    name="resize_image",
    description="缩放图片尺寸，可指定宽高（另一个维度自动等比缩放）",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "width": {"type": "integer", "description": "目标宽度（像素，0 表示按高度等比）"},
        "height": {"type": "integer", "description": "目标高度（像素，0 表示按宽度等比）"},
    },
    examples=["把图片缩放到800x600", "缩小图片宽度到500"],
    before_execute=validate_video_exists,
)
async def tool_resize_image(video_id: int, width: int = 0, height: int = 0, **kwargs) -> Dict[str, Any]:
    if width <= 0 and height <= 0:
        return {"success": False, "error": "请指定 width 或 height 至少一个"}
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            w = width if width > 0 else -1
            h = height if height > 0 else -1
            tmp_out = _make_temp_output(f"_resize{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', f'scale={w}:{h}',
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, "缩放", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片缩放失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="crop_image",
    description="裁剪图片指定区域",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "crop_width": {"type": "integer", "description": "裁剪宽度（像素）"},
        "crop_height": {"type": "integer", "description": "裁剪高度（像素）"},
        "x": {"type": "integer", "description": "起始 X 坐标（默认0）"},
        "y": {"type": "integer", "description": "起始 Y 坐标（默认0）"},
    },
    examples=["裁剪图片中心区域", "把图片裁剪到800x600"],
    before_execute=validate_video_exists,
)
async def tool_crop_image(video_id: int, crop_width: int = 0, crop_height: int = 0,
                          x: int = 0, y: int = 0, **kwargs) -> Dict[str, Any]:
    if crop_width <= 0 or crop_height <= 0:
        return {"success": False, "error": "请指定 crop_width 和 crop_height"}
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            tmp_out = _make_temp_output(f"_crop{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', f'crop={crop_width}:{crop_height}:{x}:{y}',
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, "裁剪", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片裁剪失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="rotate_image",
    description="旋转图片（90/180/270度）",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "angle": {"type": "integer", "description": "旋转角度（90/180/270，默认90）"},
    },
    examples=["把图片旋转90度", "旋转图片180度"],
    before_execute=validate_video_exists,
)
async def tool_rotate_image(video_id: int, angle: int = 90, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            if angle == 90:
                vf = 'transpose=1'
            elif angle == 180:
                vf = 'hflip,vflip'
            elif angle == 270:
                vf = 'transpose=2'
            else:
                return {"success": False, "error": "angle 仅支持 90/180/270"}
            tmp_out = _make_temp_output(f"_rotate{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', vf,
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, f"旋转{angle}度", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片旋转失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="flip_image",
    description="翻转图片（水平或垂直）",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "direction": {"type": "string", "description": "翻转方向: horizontal(水平) / vertical(垂直)，默认 horizontal"},
    },
    examples=["水平翻转图片", "垂直翻转图片"],
    before_execute=validate_video_exists,
)
async def tool_flip_image(video_id: int, direction: str = 'horizontal', **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            vf = 'hflip' if direction in ('horizontal', 'h', '水平') else 'vflip'
            tmp_out = _make_temp_output(f"_flip{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', vf,
                tmp_out
            ])
            label = "水平翻转" if vf == 'hflip' else "垂直翻转"
            return _save_image_result(tmp_out, video_id, label, ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片翻转失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="adjust_image",
    description="调整图片亮度、对比度和饱和度",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "brightness": {"type": "number", "description": "亮度 (-1.0~1.0，默认0)"},
        "contrast": {"type": "number", "description": "对比度 (0.1~10.0，默认1)"},
        "saturation": {"type": "number", "description": "饱和度 (0.0~3.0，默认1)"},
    },
    examples=["把图片调亮", "增加对比度", "降低饱和度"],
    before_execute=validate_video_exists,
)
async def tool_adjust_image(video_id: int, brightness: float = 0, contrast: float = 1.0,
                            saturation: float = 1.0, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        brightness = max(-1.0, min(1.0, float(brightness)))
        contrast = max(0.1, min(10.0, float(contrast)))
        saturation = max(0.0, min(3.0, float(saturation)))
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            tmp_out = _make_temp_output(f"_adj{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', f'eq=brightness={brightness}:contrast={contrast}:saturation={saturation}',
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, "调色", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片调色失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="blur_image",
    description="对图片应用模糊效果",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "sigma": {"type": "number", "description": "模糊强度 (0.1~20.0，默认5)"},
    },
    examples=["模糊图片", "给图片加模糊效果"],
    before_execute=validate_video_exists,
)
async def tool_blur_image(video_id: int, sigma: float = 5.0, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        sigma = max(0.1, min(20.0, float(sigma)))
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            tmp_out = _make_temp_output(f"_blur{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', f'gblur=sigma={sigma}',
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, "模糊", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片模糊失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="sharpen_image",
    description="对图片应用锐化效果",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "amount": {"type": "number", "description": "锐化强度 (0.5~5.0，默认1.5)"},
    },
    examples=["锐化图片", "让图片更清晰"],
    before_execute=validate_video_exists,
)
async def tool_sharpen_image(video_id: int, amount: float = 1.5, **kwargs) -> Dict[str, Any]:
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        amount = max(0.5, min(5.0, float(amount)))
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            tmp_out = _make_temp_output(f"_sharp{ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                '-vf', f'unsharp=5:5:{amount}',
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, "锐化", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片锐化失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="convert_image",
    description="转换图片格式（jpg/png/webp/bmp）",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "format": {"type": "string", "description": "目标格式: jpg/png/webp/bmp"},
    },
    examples=["把PNG转为JPG", "转换为WEBP格式"],
    before_execute=validate_video_exists,
)
async def tool_convert_image(video_id: int, format: str = 'jpg', **kwargs) -> Dict[str, Any]:
    fmt = format.lower().lstrip('.')
    if fmt == 'jpeg':
        fmt = 'jpg'
    if fmt not in ('jpg', 'png', 'webp', 'bmp', 'gif'):
        return {"success": False, "error": f"不支持的格式: {format}，支持 jpg/png/webp/bmp/gif"}
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            new_ext = f".{fmt}"
            tmp_out = _make_temp_output(f"_conv{new_ext}", video_id)
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', local,
                tmp_out
            ])
            return _save_image_result(tmp_out, video_id, f"转{fmt}", new_ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片格式转换失败: {e}")
        return {"success": False, "error": str(e)}


@registry.register(
    name="compress_image",
    description="压缩图片（降低质量以减小文件大小）",
    parameters={
        "video_id": {"type": "integer", "description": "图片素材 ID"},
        "quality": {"type": "integer", "description": "质量 (1~100，数字越小文件越小，默认75)"},
    },
    examples=["压缩图片", "把图片质量降到60"],
    before_execute=validate_video_exists,
)
async def tool_compress_image(video_id: int, quality: int = 75, **kwargs) -> Dict[str, Any]:
    quality = max(1, min(100, int(quality)))
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from src.application.services import ffmpeg_adapter as ffmpeg
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}
            tmp_out = _make_temp_output(f"_comp{ext}", video_id)
            cmd = ['-y', '-i', local]
            if ext in ('.jpg', '.jpeg'):
                cmd.extend(['-q:v', str(max(1, min(31, int((100 - quality) / 100 * 31 + 1))))])
            elif ext == '.png':
                cmd.extend(['-compression_level', str(max(0, min(9, int((100 - quality) / 100 * 9))))])
            cmd.append(tmp_out)
            ffmpeg.run_ffmpeg_cmd(cmd)
            return _save_image_result(tmp_out, video_id, "压缩", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片压缩失败: {e}")
        return {"success": False, "error": str(e)}


def _find_font_path() -> str:
    """查找可用的中文字体路径（绝对路径），供 Pillow 使用。"""
    # 优先项目字体目录
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_font = os.path.join(_project_root, 'static', 'fonts', 'simhei.ttf')
    if os.path.exists(project_font):
        return project_font
    # 系统字体
    import platform
    if platform.system() == 'Windows':
        fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
        for name in ['simhei.ttf', 'msyh.ttc', 'simkai.ttf', 'simsun.ttc']:
            p = os.path.join(fonts_dir, name)
            if os.path.exists(p):
                return p
    elif platform.system() == 'Darwin':
        for p in ['/System/Library/Fonts/PingFang.ttc', '/Library/Fonts/Arial Unicode.ttf']:
            if os.path.exists(p):
                return p
    else:
        for p in ['/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                   '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                   '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf']:
            if os.path.exists(p):
                return p
    return ''


def _resolve_color(color_str: str):
    """将颜色字符串转为 Pillow 可用的颜色值。"""
    from PIL import ImageColor
    try:
        return ImageColor.getrgb(color_str)
    except Exception:
        return (255, 255, 255)


@registry.register(
    name="add_text_to_image",
    description="在图片上叠加文字。重要：调整参数（改颜色/字号/位置等）时，应使用原始素材的 video_id 重新执行，而非对上一次的输出再次叠加，否则文字会重复叠加。",
    parameters={
        "video_id": {"type": "integer", "description": "原始图片素材 ID（调整参数时始终用原始素材 ID）"},
        "text": {"type": "string", "description": "要叠加的文字内容"},
        "font_size": {"type": "integer", "description": "字号（默认36）"},
        "color": {"type": "string", "description": "文字颜色，如 white、red、#FF0000（默认 white）"},
        "position": {"type": "string", "description": "位置预设：top-left/center/bottom-right 等，优先于 x/y"},
        "x": {"type": "integer", "description": "X 坐标（像素值，默认10）"},
        "y": {"type": "integer", "description": "Y 坐标（像素值，默认10）"},
        "outline_width": {"type": "integer", "description": "描边宽度（默认0，无描边）"},
        "outline_color": {"type": "string", "description": "描边颜色（默认 black）"},
    },
    examples=["在图片上写标题", "给图片加水印文字", "在右下角添加文字"],
    before_execute=validate_video_exists,
)
async def tool_add_text_to_image(video_id: int, text: str, font_size: int = 36,
                                 color: str = 'white', position: str = None,
                                 x=None, y=None, outline_width: int = 0,
                                 outline_color: str = 'black', **kwargs) -> Dict[str, Any]:
    if not text:
        return {"success": False, "error": "请输入要叠加的文字"}
    from src.infrastructure.db.session import get_db_context
    from src.infrastructure.repositories import VideoRepository
    from PIL import Image, ImageDraw, ImageFont
    try:
        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            local, ext, err = _get_image_info(video)
            if err:
                return {"success": False, "error": err}

            img = Image.open(local)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # 加载字体
            font_path = _find_font_path()
            if font_path:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except Exception:
                    font = ImageFont.load_default()
            else:
                font = ImageFont.load_default()

            fill_color = _resolve_color(color)
            stroke_color = _resolve_color(outline_color) if outline_width > 0 else None

            # 计算文字尺寸
            text_bbox = draw.textbbox((0, 0), text, font=font, stroke_width=outline_width)
            tw = text_bbox[2] - text_bbox[0]
            th = text_bbox[3] - text_bbox[1]
            margin = 10

            # 解析位置
            pos_lower = (position or '').lower().replace('_', '-')
            h_align = None  # 'left', 'center', 'right'
            v_align = None  # 'top', 'center', 'bottom'

            # 英文预设
            preset_map = {
                'top-left': ('left', 'top'), 'top-center': ('center', 'top'),
                'top-right': ('right', 'top'),
                'center-left': ('left', 'center'), 'center': ('center', 'center'),
                'center-right': ('right', 'center'),
                'bottom-left': ('left', 'bottom'), 'bottom-center': ('center', 'bottom'),
                'bottom-right': ('right', 'bottom'),
            }
            if pos_lower in preset_map:
                h_align, v_align = preset_map[pos_lower]
            elif position:
                if '右' in pos_lower or 'right' in pos_lower:
                    h_align = 'right'
                elif '左' in pos_lower or 'left' in pos_lower:
                    h_align = 'left'
                elif '中' in pos_lower or 'center' in pos_lower:
                    h_align = 'center'
                if '上' in pos_lower or 'top' in pos_lower:
                    v_align = 'top'
                elif '下' in pos_lower or 'bottom' in pos_lower:
                    v_align = 'bottom'
                elif '中' in pos_lower or 'center' in pos_lower:
                    v_align = 'center'

            # 计算 x 坐标
            if h_align == 'center':
                px = (img.width - tw) // 2
            elif h_align == 'right':
                px = img.width - tw - margin
            elif h_align == 'left':
                px = margin
            else:
                px = int(x) if x is not None else margin

            # 计算 y 坐标
            if v_align == 'center':
                py = (img.height - th) // 2
            elif v_align == 'bottom':
                py = img.height - th - margin
            elif v_align == 'top':
                py = margin
            else:
                py = int(y) if y is not None else margin

            draw.text((px, py), text, font=font, fill=fill_color,
                      stroke_width=outline_width, stroke_fill=stroke_color)

            result_img = Image.alpha_composite(img, overlay)
            tmp_out = _make_temp_output(f"_text{ext}", video_id)
            if ext in ('.jpg', '.jpeg'):
                result_img = result_img.convert('RGB')
                result_img.save(tmp_out, quality=95)
            else:
                result_img.save(tmp_out)

            return _save_image_result(tmp_out, video_id, "加文字", ext, kwargs.get("project_id"))
    except Exception as e:
        logger.error(f"图片加文字失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 本机文件操作工具 ====================

def _format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


@registry.register(
    name="list_local_files",
    description="列出本机指定目录下的文件和文件夹，可查看任意路径",
    parameters={
        "path": {"type": "string", "description": "目录路径"},
        "pattern": {"type": "string", "description": "文件名过滤，支持通配符如 *.mp4（可选）"},
        "recursive": {"type": "boolean", "description": "是否递归列出子目录内容（默认否）"},
    },
    examples=["E:\\aupi\\2 有什么文件", "列出 D:\\videos 下所有 mp4 文件"],
    permission="read_only",
    category="common",
)
async def tool_list_local_files(
    path: str,
    pattern: str = None,
    recursive: bool = False,
    **kwargs
) -> Dict[str, Any]:
    import fnmatch
    from pathlib import Path as FilePath

    try:
        target = FilePath(path).resolve()
        if not target.is_dir():
            return {"success": False, "error": f"目录不存在: {path}"}

        items = []
        if recursive:
            for root, dirs, files in os.walk(str(target)):
                for name in files + dirs:
                    full = FilePath(root) / name
                    if pattern and not fnmatch.fnmatch(name.lower(), pattern.lower()):
                        continue
                    items.append({
                        "name": name,
                        "path": str(full),
                        "type": "directory" if full.is_dir() else "file",
                        "size": _format_size(full.stat().st_size) if full.is_file() else "-",
                    })
        else:
            for item in target.iterdir():
                if pattern and not fnmatch.fnmatch(item.name.lower(), pattern.lower()):
                    continue
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": _format_size(item.stat().st_size) if item.is_file() else "-",
                })

        return {
            "success": True,
            "path": str(target),
            "items": items[:200],
            "count": len(items),
            "message": f"共 {len(items)} 个项目" + (f"（已截断前 200 项）" if len(items) > 200 else ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="read_local_file",
    description="读取本机文本文件的内容",
    parameters={
        "file_path": {"type": "string", "description": "文件完整路径"},
        "max_lines": {"type": "integer", "description": "最多读取的行数（默认 100）"},
    },
    examples=["读取 E:\\config\\settings.json 的内容", "看看 D:\\log.txt 最后 50 行"],
    permission="read_only"
)
async def tool_read_local_file(
    file_path: str,
    max_lines: int = 100,
    **kwargs
) -> Dict[str, Any]:
    from pathlib import Path as FilePath

    try:
        target = FilePath(file_path).resolve()
        if not target.is_file():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        size = target.stat().st_size
        if size > 100 * 1024:
            return {"success": False, "error": f"文件过大（{_format_size(size)}），仅支持 100KB 以内的文本文件"}

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = target.read_text(encoding="gbk")
            except UnicodeDecodeError:
                return {"success": False, "error": "无法解码文件，可能是二进制文件"}

        lines = content.splitlines()
        truncated = len(lines) > max_lines
        shown_lines = lines[:max_lines]

        return {
            "success": True,
            "file_path": str(target),
            "content": "\n".join(shown_lines),
            "total_lines": len(lines),
            "shown_lines": len(shown_lines),
            "size": _format_size(size),
            "truncated": truncated,
            "message": f"共 {len(lines)} 行，显示前 {len(shown_lines)} 行" if truncated else f"共 {len(lines)} 行",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="search_local_files",
    description="在本机指定目录中递归搜索文件",
    parameters={
        "path": {"type": "string", "description": "搜索根目录路径"},
        "keyword": {"type": "string", "description": "文件名关键词"},
        "file_type": {"type": "string", "description": "文件扩展名过滤，如 mp4、txt（可选）"},
    },
    examples=["在 E:\\aupi 里搜索所有 mp4 文件", "找找 D:\\projects 里有没有 readme"],
    permission="read_only",
    category="common",
)
async def tool_search_local_files(
    path: str,
    keyword: str = "",
    file_type: str = "",
    **kwargs
) -> Dict[str, Any]:
    import fnmatch
    from pathlib import Path as FilePath

    try:
        target = FilePath(path).resolve()
        if not target.is_dir():
            return {"success": False, "error": f"目录不存在: {path}"}

        results = []
        for root, dirs, files in os.walk(str(target)):
            for name in files:
                if keyword and keyword.lower() not in name.lower():
                    continue
                if file_type and not name.lower().endswith(f".{file_type.lower().lstrip('.')}"):
                    continue
                full = FilePath(root) / name
                results.append({
                    "name": name,
                    "path": str(full),
                    "size": _format_size(full.stat().st_size),
                })
                if len(results) >= 200:
                    break
            if len(results) >= 200:
                break

        return {
            "success": True,
            "path": str(target),
            "keyword": keyword,
            "file_type": file_type,
            "files": results,
            "count": len(results),
            "message": f"找到 {len(results)} 个文件" + ("（已达上限 200）" if len(results) >= 200 else ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="get_file_info",
    description="获取本机文件或目录的详细信息（大小、修改时间等）",
    parameters={
        "file_path": {"type": "string", "description": "文件或目录的完整路径"},
    },
    examples=["查看 E:\\video.mp4 的文件信息"],
    permission="read_only"
)
async def tool_get_file_info(
    file_path: str,
    **kwargs
) -> Dict[str, Any]:
    import datetime
    from pathlib import Path as FilePath

    try:
        target = FilePath(file_path).resolve()
        if not target.exists():
            return {"success": False, "error": f"路径不存在: {file_path}"}

        stat = target.stat()
        info = {
            "name": target.name,
            "path": str(target),
            "type": "directory" if target.is_dir() else "file",
            "size": _format_size(stat.st_size) if target.is_file() else "-",
            "size_bytes": stat.st_size,
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "created": datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        }

        if target.is_file() and target.suffix:
            info["extension"] = target.suffix

        if target.is_dir():
            child_count = sum(1 for _ in target.iterdir())
            info["child_count"] = child_count

        return {"success": True, "info": info, "message": f"文件信息: {target.name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register(
    name="rename_files",
    description="批量重命名本机文件",
    parameters={
        "renames": {"type": "array", "description": "重命名列表，每项包含 old_path 和 new_path"},
    },
    examples=["把这些文件批量重命名", "把 E:\\photos 里的 IMG_ 改成 旅行_"],
    param_model=RenameFilesParams,
    permission="destructive"
)
async def tool_rename_files(
    renames: list,
    **kwargs
) -> Dict[str, Any]:
    from pathlib import Path as FilePath

    results = []
    for item in renames:
        old = FilePath(item["old_path"]).resolve()
        new = FilePath(item["new_path"]).resolve()
        try:
            if not old.exists():
                results.append({"path": str(old), "success": False, "error": "文件不存在"})
                continue
            if new.exists():
                results.append({"path": str(old), "success": False, "error": f"目标已存在: {new.name}"})
                continue
            old.rename(new)
            results.append({"path": str(old), "success": True, "new_path": str(new)})
        except Exception as e:
            results.append({"path": str(old), "success": False, "error": str(e)})

    ok = sum(1 for r in results if r["success"])
    return {
        "success": ok > 0,
        "results": results,
        "success_count": ok,
        "fail_count": len(results) - ok,
        "message": f"重命名完成: {ok} 成功, {len(results) - ok} 失败",
    }


@registry.register(
    name="delete_files",
    description="批量删除本机文件（仅删除文件，不删除目录）",
    parameters={
        "file_paths": {"type": "array", "description": "要删除的文件完整路径列表"},
    },
    examples=["删除这些临时文件", "清理 E:\\temp 下的 log 文件"],
    param_model=DeleteFilesParams,
    permission="destructive"
)
async def tool_delete_files(
    file_paths: list,
    **kwargs
) -> Dict[str, Any]:
    from pathlib import Path as FilePath

    results = []
    for fp in file_paths:
        target = FilePath(fp).resolve()
        try:
            if not target.exists():
                results.append({"path": str(target), "success": False, "error": "文件不存在"})
                continue
            if target.is_dir():
                results.append({"path": str(target), "success": False, "error": "不允许删除目录"})
                continue
            os.remove(str(target))
            results.append({"path": str(target), "success": True})
        except Exception as e:
            results.append({"path": str(target), "success": False, "error": str(e)})

    ok = sum(1 for r in results if r["success"])
    return {
        "success": ok > 0,
        "results": results,
        "success_count": ok,
        "fail_count": len(results) - ok,
        "message": f"删除完成: {ok} 成功, {len(results) - ok} 失败",
    }


@registry.register(
    name="move_files",
    description="批量移动本机文件到新位置",
    parameters={
        "moves": {"type": "array", "description": "移动列表，每项包含 src（源路径）和 dst（目标路径）"},
    },
    examples=["把这些文件移到 D:\\sorted 目录", "移动 mp4 文件到视频文件夹"],
    param_model=MoveFilesParams,
    permission="destructive"
)
async def tool_move_files(
    moves: list,
    **kwargs
) -> Dict[str, Any]:
    import shutil
    from pathlib import Path as FilePath

    results = []
    for item in moves:
        src = FilePath(item["src"]).resolve()
        dst = FilePath(item["dst"]).resolve()
        try:
            if not src.is_file():
                results.append({"path": str(src), "success": False, "error": "源文件不存在"})
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                results.append({"path": str(src), "success": False, "error": f"目标已存在: {dst}"})
                continue
            shutil.move(str(src), str(dst))
            results.append({"path": str(src), "success": True, "new_path": str(dst)})
        except Exception as e:
            results.append({"path": str(src), "success": False, "error": str(e)})

    ok = sum(1 for r in results if r["success"])
    return {
        "success": ok > 0,
        "results": results,
        "success_count": ok,
        "fail_count": len(results) - ok,
        "message": f"移动完成: {ok} 成功, {len(results) - ok} 失败",
    }


@registry.register(
    name="copy_files",
    description="批量复制本机文件到新位置",
    parameters={
        "copies": {"type": "array", "description": "复制列表，每项包含 src（源路径）和 dst（目标路径）"},
    },
    examples=["复制这些文件到备份目录", "把选中的图片复制到 D:\\backup"],
    param_model=CopyFilesParams,
    permission="destructive"
)
async def tool_copy_files(
    copies: list,
    **kwargs
) -> Dict[str, Any]:
    import shutil
    from pathlib import Path as FilePath

    results = []
    for item in copies:
        src = FilePath(item["src"]).resolve()
        dst = FilePath(item["dst"]).resolve()
        try:
            if not src.is_file():
                results.append({"path": str(src), "success": False, "error": "源文件不存在"})
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                results.append({"path": str(src), "success": False, "error": f"目标已存在: {dst}"})
                continue
            shutil.copy2(str(src), str(dst))
            results.append({"path": str(src), "success": True, "new_path": str(dst)})
        except Exception as e:
            results.append({"path": str(src), "success": False, "error": str(e)})

    ok = sum(1 for r in results if r["success"])
    return {
        "success": ok > 0,
        "results": results,
        "success_count": ok,
        "fail_count": len(results) - ok,
        "message": f"复制完成: {ok} 成功, {len(results) - ok} 失败",
    }


@registry.register(
    name="create_directory",
    description="在本机创建新目录（支持多级）",
    parameters={
        "path": {"type": "string", "description": "要创建的目录完整路径"},
    },
    examples=["创建目录 D:\\projects\\new_folder", "在 E:\\aupi 下建一个 backup 文件夹"],
    permission="destructive"
)
async def tool_create_directory(
    path: str,
    **kwargs
) -> Dict[str, Any]:
    from pathlib import Path as FilePath

    try:
        target = FilePath(path).resolve()
        if target.exists():
            return {"success": False, "error": f"路径已存在: {target}"}
        target.mkdir(parents=True, exist_ok=False)
        return {"success": True, "path": str(target), "message": f"目录已创建: {target}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

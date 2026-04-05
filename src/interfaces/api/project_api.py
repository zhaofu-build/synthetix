"""
视频项目 API

提供强控制性剪辑的项目管理接口
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import os, uuid, logging

from src.shared.models.response import success_response, error_response
from src.infrastructure.db.session import get_db
from src.domain.entities.video_project import VideoProject, ClipPlanItem
from src.domain.entities.bgm_item import BGMItem
from src.shared.models.timeline import Timeline, ClipPlan, generate_id
from src import config

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求模型 ====================

class CreateProjectRequest(BaseModel):
    """创建项目请求"""
    name: str
    description: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    timeline_data: Optional[Dict] = None
    plan_data: Optional[Dict] = None


class SaveTimelineRequest(BaseModel):
    """保存时间线请求"""
    timeline_data: Dict


class GeneratePlanRequest(BaseModel):
    """生成剪辑方案请求"""
    description: str
    duration: float = 30.0
    style: str = "动感"


class AdjustPlanRequest(BaseModel):
    """调整方案请求"""
    clip_index: int
    adjustments: Dict[str, Any]


# ==================== 项目 CRUD ====================

# BGM 路由必须在 /{project_id} 之前，否则 "bgm" 会被当作 project_id

@router.get("/bgm", summary="获取BGM列表")
def list_bgm(db: Session = Depends(get_db)):
    """获取所有BGM"""
    items = db.query(BGMItem).order_by(BGMItem.created_at.desc()).all()
    return success_response(data={"items": [b.to_dict() for b in items]})


@router.post("/bgm", summary="上传BGM")
async def upload_bgm(
    file: UploadFile = File(...),
    name: str = Form(...),
    style: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """上传BGM文件"""
    try:
        upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "bgm")
        os.makedirs(upload_dir, exist_ok=True)

        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "mp3"
        save_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(upload_dir, save_name)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        bgm = BGMItem(
            name=name,
            web_path=f"static/bgm/{save_name}",
            local_path=file_path,
            style=style or ""
        )
        db.add(bgm)
        db.commit()
        db.refresh(bgm)

        return success_response(data=bgm.to_dict(), message="上传成功", code=201)
    except Exception as e:
        return error_response(error="UploadError", message=str(e), code=500)


@router.delete("/bgm/{bgm_id}", summary="删除BGM")
def delete_bgm(bgm_id: int, db: Session = Depends(get_db)):
    """删除BGM"""
    bgm = db.query(BGMItem).filter(BGMItem.id == bgm_id).first()
    if not bgm:
        return error_response(error="NotFound", message="BGM不存在", code=404)
    try:
        if bgm.local_path and os.path.exists(bgm.local_path):
            os.remove(bgm.local_path)
        db.delete(bgm)
        db.commit()
        return success_response(message="删除成功")
    except Exception as e:
        db.rollback()
        return error_response(error="DeleteError", message=str(e), code=500)


class AiSelectBgmRequest(BaseModel):
    description: str
    style: Optional[str] = None


@router.post("/bgm/ai-select", summary="AI自动选曲")
def ai_select_bgm(req: AiSelectBgmRequest, db: Session = Depends(get_db)):
    """根据描述和风格从BGM库中AI推荐"""
    bgm_list = db.query(BGMItem).all()
    if not bgm_list:
        return success_response(data=None, message="BGM库为空")

    try:
        from src.application.services.llm_adapter import generate_response
        import json

        bgm_info = "\n".join([
            f"- ID: {b.id}, 名称: {b.name}, 风格: {b.style or '未知'}, 描述: {b.description or '无'}"
            for b in bgm_list
        ])

        prompt = f"""根据以下视频描述和风格，从BGM库中选择最合适的一个BGM，只返回该BGM的ID（数字）。

视频描述: {req.description}
风格偏好: {req.style or '无'}

BGM库:
{bgm_info}

只返回最合适的BGM的ID数字，不要返回其他内容。"""

        response = generate_response([{"role": "user", "content": prompt}])
        from src.shared.utils import string_util
        response = string_util.remove_think_tags(response)

        selected_id = int(response.strip())
        bgm = db.query(BGMItem).filter(BGMItem.id == selected_id).first()
        if bgm:
            return success_response(data=bgm.to_dict(), message="AI推荐成功")
        return success_response(data=None, message="未找到合适的BGM")
    except Exception as e:
        logger.error(f"AI选曲失败: {e}")
        return success_response(data=None, message="AI选曲失败")


class AiGenerateBgmRequest(BaseModel):
    description: str
    style: Optional[str] = None
    duration: float = 30.0


@router.post("/bgm/ai-generate", summary="AI生成BGM")
def ai_generate_bgm(req: AiGenerateBgmRequest, db: Session = Depends(get_db)):
    """根据文案和风格AI生成BGM音乐"""
    import base64

    try:
        # 1. 用 LLM 根据文案生成音乐提示词
        from src.application.services.llm_adapter import generate_response
        from src.shared.utils.string_util import remove_think_tags

        prompt = f"""你是一位音乐制作人。请根据以下视频文案和风格要求，生成一段用于AI音乐生成的提示词。

视频文案: {req.description}
风格要求: {req.style or '自动匹配'}

请直接返回一段英文的音乐生成提示词（prompt），描述音乐的节奏、乐器、情感、氛围等。
不要返回任何其他内容，只返回提示词本身。"""

        music_prompt = generate_response([{"role": "user", "content": prompt}])
        music_prompt = remove_think_tags(music_prompt).strip()

        logger.info(f"AI生成的音乐提示词: {music_prompt}")

        # 2. 调用音乐生成接口
        from src.shared.utils.core_nexus_client import CoreNexusClient
        client = CoreNexusClient()

        result = client.text_to_music(
            prompt=music_prompt,
            duration=min(req.duration, 30),
            style=req.style
        )

        if not result:
            return error_response(error="GenerateError", message="AI生成BGM失败", code=500)

        upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "bgm")
        os.makedirs(upload_dir, exist_ok=True)

        save_name = f"{uuid.uuid4().hex}.wav"
        file_path = os.path.join(upload_dir, save_name)

        # 3. 处理不同返回格式
        audio_bytes = None
        if isinstance(result, bytes):
            audio_bytes = result
        elif isinstance(result, dict):
            audio_data = result.get("audio") or result.get("audio_data") or result.get("data")
            if audio_data:
                if isinstance(audio_data, bytes):
                    audio_bytes = audio_data
                elif isinstance(audio_data, str):
                    # 去掉 data URL 前缀
                    if "," in audio_data:
                        audio_data = audio_data.split(",", 1)[1]
                    # 修复 base64 padding
                    padding = 4 - len(audio_data) % 4
                    if padding != 4:
                        audio_data += "=" * padding
                    audio_bytes = base64.b64decode(audio_data)

        if not audio_bytes:
            logger.error(f"AI返回格式异常, result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            return error_response(error="GenerateError", message="AI返回格式异常", code=500)

        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        bgm = BGMItem(
            name=f"AI生成-{req.description[:20]}",
            web_path=f"static/bgm/{save_name}",
            local_path=file_path,
            style=req.style or "",
            duration=req.duration,
            description=f"提示词: {music_prompt[:100]}"
        )
        db.add(bgm)
        db.commit()
        db.refresh(bgm)

        return success_response(data=bgm.to_dict(), message="BGM生成成功")
    except Exception as e:
        logger.error(f"AI生成BGM失败: {e}", exc_info=True)
        return error_response(error="GenerateError", message=str(e), code=500)


class GenerateTtsRequest(BaseModel):
    text: str
    speaker_id: int


@router.post("/generate-tts", summary="生成文案语音")
def generate_tts(req: GenerateTtsRequest):
    """生成TTS语音并返回音频路径"""
    try:
        from src.application.services.audio_service import AudioService
        audio_service = AudioService()
        result = audio_service.generate_fish_speech_tts(
            text=req.text,
            audio_source_id=req.speaker_id
        )
        tts_path = result.get("local_path")
        if tts_path:
            return success_response(data={"web_path": tts_path, "local_path": tts_path}, message="语音生成成功")
        return error_response(error="TtsError", message="语音生成失败", code=500)
    except Exception as e:
        logger.error(f"TTS生成失败: {e}")
        return error_response(error="TtsError", message=str(e), code=500)


@router.post("", summary="创建项目")
def create_project(
    req: CreateProjectRequest,
    db: Session = Depends(get_db)
):
    """创建新的视频项目"""
    try:
        project = VideoProject(
            name=req.name,
            description=req.description,
            status="draft"
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="项目创建成功")

    except Exception as e:
        return error_response(error="CreateError", message=str(e), code=500)


@router.get("", summary="获取项目列表")
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取项目列表（分页）"""
    try:
        query = db.query(VideoProject)

        if status:
            query = query.filter(VideoProject.status == status)

        total = query.count()
        items = query.order_by(VideoProject.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return success_response(data={
            "items": [p.to_dict() for p in items],
            "total": total,
            "page": page,
            "page_size": page_size
        })

    except Exception as e:
        return error_response(error="QueryError", message=str(e), code=500)


@router.get("/{project_id}", summary="获取项目详情")
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    return success_response(data=project.to_dict())


@router.patch("/{project_id}", summary="更新项目")
def update_project(
    project_id: int,
    req: UpdateProjectRequest,
    db: Session = Depends(get_db)
):
    """更新项目信息"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    try:
        if req.name is not None:
            project.name = req.name
        if req.description is not None:
            project.description = req.description
        if req.timeline_data is not None:
            project.timeline_data = req.timeline_data
        if req.plan_data is not None:
            project.plan_data = req.plan_data

        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="更新成功")

    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


@router.delete("/{project_id}", summary="删除项目")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """删除项目"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    try:
        # 同时删除相关的剪辑方案项
        db.query(ClipPlanItem).filter(ClipPlanItem.project_id == project_id).delete()
        db.delete(project)
        db.commit()

        return success_response(message="项目已删除")

    except Exception as e:
        db.rollback()
        return error_response(error="DeleteError", message=str(e), code=500)


# ==================== 时间线操作 ====================

@router.get("/{project_id}/timeline", summary="获取时间线")
def get_timeline(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目的时间线数据"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    if project.timeline_data:
        return success_response(data=project.timeline_data)
    else:
        # 返回空时间线
        timeline = Timeline(
            id=generate_id(),
            project_id=project_id
        )
        return success_response(data=timeline.to_dict())


@router.post("/{project_id}/timeline", summary="保存时间线")
def save_timeline(
    project_id: int,
    req: SaveTimelineRequest,
    db: Session = Depends(get_db)
):
    """保存时间线数据"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    try:
        project.timeline_data = req.timeline_data

        # 更新总时长
        if req.timeline_data.get("duration"):
            project.duration = req.timeline_data["duration"]

        db.commit()

        return success_response(message="时间线已保存")

    except Exception as e:
        db.rollback()
        return error_response(error="SaveError", message=str(e), code=500)


# ==================== 剪辑方案 ====================

@router.post("/{project_id}/plan/generate", summary="生成剪辑方案")
def generate_plan(
    project_id: int,
    req: GeneratePlanRequest,
    db: Session = Depends(get_db)
):
    """使用 AI 生成剪辑方案"""
    from src.application.services.clip_planner import ClipPlanner

    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    try:
        # 获取可用素材
        from src.infrastructure.repositories import VideoRepository
        repo = VideoRepository(db)
        materials = repo.get_all(limit=50, filters={"video_type": 1})

        # 生成方案
        planner = ClipPlanner()
        plan = planner.generate_plan(
            description=req.description,
            materials=[m.to_dict() for m in materials],
            duration=req.duration,
            style=req.style
        )

        # 保存方案
        project.plan_data = plan.to_dict()
        db.commit()

        return success_response(data=plan.to_dict(), message="方案生成成功")

    except Exception as e:
        return error_response(error="PlanError", message=str(e), code=500)


@router.post("/{project_id}/plan/adjust", summary="调整方案")
def adjust_plan(
    project_id: int,
    req: AdjustPlanRequest,
    db: Session = Depends(get_db)
):
    """调整剪辑方案"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project or not project.plan_data:
        return error_response(error="NotFound", message="项目或方案不存在", code=404)

    try:
        plan_data = project.plan_data
        clips = plan_data.get("clips", [])

        if 0 <= req.clip_index < len(clips):
            # 应用调整
            for key, value in req.adjustments.items():
                clips[req.clip_index][key] = value

            plan_data["clips"] = clips
            project.plan_data = plan_data
            db.commit()

        return success_response(data=plan_data, message="方案已调整")

    except Exception as e:
        db.rollback()
        return error_response(error="AdjustError", message=str(e), code=500)


@router.post("/{project_id}/plan/apply", summary="应用方案到时间线")
def apply_plan(
    project_id: int,
    db: Session = Depends(get_db)
):
    """将剪辑方案应用到时间线"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project or not project.plan_data:
        return error_response(error="NotFound", message="项目或方案不存在", code=404)

    try:
        plan_data = project.plan_data
        clips = plan_data.get("clips", [])
        transitions = plan_data.get("transitions", [])

        # 创建时间线
        timeline = Timeline(
            id=generate_id(),
            project_id=project_id
        )

        # 添加片段
        current_time = 0.0
        from src.shared.models.timeline import TimelineClip, Transition

        for i, clip_data in enumerate(clips):
            # 解析时间
            start_parts = clip_data.get("start_time", "00:00:00").split(":")
            trim_start = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + float(start_parts[2])

            end_parts = clip_data.get("end_time", "00:00:10").split(":")
            trim_end = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + float(end_parts[2])

            duration = trim_end - trim_start

            clip = TimelineClip(
                id=generate_id(),
                material_id=clip_data.get("material_id", 0),
                material_name=clip_data.get("material_name", ""),
                start=current_time,
                end=current_time + duration,
                trim_start=trim_start,
                trim_end=trim_end
            )

            timeline.add_clip(clip, "video")
            current_time += duration

            # 添加转场
            if i < len(transitions):
                trans = transitions[i]
                timeline.add_transition(Transition(
                    id=generate_id(),
                    type=trans.get("type", "cut"),
                    position=current_time,
                    duration=trans.get("duration", 0.5)
                ))

        # 保存时间线
        project.timeline_data = timeline.to_dict()
        project.duration = timeline.duration
        project.status = "ready"
        db.commit()

        return success_response(data=timeline.to_dict(), message="方案已应用到时间线")

    except Exception as e:
        db.rollback()
        return error_response(error="ApplyError", message=str(e), code=500)


# ==================== 渲染导出 ====================

class RenderRequest(BaseModel):
    """渲染请求"""
    creative: Optional[str] = None
    speaker_id: Optional[int] = None
    tts_path: Optional[str] = None
    bgm_id: Optional[int] = None
    bgm_volume: Optional[float] = 0.3


@router.post("/{project_id}/render", summary="渲染视频")
def render_project(
    project_id: int,
    db: Session = Depends(get_db),
    req: Optional[RenderRequest] = Body(default=None)
):
    """渲染项目为视频"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project or not project.timeline_data:
        return error_response(error="NotFound", message="项目或时间线不存在", code=404)

    try:
        from src.application.services.render_service import RenderService

        project.status = "processing"
        db.commit()

        # 构建音频配置
        audio_config = {}
        if req:
            if req.tts_path:
                audio_config["tts_path"] = req.tts_path
            elif req.creative and req.speaker_id:
                audio_config["creative"] = req.creative
                audio_config["speaker_id"] = req.speaker_id
            if req.bgm_id:
                audio_config["bgm_id"] = req.bgm_id
            if req.bgm_volume is not None:
                audio_config["bgm_volume"] = req.bgm_volume

        # 执行渲染
        render = RenderService()
        output_path = render.render_timeline(
            Timeline.from_dict(project.timeline_data),
            audio_config if audio_config else None
        )

        project.output_path = output_path
        project.status = "completed"
        db.commit()

        return success_response(data={
            "output_path": output_path,
            "web_path": output_path
        }, message="渲染完成")

    except Exception as e:
        project.status = "error"
        db.commit()
        return error_response(error="RenderError", message=str(e), code=500)



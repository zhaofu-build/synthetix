"""
视频项目 API

提供强控制性剪辑的项目管理接口
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import os, uuid, logging, json
from datetime import datetime

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
    mode: str = "workflow"


class UpdateProjectRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[str] = None
    material_ids: Optional[List[int]] = None
    creative: Optional[str] = None
    target_duration: Optional[float] = None
    style: Optional[str] = None
    speaker_id: Optional[int] = None
    tts_path: Optional[str] = None
    bgm_id: Optional[int] = None
    bgm_volume: Optional[float] = None
    current_step: Optional[int] = None
    chat_history: Optional[List[Dict]] = None
    timeline_data: Optional[Dict] = None
    plan_data: Optional[Dict] = None
    output_path: Optional[str] = None
    output_videos: Optional[List[Dict]] = None


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
        from src.infrastructure.db.session import get_db_context
        with get_db_context() as db:
            audio_service = AudioService(db)
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


# ==================== 项目导入导出（必须在 /{project_id} 之前） ====================

@router.post("/import", summary="导入项目")
async def import_project(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """从 JSON 文件导入项目"""
    try:
        content = await file.read()
        data = json.loads(content)

        project = VideoProject(
            name=data.get("name", "导入项目"),
            description=data.get("description"),
            mode=data.get("mode", "workflow"),
            material_ids=data.get("material_ids", []),
            creative=data.get("creative"),
            target_duration=data.get("target_duration"),
            style=data.get("style"),
            speaker_id=data.get("speaker_id"),
            tts_path=data.get("tts_path"),
            bgm_id=data.get("bgm_id"),
            bgm_volume=data.get("bgm_volume", 0.3),
            current_step=data.get("current_step", 0),
            chat_history=data.get("chat_history", []),
            timeline_data=data.get("timeline_data"),
            plan_data=data.get("plan_data"),
            status="draft"
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="项目导入成功")
    except json.JSONDecodeError:
        return error_response(error="ImportError", message="无效的JSON文件", code=400)
    except Exception as e:
        return error_response(error="ImportError", message=str(e), code=500)


@router.post("", summary="创建项目")
def create_project(
    req: CreateProjectRequest,
    db: Session = Depends(get_db)
):
    """创建新的视频项目"""
    try:
        # 检查项目名称是否重复
        existing = db.query(VideoProject).filter(VideoProject.name == req.name).first()
        if existing:
            return error_response(error="DuplicateName", message="项目名称已存在，请换一个名称", code=400)

        project = VideoProject(
            name=req.name,
            description=req.description,
            mode=req.mode,
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


class SaveToLibraryRequest(BaseModel):
    """保存临时资产到素材库"""
    video_id: int


@router.post("/save-to-library", summary="保存临时资产到素材库")
async def save_to_library(request: SaveToLibraryRequest, db: Session = Depends(get_db)):
    """将临时素材转为正式素材"""
    try:
        from src.infrastructure.repositories import VideoRepository
        repo = VideoRepository(db)
        updated = repo.update(request.video_id, is_temp=False)
        if not updated:
            return error_response(error="NotFound", message="素材不存在", code=404)
        return success_response(data={"video_id": request.video_id})
    except Exception as e:
        logger.error(f"保存到素材库失败: {e}")
        return error_response(error="SaveError", message=str(e), code=500)


@router.delete("/temp-material/{video_id}", summary="删除临时素材")
async def delete_temp_material(video_id: int, db: Session = Depends(get_db)):
    """删除临时素材（DB记录 + 物理文件），并从项目中移除关联"""
    try:
        from src.domain.entities.video_source import VideoSource
        video = db.query(VideoSource).filter(VideoSource.id == video_id).first()
        if not video:
            return error_response(error="NotFound", message="素材不存在", code=404)

        # 从所有项目的 material_ids 中移除
        projects = db.query(VideoProject).all()
        for p in projects:
            if p.material_ids and video_id in p.material_ids:
                p.material_ids = [x for x in p.material_ids if x != video_id]

        # 删除物理文件
        if video.local_path and os.path.exists(video.local_path):
            os.remove(video.local_path)

        db.delete(video)
        db.commit()
        return success_response(message="已删除")
    except Exception as e:
        logger.error(f"删除临时素材失败: {e}")
        return error_response(error="DeleteError", message=str(e), code=500)


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


@router.get("/{project_id}/full", summary="获取项目完整状态")
def get_project_full(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目完整状态（含关联数据）"""
    from src.domain.entities.video_source import VideoSource
    from src.domain.entities.audio_source import AudioSource

    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    data = project.to_dict()

    # 关联素材
    material_ids = project.material_ids or []
    if material_ids:
        videos = db.query(VideoSource).filter(VideoSource.id.in_(material_ids)).all()
        data["materials"] = [{
            "id": v.id,
            "videoName": v.video_name,
            "webPath": v.web_path,
            "duration": v.duration,
            "durationHms": v.duration_hms,
            "description": v.description,
            "isTemp": v.is_temp if v.is_temp is not None else False,
            "fileType": v.file_type or "video",
        } for v in videos]
    else:
        data["materials"] = []

    # 关联音色
    if project.speaker_id:
        speaker = db.query(AudioSource).filter(AudioSource.id == project.speaker_id).first()
        if speaker:
            data["speaker"] = {
                "id": speaker.id,
                "audioName": speaker.audio_name,
                "webPath": speaker.web_path,
            }

    # 关联BGM
    if project.bgm_id:
        bgm = db.query(BGMItem).filter(BGMItem.id == project.bgm_id).first()
        if bgm:
            data["bgm"] = bgm.to_dict()

    return success_response(data=data)


@router.get("/{project_id}/export", summary="导出项目为JSON")
def export_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """导出项目为JSON文件"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    data = project.to_dict()
    data["exported_at"] = datetime.utcnow().isoformat()
    data["export_version"] = 1

    content = json.dumps(data, ensure_ascii=False, indent=2)
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f"attachment; filename=project_{project_id}.json"
        }
    )


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
            # 检查名称是否与其他项目重复
            existing = db.query(VideoProject).filter(
                VideoProject.name == req.name,
                VideoProject.id != project_id
            ).first()
            if existing:
                return error_response(error="DuplicateName", message="项目名称已存在", code=400)
            project.name = req.name
        if req.description is not None:
            project.description = req.description
        if req.mode is not None:
            project.mode = req.mode
        if req.material_ids is not None:
            project.material_ids = req.material_ids
        if req.creative is not None:
            project.creative = req.creative
        if req.target_duration is not None:
            project.target_duration = req.target_duration
        if req.style is not None:
            project.style = req.style
        if req.speaker_id is not None:
            project.speaker_id = req.speaker_id
        if req.tts_path is not None:
            project.tts_path = req.tts_path
        if req.bgm_id is not None:
            project.bgm_id = req.bgm_id
        if req.bgm_volume is not None:
            project.bgm_volume = req.bgm_volume
        if req.current_step is not None:
            project.current_step = req.current_step
        if req.chat_history is not None:
            project.chat_history = req.chat_history
        if req.timeline_data is not None:
            project.timeline_data = req.timeline_data
        if req.plan_data is not None:
            project.plan_data = req.plan_data
        if req.output_path is not None:
            project.output_path = req.output_path
        if req.output_videos is not None:
            project.output_videos = req.output_videos

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

        # 构建音频配置 & 保存到项目
        audio_config = {}
        if req:
            if req.tts_path:
                audio_config["tts_path"] = req.tts_path
                project.tts_path = req.tts_path
            elif req.creative and req.speaker_id:
                audio_config["creative"] = req.creative
                audio_config["speaker_id"] = req.speaker_id
                project.creative = req.creative
                project.speaker_id = req.speaker_id
            if req.bgm_id:
                audio_config["bgm_id"] = req.bgm_id
                project.bgm_id = req.bgm_id
            if req.bgm_volume is not None:
                audio_config["bgm_volume"] = req.bgm_volume
                project.bgm_volume = req.bgm_volume
            db.commit()

        # 执行渲染
        render = RenderService()
        output_path = render.render_timeline(
            Timeline.from_dict(project.timeline_data),
            audio_config if audio_config else None
        )

        project.output_path = output_path
        # 追加到输出视频列表
        from datetime import datetime
        video_entry = {
            "path": output_path,
            "created_at": datetime.utcnow().isoformat(),
        }
        output_videos = project.output_videos or []
        output_videos.append(video_entry)
        project.output_videos = output_videos
        project.status = "completed"
        db.commit()

        return success_response(data={
            "output_path": output_path,
            "web_path": output_path,
            "output_videos": output_videos,
        }, message="渲染完成")

    except Exception as e:
        project.status = "error"
        db.commit()
        return error_response(error="RenderError", message=str(e), code=500)


# ==================== 字幕数据接口 ====================

class SubtitleDataRequest(BaseModel):
    entries: List[Dict[str, Any]] = []
    speakers: List[Dict[str, Any]] = []
    style: Dict[str, Any] = {}


@router.get("/{project_id}/subtitles", summary="获取字幕数据")
async def get_subtitles(project_id: int, db: Session = Depends(get_db)):
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    return success_response(data=project.subtitle_data if hasattr(project, 'subtitle_data') and project.subtitle_data else {})


@router.post("/{project_id}/subtitles", summary="保存字幕数据")
async def save_subtitles(project_id: int, request: SubtitleDataRequest, db: Session = Depends(get_db)):
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)

    subtitle_data = {
        "entries": request.entries,
        "speakers": request.speakers,
        "style": request.style,
    }

    if hasattr(project, 'subtitle_data'):
        project.subtitle_data = subtitle_data
    else:
        # 如果列不存在（未迁移），存到 plan_data 的扩展字段
        plan = project.plan_data or {}
        plan["subtitle_data"] = subtitle_data
        project.plan_data = plan

    db.commit()
    return success_response(data=subtitle_data, message="字幕数据已保存")


# ==================== 质量检测 ====================

class QualityCheckRequest(BaseModel):
    video_id: Optional[int] = None
    project_id: Optional[int] = None


@router.post("/quality-check", summary="视频质量检测")
async def quality_check(request: QualityCheckRequest, db: Session = Depends(get_db)):
    """检测视频黑屏、爆音、跳切、时长合规等问题"""
    from src.application.services.quality_service import run_quality_check
    from src.infrastructure.repositories import VideoRepository

    video_path = None
    clips = None
    target_duration = None

    if request.video_id:
        repo = VideoRepository(db)
        video = repo.get_by_id(request.video_id)
        if video:
            video_path = video.local_path

    if request.project_id:
        proj = db.query(VideoProject).filter(VideoProject.id == request.project_id).first()
        if proj:
            target_duration = proj.target_duration
            if proj.plan_data and proj.plan_data.get("clips"):
                clips = proj.plan_data["clips"]

    result = run_quality_check(
        video_path=video_path,
        clips=clips,
        target_duration=target_duration,
    )
    return success_response(data=result, message=result["summary"])


# ==================== 版本快照 ====================

class SnapshotRequest(BaseModel):
    label: str = ""
    data: dict = {}


@router.post("/{project_id}/plan/snapshot", summary="创建版本快照")
async def create_plan_snapshot(project_id: int, req: SnapshotRequest, db: Session = Depends(get_db)):
    project = db.query(VideoProject).filter_by(id=project_id).first()
    if not project:
        return error_response(message="项目不存在", code=404)
    snapshots = project.plan_versions or []
    snapshots.insert(0, {**req.data, "label": req.label, "timestamp": datetime.utcnow().isoformat()})
    snapshots = snapshots[:50]
    project.plan_versions = snapshots
    db.commit()
    return success_response(data={"snapshot_count": len(snapshots)}, message="快照已保存")


@router.get("/{project_id}/plan/snapshots", summary="获取版本快照列表")
async def list_plan_snapshots(project_id: int, db: Session = Depends(get_db)):
    project = db.query(VideoProject).filter_by(id=project_id).first()
    if not project:
        return error_response(message="项目不存在", code=404)
    snapshots = project.plan_versions or []
    return success_response(data={"snapshots": snapshots})
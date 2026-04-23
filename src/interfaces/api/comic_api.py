"""
漫剧项目 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from src.shared.models.response import success_response, error_response
from src.infrastructure.db.session import get_db
from src.domain.entities.comic_project import ComicProject
from src.shared.models.comic_models import (
    CreateComicProjectRequest,
    UpdateComicProjectRequest,
    GenerateScriptRequest,
    GeneratePanelImageRequest,
    GeneratePanelAudioRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 项目 CRUD ====================

@router.post("", summary="创建漫剧项目")
def create_comic_project(req: CreateComicProjectRequest, db: Session = Depends(get_db)):
    try:
        existing = db.query(ComicProject).filter(ComicProject.name == req.name).first()
        if existing:
            return error_response(error="DuplicateName", message="项目名称已存在", code=400)

        project = ComicProject(
            name=req.name,
            description=req.description,
            genre=req.genre,
            status="draft",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="项目创建成功", code=201)
    except Exception as e:
        return error_response(error="CreateError", message=str(e), code=500)


@router.get("", summary="漫剧项目列表")
def list_comic_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        query = db.query(ComicProject)
        if status:
            query = query.filter(ComicProject.status == status)
        total = query.count()
        items = query.order_by(ComicProject.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return success_response(data={
            "items": [p.to_dict() for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        return error_response(error="QueryError", message=str(e), code=500)


@router.get("/{project_id}", summary="获取漫剧项目")
def get_comic_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    return success_response(data=project.to_dict())


@router.patch("/{project_id}", summary="更新漫剧项目")
def update_comic_project(project_id: int, req: UpdateComicProjectRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        for field in ("name", "description", "genre", "style", "script_data", "characters",
                       "panels", "audio_config", "bgm_config", "current_step", "status"):
            val = getattr(req, field, None)
            if val is not None:
                setattr(project, field, val)
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="更新成功")
    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


@router.delete("/{project_id}", summary="删除漫剧项目")
def delete_comic_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        db.delete(project)
        db.commit()
        return success_response(message="项目已删除")
    except Exception as e:
        db.rollback()
        return error_response(error="DeleteError", message=str(e), code=500)


# ==================== 脚本生成 ====================

@router.post("/{project_id}/generate-script", summary="AI生成漫剧脚本")
def generate_script(project_id: int, req: GenerateScriptRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        from src.application.services.llm_adapter import generate_response
        from src.shared.utils.string_util import remove_think_tags
        import json, re

        characters_str = "未指定"
        if req.characters:
            characters_str = "\n".join([
                f"- {c.get('name', '?')}: {c.get('appearance', '?')}, 性格: {c.get('personality', '未指定')}"
                for c in req.characters
            ])

        prompt = f"""你是一个专业的漫剧编剧。请根据以下信息生成一个完整的漫剧脚本。

故事设定: {req.description}
类型: {req.genre}
分镜数量: {req.num_panels}
角色:
{characters_str}

请严格按照以下 JSON 格式输出（不要输出其他内容，不要用 ```json 标记）:
{{
  "title": "漫剧标题",
  "synopsis": "一句话简介",
  "genre": "{req.genre}",
  "scenes": [
    {{
      "sequence": 0,
      "scene_description": "详细场景视觉描述（用于AI图片生成，包含环境、光线、角色动作和表情）",
      "background_description": "背景描述",
      "characters": ["出镜角色名"],
      "dialogues": [
        {{"character_id": "角色名", "text": "台词", "emotion": "开心/悲伤/愤怒/惊讶/平静"}}
      ],
      "narration": "旁白文本或null",
      "emotion": "happy/sad/angry/neutral/tense/romantic",
      "duration": 3.0,
      "transition": "cut",
      "camera": "特写/近景/中景/全景/远景"
    }}
  ],
  "bgm_prompt": "BGM风格描述"
}}

要求:
1. 每个 scene_description 必须足够详细，能直接用于AI图片生成
2. 对白要自然口语化
3. 总分镜时长应合理分配
4. 情绪曲线要有起伏
5. 镜头语言要丰富"""

        result_text = generate_response([{"role": "user", "content": prompt}])
        result_text = remove_think_tags(result_text).strip()

        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if not json_match:
            return error_response(error="ParseError", message="AI 返回格式异常，无法解析脚本", code=500)

        script_data = json.loads(json_match.group())

        project.script_data = script_data
        if script_data.get("scenes"):
            project.panels = script_data["scenes"]
        if not project.genre and script_data.get("genre"):
            project.genre = script_data["genre"]
        project.current_step = 1
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="脚本生成成功")
    except json.JSONDecodeError:
        return error_response(error="ParseError", message="AI 返回 JSON 解析失败", code=500)
    except Exception as e:
        logger.error(f"脚本生成失败: {e}", exc_info=True)
        return error_response(error="GenerateError", message=str(e), code=500)


# ==================== 角色管理 ====================

@router.put("/{project_id}/characters", summary="更新角色列表")
def update_characters(project_id: int, characters: list, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        project.characters = characters
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="角色已更新")
    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


# ==================== 分镜操作 ====================

@router.put("/{project_id}/panels", summary="更新分镜列表")
def update_panels(project_id: int, panels: list, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        project.panels = panels
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="分镜已更新")
    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


@router.post("/{project_id}/panels/generate-image", summary="生成分镜图片（stub）")
def generate_panel_image(project_id: int, req: GeneratePanelImageRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        from src.shared.utils.core_nexus_client import get_client
        client = get_client()

        panels = project.panels or []
        idx = req.panel_index
        if idx < 0 or idx >= len(panels):
            return error_response(error="InvalidIndex", message="分镜索引越界", code=400)

        panel = panels[idx]
        prompt = req.scene_description or panel.get("scene_description", "")
        style = project.style or "动漫"

        style_map = {
            "动漫": "anime style, high quality, detailed",
            "写实": "photorealistic, cinematic lighting, 8k",
            "水墨": "chinese ink painting style, elegant",
            "像素": "pixel art style, retro game aesthetic",
            "美漫": "western comic style, bold lines, vibrant colors",
        }
        style_prefix = style_map.get(style, "anime style, high quality")
        full_prompt = f"{style_prefix}, {prompt}"

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            client.text_to_image_async(prompt=full_prompt)
        )

        if result.get("status") == "stub":
            return success_response(data={"stub": True, "message": "图片生成服务尚未就绪"}, message="图片生成功能暂未开放")

        image_path = result.get("image_url") or result.get("image_path")
        if image_path:
            panel["generated_image_path"] = image_path
            project.panels = panels
            db.commit()
            db.refresh(project)

        return success_response(data=project.to_dict(), message="图片生成完成")
    except Exception as e:
        logger.error(f"分镜图片生成失败: {e}", exc_info=True)
        return error_response(error="GenerateError", message=str(e), code=500)


@router.post("/{project_id}/panels/generate-audio", summary="生成分镜语音")
def generate_panel_audio(project_id: int, req: GeneratePanelAudioRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        from src.shared.utils.core_nexus_client import get_client
        import base64, uuid, os
        from src import config

        panels = project.panels or []
        idx = req.panel_index
        if idx < 0 or idx >= len(panels):
            return error_response(error="InvalidIndex", message="分镜索引越界", code=400)

        panel = panels[idx]
        text = req.text
        if not text:
            dialogues = panel.get("dialogues") or []
            text = " ".join([d.get("text", "") for d in dialogues])
        if not text:
            return error_response(error="NoText", message="没有可用的文本内容", code=400)

        client = get_client()
        audio_bytes = client.tts_generate(text=text, speaker=req.voice_id)

        if audio_bytes:
            upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
            os.makedirs(upload_dir, exist_ok=True)
            save_name = f"panel_{idx}_{uuid.uuid4().hex[:8]}.wav"
            file_path = os.path.join(upload_dir, save_name)
            with open(file_path, "wb") as f:
                f.write(audio_bytes if isinstance(audio_bytes, bytes) else base64.b64decode(audio_bytes))

            audio_paths = panel.get("generated_audio_paths") or []
            audio_paths.append(f"static/projects/{project_id}/{save_name}")
            panel["generated_audio_paths"] = audio_paths
            project.panels = panels
            db.commit()
            db.refresh(project)

        return success_response(data=project.to_dict(), message="语音生成完成")
    except Exception as e:
        logger.error(f"分镜语音生成失败: {e}", exc_info=True)
        return error_response(error="GenerateError", message=str(e), code=500)


# ==================== BGM ====================

@router.put("/{project_id}/bgm", summary="更新BGM配置")
def update_bgm_config(project_id: int, bgm_config: dict, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        project.bgm_config = bgm_config
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="BGM配置已更新")
    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


# ==================== 合成 ====================

@router.post("/{project_id}/compose", summary="合成漫剧视频")
def compose_comic_video(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        return error_response(error="NotFound", message="项目不存在", code=404)
    try:
        from src.application.services.comic_composer import ComicComposer
        from datetime import datetime as dt

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
            return error_response(error="ComposeError", message=result.get("error", "合成失败"), code=500)

        video_entry = {
            "path": result["output_path"],
            "created_at": dt.utcnow().isoformat(),
        }
        output_videos = project.output_videos or []
        output_videos.append(video_entry)
        project.output_videos = output_videos
        project.status = "completed"
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="漫剧视频合成完成")
    except Exception as e:
        project.status = "draft"
        db.commit()
        logger.error(f"漫剧合成失败: {e}", exc_info=True)
        return error_response(error="ComposeError", message=str(e), code=500)

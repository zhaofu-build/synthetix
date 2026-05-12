"""
漫剧项目 API
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional
import logging
import httpx

from src.shared.models.response import success_response, error_response
from src.shared.exceptions.exceptions import ResourceNotFoundException, BusinessException, ConflictException, ExternalServiceException, ValidationException
from src.infrastructure.db.session import get_db
from src.domain.entities.comic_project import ComicProject
from src.shared.models.comic_models import (
    CreateComicProjectRequest,
    UpdateComicProjectRequest,
    GenerateScriptRequest,
    GeneratePanelImageRequest,
    GeneratePanelAudioRequest,
    GeneratePanelVideoRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 统一风格 → 英文 prompt 映射（角色/场景/分镜共用）
STYLE_PROMPT_MAP = {
    "动漫": "anime style, high quality",
    "写实": "photorealistic, cinematic lighting, 8k",
    "水墨": "chinese ink painting style, elegant",
    "像素": "pixel art style, retro",
    "美漫": "western comic style, bold lines, vibrant colors",
    "水彩": "watercolor painting style, soft colors, artistic",
    "赛博朋克": "cyberpunk style, neon lights, futuristic, dark atmosphere",
    "古风": "traditional chinese painting style, classical, elegant",
    "暗黑哥特": "dark gothic style, dramatic lighting, moody atmosphere",
    "日系清新": "japanese light novel illustration style, bright, pastel colors, clean",
}


def _get_style_prefix(style: str, context: str = "general") -> str:
    """根据风格和上下文生成 prompt 前缀"""
    base = STYLE_PROMPT_MAP.get(style, "anime style, high quality")
    if context == "character":
        return f"{base}, detailed character sheet"
    elif context == "scene":
        return f"{base}, detailed environment, background"
    elif context == "panel":
        return f"{base}, detailed illustration"
    return base


# ==================== 项目 CRUD ====================

@router.post("", summary="创建漫剧项目")
def create_comic_project(req: CreateComicProjectRequest, db: Session = Depends(get_db)):
    existing = db.query(ComicProject).filter(ComicProject.name == req.name).first()
    if existing:
        raise ConflictException(message="项目名称已存在")

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


@router.get("", summary="漫剧项目列表")
def list_comic_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
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


@router.get("/{project_id}", summary="获取漫剧项目")
def get_comic_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    return success_response(data=project.to_dict())


@router.patch("/{project_id}", summary="更新漫剧项目")
def update_comic_project(project_id: int, req: UpdateComicProjectRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    for field in ("name", "description", "genre", "style", "script_data", "characters",
                   "panels", "audio_config", "bgm_config", "current_step", "status",
                   "series_id", "episode_number", "target_duration"):
        val = getattr(req, field, None)
        if val is not None:
            setattr(project, field, val)
    db.commit()
    db.refresh(project)
    return success_response(data=project.to_dict(), message="更新成功")


@router.delete("/{project_id}", summary="删除漫剧项目")
def delete_comic_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    db.delete(project)
    db.commit()
    return success_response(message="项目已删除")


# ==================== 脚本生成 ====================

@router.post("/{project_id}/generate-script", summary="AI生成漫剧脚本")
async def generate_script(project_id: int, req: GenerateScriptRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        from src.application.services.llm_adapter import generate_response_async
        from src.shared.utils.string_util import remove_think_tags
        import json, re

        num_panels = req.num_panels
        if num_panels is None and req.target_duration:
            num_panels = max(3, min(100, int(req.target_duration / 3)))
        elif num_panels is None:
            num_panels = 10

        characters_str = "未指定"
        if req.characters:
            characters_str = "\n".join([
                f"- {c.get('name', '?')}: {c.get('appearance', '?')}, 性格: {c.get('personality', '未指定')}"
                for c in req.characters
            ])

        duration_hint = ""
        if req.target_duration:
            duration_hint = f"\n目标总时长: {req.target_duration} 秒（所有分镜的 duration 之和应接近此值）"

        PANELS_PER_CALL = 5

        async def llm_json_call(prompt):
            result_text = await generate_response_async([{"role": "user", "content": prompt}], max_tokens=4096)
            result_text = remove_think_tags(result_text).strip()
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if not json_match:
                raise ValueError("AI 返回格式异常，无法解析脚本")
            return json.loads(json_match.group())

        if num_panels <= PANELS_PER_CALL:
            # 小分镜数：单次调用
            prompt = f"""你是一个专业的漫剧编剧。请根据以下信息生成一个完整的漫剧脚本。

故事设定: {req.description}
类型: {req.genre}
分镜数量: {num_panels}{duration_hint}
已有角色:
{characters_str}

请严格按照以下 JSON 格式输出（不要输出其他内容，不要用 ```json 标记）:
{{
  "title": "漫剧标题",
  "synopsis": "一句话简介",
  "genre": "{req.genre}",
  "characters": [
    {{
      "name": "角色名",
      "appearance": "详细外貌描述（发型、发色、瞳色、体型、服装等，用于AI图片生成角色参考图）",
      "personality": "性格特征描述",
      "voice_description": "音色描述（如：清亮少女音、低沉磁性男声等，用于TTS语音合成）"
    }}
  ],
  "scene_library": [
    {{
      "name": "场景名称（简短，如"教室"、"森林"）",
      "description": "纯场景环境描述（只描述环境、建筑、光线、天气、氛围等，不包含任何角色描写，用于AI图片生成场景背景）"
    }}
  ],
  "scenes": [
    {{
      "sequence": 0,
      "scene_description": "画面描述（描述角色动作、表情、构图，不含环境描述）",
      "background_description": "纯场景环境描述（只描述环境背景，不包含角色）",
      "scene_id": "场景名称（必须引用 scene_library 中的某个 name）",
      "characters": ["出镜角色名（必须引用 characters 中的 name）"],
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
1. characters 数组必须列出所有出场角色，包含详细的外貌、性格和音色描述
2. scene_library 必须列出故事中出现的所有不同场景（去重），每个场景的 description 只描述纯环境
3. 每个 scenes 中的 scene_description 描述角色动作和表情（不含环境），background_description 描述纯场景环境
4. 每个分镜的 scene_id 必须引用 scene_library 中的某个场景 name
5. 每个分镜的 characters 数组列出该镜头中出现的角色名
6. 对白要自然口语化
7. 总分镜时长应合理分配（2-8秒）
8. 情绪曲线要有起伏，镜头语言要丰富
9. 总分镜数量严格为 {num_panels} 个"""

            script_data = await llm_json_call(prompt)
        else:
            # 大分镜数：先生成结构，再分批生成面板
            # 第一批：生成结构 + 首批面板（含角色、场景库的完整定义）
            prompt1 = f"""你是一个专业的漫剧编剧。请根据以下信息生成漫剧脚本的结构和前 {PANELS_PER_CALL} 个分镜。

故事设定: {req.description}
类型: {req.genre}
总分镜数量: {num_panels}（本次先生成前 {PANELS_PER_CALL} 个）
已有角色:
{characters_str}
{duration_hint}

请严格按照以下 JSON 格式输出（不要输出其他内容，不要用 ```json 标记）:
{{
  "title": "漫剧标题",
  "synopsis": "一句话简介",
  "genre": "{req.genre}",
  "characters": [
    {{
      "name": "角色名",
      "appearance": "详细外貌描述（发型、发色、瞳色、体型、服装等）",
      "personality": "性格特征描述",
      "voice_description": "音色描述（如：清亮少女音、低沉磁性男声等）"
    }}
  ],
  "scene_library": [
    {{
      "name": "场景名称",
      "description": "纯场景环境描述（只描述环境，不含角色）"
    }}
  ],
  "scenes": [
    {{
      "sequence": 0,
      "scene_description": "画面描述（角色动作、表情、构图）",
      "background_description": "纯场景环境描述",
      "scene_id": "场景名称（引用 scene_library）",
      "characters": ["出镜角色名"],
      "dialogues": [{{"character_id": "角色名", "text": "台词", "emotion": "开心/悲伤/愤怒/惊讶/平静"}}],
      "narration": "旁白或null",
      "emotion": "happy/sad/angry/neutral/tense/romantic",
      "duration": 3.0,
      "transition": "cut",
      "camera": "特写/近景/中景/全景/远景"
    }}
  ],
  "bgm_prompt": "BGM风格描述"
}}

要求:
1. characters 必须列出所有出场角色（含外貌、性格、音色）
2. scene_library 必须列出故事中所有场景（去重），description 只描述纯环境
3. 本次严格生成 {PANELS_PER_CALL} 个分镜（sequence 0-{PANELS_PER_CALL - 1}），后续会继续生成
4. 故事开头要吸引人，对白自然口语化
5. 分镜时长 2-8 秒，情绪和镜头语言要丰富"""

            script_data = await llm_json_call(prompt1)
            all_panels = script_data.get("scenes", [])

            chars_ctx = json.dumps(script_data.get("characters", []), ensure_ascii=False)
            scenes_ctx = json.dumps(script_data.get("scene_library", []), ensure_ascii=False)

            # 后续批次：基于已有角色和场景继续生成面板
            remaining = num_panels - len(all_panels)
            while remaining > 0:
                batch = min(PANELS_PER_CALL, remaining)
                start_seq = len(all_panels)
                is_last = (remaining <= PANELS_PER_CALL)

                prompt_n = f"""你是一个专业的漫剧编剧。请继续生成漫剧脚本的后续分镜。

已知角色: {chars_ctx}
已知场景库: {scenes_ctx}
故事设定: {req.description}
类型: {req.genre}

请生成接下来 {batch} 个分镜（序号从 {start_seq} 开始），{'这是最后一批，需要给故事一个合理的收尾。' if is_last else ''}{duration_hint}

严格按照以下 JSON 格式输出（不要输出其他内容）:
{{
  "scenes": [
    {{
      "sequence": {start_seq},
      "scene_description": "画面描述（角色动作、表情、构图）",
      "background_description": "纯场景环境描述",
      "scene_id": "场景名称（引用已知场景库中的 name）",
      "characters": ["出镜角色名（引用已知角色名）"],
      "dialogues": [{{"character_id": "角色名", "text": "台词", "emotion": "开心/悲伤/愤怒/惊讶/平静"}}],
      "narration": "旁白或null",
      "emotion": "happy/sad/angry/neutral/tense/romantic",
      "duration": 3.0,
      "transition": "cut",
      "camera": "特写/近景/中景/全景/远景"
    }}
  ]
}}

要求:
1. 延续之前的故事情节，保持连贯
2. scene_id 必须引用已知场景库，characters 必须引用已知角色
3. 对白自然口语化，分镜时长 2-8 秒
4. 严格生成 {batch} 个分镜"""

                more_data = await llm_json_call(prompt_n)
                more_panels = more_data.get("scenes", [])
                all_panels.extend(more_panels)
                remaining -= batch

            script_data["scenes"] = all_panels

        # 保存到数据库
        project.script_data = script_data
        if script_data.get("scenes"):
            project.panels = script_data["scenes"]
        if not project.genre and script_data.get("genre"):
            project.genre = script_data["genre"]

        # Extract character definitions from script
        script_characters = script_data.get("characters", [])
        existing_chars = project.characters or []
        existing_names = {c.get("name") for c in existing_chars if c.get("name")}
        for char in script_characters:
            name = char.get("name", "")
            if name and name not in existing_names:
                existing_chars.append({
                    "name": name,
                    "appearance": char.get("appearance", ""),
                    "personality": char.get("personality", ""),
                    "voice_description": char.get("voice_description", ""),
                    "referenceImage": "",
                })
                existing_names.add(name)

        # Extract scene library entries as scene-type characters
        scene_library = script_data.get("scene_library", [])
        for scene in scene_library:
            scene_name = scene.get("name", "")
            scene_desc = scene.get("description", "")
            if scene_name and not any(
                c.get("_type") == "scene" and c.get("name") == scene_name
                for c in existing_chars
            ):
                existing_chars.append({
                    "_type": "scene",
                    "name": scene_name,
                    "description": scene_desc,
                    "image": "",
                    "referenceImage": "",
                })

        project.characters = existing_chars
        project.current_step = 1
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="脚本生成成功")
    except json.JSONDecodeError:
        return error_response(error="ParseError", message="AI 返回 JSON 解析失败", code=500)
    except RuntimeError as e:
        logger.error(f"脚本生成 LLM 调用失败: {e}")
        return error_response(error="LLMError", message=f"AI 服务调用失败: {e}", code=500)
    except Exception as e:
        logger.error(f"脚本生成异常: {e}")
        return error_response(error="ServerError", message=f"脚本生成失败: {e}", code=500)


# ==================== 角色管理 ====================

@router.put("/{project_id}/characters", summary="更新角色列表")
def update_characters(project_id: int, characters: list, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        project.characters = characters
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="角色已更新")
    except Exception:
        db.rollback()
        raise


@router.post("/{project_id}/characters/{char_index}/reference-image", summary="上传角色参考图")
async def upload_character_reference(
    project_id: int,
    char_index: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)

    import os, uuid
    from src import config

    characters = project.characters or []
    if char_index < 0 or char_index >= len(characters):
        raise ValidationException("角色索引越界")

    upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    _ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if ext.lower() not in _ALLOWED_IMAGE_EXT:
        return error_response(error="UploadError", message=f"不支持的图片格式: {ext}", code=400)
    save_name = f"char_{char_index}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, save_name)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        return error_response(error="UploadError", message="图片文件不能超过 10MB", code=400)
    with open(file_path, "wb") as f:
        f.write(content)

    web_path = f"static/projects/{project_id}/{save_name}"
    characters[char_index]["referenceImage"] = web_path
    # Scenes use 'image' field, characters use 'referenceImage'
    if characters[char_index].get("_type") == "scene" or characters[char_index].get("Type") == "scene":
        characters[char_index]["image"] = web_path
    flag_modified(project, "characters")
    db.commit()
    db.refresh(project)

    return success_response(data=project.to_dict(), message="参考图上传成功")


@router.post("/{project_id}/characters/{char_index}/generate-reference", summary="AI生成角色参考图")
async def generate_character_reference(
    project_id: int,
    char_index: int,
    db: Session = Depends(get_db),
):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)

    import os, uuid, asyncio
    from src import config
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    characters = project.characters or []
    if char_index < 0 or char_index >= len(characters):
        raise ValidationException("角色索引越界")

    char = characters[char_index]
    is_scene = char.get("_type") == "scene" or char.get("Type") == "scene"
    style = project.style or "动漫"

    if is_scene:
        scene_desc = char.get("description", "")
        scene_name = char.get("name", "")
        style_prefix = _get_style_prefix(style, "scene")
        prompt = f"{style_prefix}, {scene_name}, {scene_desc}, wide shot, no characters, environment only"
    else:
        appearance = char.get("appearance", "")
        name = char.get("name", "角色")
        style_prefix = _get_style_prefix(style, "character")
        prompt = f"{style_prefix}, {name}, {appearance}, front view, white background, character reference sheet"

    client = get_client()
    image_model = cfg_get("core_nexus.image_model") or None
    result = await client.text_to_image_async(prompt=prompt, model=image_model)

    image_bytes = result.get("image_bytes")
    if not image_bytes:
        return success_response(data={"stub": True}, message="图片生成服务未返回有效数据")

    upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)
    save_name = f"char_{char_index}_ref_{uuid.uuid4().hex[:8]}.png"
    dst = os.path.join(upload_dir, save_name)
    with open(dst, "wb") as f:
        f.write(image_bytes)

    web_path = f"static/projects/{project_id}/{save_name}"
    characters[char_index]["referenceImage"] = web_path
    if characters[char_index].get("_type") == "scene" or characters[char_index].get("Type") == "scene":
        characters[char_index]["image"] = web_path
    flag_modified(project, "characters")
    db.commit()
    db.refresh(project)

    result = project.to_dict()
    chars_check = result.get("characters", [])
    print(f"[AI-GEN] project_id={project_id}, char_index={char_index}, total_chars={len(chars_check)}")
    if char_index < len(chars_check):
        c = chars_check[char_index]
        print(f"[AI-GEN] char[{char_index}] referenceImage={c.get('referenceImage', 'MISSING')}")
    return success_response(data=result, message="参考图生成完成")


# ==================== 分镜操作 ====================

@router.put("/{project_id}/panels", summary="更新分镜列表")
def update_panels(project_id: int, panels: list, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        project.panels = panels
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="分镜已更新")
    except Exception:
        db.rollback()
        raise


@router.post("/{project_id}/panels/upload-image", summary="上传分镜图片")
async def upload_panel_image(
    project_id: int,
    panel_index: int = Query(..., ge=0, description="分镜索引"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)

    import os, uuid
    from src import config

    panels = project.panels or []
    if panel_index < 0 or panel_index >= len(panels):
        raise ValidationException("分镜索引越界")

    upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    _ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if ext.lower() not in _ALLOWED_IMAGE_EXT:
        return error_response(error="UploadError", message=f"不支持的图片格式: {ext}", code=400)
    save_name = f"panel_{panel_index}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, save_name)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return error_response(error="UploadError", message="图片文件不能超过 10MB", code=400)
    with open(file_path, "wb") as f:
        f.write(content)

    web_path = f"static/projects/{project_id}/{save_name}"
    panels[panel_index]["generated_image_path"] = web_path
    flag_modified(project, "panels")
    db.commit()
    db.refresh(project)

    return success_response(data=project.to_dict(), message="分镜图片上传成功")


@router.post("/{project_id}/panels/generate-image", summary="生成分镜图片")
async def generate_panel_image(project_id: int, req: GeneratePanelImageRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        import os, uuid
        from src import config
        from src.shared.utils.core_nexus_client import get_client
        from src.shared.utils.config_manager import get as cfg_get
        client = get_client()

        panels = project.panels or []
        idx = req.panel_index
        if idx < 0 or idx >= len(panels):
            raise ValidationException("分镜索引越界")

        panel = panels[idx]
        style = project.style or "动漫"

        # 组合完整 prompt：场景环境 + 角色动作
        # DB 中 panels JSON 可能是 camelCase（前端保存）或 snake_case（LLM 生成）
        bg_desc = panel.get("background_description") or panel.get("backgroundDescription") or ""
        scene_desc = panel.get("scene_description") or panel.get("sceneDescription") or req.scene_description or ""
        camera = panel.get("camera") or ""

        prompt_parts = []
        if bg_desc:
            prompt_parts.append(f"Background: {bg_desc}")
        if scene_desc:
            prompt_parts.append(f"Scene: {scene_desc}")

        # 如果有 scene_id，从 scene_library 补充环境描述
        scene_id = panel.get("scene_id") or panel.get("sceneId") or ""
        if scene_id:
            script_data = project.script_data or {}
            scene_library = script_data.get("scene_library", []) if isinstance(script_data, dict) else []
            for s in scene_library:
                if s.get("name") == scene_id and s.get("description"):
                    prompt_parts.insert(0, f"Environment: {s['description']}")
                    break

        style_prefix = _get_style_prefix(style, "panel")
        full_prompt = f"{style_prefix}, {', '.join(prompt_parts)}"

        if camera:
            full_prompt += f", {camera}"

        # 注入出镜角色外貌描述
        panel_chars = panel.get("characters") or panel.get("characterIds") or []
        project_chars = project.characters or []
        char_descs = []
        for pc in panel_chars:
            for rc in project_chars:
                if rc.get("name") == pc and rc.get("appearance"):
                    char_descs.append(f"{pc}: {rc['appearance']}")
        if char_descs:
            full_prompt += f", featuring: {'; '.join(char_descs)}"

        print(f"\n{'='*60}\n[PANEL-IMG] project={project_id}, panel={idx}\n  prompt={full_prompt}\n{'='*60}")
        logger.warning(f"[PANEL-IMG] project={project_id}, panel={idx}, prompt={full_prompt[:200]}")
        image_model = cfg_get("core_nexus.image_model") or None

        # 图片生成耗时长（含 core-nexus 内部重试），使用更长超时
        payload = {"prompt": full_prompt}
        if image_model:
            payload["model"] = image_model
        payload["generation"] = {"width": 1024, "height": 1024}
        response = await client._request_async('POST', '/text-to-image', json_data=payload, timeout=180)
        result = client._extract_image_output(response)

        image_bytes = result.get("image_bytes")
        print(f"[PANEL-IMG] image_bytes size: {len(image_bytes) if image_bytes else 0}")
        if not image_bytes:
            return success_response(data={"stub": True, "message": "图片生成服务未返回有效数据"}, message="图片生成功能暂未开放")

        # 保存图片到项目目录
        upload_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
        os.makedirs(upload_dir, exist_ok=True)
        save_name = f"panel_{idx}_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(upload_dir, save_name)
        with open(save_path, "wb") as f:
            f.write(image_bytes)

        panel["generated_image_path"] = f"static/projects/{project_id}/{save_name}"
        print(f"[PANEL-IMG] saved: {save_name}")
        flag_modified(project, "panels")
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="图片生成完成")
    except Exception as e:
        import traceback
        print(f"[PANEL-IMG-ERROR] {e}")
        traceback.print_exc()
        logger.error(f"分镜图片生成失败: {e}", exc_info=True)
        raise ExternalServiceException(service_name="CoreNexus", message=f"分镜图片生成失败: {e}")


@router.post("/{project_id}/panels/generate-audio", summary="生成分镜语音")
def generate_panel_audio(project_id: int, req: GeneratePanelAudioRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        from src.shared.utils.core_nexus_client import get_client
        import base64, uuid, os
        from src import config

        panels = project.panels or []
        idx = req.panel_index
        if idx < 0 or idx >= len(panels):
            raise ValidationException("分镜索引越界")

        panel = panels[idx]
        text = req.text
        if not text:
            dialogues = panel.get("dialogues") or []
            text = " ".join([d.get("text", "") for d in dialogues])
        if not text:
            raise ValidationException("没有可用的文本内容")

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
            flag_modified(project, "panels")
            db.commit()
            db.refresh(project)

        return success_response(data=project.to_dict(), message="语音生成完成")
    except Exception as e:
        logger.error(f"分镜语音生成失败: {e}", exc_info=True)
        raise ExternalServiceException(service_name="CoreNexus", message="分镜语音生成失败，请稍后重试")


# ==================== 分镜视频生成 ====================

@router.post("/{project_id}/panels/generate-video", summary="生成分镜视频")
async def generate_panel_video(project_id: int, request: GeneratePanelVideoRequest, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)

    panels = project.panels or []
    if request.panel_index < 0 or request.panel_index >= len(panels):
        raise ValidationException(f"分镜索引 {request.panel_index} 超出范围")

    panel = panels[request.panel_index]

    try:
        import os, base64, uuid
        from src import config
        from src.shared.utils.core_nexus_client import get_client
        from src.shared.utils.config_manager import get as cfg_get

        image_path = panel.get("generated_image_path") or panel.get("generatedImagePath")
        if not image_path:
            raise ValidationException("请先生成分镜图片")

        # 将 web_path 转为绝对路径
        abs_image_path = os.path.join(str(config.ROOT_DIR_WIN), image_path.lstrip('/'))
        if not os.path.exists(abs_image_path):
            raise ValidationException(f"图片文件不存在: {image_path}")

        # 将图片转为 data URL
        ext = os.path.splitext(abs_image_path)[1].lower()
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
        mime = mime_map.get(ext, 'image/png')
        with open(abs_image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        image_data_url = f"data:{mime};base64,{image_b64}"

        # 构建 prompt
        style = project.style or "动漫"
        style_prefix = _get_style_prefix(style, "panel")
        scene_desc = panel.get("scene_description") or panel.get("sceneDescription") or ""
        bg_desc = panel.get("background_description") or panel.get("backgroundDescription") or ""
        prompt_parts = [p for p in [bg_desc, scene_desc] if p]
        prompt = f"{style_prefix}, {', '.join(prompt_parts)}" if prompt_parts else style_prefix

        duration = request.duration or panel.get("duration", 3.0)

        client = get_client()
        i2v_model = cfg_get("core_nexus.image_to_video_model") or None
        logger.info(f"[PANEL-VIDEO] project={project_id}, panel={request.panel_index}, model={i2v_model}, duration={duration}")
        result = await client.image_to_video_async(
            image=image_data_url,
            prompt=prompt,
            model=i2v_model,
            duration=int(duration),
        )

        video_bytes = result.get("video_bytes")
        if not video_bytes:
            return error_response(error="GenerateError", message="视频生成服务未返回有效数据", code=500)

        output_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "projects", str(project_id))
        os.makedirs(output_dir, exist_ok=True)
        save_name = f"panel_{request.panel_index}_{uuid.uuid4().hex[:8]}.mp4"
        save_path = os.path.join(output_dir, save_name)
        with open(save_path, 'wb') as f:
            f.write(video_bytes)

        web_path = f"static/projects/{project_id}/{save_name}"
        panel["generated_video_path"] = web_path
        panel["duration"] = duration
        flag_modified(project, "panels")
        db.commit()
        db.refresh(project)

        return success_response(data=project.to_dict(), message="分镜视频生成完成")
    except httpx.HTTPStatusError as e:
        import traceback
        print(f"[PANEL-VIDEO-ERROR] {e.response.status_code} | {e.response.text[:500]}")
        traceback.print_exc()
        db.rollback()
        raise ExternalServiceException(service_name="CoreNexus", message=f"core-nexus 返回 {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        import traceback
        print(f"[PANEL-VIDEO-ERROR] {e}")
        traceback.print_exc()
        db.rollback()
        logger.error(f"分镜视频生成失败: {e}", exc_info=True)
        raise ExternalServiceException(service_name="CoreNexus", message=f"分镜视频生成失败: {e}")


# ==================== BGM ====================

@router.put("/{project_id}/bgm", summary="更新BGM配置")
def update_bgm_config(project_id: int, bgm_config: dict, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
    try:
        project.bgm_config = bgm_config
        db.commit()
        db.refresh(project)
        return success_response(data=project.to_dict(), message="BGM配置已更新")
    except Exception:
        db.rollback()
        raise


# ==================== 合成 ====================

@router.post("/{project_id}/compose", summary="合成漫剧视频")
def compose_comic_video(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ComicProject).filter(ComicProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException(resource_type="ComicProject", resource_id=project_id)
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
            characters=project.characters or [],
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
        raise ExternalServiceException(service_name="ComicComposer", message="漫剧合成失败，请稍后重试")

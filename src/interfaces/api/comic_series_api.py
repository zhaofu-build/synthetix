"""
漫剧系列 API — 管理系列、全局角色库、集数
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from src.shared.models.response import success_response, error_response
from src.infrastructure.db.session import get_db
from src.domain.entities.comic_series import ComicSeries
from src.domain.entities.comic_project import ComicProject

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 系列 CRUD ====================

@router.post("", summary="创建漫剧系列")
def create_series(req: dict, db: Session = Depends(get_db)):
    name = req.get("name", "").strip()
    if not name:
        return error_response(error="InvalidParam", message="系列名称不能为空", code=400)

    existing = db.query(ComicSeries).filter(ComicSeries.name == name).first()
    if existing:
        return error_response(error="DuplicateName", message="系列名称已存在", code=400)

    series = ComicSeries(
        name=name,
        description=req.get("description"),
        style=req.get("style", "动漫"),
        genre=req.get("genre"),
        characters=req.get("characters", []),
        bgm_config=req.get("bgm_config"),
    )
    db.add(series)
    db.commit()
    db.refresh(series)
    return success_response(data=series.to_dict(), message="系列创建成功", code=201)


@router.get("", summary="漫剧系列列表")
def list_series(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        total = db.query(ComicSeries).count()
        items = db.query(ComicSeries).order_by(ComicSeries.updated_at.desc()) \
            .offset((page - 1) * page_size).limit(page_size).all()

        result_items = []
        for s in items:
            s_dict = s.to_dict()
            # 统计集数
            episode_count = db.query(ComicProject).filter(ComicProject.series_id == s.id).count()
            s_dict["episode_count"] = episode_count
            result_items.append(s_dict)

        return success_response(data={
            "items": result_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        return error_response(error="QueryError", message=str(e), code=500)


@router.get("/{series_id}", summary="获取漫剧系列")
def get_series(series_id: int, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)

    result = series.to_dict()
    # 加载集数列表
    episodes = db.query(ComicProject).filter(ComicProject.series_id == series_id) \
        .order_by(ComicProject.episode_number).all()
    result["episodes"] = [ep.to_dict() for ep in episodes]
    return success_response(data=result)


@router.patch("/{series_id}", summary="更新漫剧系列")
def update_series(series_id: int, req: dict, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)
    try:
        for field in ("name", "description", "style", "genre", "characters", "bgm_config"):
            val = req.get(field)
            if val is not None:
                setattr(series, field, val)
        db.commit()
        db.refresh(series)
        return success_response(data=series.to_dict(), message="更新成功")
    except Exception as e:
        db.rollback()
        return error_response(error="UpdateError", message=str(e), code=500)


@router.delete("/{series_id}", summary="删除漫剧系列")
def delete_series(series_id: int, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)
    try:
        # 将关联项目设为无系列
        db.query(ComicProject).filter(ComicProject.series_id == series_id) \
            .update({"series_id": None})
        db.delete(series)
        db.commit()
        return success_response(message="系列已删除")
    except Exception as e:
        db.rollback()
        return error_response(error="DeleteError", message=str(e), code=500)


# ==================== 集数管理 ====================

@router.post("/{series_id}/episodes", summary="创建新集数")
def create_episode(series_id: int, req: dict, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)

    name = req.get("name", "").strip()
    if not name:
        name = f"{series.name} 第{(db.query(ComicProject).filter(ComicProject.series_id == series_id).count() + 1)}集"

    # 自动计算集数序号
    max_ep = db.query(ComicProject).filter(ComicProject.series_id == series_id) \
        .order_by(ComicProject.episode_number.desc()).first()
    episode_number = (max_ep.episode_number + 1) if max_ep else 1

    # 继承系列的角色和画风
    project = ComicProject(
        name=name,
        description=req.get("description", f"系列「{series.name}」第{episode_number}集"),
        genre=series.genre,
        style=series.style,
        status="draft",
        series_id=series_id,
        episode_number=episode_number,
        target_duration=req.get("target_duration"),
        characters=series.characters or [],
        bgm_config=series.bgm_config or {},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return success_response(data=project.to_dict(), message="集数创建成功", code=201)


@router.get("/{series_id}/episodes", summary="获取系列集数列表")
def list_episodes(series_id: int, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)

    episodes = db.query(ComicProject).filter(ComicProject.series_id == series_id) \
        .order_by(ComicProject.episode_number).all()
    return success_response(data=[ep.to_dict() for ep in episodes])


# ==================== 系列角色同步 ====================

@router.post("/{series_id}/sync-characters", summary="同步角色到所有集数")
def sync_characters_to_episodes(series_id: int, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)

    characters = series.characters or []
    episodes = db.query(ComicProject).filter(ComicProject.series_id == series_id).all()
    for ep in episodes:
        ep.characters = characters

    db.commit()
    return success_response(message=f"已同步角色到 {len(episodes)} 个集数")


# ==================== 系列画风同步 ====================

@router.post("/{series_id}/sync-style", summary="同步画风到所有集数")
def sync_style_to_episodes(series_id: int, db: Session = Depends(get_db)):
    series = db.query(ComicSeries).filter(ComicSeries.id == series_id).first()
    if not series:
        return error_response(error="NotFound", message="系列不存在", code=404)

    episodes = db.query(ComicProject).filter(ComicProject.series_id == series_id).all()
    for ep in episodes:
        ep.style = series.style
        ep.genre = series.genre

    db.commit()
    return success_response(message=f"已同步画风到 {len(episodes)} 个集数")

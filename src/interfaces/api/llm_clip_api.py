"""
LLM 创意剪辑 API 模块

提供基于 LLM 的创意内容生成 RESTful API 接口

路由前缀: /api/ai
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.shared.models.base import BaseReq
from src.shared.models.response import success_response, error_response
from src.infrastructure.db.session import get_db
from src.application.services.creative_service import CreativeService
import logging as logger

router = APIRouter()


def get_creative_service(db: Session = Depends(get_db)) -> CreativeService:
    """获取 CreativeService 依赖"""
    return CreativeService(db)


@router.post("/keywords", summary="根据关键词获取素材")
def get_source_by_keywords(
    req: BaseReq,
    service: CreativeService = Depends(get_creative_service)
):
    """根据创意关键词获取视频素材

    Args:
        req.creative: 创意描述

    Returns:
        视频素材下载结果
    """
    try:
        result = service.get_source_by_keywords(req.creative)
        return success_response(data=result, message="获取视频素材成功")
    except Exception as e:
        logger.error(f"获取视频素材失败: {e}")
        return error_response(error="CreativeError", message=str(e), code=500)


@router.post("/video-transitions", summary="创建带转场的视频")
def create_video_transitions(
    req: BaseReq,
    service: CreativeService = Depends(get_creative_service)
):
    """创建带转场的视频

    Args:
        req.creative: 创意描述
        req.audioUrl: 音频URL（可选）

    Returns:
        最终视频路径
    """
    try:
        audio_url = req.dict().get("audioUrl", None)
        result = service.create_video_with_transitions(
            creative=req.creative,
            audio_url=audio_url
        )
        return success_response(data=result, message="视频处理成功")
    except ValueError as e:
        return error_response(error="VideoProcessError", message=str(e), code=400)
    except Exception as e:
        logger.error(f"视频处理失败: {e}")
        return error_response(error="VideoProcessError", message=str(e), code=500)


@router.get("/optimize-prompt", summary="优化提示词")
def optimize_prompt(
    prompt: str = Query(..., description="原始提示词"),
    prompt_type: str = Query(..., description="类型 1:文生图 2:图生图 3:图生视频"),
    service: CreativeService = Depends(get_creative_service)
):
    """优化提示词

    Args:
        prompt: 原始提示词
        prompt_type: 提示词类型

    Returns:
        优化后的提示词
    """
    try:
        optimized_prompt = service.optimize_prompt(prompt, prompt_type)
        return success_response(
            data={"optimized_prompt": optimized_prompt},
            message="提示词优化成功"
        )
    except Exception as e:
        logger.error(f"提示词优化失败: {e}")
        return error_response(error="LLMError", message=str(e), code=500)

"""
扩展管理 API

提供扩展的列表、启用/禁用接口。
"""
from pydantic import BaseModel
from fastapi import APIRouter

from src.shared.models.response import success_response
from src.agent.extension_loader import (
    load_extensions,
    register_extension_tools,
    list_extensions,
    toggle_extension,
)

router = APIRouter()


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("", summary="列出所有扩展")
async def get_extensions():
    load_extensions()
    return success_response(data=list_extensions())


@router.post("/{name}/toggle", summary="启用/禁用扩展")
async def toggle_ext(name: str, req: ToggleRequest):
    ok = toggle_extension(name, req.enabled)
    if not ok:
        return success_response(success=False, message=f"扩展 {name} 不存在")
    return success_response(message=f"扩展 {name} 已{'启用' if req.enabled else '禁用'}")


@router.post("/reload", summary="重新加载扩展")
async def reload_extensions():
    load_extensions()
    register_extension_tools()
    return success_response(data=list_extensions())

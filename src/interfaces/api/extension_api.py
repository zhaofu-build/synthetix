"""
扩展管理 API

提供扩展的列表、创建、删除、启用/禁用接口。
"""
from pydantic import BaseModel
from fastapi import APIRouter

from src.shared.models.response import success_response, error_response
from src.agent.extension_loader import (
    load_extensions,
    register_extension_tools,
    list_extensions,
    toggle_extension,
    create_extension,
    update_extension,
    delete_extension,
)

router = APIRouter()


class ToggleRequest(BaseModel):
    enabled: bool


class CreateExtensionRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    mode: str = "all"


class UpdateExtensionRequest(BaseModel):
    description: str = None
    system_prompt: str = None
    mode: str = None


@router.get("", summary="列出所有扩展")
async def get_extensions():
    load_extensions()
    return success_response(data=list_extensions())


@router.post("", summary="创建扩展")
async def create_ext(req: CreateExtensionRequest):
    result = create_extension(req.name, req.description, req.system_prompt, req.mode)
    if not result.get("success"):
        return error_response(error="CreateError", message=result.get("error", "创建失败"), code=400)
    return success_response(data=result, message="扩展创建成功")


@router.delete("/{name}", summary="删除扩展")
async def delete_ext(name: str):
    ok = delete_extension(name)
    if not ok:
        return error_response(error="NotFound", message=f"扩展 {name} 不存在", code=404)
    return success_response(message=f"扩展 {name} 已删除")


@router.put("/{name}", summary="更新扩展")
async def update_ext(name: str, req: UpdateExtensionRequest):
    ok = update_extension(name, req.description, req.system_prompt, req.mode)
    if not ok:
        return error_response(error="NotFound", message=f"扩展 {name} 不存在", code=404)
    return success_response(message=f"扩展 {name} 已更新")


@router.post("/{name}/toggle", summary="启用/禁用扩展")
async def toggle_ext(name: str, req: ToggleRequest):
    ok = toggle_extension(name, req.enabled)
    if not ok:
        return error_response(error="NotFound", message=f"扩展 {name} 不存在", code=404)
    return success_response(message=f"扩展 {name} 已{'启用' if req.enabled else '禁用'}")


@router.post("/reload", summary="重新加载扩展")
async def reload_extensions():
    load_extensions()
    register_extension_tools()
    return success_response(data=list_extensions())

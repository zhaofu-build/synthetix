"""
任务管理 API

提供后台任务的查看、取消、删除等接口
"""
from fastapi import APIRouter
from typing import Optional

from src.shared.models.response import success_response, error_response
from src.shared.utils.task_manager import task_manager

router = APIRouter()


@router.get("", summary="获取任务列表")
async def list_tasks(status: Optional[str] = None):
    """获取所有任务，可按状态过滤"""
    tasks = []
    for task_id, task in task_manager._tasks.items():
        if status and task.status.value != status:
            continue
        tasks.append(task_manager.get_task_status(task_id))
    return success_response(data={"tasks": tasks, "count": len(tasks)})


@router.get("/stats", summary="任务统计")
async def task_stats():
    """获取任务统计信息"""
    stats = {"total": 0, "pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
    for task in task_manager._tasks.values():
        stats["total"] += 1
        key = task.status.value
        if key in stats:
            stats[key] += 1
    return success_response(data=stats)


@router.get("/{task_id}", summary="获取任务详情")
async def get_task(task_id: str):
    """获取单个任务详情"""
    status = task_manager.get_task_status(task_id)
    if not status:
        return error_response(error="TaskNotFound", message="任务不存在", code=404)
    return success_response(data=status)


@router.post("/{task_id}/cancel", summary="取消任务")
async def cancel_task(task_id: str):
    """取消等待中的任务"""
    task = task_manager.get_task(task_id)
    if not task:
        return error_response(error="TaskNotFound", message="任务不存在", code=404)
    if task.status.value not in ("pending", "running"):
        return error_response(error="InvalidState", message=f"任务状态为 {task.status.value}，无法取消", code=400)
    task.status = task.status.__class__("cancelled")
    return success_response(message="任务已取消")


@router.delete("/{task_id}", summary="删除任务")
async def delete_task(task_id: str):
    """删除已完成的任务记录"""
    if task_id not in task_manager._tasks:
        return error_response(error="TaskNotFound", message="任务不存在", code=404)
    del task_manager._tasks[task_id]
    return success_response(message="任务已删除")

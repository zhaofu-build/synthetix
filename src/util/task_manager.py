"""异步任务处理模块

提供后台任务执行功能，用于处理耗时的操作
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class TaskResult:
    """任务结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None


@dataclass
class Task:
    """后台任务"""
    id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0.0 - 1.0

    async def run(self):
        """执行任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

        try:
            # 如果是协程函数，直接 await
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(*self.args, **self.kwargs)
            else:
                # 如果是普通函数，在线程池中执行
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, self.func, *self.args, **self.kwargs
                )

            self.result = TaskResult(success=True, data=result)
            self.status = TaskStatus.COMPLETED
            self.progress = 1.0

        except Exception as e:
            logger.error(f"Task {self.id} failed: {e}", exc_info=True)
            self.result = TaskResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__
            )
            self.status = TaskStatus.FAILED
            self.error = str(e)

        finally:
            self.completed_at = datetime.now()


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)

    def create_task(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> str:
        """创建新任务

        Args:
            name: 任务名称
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())

        task = Task(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs
        )

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"Task created: {task_id} ({name})")
        return task_id

    async def submit_task(self, task_id: str) -> bool:
        """提交任务执行

        Args:
            task_id: 任务ID

        Returns:
            是否成功提交
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.error(f"Task not found: {task_id}")
                return False

            if task.status != TaskStatus.PENDING:
                logger.warning(f"Task {task_id} already processed")
                return False

        # 在后台执行任务
        asyncio.create_task(task.run())
        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_task_status(
        self,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.get_task(task_id)
        if not task:
            return None

        return {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "progress": task.progress,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error": task.error,
            "result": task.result.data if task.result and task.result.success else None,
        }

    async def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Optional[TaskResult]:
        """等待任务完成

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            任务结果
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            task = self.get_task(task_id)
            if not task:
                return None

            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return task.result

            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Task {task_id} timeout after {timeout}s")
                    return None

            await asyncio.sleep(0.5)

    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """清理旧任务

        Args:
            max_age_seconds: 任务最大保留时间（秒）
        """
        now = datetime.now()
        to_remove = []

        with self._lock:
            for task_id, task in self._tasks.items():
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# 全局任务管理器实例
task_manager = TaskManager()


async def create_and_run_task(
    name: str,
    func: Callable,
    *args,
    auto_run: bool = True,
    **kwargs
) -> str:
    """创建并运行任务

    Args:
        name: 任务名称
        func: 要执行的函数
        auto_run: 是否自动运行
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        任务ID
    """
    task_id = task_manager.create_task(name, func, *args, **kwargs)

    if auto_run:
        await task_manager.submit_task(task_id)

    return task_id


# 便捷函数
def run_in_background(name: str, func: Callable, *args, **kwargs) -> str:
    """在后台运行任务（同步接口）

    注意：此函数创建任务但不立即执行，需要配合 submit_task 使用
    """
    return task_manager.create_task(name, func, *args, **kwargs)

"""
PlanExecutor — 计划执行引擎

一次规划 + 按序执行模式的核心引擎。接收有序步骤列表，
自动解析 $stepN 引用，按序执行工具，通过 SSE 流式推送进度。
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# $stepN.field 引用解析正则
_STEP_REF_PATTERN = re.compile(r'\$step(\d+)\.(.+)')

# 简化的 JSON path 解析，支持 field 和 field.subfield 以及数组 [0]
_INDEX_PATTERN = re.compile(r'^(\w+)$')
_NESTED_PATTERN = re.compile(r'^(\w+)\.(\w+(?:\.\w+)*)$')
_ARRAY_PATTERN = re.compile(r'^(\w+)\[(\d+)\]$')
_ARRAY_NESTED_PATTERN = re.compile(r'^(\w+)\[(\d+)\]\.(\w+(?:\.\w+)*)$')


@dataclass
class PlanStep:
    """计划中的单个步骤"""
    id: str
    tool: str
    params: Dict[str, Any]
    description: str
    risk: str = "safe"  # safe / needs_confirm / destructive
    estimated_time: Optional[int] = None


def resolve_step_references(params: Dict[str, Any], step_results: Dict[str, Dict]) -> Dict[str, Any]:
    """
    将参数中的 $stepN.field 引用替换为前序步骤的实际返回值。

    支持格式:
      $step0.video_id          → step_results["step_0"]["video_id"]
      $step0.output_path       → step_results["step_0"]["output_path"]
      $step0.videos[0].id      → step_results["step_0"]["videos"][0]["id"]
      $step0.result.field      → step_results["step_0"]["result"]["field"]
    """
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and "$step" in value:
            match = _STEP_REF_PATTERN.match(value)
            if match:
                step_num = match.group(1)
                path = match.group(2)
                step_key = f"step_{step_num}"
                actual = _resolve_path(step_results.get(step_key, {}), path)
                if actual is not None:
                    resolved[key] = actual
                else:
                    logger.warning(f"[PlanExecutor] 无法解析引用: {value}，保留原值")
                    resolved[key] = value
            else:
                resolved[key] = value
        elif isinstance(value, dict):
            resolved[key] = resolve_step_references(value, step_results)
        elif isinstance(value, list):
            resolved[key] = [
                resolve_step_references(item, step_results) if isinstance(item, dict)
                else _resolve_ref_if_needed(item, step_results)
                for item in value
            ]
        else:
            resolved[key] = value
    return resolved


def _resolve_ref_if_needed(value: Any, step_results: Dict[str, Dict]) -> Any:
    """对列表中的字符串元素也做引用解析"""
    if isinstance(value, str) and "$step" in value:
        match = _STEP_REF_PATTERN.match(value)
        if match:
            step_num = match.group(1)
            path = match.group(2)
            step_key = f"step_{step_num}"
            actual = _resolve_path(step_results.get(step_key, {}), path)
            return actual if actual is not None else value
    return value


def _resolve_path(data: Any, path: str) -> Any:
    """根据点分路径从嵌套 dict/list 中取值"""
    current = data
    # 处理形如 "videos[0].id" 的路径
    parts = re.split(r'\.', path)
    for part in parts:
        if current is None:
            return None
        # 检查数组索引：field[0]
        arr_match = re.match(r'^(\w+)\[(\d+)\]$', part)
        if arr_match:
            field_name = arr_match.group(1)
            idx = int(arr_match.group(2))
            if isinstance(current, dict) and field_name in current:
                current = current[field_name]
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


class PlanExecutor:
    """
    计划执行器：按序执行步骤列表，自动解析步骤间引用。

    复用 ReActAgent._execute_tool() 确保验证、Hook、拦截器全部生效。
    """

    def __init__(self, agent):
        self.agent = agent

    async def execute_plan_stream(
        self,
        steps: List[PlanStep],
        state,
        progress_callback=None,
    ):
        """
        按序执行计划步骤，yield SSE 事件。

        Args:
            steps: 有序步骤列表
            state: DialogState 会话状态
            progress_callback: 可选的进度回调（用于下载类工具）

        Yields:
            SSE 事件 dict，包含 type 键
        """
        step_results: Dict[str, Dict] = {}
        completed_steps = 0
        total_steps = len(steps)
        plan_start_time = time.time()

        yield {
            "type": "plan_start",
            "total_steps": total_steps,
        }

        for i, step in enumerate(steps):
            step_start_time = time.time()

            # 解析前序引用
            try:
                resolved_params = resolve_step_references(step.params, step_results)
            except Exception as e:
                logger.error(f"[PlanExecutor] 解析步骤 {step.id} 参数引用失败: {e}")
                yield {
                    "type": "plan_step_result",
                    "step_id": step.id,
                    "step_index": i,
                    "tool": step.tool,
                    "success": False,
                    "error": f"参数引用解析失败: {e}",
                    "duration_ms": 0,
                }
                yield {
                    "type": "plan_done",
                    "status": "error",
                    "completed_steps": completed_steps,
                    "total_steps": total_steps,
                    "duration_ms": int((time.time() - plan_start_time) * 1000),
                }
                return

            # 检查是否还有未解析的引用（依赖缺失）
            unresolved = self._find_unresolved_refs(resolved_params)
            if unresolved:
                yield {
                    "type": "plan_step_result",
                    "step_id": step.id,
                    "step_index": i,
                    "tool": step.tool,
                    "success": False,
                    "error": f"存在未解析的引用: {unresolved}，前序步骤可能未返回预期数据",
                    "duration_ms": 0,
                }
                yield {
                    "type": "plan_done",
                    "status": "error",
                    "completed_steps": completed_steps,
                    "total_steps": total_steps,
                    "duration_ms": int((time.time() - plan_start_time) * 1000),
                }
                return

            # yield 开始事件
            yield {
                "type": "plan_step_start",
                "step_id": step.id,
                "step_index": i,
                "total_steps": total_steps,
                "tool": step.tool,
                "params": resolved_params,
                "description": step.description,
                "risk": step.risk,
            }

            # 破坏性工具需要用户确认
            tool_obj = self._get_tool(step.tool)
            permission = tool_obj.permission if tool_obj else step.risk
            if permission == "destructive" or step.risk == "destructive":
                yield {
                    "type": "plan_step_confirm",
                    "step_id": step.id,
                    "step_index": i,
                    "tool": step.tool,
                    "params": resolved_params,
                    "description": step.description,
                    "permission": "destructive",
                }
                # 等待确认
                confirmed = await self._wait_for_step_confirm(state, step.id)
                if not confirmed:
                    yield {
                        "type": "plan_step_result",
                        "step_id": step.id,
                        "step_index": i,
                        "tool": step.tool,
                        "success": False,
                        "error": "用户取消执行",
                        "duration_ms": int((time.time() - step_start_time) * 1000),
                    }
                    yield {
                        "type": "plan_done",
                        "status": "cancelled",
                        "completed_steps": completed_steps,
                        "total_steps": total_steps,
                        "duration_ms": int((time.time() - plan_start_time) * 1000),
                    }
                    return

            # 执行工具
            progress_dict = {} if step.tool == "download_video" else None
            try:
                result = await self.agent._execute_tool(
                    tool_name=step.tool,
                    params=resolved_params,
                    state=state,
                    progress_dict=progress_dict,
                )
            except Exception as e:
                logger.error(f"[PlanExecutor] 步骤 {step.id} ({step.tool}) 执行异常: {e}")
                result = {"success": False, "error": str(e)}

            duration_ms = int((time.time() - step_start_time) * 1000)

            # 存储结果供后续步骤引用
            step_results[step.id] = result
            if result.get("success", True):
                completed_steps += 1

            # 更新状态追踪
            self._update_state_from_result(state, step.tool, result)

            # yield 结果事件
            yield {
                "type": "plan_step_result",
                "step_id": step.id,
                "step_index": i,
                "total_steps": total_steps,
                "tool": step.tool,
                "success": result.get("success", True),
                "error": result.get("error"),
                "preview": result.get("preview"),
                "media_info": result.get("media_info"),
                "result": result,
                "duration_ms": duration_ms,
            }

        # 全部完成
        yield {
            "type": "plan_done",
            "status": "completed",
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "duration_ms": int((time.time() - plan_start_time) * 1000),
        }

    def _get_tool(self, tool_name: str):
        """从 registry 获取工具对象"""
        from src.agent.tool_registry import registry
        return registry.get_tool(tool_name)

    def _find_unresolved_refs(self, params: Dict) -> List[str]:
        """检查参数中是否还有未解析的 $stepN 引用"""
        unresolved = []
        for value in params.values():
            if isinstance(value, str) and "$step" in value and _STEP_REF_PATTERN.match(value):
                unresolved.append(value)
            elif isinstance(value, dict):
                unresolved.extend(self._find_unresolved_refs(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and "$step" in item and _STEP_REF_PATTERN.match(item):
                        unresolved.append(item)
        return unresolved

    async def _wait_for_step_confirm(self, state, step_id: str) -> bool:
        """等待用户确认破坏性工具步骤"""
        confirm_key = f"_step_confirm_{step_id}"
        state.metadata[confirm_key] = False
        timeout = 120  # 破坏性操作给 2 分钟确认时间
        check_interval = 0.5
        elapsed = 0
        while elapsed < timeout:
            if state.metadata.get(confirm_key) is True:
                return True
            if state.metadata.get("_plan_cancelled"):
                return False
            await asyncio.sleep(check_interval)
            elapsed += check_interval
        return False

    def _update_state_from_result(self, state, tool_name: str, result: Dict):
        """更新会话状态（last_video_list 等），与 TAOR 循环保持一致"""
        if tool_name == "list_videos" and result.get("success"):
            videos = result.get("videos", result.get("result", []))
            if isinstance(videos, list):
                state.last_video_list = videos[:10]

        if tool_name in ("cut_video", "merge_videos", "smart_clip", "download_video"):
            video_id = result.get("video_id")
            if video_id:
                state.last_referenced_video_id = video_id

    @staticmethod
    def confirm_step(state, step_id: str):
        """外部调用，确认某个破坏性步骤"""
        confirm_key = f"_step_confirm_{step_id}"
        state.metadata[confirm_key] = True

    @staticmethod
    def cancel_plan(state):
        """外部调用，取消整个计划"""
        state.metadata["_plan_cancelled"] = True

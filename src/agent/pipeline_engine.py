"""
PipelineEngine — 流水线模板引擎

解析流水线模板定义，处理 {{param}} 用户参数替换，
将模板步骤转换为 PlanStep 列表供 PlanExecutor 执行。
"""
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.agent.plan_executor import PlanStep

logger = logging.getLogger(__name__)

# {{param}} 用户参数引用正则
_USER_PARAM_PATTERN = re.compile(r'\{\{(\w+)\}\}')


@dataclass
class PipelineTemplate:
    """流水线模板"""
    name: str
    description: str
    icon: str = "⚡"
    category: str = "general"
    user_params: List[Dict[str, Any]] = None
    steps: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.user_params is None:
            self.user_params = []
        if self.steps is None:
            self.steps = []


class PipelineEngine:
    """流水线模板引擎：解析模板 → 替换参数 → 生成 PlanStep 列表"""

    def resolve_user_params(
        self,
        template: PipelineTemplate,
        user_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        合并用户输入与默认值，校验必填参数。

        Returns:
            合并后的参数 dict

        Raises:
            ValueError: 缺少必填参数
        """
        resolved = {}
        for param_def in template.user_params:
            key = param_def.get("key")
            default = param_def.get("default")
            required = param_def.get("required", False)
            value = user_input.get(key, default)
            if required and value is None:
                raise ValueError(f"缺少必填参数: {key} ({param_def.get('label', key)})")
            resolved[key] = value
        return resolved

    def resolve_template_steps(
        self,
        template: PipelineTemplate,
        resolved_params: Dict[str, Any],
    ) -> List[PlanStep]:
        """
        将模板步骤中的 {{param}} 替换为用户填写的值。
        $stepN 引用保留，由 PlanExecutor 在执行时解析。

        Returns:
            PlanStep 列表
        """
        plan_steps = []
        for i, step_def in enumerate(template.steps):
            step_id = step_def.get("id", f"step_{i}")
            tool = step_def.get("tool", "")
            raw_params = step_def.get("params", {})
            description = step_def.get("description", f"执行 {tool}")
            risk = step_def.get("risk", "safe")
            estimated_time = step_def.get("estimated_time")

            # 替换 {{param}} 引用
            resolved_p = self._replace_user_params(raw_params, resolved_params)

            plan_steps.append(PlanStep(
                id=step_id,
                tool=tool,
                params=resolved_p,
                description=description,
                risk=risk,
                estimated_time=estimated_time,
            ))

        return plan_steps

    def template_to_plan(
        self,
        template_def: Dict[str, Any],
        user_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        从模板定义和用户输入生成完整计划。

        Args:
            template_def: 模板定义 dict（来自 manifest.json）
            user_input: 用户填写的参数

        Returns:
            {plan_id, summary, steps: [PlanStep dict]}
        """
        template = PipelineTemplate(
            name=template_def.get("name", ""),
            description=template_def.get("description", ""),
            icon=template_def.get("icon", "⚡"),
            category=template_def.get("category", "general"),
            user_params=template_def.get("user_params", []),
            steps=template_def.get("steps", []),
        )

        resolved_params = self.resolve_user_params(template, user_input)
        plan_steps = self.resolve_template_steps(template, resolved_params)

        return {
            "plan_id": f"pipeline_{int(time.time())}",
            "summary": template.description,
            "steps": [
                {
                    "id": s.id,
                    "tool": s.tool,
                    "params": s.params,
                    "description": s.description,
                    "risk": s.risk,
                    "estimated_time": s.estimated_time,
                }
                for s in plan_steps
            ],
        }

    def _replace_user_params(
        self,
        params: Dict[str, Any],
        resolved: Dict[str, Any],
    ) -> Dict[str, Any]:
        """递归替换 params dict 中的 {{param}} 引用"""
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 替换所有 {{param}} 引用
                def replacer(match):
                    param_name = match.group(1)
                    val = resolved.get(param_name)
                    if val is None:
                        return match.group(0)  # 未找到，保留原值
                    return str(val)
                result[key] = _USER_PARAM_PATTERN.sub(replacer, value)
            elif isinstance(value, dict):
                result[key] = self._replace_user_params(value, resolved)
            elif isinstance(value, list):
                result[key] = [
                    self._replace_user_params(item, resolved) if isinstance(item, dict)
                    else (_USER_PARAM_PATTERN.sub(
                        lambda m: str(resolved.get(m.group(1), m.group(0))),
                        item
                    ) if isinstance(item, str) and "{{" in item else item)
                    for item in value
                ]
            else:
                result[key] = value
        return result

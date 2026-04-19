"""
多 Agent 协作系统

提供专业化子 Agent：规划 Agent、执行 Agent、审查 Agent。
主 Agent 通过 agent_tool_call 调度子 Agent。
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from src.agent.tool_registry import registry
from src.application.services.llm_adapter import generate_response_async

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"


# 子 Agent 系统提示词
AGENT_PROMPTS = {
    AgentRole.PLANNER: (
        "你是一个视频剪辑方案规划专家。\n"
        "你的任务是根据用户需求和素材情况，制定详细的剪辑方案。\n"
        "输出格式要求：\n"
        "1. 方案概述（目标、风格、时长）\n"
        "2. 分镜列表（每个片段的起止时间、素材来源、特效要求）\n"
        "3. 音频方案（BGM选择、配音要求）\n"
        "只输出方案，不执行任何工具调用。"
    ),
    AgentRole.EXECUTOR: (
        "你是一个视频剪辑执行专家。\n"
        "你接收规划方案，按步骤调用工具执行剪辑操作。\n"
        "执行原则：\n"
        "1. 按分镜顺序逐步执行\n"
        "2. 每步确认成功后再执行下一步\n"
        "3. 遇到失败时尝试替代方案\n"
        "你可以使用所有可用工具。"
    ),
    AgentRole.REVIEWER: (
        "你是一个视频质量审查专家。\n"
        "你检查剪辑结果的质量，评估以下方面：\n"
        "1. 技术质量（分辨率、码率、帧率是否达标）\n"
        "2. 内容连贯性（片段之间过渡是否自然）\n"
        "3. 音视频同步（字幕、配音是否对齐）\n"
        "4. 整体观感（节奏、氛围是否符合需求）\n"
        "输出审查报告，标注通过/需修改的项目。只输出报告，不执行工具。"
    ),
}


async def run_sub_agent(
    role: AgentRole,
    task: str,
    context: str = "",
    project_id: Optional[int] = None,
) -> str:
    """
    运行子 Agent

    Args:
        role: Agent 角色
        task: 任务描述
        context: 上下文信息
        project_id: 项目 ID

    Returns:
        子 Agent 的输出
    """
    system_prompt = AGENT_PROMPTS[role]
    if context:
        system_prompt += f"\n\n## 上下文\n{context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    # 子 Agent 可调用工具（执行 Agent 需要）
    if role == AgentRole.EXECUTOR:
        tools_desc = registry.get_tools_description()
        messages[0]["content"] += f"\n\n## 可用工具\n{tools_desc}"

        # TAOR 循环
        for iteration in range(3):
            response = await generate_response_async(messages=messages, temperature=0.5, max_tokens=2048)
            import re
            tool_calls = re.findall(
                r'<tool_call\s+name=["\']([^"\']+)["\']>\s*\n?(.*?)\n?\s*</tool_call\s*>?',
                response, re.DOTALL
            )
            if not tool_calls:
                return response.strip()

            # 执行工具
            import json
            for tool_name, params_str in tool_calls:
                try:
                    params = json.loads(params_str.strip())
                except (json.JSONDecodeError, ValueError):
                    params = {}
                if project_id and "project_id" not in params:
                    params["project_id"] = project_id

                tool = registry.get_tool(tool_name)
                if tool:
                    try:
                        result = await tool.execute(**params)
                        messages.append({"role": "assistant", "content": response})
                        result_str = json.dumps(result, ensure_ascii=False, default=str)
                        messages.append({"role": "user", "content": f"工具 {tool_name} 结果: {result_str[:1000]}"})
                    except Exception as e:
                        messages.append({"role": "user", "content": f"工具 {tool_name} 失败: {str(e)}"})
                break  # 每轮只执行一个工具，简化逻辑
        return response.strip() if 'response' in dir() else "执行超时"

    # 规划/审查 Agent 不调用工具，直接生成
    response = await generate_response_async(messages=messages, temperature=0.7, max_tokens=2048)
    return response.strip()


async def run_pipeline(
    user_request: str,
    project_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    运行完整的多 Agent 协作流水线：规划 → 执行 → 审查

    Returns:
        流水线结果
    """
    # Stage 1: 规划
    logger.info("[MultiAgent] Stage 1: 规划")
    plan = await run_sub_agent(
        AgentRole.PLANNER,
        task=user_request,
        project_id=project_id,
    )

    # Stage 2: 执行
    logger.info("[MultiAgent] Stage 2: 执行")
    execution_result = await run_sub_agent(
        AgentRole.EXECUTOR,
        task=f"请执行以下剪辑方案:\n{plan}",
        project_id=project_id,
    )

    # Stage 3: 审查
    logger.info("[MultiAgent] Stage 3: 审查")
    review = await run_sub_agent(
        AgentRole.REVIEWER,
        task=f"请审查以下剪辑结果:\n{execution_result}",
        context=f"原始需求: {user_request}\n方案: {plan}",
    )

    return {
        "plan": plan,
        "execution": execution_result,
        "review": review,
        "status": "completed",
    }

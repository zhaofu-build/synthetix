"""
PlanGenerator — LLM 计划生成器

一次 LLM 调用生成完整的工具执行计划（JSON 格式），
包含有序步骤列表和 $stepN 引用关系。
"""
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from src.agent.tool_registry import registry
from src.agent.project_memory import get_project_memory
from src.application.services.llm_adapter import generate_response_async

logger = logging.getLogger(__name__)

PLAN_GENERATION_SYSTEM_PROMPT = """你是视频剪辑方案规划器。用户描述需求后，你需要生成一个结构化的工具执行计划。

## 输出格式

严格输出 JSON（不要包含其他文字）：
{
  "summary": "方案概述（一句话）",
  "steps": [
    {
      "id": "step_0",
      "tool": "工具名",
      "params": {"参数名": "参数值"},
      "description": "人类可读的操作描述",
      "risk": "safe",
      "estimated_time": 5
    }
  ]
}

## 字段说明

- id: 步骤 ID，格式 "step_N"（从 step_0 开始递增）
- tool: 要调用的工具名（必须是下方列出的工具之一）
- params: 工具参数
  - project_id 留 null，系统会自动注入
  - 当参数依赖前序步骤结果时，使用引用格式 "$stepN.field"
- description: 这一步做什么
- risk: "safe"（只读/生成）/ "needs_confirm"（修改视频）/ "destructive"（删除/覆盖）
- estimated_time: 预估耗时（秒），不确定时可省略

## 步骤间引用规则

后续步骤可以引用前序步骤的返回值，格式为 $stepN.field：
- "$step0.videos[0].id" → 第 0 步返回的 videos 数组中第一个的 id
- "$step0.output_path" → 第 0 步返回的 output_path
- "$step0.video_id" → 第 0 步返回的 video_id
- "$step0.result.subtitle" → 第 0 步 result 中的 subtitle 字段

注意：只能引用编号更小的步骤（已执行的步骤）。

## 规划原则

1. **先查后做**：第一步通常是 list_videos 获取素材列表
2. **最小步骤**：能合并的依赖操作放在相邻步骤，通过引用传递
3. **并行标注**：如果多个步骤互不依赖，可以标注它们（目前按顺序执行）
4. **信息补全**：分析、转录、下载等获取信息的步骤放在前面
5. **操作在后**：剪切、合并、加字幕等修改操作放在信息获取之后
6. **合理预估**：分析/转录约 10-60s，剪切约 5-15s，合并约 10-30s，生成 TTS 约 10-30s

## 当前上下文

- 项目 ID: {project_id}
- 项目名: {project_name}
- 当前日期: {current_date}
"""

PLAN_GENERATION_USER_TEMPLATE = """用户需求：{user_input}

请生成执行计划。"""


def _get_enhanced_tools_description(mode: str = "video") -> str:
    """获取增强版工具描述，包含参数详情，帮助 LLM 生成正确的参数"""
    descriptions = []
    for tool in registry._tools.values():
        if tool.category == "common" or tool.category == mode:
            params_detail = []
            for pname, pinfo in tool.parameters.items():
                if isinstance(pinfo, dict):
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    params_detail.append(f"    {pname}: {ptype} — {pdesc}")
                else:
                    params_detail.append(f"    {pname}")
            params_block = "\n".join(params_detail) if params_detail else "    (无参数)"
            descriptions.append(
                f"- {tool.name}: {tool.description}\n"
                f"  参数:\n{params_block}"
            )
    return "\n".join(descriptions)


def _get_context_section(state) -> str:
    """构建上下文信息（素材列表等）"""
    parts = []
    if hasattr(state, 'last_video_list') and state.last_video_list:
        parts.append("当前素材列表（部分）：")
        for i, v in enumerate(state.last_video_list[:10]):
            vid = v.get("id") or v.get("video_id")
            name = v.get("name") or v.get("file_name") or v.get("original_name", "")
            duration = v.get("duration", "")
            parts.append(f"  {i+1}. [id={vid}] {name} (时长: {duration})")
    if hasattr(state, 'last_referenced_video_id') and state.last_referenced_video_id:
        parts.append(f"最近引用的视频 ID: {state.last_referenced_video_id}")
    return "\n".join(parts)


async def generate_plan_from_llm(
    user_input: str,
    state,
    mode: str = "video",
) -> Dict[str, Any]:
    """
    一次 LLM 调用生成完整执行计划。

    Args:
        user_input: 用户输入的剪辑需求
        state: DialogState 会话状态
        mode: 当前模式（video/comic）

    Returns:
        {
            "plan_id": "plan_xxx",
            "summary": "...",
            "steps": [PlanStep dict, ...]
        }
    """
    from datetime import datetime

    # 获取工具描述
    tools_desc = _get_enhanced_tools_description(mode)

    # 获取项目名
    project_name = ""
    project_id = getattr(state, 'project_id', None)
    if project_id:
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.video_project import VideoProject
            with get_db_context() as db:
                proj = db.query(VideoProject).filter(VideoProject.id == project_id).first()
                if proj:
                    project_name = proj.name
        except Exception:
            pass

    # 构建系统提示词
    system_prompt = PLAN_GENERATION_SYSTEM_PROMPT.format(
        project_id=project_id or "无",
        project_name=project_name or "无",
        current_date=datetime.now().strftime("%Y年%m月%d日"),
    )

    # 注入工具列表
    system_prompt += f"\n\n## 可用工具\n\n{tools_desc}"

    # 注入项目偏好记忆
    if project_id:
        try:
            memory = get_project_memory(project_id)
            pref_summary = memory.get_relevant_summary(query=user_input[:200])
            if pref_summary:
                system_prompt += f"\n\n## 用户偏好\n\n{pref_summary}"
        except Exception:
            pass

    # 注入当前上下文（素材列表等）
    context = _get_context_section(state)
    if context:
        system_prompt += f"\n\n## 当前项目信息\n\n{context}"

    # 注入扩展提示词
    try:
        from src.agent.extension_loader import get_extensions_prompt_section
        ext_section = get_extensions_prompt_section(current_mode=mode)
        if ext_section:
            system_prompt += f"\n\n{ext_section}"
    except Exception:
        pass

    # 构建消息
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": PLAN_GENERATION_USER_TEMPLATE.format(user_input=user_input)},
    ]

    # 调用 LLM
    try:
        response_text = await generate_response_async(
            messages,
            temperature=0.3,
            max_tokens=2000,
            timeout=60,
        )
    except Exception as e:
        logger.error(f"[PlanGenerator] LLM 调用失败: {e}")
        return {
            "plan_id": f"plan_{int(time.time())}",
            "summary": f"方案生成失败: {e}",
            "steps": [],
            "error": str(e),
        }

    # 解析 JSON
    plan_data = _parse_plan_json(response_text)

    # 生成 plan_id
    plan_id = f"plan_{int(time.time())}"
    plan_data["plan_id"] = plan_id

    # 校验步骤格式
    steps = plan_data.get("steps", [])
    validated_steps = []
    for i, step in enumerate(steps):
        step_id = step.get("id", f"step_{i}")
        tool_name = step.get("tool", "")
        params = step.get("params", {})
        description = step.get("description", f"执行 {tool_name}")
        risk = step.get("risk", "safe")
        estimated_time = step.get("estimated_time")

        # 验证工具是否存在
        if not registry.has_tool(tool_name):
            logger.warning(f"[PlanGenerator] 步骤 {step_id} 引用了未知工具: {tool_name}")
            step["_warning"] = f"工具 {tool_name} 不存在，可能执行失败"

        # 自动注入 project_id
        if project_id and "project_id" not in params:
            params["project_id"] = project_id

        validated_steps.append({
            "id": step_id,
            "tool": tool_name,
            "params": params,
            "description": description,
            "risk": risk,
            "estimated_time": estimated_time,
        })

    plan_data["steps"] = validated_steps
    return plan_data


def _parse_plan_json(text: str) -> Dict[str, Any]:
    """从 LLM 返回文本中提取 JSON 计划"""
    # 尝试直接解析
    text = text.strip()
    if text.startswith("```"):
        # 去除 markdown 代码块
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # 尝试提取 JSON 块
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"[PlanGenerator] JSON 解析失败: {e}")

    # 解析失败，返回空计划
    return {
        "summary": text[:200] if text else "方案解析失败",
        "steps": [],
        "raw": text,
    }

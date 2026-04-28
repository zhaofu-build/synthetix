"""
LLM 文本生成服务

通过 core-nexus-ai API 调用大语言模型
"""
import asyncio
import logging
from typing import Optional, List, Dict, AsyncGenerator

from src.shared.utils.core_nexus_client import get_client
from src.shared.utils.config_manager import get as cfg_get
from src import config

logger = logging.getLogger(__name__)


def _estimate_complexity(messages: List[Dict[str, str]]) -> str:
    """Estimate task complexity from message content.

    Returns: 'simple' | 'medium' | 'complex'
    """
    last_msg = messages[-1]["content"] if messages else ""
    recent = " ".join(m.get("content", "") for m in messages[-3:])
    total_len = len(recent)

    # Tool calls → always complex
    if "<tool_call" in recent:
        return "complex"

    # Keywords indicating complex reasoning
    complex_keywords = [
        "分析", "规划", "方案", "策略", "对比", "评估", "推理",
        "总结", "归纳", "创作", "编写", "设计", "优化",
        "analyze", "plan", "design", "create", "compare", "reason",
    ]
    simple_keywords = [
        "是什么", "多少", "什么时候", "列出", "查询", "获取",
        "什么", "哪个", "是否", "有没有",
        "what", "how many", "when", "list", "get", "is",
    ]

    complex_score = sum(1 for kw in complex_keywords if kw in last_msg)
    simple_score = sum(1 for kw in simple_keywords if kw in last_msg)

    if complex_score >= 2 or total_len > 2000:
        return "complex"
    if complex_score > 0 and simple_score == 0:
        return "medium"
    if simple_score > 0 and complex_score == 0:
        return "simple"
    if total_len > 500:
        return "medium"
    return "simple"


def select_model(
    messages: List[Dict[str, str]],
    force_model: str = None,
    iteration: int = 0,
    task_type: str = None,
) -> str:
    """根据消息复杂度选择快/慢模型（三层路由）

    Args:
        messages: 对话消息列表
        force_model: 强制使用的模型名
        iteration: TAOR 循环轮次（>0 时始终用主模型）
        task_type: 显式任务类型 "simple"/"medium"/"complex"，覆盖自动检测
    """
    if force_model:
        return force_model

    configured_model = cfg_get("core_nexus.llm_model")
    fast_model = config.FAST_MODEL
    # 设置页配置优先于环境变量默认值
    slow_model = configured_model or config.SLOW_MODEL or ""
    # Optional mid-tier model
    mid_model = cfg_get("llm.mid_model") or slow_model

    if not fast_model:
        return slow_model

    # Subsequent iterations always use the strongest model
    if iteration > 0:
        logger.info(f"[ModelRouter] 轮次 {iteration} → 强模型: {slow_model}")
        return slow_model

    # Determine complexity
    complexity = task_type or _estimate_complexity(messages)

    if complexity == "simple":
        logger.info(f"[ModelRouter] simple → 快模型: {fast_model}")
        return fast_model
    elif complexity == "medium":
        logger.info(f"[ModelRouter] medium → 中模型: {mid_model}")
        return mid_model
    else:
        logger.info(f"[ModelRouter] complex → 强模型: {slow_model}")
        return slow_model


def generate_response(
    messages: List[Dict[str, str]],
    provider: str = None,  # 保留参数用于兼容，实际不再使用
    api_key: Optional[str] = None,  # 保留参数用于兼容
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_version: Optional[str] = None,
    secret_key: Optional[str] = None,
    account_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    provider_options: Optional[Dict] = None,
) -> str:
    """
    使用 core-nexus-ai API 进行文本生成（同步）

    Args:
        messages: 对话消息列表，格式为 [{"role": "user/assistant", "content": "..."}]
        provider: 保留参数（兼容性）
        api_key: 保留参数（兼容性）
        model_name: 模型名称（可选）
        base_url: 保留参数（兼容性）
        api_version: 保留参数（兼容性）
        secret_key: 保留参数（兼容性）
        account_id: 保留参数（兼容性）
        temperature: 温度参数
        max_tokens: 最大 token 数
        provider_options: 供应商特有参数（如 use_kv_cache, session_id）

    Returns:
        生成的文本内容
    """
    try:
        client = get_client()
        response = client.llm_generate(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_options=provider_options,
        )
        return response
    except Exception as e:
        logger.error(f"LLM 调用异常: {str(e)}")
        raise RuntimeError(f"LLM 调用失败: {str(e)}") from e


def generate_response_stream(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    provider_options: Optional[Dict] = None,
):
    """
    使用 core-nexus-ai API 进行流式文本生成（同步）

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数
        provider_options: 供应商特有参数（如 use_kv_cache, session_id）

    Yields:
        生成的文本片段
    """
    try:
        client = get_client()
        for chunk in client.llm_generate_stream(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_options=provider_options,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"LLM 流式调用异常: {str(e)}")
        raise RuntimeError(f"LLM 流式调用失败: {str(e)}") from e


async def generate_response_async(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    provider_options: Optional[Dict] = None,
) -> str:
    """
    使用 core-nexus-ai API 进行异步文本生成（真异步，不阻塞事件循环）

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数
        provider_options: 供应商特有参数（如 use_kv_cache, session_id）

    Returns:
        生成的文本内容
    """
    try:
        import time as _time
        from src.shared.utils.observability import record_ai_call
        t0 = _time.monotonic()
        client = get_client()
        response = await client.llm_generate_async(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_options=provider_options,
        )
        latency_ms = (_time.monotonic() - t0) * 1000
        record_ai_call(
            service="LLM", model=model_name or "default",
            tokens_in=sum(len(m.get("content", "")) // 4 for m in messages),
            tokens_out=len(response) // 4 if response else 0,
            latency_ms=latency_ms, success=True,
        )
        return response
    except Exception as e:
        try:
            from src.shared.utils.observability import record_ai_call
            record_ai_call(service="LLM", model=model_name or "default", success=False, error=str(e))
        except Exception:
            pass
        logger.error(f"LLM 异步调用异常: {str(e)}")
        raise RuntimeError(f"LLM 异步调用失败: {str(e)}") from e


async def chunked_generate(
    text: str,
    prompt: str,
    chunk_size: int = 3000,
    model_name: Optional[str] = None,
    merge_prompt: Optional[str] = None,
) -> str:
    """分块处理长文本：自动分段 → 逐块处理 → 合并结果

    Args:
        text: 待处理长文本（如字幕）
        prompt: 每个分块的处理指令
        chunk_size: 每块字符数上限
        model_name: 模型名
        merge_prompt: 合并阶段的指令（可选，默认拼接）

    Returns:
        合并后的结果
    """
    import re

    # Pre-process: split into lines, filter empty/punctuation-only
    lines = [l.strip() for l in text.split("\n") if l.strip() and not re.match(r'^[\s\W\d]+$', l)]

    # Chunk by character count, preferring line boundaries
    chunks = []
    current_chunk = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    if not chunks:
        return ""

    # Single chunk — process directly
    if len(chunks) == 1:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": chunks[0]},
        ]
        return await generate_response_async(messages, model_name=model_name)

    # Multi-chunk: process each then merge
    partial_results = []
    for i, chunk in enumerate(chunks):
        messages = [
            {"role": "system", "content": f"{prompt}\n\n[这是第 {i+1}/{len(chunks)} 部分，请只处理这部分]"},
            {"role": "user", "content": chunk},
        ]
        try:
            result = await generate_response_async(messages, model_name=model_name)
            partial_results.append(result or "")
        except Exception as e:
            logger.warning(f"分块处理第 {i+1} 块失败: {e}")
            partial_results.append("")

    # Merge phase
    if merge_prompt:
        combined = "\n\n---\n\n".join(partial_results)
        messages = [
            {"role": "system", "content": merge_prompt},
            {"role": "user", "content": combined},
        ]
        return await generate_response_async(messages, model_name=model_name)

    return "\n\n".join(partial_results)


async def generate_response_stream_async(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    provider_options: Optional[Dict] = None,
) -> AsyncGenerator[str, None]:
    """
    使用 core-nexus-ai API 进行异步流式文本生成

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数
        provider_options: 供应商特有参数（如 use_kv_cache, session_id）

    Yields:
        生成的文本片段
    """
    try:
        client = get_client()
        async for chunk in client.llm_generate_stream_async(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_options=provider_options,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"LLM 异步流式调用异常: {str(e)}")
        raise RuntimeError(f"LLM 异步流式调用失败: {str(e)}") from e


if __name__ == "__main__":
    # 测试代码
    test_messages = [{"role": "user", "content": "你好，请介绍一下你自己"}]

    print("测试 LLM 调用:")
    response = generate_response(test_messages)
    print(response)

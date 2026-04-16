"""
LLM 文本生成服务

通过 core-nexus-ai API 调用大语言模型
"""
import asyncio
import logging
from typing import Optional, List, Dict, AsyncGenerator

from src.shared.utils.core_nexus_client import get_client

logger = logging.getLogger(__name__)


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

    Returns:
        生成的文本内容
    """
    try:
        client = get_client()
        response = client.llm_generate(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
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
):
    """
    使用 core-nexus-ai API 进行流式文本生成（同步）

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数

    Yields:
        生成的文本片段
    """
    try:
        client = get_client()
        for chunk in client.llm_generate_stream(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
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
) -> str:
    """
    使用 core-nexus-ai API 进行异步文本生成（真异步，不阻塞事件循环）

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数

    Returns:
        生成的文本内容
    """
    try:
        client = get_client()
        return await client.llm_generate_async(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    except Exception as e:
        logger.error(f"LLM 异步调用异常: {str(e)}")
        raise RuntimeError(f"LLM 异步调用失败: {str(e)}") from e


async def generate_response_stream_async(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """
    使用 core-nexus-ai API 进行异步流式文本生成

    Args:
        messages: 对话消息列表
        model_name: 模型名称（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数

    Yields:
        生成的文本片段
    """
    try:
        client = get_client()
        async for chunk in client.llm_generate_stream_async(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
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

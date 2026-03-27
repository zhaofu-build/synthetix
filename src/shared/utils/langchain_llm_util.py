"""
LangChain LLM模型处理工具类
提供各种大语言模型的处理功能
"""
import logging
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser


def convert_messages(messages: List[dict]) -> List:
    """将字典格式的消息转换为LangChain消息对象"""
    converted_messages = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            converted_messages.append(HumanMessage(content=content))
        elif role == "system":
            converted_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            converted_messages.append(AIMessage(content=content))
        else:
            converted_messages.append(HumanMessage(content=content))
    
    return converted_messages


def handle_g4f(messages: List, model_name: str = None) -> str:
    """处理g4f免费模型请求"""
    from langchain_g4f import G4FProvider
    import g4f
    
    model = model_name or "gpt-3.5-turbo-16k-0613"
    llm = G4FProvider(
        model=model,
        provider=g4f.Provider.Bing,
        temperature=0.7
    )
    
    chain = llm | StrOutputParser()
    response = chain.invoke(messages)
    return response.replace("\n", "")


def handle_qwen(messages: List, api_key: str, model_name: str) -> str:
    """处理阿里云通义千问请求"""
    from langchain_community.chat_models import ChatTongyi
    
    llm = ChatTongyi(
        model_name=model_name,
        dashscope_api_key=api_key,
        temperature=0.7
    )
    
    chain = llm | StrOutputParser()
    response = chain.invoke(messages)
    return response.replace("\n", "")


def handle_gemini(messages: List, api_key: str, model_name: str) -> str:
    """处理Google Gemini模型请求"""
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.7
    )
    
    chain = llm | StrOutputParser()
    response = chain.invoke(messages)
    return response.replace("\n", "")


def handle_cloudflare(messages: List, api_key: str, account_id: str, model_name: str) -> str:
    """处理Cloudflare Workers AI请求"""
    import requests
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"messages": [msg.dict() for msg in messages]}
    )
    return response.json()["result"]["response"]


def handle_ernie(messages: List, api_key: str, secret_key: str, base_url: str) -> str:
    """处理百度文心一言请求"""
    import requests
    
    # 获取访问令牌
    token_response = requests.post(
        "https://aip.baidubce.com/oauth/2.0/token",
        params={"grant_type": "client_credentials", "client_id": api_key, "client_secret": secret_key}
    )
    token = token_response.json()["access_token"]

    # 生成响应
    response = requests.post(
        f"{base_url}?access_token={token}",
        json={"messages": [msg.dict() for msg in messages]},
        headers={"Content-Type": "application/json"}
    )
    return response.json().get("result", "")


def handle_azure(messages: List, api_key: str, model_name: str, base_url: str, api_version: str) -> str:
    """处理Azure OpenAI请求"""
    from langchain_openai import AzureChatOpenAI
    
    llm = AzureChatOpenAI(
        azure_deployment=model_name,
        azure_endpoint=base_url,
        api_key=api_key,
        api_version=api_version,
        temperature=0.7
    )
    
    chain = llm | StrOutputParser()
    response = chain.invoke(messages)
    return response.replace("\n", "")


def handle_openai_compatible(
    chat_messages: List,
    provider: str,
    api_key: str,
    model_name: str = None,
    base_url: str = None
) -> str:
    """处理OpenAI兼容API请求"""
    from langchain_openai import ChatOpenAI

    # 设置各供应商默认值
    if provider == "moonshot":
        base_url = base_url or "https://api.moonshot.cn/v1"
        model_name = model_name or "moonshot-v1-128k"
    elif provider == "ollama":
        api_key = api_key or "1"
        base_url = base_url or "http://localhost:11434/v1"
        model_name = model_name or "llama3.1:latest"
    elif provider == "deepseek":
        base_url = base_url or "https://api.deepseek.com/v1"
        model_name = model_name or "deepseek-chat"
    elif provider == "openai":
        base_url = base_url or "https://api.openai.com/v1"
        model_name = model_name or "gpt-3.5-turbo"

    # 参数校验
    if not api_key:
        raise ValueError(f"{provider} 需要api_key参数")
    if not model_name:
        raise ValueError(f"{provider} 需要model_name参数")
    if not base_url:
        raise ValueError(f"{provider} 需要base_url参数")

    # 创建LangChain LLM实例
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7
    )

    chain = llm | StrOutputParser()
    response = chain.invoke(chat_messages)
    return response.replace("\n", "")
"""
使用LangChain实现的大语言模型服务
"""
import logging
from typing import Optional, List, Dict, Any
import config
from src.util.langchain_llm_util import (
    convert_messages,
    handle_g4f,
    handle_qwen,
    handle_gemini,
    handle_cloudflare,
    handle_ernie,
    handle_azure,
    handle_openai_compatible
)


def generate_response(
    messages: List[Dict[str, str]],
    provider: str = config.llm_model,
    api_key: Optional[str] = config.llm_key,
    model_name: Optional[str] = config.model_name,
    base_url: Optional[str] = None,
    api_version: Optional[str] = None,
    secret_key: Optional[str] = None,
    account_id: Optional[str] = None,
) -> str:
    """
    使用LangChain实现的生成响应函数，与原use_llm接口保持一致
    """
    try:
        # 转换消息格式
        chat_messages = convert_messages(messages)
        
        # 根据供应商类型选择对应的处理函数
        if provider == "g4f":
            return handle_g4f(chat_messages, model_name)
        elif provider == "qwen":
            return handle_qwen(chat_messages, api_key, model_name)
        elif provider == "gemini":
            return handle_gemini(chat_messages, api_key, model_name)
        elif provider == "cloudflare":
            return handle_cloudflare(chat_messages, api_key, account_id, model_name)
        elif provider == "ernie":
            return handle_ernie(chat_messages, api_key, secret_key, base_url)
        elif provider == "azure":
            return handle_azure(chat_messages, api_key, model_name, base_url, api_version)
        elif provider in ["openai", "moonshot", "ollama", "deepseek", "oneapi"]:
            return handle_openai_compatible(
                chat_messages=chat_messages,
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                base_url=base_url
            )
        
        raise ValueError(f"不支持的供应商类型: {provider}")
    except Exception as e:
        logging.error(f"{provider} 模型调用异常: {str(e)}")
        return f"错误: {str(e)}"


if __name__ == "__main__":
    """
    支持的供应商及参数要求：
    - 'g4f'       : 免费模型，无需认证参数
    - 'openai'    : 需要api_key和model_name，默认模型gpt-3.5-turbo
    - 'azure'     : 需要api_key, model_name, base_url和api_version
    - 'moonshot'  : 需要api_key和model_name，默认API地址https://api.moonshot.cn/v1
    - 'ollama'    : 需要model_name，默认本地地址http://localhost:11434/v1
    - 'qwen'      : 需要api_key和model_name，需安装dashscope包
    - 'gemini'    : 需要api_key和model_name，需安装google-generativeai包
    - 'cloudflare': 需要api_key, account_id和model_name
    - 'ernie'     : 需要api_key, secret_key和base_url
    - 'deepseek'  : 需要api_key和model_name 模型名称：deepseek-chat  deepseek-reasoner
    - 'oneapi'    : 需要api_key, model_name和base_url
    """
    keywords_prompt = f"""
    扩写文案：
    我当然知道那不是我的月亮
    但有一刻
    月亮的确照在了我身上
    可生活不是电影
    我也缺少点运气
    我悄然触摸你
    却未曾料想
    你像蒲公英散开了
    到处啊
    都是你的模样
    """
    
    print("=========================================================")
    messages = [{"role": "user", "content": keywords_prompt}]
    
    # 尝试使用deepseek模型（根据用户偏好）
    try:
        response = _generate_response(
            messages=messages,
            provider="deepseek",
            api_key=config.llm_key,  # 使用配置文件中的API密钥
            model_name="deepseek-chat"
        )
        print(response)
    except Exception as e:
        print(f"DeepSeek调用失败: {e}")
        print("尝试使用g4f免费模型:")
        response = _generate_response(
            messages=messages,
            provider="g4f",
            model_name="gpt-3.5-turbo"
        )
        print(response)
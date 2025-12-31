import logging
from typing import Optional
import g4f
import requests
from openai import AzureOpenAI, OpenAI
import config


def _generate_response(
        messages: str,
        provider: str = config.llm_model,
        api_key: Optional[str] = config.llm_key,
        model_name: Optional[str] = config.model_name,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        secret_key: Optional[str] = None,
        account_id: Optional[str] = None,
) -> str:
    """
    使用指定的大模型生成文本回复

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
    - 'deepseek'  : 需要api_key和model_name
    - 'oneapi'    : 需要api_key, model_name和base_url
    """
    try:
        # 各供应商处理逻辑分流
        if provider == "g4f":
            return _handle_g4f(messages, model_name)

        elif provider == "qwen":
            return _handle_qwen(messages, api_key, model_name)

        # elif provider == "gemini":
        #     return _handle_gemini(messages, api_key, model_name)

        elif provider == "cloudflare":
            return _handle_cloudflare(messages, api_key, account_id, model_name)

        elif provider == "ernie":
            return _handle_ernie(messages, api_key, secret_key, base_url)

        elif provider == "azure":
            return _handle_azure(messages, api_key, model_name, base_url, api_version)

        elif provider in ["openai", "moonshot", "ollama", "deepseek", "oneapi"]:
            return _handle_openai_compatible(
                messages=messages,
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                base_url=base_url
            )

        raise ValueError(f"不支持的供应商类型: {provider}")

    except Exception as e:
        logging.error(f"{provider} 模型调用异常: {str(e)}")
        return f"错误: {str(e)}"


def _handle_g4f(messages: str, model_name: Optional[str]) -> str:
    """处理g4f免费模型请求"""
    model = model_name or "gpt-3.5-turbo-16k-0613"
    response = g4f.ChatCompletion.create(
        model=model,
        messages=messages,
    )
    return response.replace("\n", "")


def _handle_qwen(messages: str, api_key: str, model_name: str) -> str:
    """处理阿里云通义千问请求"""
    import dashscope

    dashscope.api_key = api_key
    response = dashscope.Generation.call(
        model=model_name,
        messages=messages
    )

    if response.status_code != 200:
        raise Exception(f"通义千问API错误: {response}")
    return response["output"]["text"].replace("\n", "")


def _handle_gemini(prompt: str, api_key: str, model_name: str) -> str:
    """处理Google Gemini模型请求"""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.candidates[0].content.parts[0].text


def _handle_cloudflare(messages: str, api_key: str, account_id: str, model_name: str) -> str:
    """处理Cloudflare Workers AI请求"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"messages": messages}
    )
    return response.json()["result"]["response"]


def _handle_ernie(messages: str, api_key: str, secret_key: str, base_url: str) -> str:
    """处理百度文心一言请求"""
    # 获取访问令牌
    token_response = requests.post(
        "https://aip.baidubce.com/oauth/2.0/token",
        params={"grant_type": "client_credentials", "client_id": api_key, "client_secret": secret_key}
    )
    token = token_response.json()["access_token"]

    # 生成响应
    response = requests.post(
        f"{base_url}?access_token={token}",
        json={"messages": messages},
        headers={"Content-Type": "application/json"}
    )
    return response.json().get("result", "")


def _handle_azure(
        messages: str,
        api_key: str,
        model_name: str,
        base_url: str,
        api_version: str
) -> str:
    """处理Azure OpenAI请求"""
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=base_url,
    )
    response = client.chat.completions.create(
        model=model_name,
        messages=messages
    )
    return response.choices[0].message.content


def _handle_openai_compatible(
        messages: str,
        provider: str,
        api_key: str,
        model_name: Optional[str],
        base_url: Optional[str]
) -> str:
    """处理OpenAI兼容API请求"""
    # 设置各供应商默认值
    if provider == "moonshot":
        base_url = base_url or "https://api.moonshot.cn/v1"
        model_name = model_name or "moonshot-v1-128k"
    elif provider == "ollama":
        if api_key is None:
            api_key = "1"
        base_url = base_url or "http://localhost:11434/v1"
        model_name = model_name or "llama3.1:latest "
    elif provider == "deepseek":
        base_url = base_url or "https://api.deepseek.com/v1"
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

    # 创建客户端并获取响应
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=messages
    )
    return response.choices[0].message.content


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
    print(_generate_response(messages))

"""
响应工具函数

提供 API 响应字段命名转换功能
"""
import re
from typing import Any, Dict, List


def to_camel_case(name: str) -> str:
    """
    将 snake_case 转换为 camelCase

    Args:
        name: snake_case 字符串

    Returns:
        camelCase 字符串
    """
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(name: str) -> str:
    """
    将 camelCase 转换为 snake_case

    Args:
        name: camelCase 字符串

    Returns:
        snake_case 字符串
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def convert_keys_to_camel(data: Any) -> Any:
    """
    递归将字典的所有 key 转换为 camelCase

    Args:
        data: 要转换的数据（字典、列表或基本类型）

    Returns:
        转换后的数据
    """
    if isinstance(data, dict):
        return {to_camel_case(k): convert_keys_to_camel(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_keys_to_camel(item) for item in data]
    else:
        return data


def convert_keys_to_snake(data: Any) -> Any:
    """
    递归将字典的所有 key 转换为 snake_case

    Args:
        data: 要转换的数据（字典、列表或基本类型）

    Returns:
        转换后的数据
    """
    if isinstance(data, dict):
        return {to_snake_case(k): convert_keys_to_snake(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_keys_to_snake(item) for item in data]
    else:
        return data

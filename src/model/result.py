"""
响应工具函数
提供统一的成功和错误响应格式
"""

from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse


def success_result(
        data: Any = None,
        message: str = "操作成功",
        code: int = 200,
        **kwargs
) -> JSONResponse:
    """
    创建成功响应

    Args:
        data: 响应数据
        message: 成功消息
        code: HTTP状态码
        **kwargs: 其他参数

    Returns:
        JSONResponse: 统一格式的成功响应
    """
    result_data = {
        "success": True,
        "data": data,
        "message": message,
        "code": code
    }
    result_data.update(kwargs)

    return JSONResponse(status_code=code, content=result_data)


def error_result(
        message: str = "操作失败",
        code: int = 400,
        error_type: str = "BusinessError",
        details: Optional[Dict] = None,
        path: str = ""
) -> JSONResponse:
    """
    创建错误响应

    Args:
        message: 错误消息
        code: HTTP状态码
        error_type: 错误类型
        details: 错误详情
        path: 请求路径

    Returns:
        JSONResponse: 统一格式的错误响应
    """
    error_data = {
        "success": False,
        "data": None,
        "message": message,
        "code": code,
        "error_type": error_type,
        "path": path
    }

    return JSONResponse(status_code=code, content=error_data)
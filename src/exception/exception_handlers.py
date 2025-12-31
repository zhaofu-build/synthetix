"""
全局异常处理器
处理系统中所有未捕获的异常，提供统一的错误响应格式
"""

import logging
import traceback
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from src.exception.exceptions import (
    BusinessException,
    DatabaseException,
    ValidationException,
    AuthenticationException,
    PermissionException,
    ResourceNotFoundException
)

logger = logging.getLogger(__name__)

# 从环境变量获取DEBUG配置，默认为False
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'


async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """
    处理FastAPI的HTTPException
    """
    # 根据状态码选择日志级别
    if exc.status_code >= 500:
        log_level = logger.error
    elif exc.status_code == 404:
        log_level = logger.warning
    else:
        log_level = logger.warning
    
    error_msg = f"""
HTTPException捕获:
  状态码: {exc.status_code}
  错误信息: {exc.detail}
  请求URL: {request.url}
  请求方法: {request.method}
"""
    log_level(error_msg)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.detail,
            "code": exc.status_code,
            "error_type": "HTTPException",
            "path": str(request.url.path),
            "details": {}
        }
    )


async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器
    捕获所有未被特定处理器处理的异常

    Args:
        request: 请求对象
        exc: 异常对象

    Returns:
        JSONResponse: 统一的错误响应
    """
    # 记录异常堆栈信息（同时打印到控制台和日志文件）
    error_msg = f"""
{'=' * 80}
        全局异常捕获:
          异常类型: {type(exc).__name__}
          异常信息: {str(exc)}
          请求URL: {request.url}
          请求方法: {request.method}
        异常堆栈信息:
        {traceback.format_exc()}
        {'=' * 80}
"""
    logger.error(error_msg)

    # 根据异常类型返回不同的错误响应
    error_response = {
        "success": False,
        "data": None,
        "message": "服务器内部错误",
        "code": 500,
        "error_type": "InternalServerError",
        "path": str(request.url.path),
        "details": {}
    }

    # 处理自定义异常
    if isinstance(exc, BusinessException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "BusinessError",
            "details": exc.details
        })
        status_code = exc.code
    elif isinstance(exc, DatabaseException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "DatabaseError",
            "details": exc.details
        })
        status_code = exc.code
    elif isinstance(exc, ValidationException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "ValidationError",
            "details": exc.details
        })
        status_code = exc.code
    elif isinstance(exc, AuthenticationException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "AuthenticationError",
            "details": exc.details
        })
        status_code = exc.code
    elif isinstance(exc, PermissionException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "PermissionError",
            "details": exc.details
        })
        status_code = exc.code
    elif isinstance(exc, ResourceNotFoundException):
        error_response.update({
            "code": exc.code,
            "message": exc.message,
            "error_type": "ResourceNotFoundError",
            "details": exc.details
        })
        status_code = exc.code
    else:
        # 处理其他所有未预期的异常
        # 在生产环境中，不建议将详细错误信息返回给客户端
        if DEBUG:
            error_response["details"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc().split('\n')
            }
        else:
            error_response["details"] = {"message": "服务器内部错误，请联系管理员"}
        status_code = 500

    return JSONResponse(status_code=status_code, content=error_response)


async def not_found_exception_handler(request: Request, exc: Exception):
    """处理404未找到异常"""
    warning_msg = f"404错误 - 请求路径不存在: {request.url}"
    logger.warning(warning_msg)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "data": None,
            "message": "请求的资源不存在",
            "code": 404,
            "error_type": "NotFoundError",
            "path": str(request.url.path),
            "details": {}
        }
    )


async def validation_exception_handler(request: Request, exc: Exception):
    """处理422参数验证异常"""
    warning_msg = f"422错误 - 请求参数验证失败: {request.url}\n详细信息: {str(exc)}"
    logger.warning(warning_msg)
    print(warning_msg, flush=True)
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "message": "请求参数验证失败",
            "code": 422,
            "error_type": "ValidationError",
            "path": str(request.url.path),
            "details": {}
        }
    )


def register_exception_handlers(app):
    """
    注册fastapi全局异常处理器
    """
    # 注册HTTPException处理器（必须在全局异常处理器之前）
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)

    # 注册全局异常处理器
    app.add_exception_handler(Exception, global_exception_handler)

    # 注册特定HTTP状态码异常处理器
    app.add_exception_handler(404, not_found_exception_handler)
    app.add_exception_handler(422, validation_exception_handler)

    # 注册自定义异常处理器
    app.add_exception_handler(BusinessException, global_exception_handler)
    app.add_exception_handler(DatabaseException, global_exception_handler)
    app.add_exception_handler(ValidationException, global_exception_handler)
    app.add_exception_handler(AuthenticationException, global_exception_handler)
    app.add_exception_handler(PermissionException, global_exception_handler)
    app.add_exception_handler(ResourceNotFoundException, global_exception_handler)

    logger.info("全局异常处理器注册完成")
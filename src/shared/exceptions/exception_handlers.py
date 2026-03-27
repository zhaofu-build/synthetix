"""
全局异常处理器
处理系统中所有未捕获的异常，提供统一的错误响应格式
"""

import logging
import traceback
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException, RequestValidationError
from pydantic import ValidationError

from src.shared.exceptions.exceptions import (
    BaseAppException,
    BusinessException,
    DatabaseException,
    ValidationException,
    AuthenticationException,
    PermissionException,
    ResourceNotFoundException,
    FileOperationException,
    VideoProcessingException,
    AudioProcessingException,
    ExternalServiceException,
    TaskExecutionException,
    ConfigurationException,
    RateLimitException,
    ConflictException,
)

logger = logging.getLogger(__name__)

# 从环境变量获取DEBUG配置，默认为False
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'


def build_error_response(
    exc: Exception,
    request: Request,
    status_code: int = 500,
    include_path: bool = True
) -> dict:
    """构建统一错误响应"""
    response = {
        "success": False,
        "message": "服务器内部错误",
        "code": status_code,
        "timestamp": int(__import__('time').time()),
    }

    if include_path:
        response["path"] = str(request.url.path)

    # 处理 BaseAppException 及其子类
    if isinstance(exc, BaseAppException):
        response.update({
            "error": exc.error_type,
            "message": exc.message,
            "code": exc.code,
            "details": exc.details
        })
    else:
        # 处理其他异常
        response["error"] = type(exc).__name__
        if DEBUG:
            response["details"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }

    return response


async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """处理FastAPI的HTTPException"""
    # 根据状态码选择日志级别
    if exc.status_code >= 500:
        log_level = logger.error
    elif exc.status_code == 404:
        log_level = logger.warning
    else:
        log_level = logger.warning

    logger.warning(
        f"HTTPException: status={exc.status_code}, detail={exc.detail}, "
        f"path={request.url.path}, method={request.method}"
    )

    response = {
        "success": False,
        "message": exc.detail,
        "code": exc.status_code,
        "error": "HTTPException",
        "path": str(request.url.path),
        "timestamp": int(__import__('time').time()),
    }

    return JSONResponse(status_code=exc.status_code, content=response)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理Pydantic请求验证异常"""
    # 获取请求体
    try:
        import json
        body = await request.body()
        body_str = body.decode() if body else "empty"
    except:
        body_str = "unable to read"

    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
            "loc": error["loc"]
        })

    logger.warning(
        f"ValidationError: path={request.url.path}, method={request.method}, "
        f"body={body_str}, errors={errors}"
    )

    response = {
        "success": False,
        "message": "请求参数验证失败",
        "code": 422,
        "error": "ValidationError",
        "path": str(request.url.path),
        "details": {"errors": errors},
        "timestamp": int(__import__('time').time()),
    }

    return JSONResponse(status_code=422, content=response)


async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器
    捕获所有未被特定处理器处理的异常
    """
    # BaseAppException 子类不需要记录完整堆栈（已在业务层处理）
    if isinstance(exc, BaseAppException):
        # 根据状态码选择日志级别
        if exc.code >= 500:
            logger.error(f"{exc.error_type}: {exc.message} - {exc.details}")
        elif exc.code == 404:
            logger.warning(f"{exc.error_type}: {exc.message}")
        else:
            logger.warning(f"{exc.error_type}: {exc.message}")

        return JSONResponse(
            status_code=exc.code,
            content=build_error_response(exc, request, exc.code)
        )

    # 其他异常记录完整堆栈
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}\n"
        f"path={request.url.path}, method={request.method}\n"
        f"{traceback.format_exc()}"
    )

    return JSONResponse(
        status_code=500,
        content=build_error_response(exc, request, 500)
    )


async def not_found_exception_handler(request: Request, exc: Exception):
    """处理404未找到异常"""
    logger.warning(f"404: path={request.url.path} not found")
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "请求的资源不存在",
            "code": 404,
            "error": "NotFoundError",
            "path": str(request.url.path),
            "timestamp": int(__import__('time').time()),
        }
    )


def register_exception_handlers(app):
    """
    注册fastapi全局异常处理器
    """
    # Pydantic 验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # HTTPException
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)

    # 自定义业务异常
    app.add_exception_handler(BaseAppException, global_exception_handler)

    # 全局异常处理器（放在最后，作为兜底）
    app.add_exception_handler(Exception, global_exception_handler)

    # 404 处理器
    app.add_exception_handler(404, not_found_exception_handler)

    logger.info("全局异常处理器注册完成")
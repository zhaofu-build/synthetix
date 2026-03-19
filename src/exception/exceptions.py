"""
自定义异常类定义
用于业务系统中的各种异常情况
"""
from typing import Optional, Dict, Any


class BaseAppException(Exception):
    """应用异常基类"""

    def __init__(
        self,
        message: str,
        code: int = 500,
        error_type: str = "AppError",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.error_type = error_type
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "code": self.code,
            "details": self.details
        }

    def __str__(self) -> str:
        if self.details:
            return f"{self.error_type}: {self.message} - {self.details}"
        return f"{self.error_type}: {self.message}"


class BusinessException(BaseAppException):
    """业务异常类，用于处理业务逻辑错误"""

    def __init__(self, message: str, code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, "BusinessError", details)


class DatabaseException(BaseAppException):
    """数据库异常类"""

    def __init__(self, message: str, code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, "DatabaseError", details)


class ValidationException(BaseAppException):
    """数据验证异常类"""

    def __init__(self, message: str, code: int = 422, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, "ValidationError", details)


class AuthenticationException(BaseAppException):
    """认证异常类"""

    def __init__(self, message: str = "认证失败", code: int = 401, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, "AuthenticationError", details)


class PermissionException(BaseAppException):
    """权限异常类"""

    def __init__(self, message: str = "权限不足", code: int = 403, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, "PermissionError", details)


class ResourceNotFoundException(BaseAppException):
    """资源未找到异常类"""

    def __init__(
        self,
        message: str = "请求的资源不存在",
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id is not None:
            details["resource_id"] = str(resource_id)

        if resource_type and resource_id:
            message = f"{resource_type} (ID: {resource_id}) 不存在"
        elif resource_type:
            message = f"{resource_type} 不存在"

        super().__init__(message, 404, "NotFoundError", details)


# ========== 新增特定业务异常 ==========

class FileOperationException(BaseAppException):
    """文件操作异常"""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        code: int = 500
    ):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation

        super().__init__(message, code, "FileOperationError", details)


class VideoProcessingException(BaseAppException):
    """视频处理异常"""

    def __init__(
        self,
        message: str,
        input_path: Optional[str] = None,
        operation: Optional[str] = None,
        code: int = 500
    ):
        details = {}
        if input_path:
            details["input_path"] = input_path
        if operation:
            details["operation"] = operation

        super().__init__(message, code, "VideoProcessingError", details)


class AudioProcessingException(BaseAppException):
    """音频处理异常"""

    def __init__(
        self,
        message: str,
        input_path: Optional[str] = None,
        operation: Optional[str] = None,
        code: int = 500
    ):
        details = {}
        if input_path:
            details["input_path"] = input_path
        if operation:
            details["operation"] = operation

        super().__init__(message, code, "AudioProcessingError", details)


class ExternalServiceException(BaseAppException):
    """外部服务异常"""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        code: int = 502
    ):
        details = {}
        if service_name:
            details["service"] = service_name
        if status_code:
            details["status_code"] = status_code

        super().__init__(message, code, "ExternalServiceError", details)


class TaskExecutionException(BaseAppException):
    """任务执行异常"""

    def __init__(
        self,
        message: str,
        task_id: Optional[str] = None,
        task_type: Optional[str] = None,
        code: int = 500
    ):
        details = {}
        if task_id:
            details["task_id"] = task_id
        if task_type:
            details["task_type"] = task_type

        super().__init__(message, code, "TaskExecutionError", details)


class ConfigurationException(BaseAppException):
    """配置异常"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        code: int = 500
    ):
        details = {}
        if config_key:
            details["config_key"] = config_key

        super().__init__(message, code, "ConfigurationError", details)


class RateLimitException(BaseAppException):
    """请求限流异常"""

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后再试",
        retry_after: Optional[int] = None,
        code: int = 429
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(message, code, "RateLimitError", details)


class ConflictException(BaseAppException):
    """冲突异常"""

    def __init__(
        self,
        message: str = "资源冲突",
        conflict_type: Optional[str] = None,
        code: int = 409
    ):
        details = {}
        if conflict_type:
            details["conflict_type"] = conflict_type

        super().__init__(message, code, "ConflictError", details)
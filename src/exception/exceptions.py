"""
自定义异常类定义
用于业务系统中的各种异常情况
"""

class BusinessException(Exception):
    """业务异常类，用于处理业务逻辑错误"""
    def __init__(self, message: str, code: int = 400, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class DatabaseException(Exception):
    """数据库异常类"""
    def __init__(self, message: str, code: int = 500, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class ValidationException(Exception):
    """数据验证异常类"""
    def __init__(self, message: str, code: int = 422, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationException(Exception):
    """认证异常类"""
    def __init__(self, message: str = "认证失败", code: int = 401, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class PermissionException(Exception):
    """权限异常类"""
    def __init__(self, message: str = "权限不足", code: int = 403, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class ResourceNotFoundException(Exception):
    """资源未找到异常类"""
    def __init__(self, message: str = "请求的资源不存在", code: int = 404, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
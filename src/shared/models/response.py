"""统一API响应模型"""
from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """统一API响应格式

    Args:
        success: 请求是否成功
        data: 响应数据
        message: 响应消息
        code: 状态码
        timestamp: 响应时间戳
    """
    success: bool = Field(default=True, description="请求是否成功")
    data: Optional[T] = Field(default=None, description="响应数据")
    message: str = Field(default="", description="响应消息")
    code: int = Field(default=200, description="状态码")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()), description="响应时间戳")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "example"},
                "message": "操作成功",
                "code": 200,
                "timestamp": 1710123456
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式

    Args:
        items: 数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        total_pages: 总页数
    """
    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码", ge=1)
    page_size: int = Field(default=10, description="每页大小", ge=1, le=100)
    total_pages: int = Field(default=0, description="总页数", ge=0)

    @classmethod
    def create(cls, items: List[T], total: int, page: int = 1, page_size: int = 10):
        """创建分页响应

        Args:
            items: 数据列表
            total: 总记录数
            page: 当前页码
            page_size: 每页大小
        """
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


class ErrorResponse(BaseModel):
    """错误响应格式"""
    success: bool = Field(default=False, description="请求是否成功")
    error: str = Field(description="错误类型")
    message: str = Field(description="错误消息")
    code: int = Field(default=500, description="错误码")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()), description="响应时间戳")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "参数验证失败",
                "code": 400,
                "timestamp": 1710123456
            }
        }


# 常用响应构造函数
def success_response(data: Any = None, message: str = "操作成功", code: int = 200, to_camel: bool = True) -> APIResponse:
    """
    构造成功响应

    Args:
        data: 响应数据
        message: 响应消息
        code: 状态码
        to_camel: 是否将 key 转换为 camelCase（默认 True，方便前端使用）
    """
    from src.shared.utils.response_util import convert_keys_to_camel

    if to_camel and data is not None:
        data = convert_keys_to_camel(data)
    return APIResponse(success=True, data=data, message=message, code=code)


def error_response(error: str, message: str, code: int = 500) -> ErrorResponse:
    """构造错误响应"""
    return ErrorResponse(success=False, error=error, message=message, code=code)


def paginated_response(items: List[Any], total: int, page: int = 1, page_size: int = 10) -> PaginatedResponse:
    """构造分页响应"""
    return PaginatedResponse.create(items, total, page, page_size)

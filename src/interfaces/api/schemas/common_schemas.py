"""通用 API Schema"""
from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, List
from src.shared.constants import Pagination

T = TypeVar('T')


class PaginationRequest(BaseModel):
    """分页请求基类"""
    current: int = Field(default=Pagination.DEFAULT_PAGE, ge=1, description="当前页码")
    size: int = Field(
        default=Pagination.DEFAULT_PAGE_SIZE,
        ge=Pagination.MIN_PAGE_SIZE,
        le=Pagination.MAX_PAGE_SIZE,
        description="每页大小"
    )

    class Config:
        extra = 'forbid'

    @property
    def skip(self) -> int:
        """计算跳过的记录数"""
        return (self.current - 1) * self.size


class DeleteRequest(BaseModel):
    """删除请求"""
    id: int = Field(..., ge=1, description="要删除的记录ID")

    class Config:
        extra = 'forbid'


class PaginatedData(BaseModel, Generic[T]):
    """分页数据响应"""
    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页大小")
    total_pages: int = Field(default=0, description="总页数")

    @classmethod
    def create(cls, items: List[T], total: int, page: int = 1, page_size: int = 10):
        """创建分页数据"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

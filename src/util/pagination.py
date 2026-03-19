"""分页工具模块"""
from typing import Generic, TypeVar, List, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel

T = TypeVar('T')


class PaginatedQuery(BaseModel):
    """分页查询参数"""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResult(BaseModel, Generic[T]):
    """分页查询结果"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        arbitrary_types_allowed = True


def paginate_query(
    db: Session,
    query,
    page_params: PaginatedQuery
) -> PaginatedResult:
    """对查询结果进行分页

    Args:
        db: 数据库会话
        query: SQLAlchemy 查询对象
        page_params: 分页参数

    Returns:
        分页结果
    """
    total = query.count()
    items = query.offset(page_params.offset).limit(page_params.limit).all()

    total_pages = (total + page_params.page_size - 1) // page_params.page_size if page_params.page_size > 0 else 0

    return PaginatedResult(
        items=items,
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
        total_pages=total_pages
    )

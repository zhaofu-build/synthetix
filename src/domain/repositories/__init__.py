"""领域仓储接口模块

定义仓储接口规范
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any

T = TypeVar('T')


class IRepository(ABC, Generic[T]):
    """仓储接口基类
    
    定义所有仓储必须实现的基本操作
    """
    
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """根据ID获取实体"""
        pass
    
    @abstractmethod
    def get_all(self, skip: int = 0, limit: int = 100, filters: Dict = None) -> List[T]:
        """获取所有实体（支持分页和过滤）"""
        pass
    
    @abstractmethod
    def create(self, **kwargs) -> T:
        """创建实体"""
        pass
    
    @abstractmethod
    def update(self, id: int, **kwargs) -> Optional[T]:
        """更新实体"""
        pass
    
    @abstractmethod
    def delete(self, id: int) -> bool:
        """删除实体"""
        pass
    
    @abstractmethod
    def count(self, filters: Dict = None) -> int:
        """统计实体数量"""
        pass


__all__ = ['IRepository']

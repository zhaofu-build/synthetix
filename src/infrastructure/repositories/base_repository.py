"""
基础 Repository 类

提供通用的数据访问方法，所有具体的 Repository 都应该继承这个类
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update as sql_update, delete as sql_delete
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

# 泛型类型变量，表示模型类型
T = TypeVar('T')


class BaseRepository(Generic[T], ABC):
    """
    基础 Repository 类，提供通用的 CRUD 操作

    使用泛型支持不同的实体类型
    """

    def __init__(self, session: Session, model: Type[T]):
        """
        初始化 Repository

        Args:
            session: SQLAlchemy 数据库会话
            model: SQLAlchemy 实体模型类
        """
        self._session = session
        self._model = model

    @property
    def session(self) -> Session:
        """获取数据库会话"""
        return self._session

    @property
    def model(self) -> Type[T]:
        """获取实体模型类"""
        return self._model

    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        根据 ID 查询单个实体

        Args:
            entity_id: 实体 ID

        Returns:
            实体对象，不存在则返回 None
        """
        return self._session.query(self._model).filter(self._model.id == entity_id).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """
        获取所有实体列表（支持分页和过滤）

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            filters: 过滤条件字典，例如 {'del_flag': 0}

        Returns:
            实体列表
        """
        query = self._session.query(self._model)

        # 应用过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self._model, key):
                    query = query.filter(getattr(self._model, key) == value)

        return query.offset(skip).limit(limit).all()

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        统计符合条件的记录数

        Args:
            filters: 过滤条件字典

        Returns:
            记录总数
        """
        query = self._session.query(func.count(self._model.id))

        if filters:
            for key, value in filters.items():
                if hasattr(self._model, key):
                    query = query.filter(getattr(self._model, key) == value)

        return query.scalar() or 0

    def create(self, **kwargs) -> T:
        """
        创建新实体

        Args:
            **kwargs: 实体属性键值对

        Returns:
            创建的实体对象
        """
        entity = self._model(**kwargs)
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def update(self, entity_id: int, **kwargs) -> Optional[T]:
        """
        更新实体

        Args:
            entity_id: 实体 ID
            **kwargs: 要更新的属性键值对

        Returns:
            更新后的实体对象，不存在则返回 None
        """
        entity = self.get_by_id(entity_id)
        if not entity:
            return None

        for key, value in kwargs.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)

        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity_id: int) -> bool:
        """
        根据 ID 删除实体

        Args:
            entity_id: 实体 ID

        Returns:
            删除成功返回 True，实体不存在返回 False
        """
        entity = self.get_by_id(entity_id)
        if not entity:
            return False

        self._session.delete(entity)
        self._session.flush()
        return True

    def soft_delete(self, entity_id: int) -> bool:
        """
        软删除（逻辑删除）实体

        如果实体有 del_flag 字段，则将其设置为 1，否则执行物理删除

        Args:
            entity_id: 实体 ID

        Returns:
            删除成功返回 True，实体不存在返回 False
        """
        entity = self.get_by_id(entity_id)
        if not entity:
            return False

        if hasattr(entity, 'del_flag'):
            entity.del_flag = 1
        else:
            self._session.delete(entity)

        self._session.flush()
        return True

    def exists(self, entity_id: int) -> bool:
        """
        检查实体是否存在

        Args:
            entity_id: 实体 ID

        Returns:
            存在返回 True，否则返回 False
        """
        return self._session.query(
            self._session.query(self._model).filter(self._model.id == entity_id).exists()
        ).scalar()

    def get_random(self, filters: Optional[Dict[str, Any]] = None) -> Optional[T]:
        """
        随机获取一条记录

        Args:
            filters: 过滤条件字典

        Returns:
            随机实体，不存在则返回 None
        """
        query = self._session.query(self._model)

        if filters:
            for key, value in filters.items():
                if hasattr(self._model, key):
                    query = query.filter(getattr(self._model, key) == value)

        return query.order_by(func.random()).limit(1).first()

    def bulk_create(self, items: List[Dict[str, Any]]) -> List[T]:
        """
        批量创建实体

        Args:
            items: 实体属性字典列表

        Returns:
            创建的实体列表
        """
        entities = [self._model(**item) for item in items]
        self._session.add_all(entities)
        self._session.flush()
        return entities

    def bulk_update(self, ids: List[int], **kwargs) -> int:
        """
        批量更新实体

        Args:
            ids: 实体 ID 列表
            **kwargs: 要更新的属性键值对

        Returns:
            更新的记录数
        """
        if not ids:
            return 0

        # 只更新非 None 的值
        update_data = {k: v for k, v in kwargs.items() if v is not None}

        result = self._session.query(self._model).filter(
            self._model.id.in_(ids)
        ).update(update_data, synchronize_session=False)

        self._session.flush()
        return result

    def get_by_ids(self, ids: List[int]) -> List[T]:
        """
        根据 ID 列表批量查询实体

        Args:
            ids: 实体 ID 列表

        Returns:
            实体列表
        """
        if not ids:
            return []

        return self._session.query(self._model).filter(
            self._model.id.in_(ids)
        ).all()

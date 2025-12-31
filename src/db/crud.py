"""SQLAlchemy CRUD 操作封装"""
from typing import List, Dict, Any, Optional, Type, TypeVar
from sqlalchemy.orm import Session
from fastapi import HTTPException
"""SQLAlchemy 基类定义"""
from sqlalchemy.ext.declarative import declarative_base

# SQLAlchemy 基类
Base = declarative_base()
T = TypeVar('T', bound=Base)


class CRUDBase:
    """基础CRUD操作类"""
    
    def __init__(self, model: Type[T]):
        """
        初始化CRUD操作
        
        Args:
            model: SQLAlchemy模型类
        """
        self.model = model
    
    def get_by_id(self, db: Session, id: int) -> Optional[T]:
        """根据ID查询单条记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            
        Returns:
            模型实例或None
        """
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]:
        """查询所有记录
        
        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 限制返回记录数
            
        Returns:
            模型实例列表
        """
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, db: Session, obj_data: dict) -> T:
        """创建新记录
        
        Args:
            db: 数据库会话
            obj_data: 数据字典
            
        Returns:
            创建的模型实例
        """
        # 过滤掉None值和id字段
        filtered_data = {k: v for k, v in obj_data.items() 
                        if v is not None and k not in ['id', 'table_name']}
        
        if not filtered_data:
            raise HTTPException(status_code=400, detail="No fields to insert")
        
        db_obj = self.model(**filtered_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(self, db: Session, id: int, obj_data: dict) -> Optional[T]:
        """更新记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            obj_data: 更新数据字典
            
        Returns:
            更新后的模型实例或None
        """
        db_obj = self.get_by_id(db, id)
        if not db_obj:
            return None
        
        # 过滤掉None值和id字段
        update_data = {k: v for k, v in obj_data.items() 
                      if v is not None and k not in ['id', 'table_name']}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, id: int) -> bool:
        """删除记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            
        Returns:
            是否删除成功
        """
        db_obj = self.get_by_id(db, id)
        if not db_obj:
            return False
        
        db.delete(db_obj)
        db.commit()
        return True
    
    def add_or_update(self, db: Session, obj_data: dict) -> int:
        """添加或更新记录
        
        Args:
            db: 数据库会话
            obj_data: 数据字典
            
        Returns:
            记录ID
        """
        obj_id = obj_data.get('id')
        
        if obj_id:
            # 更新操作
            db_obj = self.update(db, obj_id, obj_data)
            return db_obj.id if db_obj else obj_id
        else:
            # 创建操作
            db_obj = self.create(db, obj_data)
            return db_obj.id
    
    def filter_by(self, db: Session, **filters) -> List[T]:
        """根据条件查询记录
        
        Args:
            db: 数据库会话
            **filters: 过滤条件
            
        Returns:
            模型实例列表
        """
        query = db.query(self.model)
        
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                query = query.filter(getattr(self.model, field) == value)
        
        return query.all()
    
    def to_dict(self, obj: T) -> Dict[str, Any]:
        """将SQLAlchemy模型转换为字典
        
        Args:
            obj: 模型实例
            
        Returns:
            字典
        """
        if obj is None:
            return None
        
        result = {}
        for column in obj.__table__.columns:
            value = getattr(obj, column.name)
            # 处理datetime类型
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            result[column.name] = value
        
        return result
    
    def to_dict_list(self, objs: List[T]) -> List[Dict[str, Any]]:
        """将SQLAlchemy模型列表转换为字典列表
        
        Args:
            objs: 模型实例列表
            
        Returns:
            字典列表
        """
        return [self.to_dict(obj) for obj in objs]

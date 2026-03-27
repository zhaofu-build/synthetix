"""
SQLAlchemy 数据库会话管理
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from src import config
# 数据库文件路径
DATABASE_URL = f"sqlite:///{config.database_path}"

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 需要
    echo=False  # 设置为 True 可以看到 SQL 日志
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    用于 FastAPI 的依赖注入
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # 提交事务
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context(commit: bool = False):
    """
    获取数据库会话的上下文管理器
    用于非 FastAPI 场景

    Args:
        commit: 是否在退出时自动提交事务
    """
    db = SessionLocal()
    try:
        yield db
        if commit:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

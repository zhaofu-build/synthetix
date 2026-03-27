"""领域实体基类

定义所有领域实体的公共基类
"""
from sqlalchemy.ext.declarative import declarative_base

# SQLAlchemy Base - 所有实体的基类
Base = declarative_base()

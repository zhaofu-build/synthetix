from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
from datetime import datetime
from pydantic import BaseModel, Field

# SQLAlchemy Base
Base = declarative_base()

# Pydantic 基础请求模型（用于API请求）
class BaseReq(BaseModel):
    table_name: str = "contents"
    current: int = Field(default=1, ge=1)  # 默认值为1，且必须大于等于1
    size: int = Field(default=10, ge=-1)  # 默认值为10，允许-1表示不分页

    class Config:
        extra = 'allow'  # 允许额外的字段
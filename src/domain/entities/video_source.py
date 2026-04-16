"""视频素材实体

领域层实体，代表视频素材的业务概念
"""
from sqlalchemy import Column, Integer, Text, TIMESTAMP, SmallInteger, func, Index

from src.domain.entities.base import Base
from src.domain.entities.mixins import ToDictMixin


class VideoSource(Base, ToDictMixin):
    """视频素材表"""
    __tablename__ = 'video_source'

    # 主键，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    
    # 视频名称
    video_name = Column(Text, nullable=True, comment='视频名称', index=True)
    
    # web路径
    web_path = Column(Text, nullable=True, comment='Web访问路径')
    
    # 本地路径
    local_path = Column(Text, nullable=True, comment='本地存储路径')
    
    # 时长（秒数）
    duration = Column(Text, nullable=True, comment='视频时长（秒）')
    
    # 时长（时分秒格式）
    duration_hms = Column(Text, nullable=True, comment='视频时长（HH:MM:SS）')
    
    # 描述
    description = Column(Text, nullable=True, comment='视频描述')
    
    # 视频类型：0-未使用，1-使用中
    video_type = Column(SmallInteger, default=0, comment='视频类型 0:未使用 1:使用中', index=True)
    
    # 创建时间
    create_time = Column(TIMESTAMP, default=func.current_timestamp(), comment='创建时间')
    
    # 逻辑删除标志：0-未删除，1-已删除
    del_flag = Column(SmallInteger, default=0, comment='逻辑删除 0:未删除 1:已删除', index=True)

    # NOTE: 时间字段使用 TIMESTAMP + func.current_timestamp()，与 VideoProject/ClipPlanItem 的
    # DateTime + datetime.utcnow 不一致。统一为同一种方案需要数据迁移，暂不修改。

    def __repr__(self):
        return f"<VideoSource(id={self.id}, video_name='{self.video_name}', video_type={self.video_type})>"

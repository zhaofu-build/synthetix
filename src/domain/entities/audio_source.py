"""音频素材实体

领域层实体，代表音频素材的业务概念
"""
from sqlalchemy import Column, Integer, Text, TIMESTAMP, SmallInteger, Float, func, Index

from src.domain.entities.base import Base
from src.domain.entities.mixins import ToDictMixin


class AudioSource(Base, ToDictMixin):
    """音频素材表"""
    __tablename__ = 'audio_source'

    # 主键，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    
    # 音频名称
    audio_name = Column(Text, nullable=True, comment='音频名称')
    
    # 参考文本
    prompt_text = Column(Text, nullable=True, comment='参考文本')
    
    # web路径
    web_path = Column(Text, nullable=True, comment='Web访问路径')
    
    # 创建时间
    create_time = Column(TIMESTAMP, default=func.current_timestamp(), comment='创建时间')
    
    # 逻辑删除标志：0-未删除，1-已删除
    del_flag = Column(SmallInteger, default=0, comment='逻辑删除 0:未删除 1:已删除', index=True)

    # NOTE: 时间字段使用 TIMESTAMP + func.current_timestamp()，与 VideoProject/ClipPlanItem 的
    # DateTime + datetime.utcnow 不一致。统一为同一种方案需要数据迁移，暂不修改。
    
    # 随机种子参数[1-100000]
    seed = Column(Integer, nullable=True, comment='随机种子参数[1-100000]')
    
    # 速度因子
    speed = Column(Float, nullable=True, comment='速度因子')
    
    # top_p采样参数
    top_p = Column(Float, nullable=True, comment='top_p采样参数')
    
    # 温度参数
    temperature = Column(Float, nullable=True, comment='温度参数')
    
    # 重复惩罚因子
    repetition_penalty = Column(Float, nullable=True, comment='重复惩罚因子')

    # 是否为默认音色
    is_default = Column(SmallInteger, default=0, comment='是否为默认音色 0:否 1:是')

    def __repr__(self):
        return f"<AudioSource(id={self.id}, audio_name='{self.audio_name}', seed={self.seed})>"

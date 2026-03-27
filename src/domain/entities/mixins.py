"""领域实体 Mixin

提供实体通用功能
"""
from typing import Dict, Any, List


class ToDictMixin:
    """将实体转换为字典的 Mixin"""

    def to_dict(self) -> Dict[str, Any]:
        """
        将实体转换为字典

        Returns:
            包含所有列值的字典
        """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @classmethod
    def bulk_to_dict(cls, items: List['ToDictMixin']) -> List[Dict[str, Any]]:
        """
        批量将实体转换为字典

        Args:
            items: 实体列表

        Returns:
            字典列表
        """
        return [item.to_dict() for item in items]

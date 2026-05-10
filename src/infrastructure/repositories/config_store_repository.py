"""
配置存储 Repository

提供配置键值对的 CRUD 操作。
"""
from typing import Optional, Any, Dict, List

from sqlalchemy.orm import Session

from src.infrastructure.repositories.base_repository import BaseRepository
from src.domain.entities.config_store import ConfigStore


class ConfigStoreRepository(BaseRepository[ConfigStore]):
    """配置存储仓库"""

    def __init__(self, session: Session):
        super().__init__(session, ConfigStore)

    def get_by_key(self, key: str) -> Optional[ConfigStore]:
        return self._session.query(ConfigStore).filter(ConfigStore.key == key).first()

    def get_value(self, key: str, default: Any = None) -> Any:
        record = self.get_by_key(key)
        return record.value if record else default

    def upsert(self, key: str, value: Any) -> ConfigStore:
        existing = self.get_by_key(key)
        if existing:
            existing.value = value
            self._session.flush()
            return existing
        return self.create(key=key, value=value)

    def delete_by_key(self, key: str) -> bool:
        record = self.get_by_key(key)
        if not record:
            return False
        self.delete(record.id)
        return True

    def get_all_as_dict(self) -> Dict[str, Any]:
        rows = self._session.query(ConfigStore).all()
        return {row.key: row.value for row in rows if row.value is not None}

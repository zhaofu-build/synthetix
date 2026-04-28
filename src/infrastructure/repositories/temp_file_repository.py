"""项目临时文件 Repository"""
import os
import shutil
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from src.domain.entities.project_temp_file import ProjectTempFile

logger = logging.getLogger(__name__)


class TempFileRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, project_id: int, file_name: str, file_path: str,
               web_path: str, file_type: str = 'video', source: str = 'upload',
               file_size: int = 0, session_id: str = None) -> ProjectTempFile:
        record = ProjectTempFile(
            project_id=project_id,
            session_id=session_id,
            file_name=file_name,
            file_path=file_path,
            web_path=web_path,
            file_type=file_type,
            file_size=file_size,
            source=source,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_by_project(self, project_id: int) -> List[ProjectTempFile]:
        return self.session.query(ProjectTempFile).filter(
            ProjectTempFile.project_id == project_id
        ).order_by(ProjectTempFile.created_at.desc()).all()

    def get_by_session(self, session_id: str) -> List[ProjectTempFile]:
        return self.session.query(ProjectTempFile).filter(
            ProjectTempFile.session_id == session_id
        ).all()

    def get_by_id(self, temp_file_id: int) -> Optional[ProjectTempFile]:
        return self.session.query(ProjectTempFile).filter(
            ProjectTempFile.id == temp_file_id
        ).first()

    def delete_by_project(self, project_id: int) -> int:
        records = self.session.query(ProjectTempFile).filter(
            ProjectTempFile.project_id == project_id
        ).all()
        count = 0
        for r in records:
            self._remove_physical_file(r.file_path)
            self.session.delete(r)
            count += 1
        self.session.flush()
        # 删除项目临时目录
        from src import config
        temp_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "temp", str(project_id))
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"清理项目 {project_id} 的临时文件: {count} 个")
        return count

    def delete_by_session(self, session_id: str) -> int:
        records = self.session.query(ProjectTempFile).filter(
            ProjectTempFile.session_id == session_id
        ).all()
        count = 0
        for r in records:
            self._remove_physical_file(r.file_path)
            self.session.delete(r)
            count += 1
        self.session.flush()
        logger.info(f"清理会话 {session_id} 的临时文件: {count} 个")
        return count

    def delete_by_id(self, temp_file_id: int) -> bool:
        record = self.get_by_id(temp_file_id)
        if not record:
            return False
        self._remove_physical_file(record.file_path)
        self.session.delete(record)
        self.session.flush()
        return True

    def _remove_physical_file(self, file_path: str):
        try:
            if file_path and os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"删除临时文件失败: {file_path}, {e}")

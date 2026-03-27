"""
重构导入路径脚本

自动更新所有文件中的导入路径，从旧结构映射到新的 DDD 结构
"""
import os
import re
from pathlib import Path

# 导入路径映射
IMPORT_MAPPINGS = {
    # 实体
    r'from src\.model\.entity\.video_source import': 'from src.domain.entities.video_source import',
    r'from src\.model\.entity\.audio_source import': 'from src.domain.entities.audio_source import',
    r'from src\.model\.entity import': 'from src.domain.entities import',

    # 仓储
    r'from src\.repository\.video_repository import': 'from src.infrastructure.repositories.video_repository import',
    r'from src\.repository\.audio_repository import': 'from src.infrastructure.repositories.audio_repository import',
    r'from src\.repository\.base_repository import': 'from src.infrastructure.repositories.base_repository import',
    r'from src\.repository import': 'from src.infrastructure.repositories import',

    # 服务
    r'from src\.service\.video_service import': 'from src.application.services.video_service import',
    r'from src\.service\.audio_service import': 'from src.application.services.audio_service import',
    r'from src\.service\.creative_service import': 'from src.application.services.creative_service import',
    r'from src\.service\.fish_voice import': 'from src.infrastructure.external.fish_voice import',
    r'from src\.service\.use_ffmpeg import': 'from src.infrastructure.external.ffmpeg_service import',
    r'from src\.service\.use_fast_whisper import': 'from src.infrastructure.external.whisper_service import',
    r'from src\.service\.use_langchain_llm import': 'from src.infrastructure.external.langchain_service import',
    r'from src\.service\.use_translation import': 'from src.infrastructure.external.translation_service import',
    r'from src\.service\.video_downloader import': 'from src.infrastructure.external.video_downloader import',
    r'from src\.service\.use_qwen_vl import': 'from src.infrastructure.external.qwen_vl_service import',
    r'from src\.service\.dh_live import': 'from src.infrastructure.external.dh_live import',
    r'from src\.service import': 'from src.application.services import',

    # API
    r'from src\.api\.video_api import': 'from src.interfaces.api.video_api import',
    r'from src\.api\.svc_api import': 'from src.interfaces.api.audio_api import',
    r'from src\.api\.tool_api import': 'from src.interfaces.api.tool_api import',
    r'from src\.api\.llm_clip_api import': 'from src.interfaces.api.ai_api import',
    r'from src\.api import': 'from src.interfaces.api import',

    # 模型
    r'from src\.model\.base import': 'from src.shared.models.base import',
    r'from src\.model\.request import': 'from src.shared.models.request import',
    r'from src\.model\.response import': 'from src.shared.models.response import',
    r'from src\.model\.result import': 'from src.shared.models.result import',
    r'from src\.model import': 'from src.shared.models import',

    # 工具类
    r'from src\.util\.file_util import': 'from src.shared.utils.file_util import',
    r'from src\.util\.time_util import': 'from src.shared.utils.time_util import',
    r'from src\.util\.string_util import': 'from src.shared.utils.string_util import',
    r'from src\.util\.pagination import': 'from src.shared.utils.pagination import',
    r'from src\.util\.task_manager import': 'from src.shared.utils.task_manager import',
    r'from src\.util\.prompt_config import': 'from src.shared.utils.prompt_config import',
    r'from src\.util\.config_util import': 'from src.shared.utils.config_util import',
    r'from src\.util\.requests_util import': 'from src.shared.utils.requests_util import',
    r'from src\.util\.system_util import': 'from src.shared.utils.system_util import',
    r'from src\.util\.ffmpeg_util import': 'from src.shared.utils.ffmpeg_util import',
    r'from src\.util\.modelscope_util import': 'from src.shared.utils.modelscope_util import',
    r'from src\.util\.langchain_llm_util import': 'from src.shared.utils.langchain_llm_util import',
    r'from src\.util import': 'from src.shared.utils import',

    # 异常
    r'from src\.exception\.exceptions import': 'from src.shared.exceptions.exceptions import',
    r'from src\.exception\.exception_handlers import': 'from src.shared.exceptions.exception_handlers import',
    r'from src\.exception import': 'from src.shared.exceptions import',

    # 常量
    r'from src\.constants import': 'from src.shared.constants import',

    # 数据库
    r'from src\.db\.session import': 'from src.infrastructure.db.session import',
    r'from src\.db\.alembic_manager import': 'from src.infrastructure.db.alembic_manager import',
    r'from src\.db import': 'from src.infrastructure.db import',
}

def update_file_imports(file_path: Path) -> bool:
    """更新单个文件的导入路径"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        for old_pattern, new_import in IMPORT_MAPPINGS.items():
            content = re.sub(old_pattern, new_import, content)

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """主函数"""
    src_path = Path('src')

    # 收集所有 Python 文件
    python_files = list(src_path.rglob('*.py'))

    updated_count = 0
    for file_path in python_files:
        if update_file_imports(file_path):
            updated_count += 1
            print(f"Updated: {file_path}")

    print(f"\nTotal files updated: {updated_count}")

if __name__ == '__main__':
    main()

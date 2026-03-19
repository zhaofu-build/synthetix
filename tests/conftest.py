"""Pytest 配置和 fixtures"""
import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_video_path():
    """示例视频文件路径"""
    return "static/source_videos/sample.mp4"


@pytest.fixture
def sample_audio_path():
    """示例音频文件路径"""
    return "static/source_timbre/sample.wav"


@pytest.fixture
def test_upload_dir(tmp_path):
    """测试上传目录"""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    return upload_dir


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    from unittest.mock import MagicMock
    session = MagicMock()
    return session

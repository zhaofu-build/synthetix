"""Repository 层单元测试"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.repository.video_repository import VideoRepository
from src.repository.audio_repository import AudioRepository
from src.model.entity.video_source import VideoSource
from src.model.entity.audio_source import AudioSource


class TestVideoRepository:
    """视频 Repository 测试"""

    def test_init(self):
        """测试初始化"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model == VideoSource

    def test_to_dict(self):
        """测试转换为字典"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        video = Mock(
            id=1,
            video_name="test.mp4",
            web_path="/static/test.mp4",
            local_path="D:/static/test.mp4",
            duration="120",
            duration_hms="00:02:00",
            description="测试视频",
            video_type=1,
            create_time="2024-01-01",
            del_flag=0
        )

        result = repo.to_dict(video)

        assert result["id"] == 1
        assert result["video_name"] == "test.mp4"
        assert result["duration"] == "120"
        assert result["video_type"] == 1
        assert result["del_flag"] == 0

    def test_bulk_to_dict(self):
        """测试批量转换"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        videos = [
            Mock(id=1, video_name="test1.mp4", web_path="", local_path="",
                 duration="", duration_hms="", description="", video_type=1,
                 create_time="", del_flag=0),
            Mock(id=2, video_name="test2.mp4", web_path="", local_path="",
                 duration="", duration_hms="", description="", video_type=1,
                 create_time="", del_flag=0),
        ]

        result = repo.bulk_to_dict(videos)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        assert result[0]["video_name"] == "test1.mp4"
        assert result[1]["video_name"] == "test2.mp4"

    def test_get_by_id_dict(self):
        """测试根据 ID 获取字典"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        video = Mock(
            id=1,
            video_name="test.mp4",
            web_path="/static/test.mp4",
            local_path="D:/static/test.mp4",
            duration="120",
            duration_hms="00:02:00",
            description="测试视频",
            video_type=1,
            create_time="2024-01-01",
            del_flag=0
        )

        with patch.object(repo, 'get_by_id', return_value=video):
            result = repo.get_by_id_dict(1)

            assert result["id"] == 1
            assert result["video_name"] == "test.mp4"

    def test_get_by_id_dict_not_found(self):
        """测试根据 ID 获取字典（不存在）"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        with patch.object(repo, 'get_by_id', return_value=None):
            result = repo.get_by_id_dict(999)

            assert result is None

    def test_update_description(self):
        """测试更新描述"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        mock_video = Mock(id=1, description="旧描述")

        with patch.object(repo, 'update', return_value=mock_video) as mock_update:
            result = repo.update_description(1, "新描述")

            mock_update.assert_called_once_with(1, description="新描述")

    def test_mark_as_used(self):
        """测试标记为使用中"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        mock_video = Mock(id=1, video_type=0)

        with patch.object(repo, 'update', return_value=mock_video) as mock_update:
            result = repo.mark_as_used(1)

            mock_update.assert_called_once_with(1, video_type=1)

    def test_mark_as_unused(self):
        """测试标记为未使用"""
        mock_session = Mock(spec=Session)
        repo = VideoRepository(mock_session)

        mock_video = Mock(id=1, video_type=1)

        with patch.object(repo, 'update', return_value=mock_video) as mock_update:
            result = repo.mark_as_unused(1)

            mock_update.assert_called_once_with(1, video_type=0)


class TestAudioRepository:
    """音频 Repository 测试"""

    def test_init(self):
        """测试初始化"""
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model == AudioSource

    def test_to_dict(self):
        """测试转换为字典"""
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)

        audio = Mock(
            id=1,
            audio_name="test.wav",
            prompt_text="测试文本",
            web_path="test.wav",
            seed=42,
            speed=1.0,
            top_p=0.5,
            temperature=0.7,
            repetition_penalty=1.35,
            create_time="2024-01-01"
        )

        result = repo.to_dict(audio)

        assert result["id"] == 1
        assert result["audio_name"] == "test.wav"
        assert result["seed"] == 42
        assert result["speed"] == 1.0
        assert result["top_p"] == 0.5

    def test_to_dict_with_web_path(self):
        """测试转换为字典（包含完整 web 路径）"""
        import os
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)

        audio = Mock(
            id=1,
            audio_name="test.wav",
            prompt_text="测试文本",
            web_path="test.wav",
            seed=42,
            speed=1.0,
            top_p=0.5,
            temperature=0.7,
            repetition_penalty=1.35,
            create_time="2024-01-01"
        )

        with patch.object(os.path, 'join', return_value="/static/test.wav"):
            result = repo.to_dict(audio, include_web_path=True)

            assert result["id"] == 1
            assert result["web_path"] == "/static/test.wav"

    def test_bulk_to_dict(self):
        """测试批量转换"""
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)

        audios = [
            Mock(id=1, audio_name="test1.wav", prompt_text="", web_path="",
                 seed=42, speed=1.0, top_p=0.5, temperature=0.7,
                 repetition_penalty=1.35, create_time=""),
            Mock(id=2, audio_name="test2.wav", prompt_text="", web_path="",
                 seed=100, speed=1.0, top_p=0.5, temperature=0.7,
                 repetition_penalty=1.35, create_time=""),
        ]

        result = repo.bulk_to_dict(audios)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        assert result[0]["audio_name"] == "test1.wav"
        assert result[1]["audio_name"] == "test2.wav"

    def test_get_by_id_dict(self):
        """测试根据 ID 获取字典"""
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)

        audio = Mock(
            id=1,
            audio_name="test.wav",
            prompt_text="测试文本",
            web_path="test.wav",
            seed=42,
            speed=1.0,
            top_p=0.5,
            temperature=0.7,
            repetition_penalty=1.35,
            create_time="2024-01-01"
        )

        with patch.object(repo, 'get_by_id', return_value=audio):
            result = repo.get_by_id_dict(1)

            assert result["id"] == 1
            assert result["audio_name"] == "test.wav"

    def test_get_by_id_dict_not_found(self):
        """测试根据 ID 获取字典（不存在）"""
        mock_session = Mock(spec=Session)
        repo = AudioRepository(mock_session)

        with patch.object(repo, 'get_by_id', return_value=None):
            result = repo.get_by_id_dict(999)

            assert result is None

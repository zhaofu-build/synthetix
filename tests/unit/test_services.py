"""Service 层单元测试"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
from sqlalchemy.orm import Session

from src.application.services.video_service import VideoService
from src.application.services.audio_service import AudioService


class TestVideoService:
    """视频服务测试"""

    def test_init(self):
        """测试初始化"""
        mock_session = Mock(spec=Session)
        service = VideoService(mock_session)
        assert service.db == mock_session
        assert service.repository is not None

    @patch('src.application.services.video_service.use_ffmpeg.get_video_info')
    @patch('src.application.services.video_service.Path')
    def test_upload_video_file_success(self, mock_path, mock_get_video_info):
        """测试视频上传成功"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_repository.create.return_value = Mock(id=1)
        mock_get_video_info.return_value = {
            "duration": "120",
            "duration_hms": "00:02:00"
        }
        mock_path.return_value = Path("/test/video.mp4")

        with patch('builtins.open', mock_open(read_data=b"fake video data")):
            with patch('os.makedirs'):
                with patch('src.application.services.video_service.os.path.join', return_value="/test/video.mp4"):
                    service = VideoService(mock_session)
                    service._repository = mock_repository

                    mock_file_stream = Mock()
                    mock_file_stream.read.return_value = b"fake video data"

                    result = service.upload_video_file(mock_file_stream, "test.mp4")

        assert result["id"] == 1
        mock_repository.create.assert_called_once()

    @patch('src.application.services.video_service.video_downloader.download_videos_from_url')
    @patch('src.application.services.video_service.time_util.seconds_to_hms')
    @patch('src.application.services.video_service.Path')
    def test_download_video_success(self, mock_path, mock_seconds_to_hms, mock_download):
        """测试视频下载成功"""
        mock_session = Mock(spec=Session)
        mock_download.return_value = ("video.mp4", 120)
        mock_seconds_to_hms.return_value = "00:02:00"
        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_instance.__str__ = Mock(return_value="/path/video.mp4")
        mock_path.return_value = mock_path_instance

        with patch('os.makedirs'):
            service = VideoService(mock_session)

            result = service.download_video("https://example.com/video.mp4")

        assert result["filename"] == "video.mp4"
        assert result["duration"] == "00:02:00"
        mock_download.assert_called_once()

    @patch('src.application.services.video_service.use_ffmpeg.process_video')
    @patch('src.application.services.video_service.use_ffmpeg.get_video_info')
    @patch('src.application.services.video_service.Path')
    def test_process_video_success(self, mock_path_class, mock_get_info, mock_process):
        """测试视频处理成功"""
        mock_session = Mock(spec=Session)
        mock_input_path = Mock(exists=True)
        mock_input_path.stem = "test_video"
        mock_input_path.parent = Path("/test")
        mock_path_class.return_value = mock_input_path

        mock_process.return_value = Path("/test/test_video_processed.mp4")
        mock_get_info.return_value = {"duration_hms": "00:02:00"}

        service = VideoService(mock_session)
        result = service.process_video("/test/test_video.mp4")

        assert result["filename"] == "test_video_processed.mp4"
        assert "duration" in result
        mock_process.assert_called_once()

    def test_process_video_file_not_found(self):
        """测试处理不存在的文件"""
        mock_session = Mock(spec=Session)
        service = VideoService(mock_session)

        with patch('src.application.services.video_service.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            with pytest.raises(FileNotFoundError):
                service.process_video("/nonexistent/video.mp4")

    @patch('src.application.services.video_service.use_ffmpeg.extract_frame')
    @patch('src.application.services.video_service.time.time')
    @patch('src.application.services.video_service.Path')
    def test_extract_frame_success(self, mock_path_class, mock_time, mock_extract):
        """测试提取帧成功"""
        mock_session = Mock(spec=Session)
        mock_time.return_value = 1234567890
        mock_extract.return_value = None

        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_class.return_value = mock_path_instance

        with patch('os.makedirs'):
            service = VideoService(mock_session)
            result = service.extract_frame("/test/video.mp4", "00:00:10")

        assert result["filename"] == "extracted_frame_1234567890.png"
        mock_extract.assert_called_once()

    @patch('src.application.services.video_service.use_ffmpeg.get_audio')
    @patch('src.application.services.video_service.Path')
    def test_extract_audio_success(self, mock_path_class, mock_get_audio):
        """测试提取音频成功"""
        mock_session = Mock(spec=Session)
        mock_get_audio.return_value = None

        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_class.return_value = mock_path_instance

        with patch('os.makedirs'):
            service = VideoService(mock_session)
            result = service.extract_audio("/test/video.mp4")

        assert result["filename"] == "distill_audio.mp3"
        mock_get_audio.assert_called_once()

    @patch('src.application.services.video_service.use_ffmpeg.add_audio_to_video')
    @patch('src.application.services.video_service.time.time')
    @patch('src.application.services.video_service.Path')
    def test_add_audio_to_video_success(self, mock_path_class, mock_time, mock_add_audio):
        """测试添加音频成功"""
        mock_session = Mock(spec=Session)
        mock_time.return_value = 1234567890
        mock_add_audio.return_value = None

        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_class.return_value = mock_path_instance

        with patch('os.makedirs'):
            service = VideoService(mock_session)
            result = service.add_audio_to_video("/test/video.mp4", "/test/audio.mp3")

        assert result["filename"] == "video_with_audio_1234567890.mp4"
        mock_add_audio.assert_called_once()

    @patch('src.application.services.video_service.use_fast_whisper.transcribe')
    def test_transcribe_success(self, mock_transcribe):
        """测试转录成功"""
        mock_session = Mock(spec=Session)
        mock_transcribe.return_value = "Subtitle content"

        service = VideoService(mock_session)
        result = service.transcribe("/test/audio.mp3")

        assert result == "Subtitle content"
        mock_transcribe.assert_called_once()

    @patch('src.application.services.video_service.use_ffmpeg.add_subtitle')
    @patch('src.application.services.video_service.use_ffmpeg.get_video_info')
    @patch('src.application.services.video_service.Path')
    def test_add_subtitle_success(self, mock_path_class, mock_get_info, mock_add_subtitle):
        """测试添加字幕成功"""
        mock_session = Mock(spec=Session)
        mock_add_subtitle.return_value = "video_subtitle.mp4"
        mock_get_info.return_value = {"duration_hms": "00:02:00"}

        mock_path_instance = Mock()
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_class.return_value = mock_path_instance

        with patch('os.makedirs'):
            service = VideoService(mock_session)
            result = service.add_subtitle("/test/video.mp4", "Subtitle content")

        assert result["filename"] == "video_subtitle.mp4"
        mock_add_subtitle.assert_called_once()

    @patch('src.application.services.video_service.file_util.del_file')
    def test_delete_video_success(self, mock_del_file):
        """测试删除视频成功"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_video = Mock(local_path="/test/video.mp4")
        mock_repository.get_by_id.return_value = mock_video
        mock_repository.delete.return_value = True

        service = VideoService(mock_session)
        service._repository = mock_repository

        result = service.delete_video(1)

        assert result is True
        mock_del_file.assert_called_once_with("/test/video.mp4")
        mock_repository.delete.assert_called_once_with(1)

    def test_delete_video_not_found(self):
        """测试删除不存在的视频"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = None

        service = VideoService(mock_session)
        service._repository = mock_repository

        with pytest.raises(FileNotFoundError):
            service.delete_video(999)


class TestAudioService:
    """音频服务测试"""

    def test_init(self):
        """测试初始化"""
        mock_session = Mock(spec=Session)
        service = AudioService(mock_session)
        assert service.db == mock_session
        assert service.repository is not None

    @patch('src.application.services.audio_service.sf.write')
    @patch('src.application.services.audio_service.fish_voice.fish_voice')
    @patch('src.application.services.audio_service.file_util.audio_to_base64')
    @patch('src.application.services.audio_service.os.path.join')
    @patch('src.application.services.audio_service.os.makedirs')
    def test_generate_fish_speech_tts_with_custom_audio(
        self, mock_makedirs, mock_join, mock_audio_base64, mock_fish_voice, mock_write
    ):
        """测试使用自定义音频生成 Fish Speech TTS"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = None  # audio_source_id = -1

        mock_fish_voice.return_value = b"audio data"

        with patch('builtins.open', mock_open()):
            with patch('src.application.services.audio_service.uuid.uuid4') as mock_uuid:
                mock_uuid.hex.return_value = "test_uuid"
                service = AudioService(mock_session)
                service._repository = mock_repository

                result = service.generate_fish_speech_tts(
                    text="测试文本",
                    audio_source_id=-1
                )

        assert "filename" in result
        mock_fish_voice.assert_called_once()

    @patch('src.application.services.audio_service.file_util.del_file')
    def test_delete_audio_success(self, mock_del_file):
        """测试删除音色成功"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_audio = Mock()
        mock_audio.web_path = "test.wav"
        mock_repository.get_by_id.return_value = mock_audio
        mock_repository.delete.return_value = True

        service = AudioService(mock_session)
        service._repository = mock_repository

        with patch('src.application.services.audio_service.os.path.join', return_value="/full/path/test.wav"):
            result = service.delete_audio(1)

        assert result is True
        mock_del_file.assert_called_once()
        mock_repository.delete.assert_called_once_with(1)

    def test_delete_audio_not_found(self):
        """测试删除不存在的音色"""
        mock_session = Mock(spec=Session)
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = None

        service = AudioService(mock_session)
        service._repository = mock_repository

        with pytest.raises(FileNotFoundError):
            service.delete_audio(999)

    @patch('src.application.services.audio_service.dh_live.do_s')
    @patch('src.application.services.audio_service.os.makedirs')
    def test_separate_audio_success(self, mock_makedirs, mock_do_s):
        """测试分离音频成功"""
        mock_session = Mock(spec=Session)
        mock_do_s.return_value = ("vocal.mp3", "accompaniment.mp3")

        service = AudioService(mock_session)
        result = service.separate_audio("/test/audio.mp3")

        assert "vocal_url" in result
        assert "accompaniment_url" in result
        mock_do_s.assert_called_once()

    @patch('src.application.services.audio_service.dh_live.do_m')
    def test_merge_audio_success(self, mock_do_m):
        """测试合并音频成功"""
        mock_session = Mock(spec=Session)
        mock_do_m.return_value = "final.mp3"

        service = AudioService(mock_session)
        result = service.merge_audio("/test/vocal.mp3", "/test/accompaniment.mp3")

        assert "final_url" in result
        mock_do_m.assert_called_once()

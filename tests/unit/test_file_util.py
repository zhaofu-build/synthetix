"""文件工具函数单元测试"""
import pytest
import os
import tempfile
from pathlib import Path
from src.shared.utils.file_util import (
    get_file_name,
    get_file_name_no_suffix,
    get_file_suffix,
    format_windows_path,
    audio_to_base64
)


class TestFilePathFunctions:
    """文件路径函数测试"""

    def test_get_file_name(self):
        """测试获取文件名（带扩展名）"""
        assert get_file_name("/path/to/video.mp4") == "video.mp4"
        assert get_file_name("C:\\Users\\test\\file.txt") == "file.txt"
        assert get_file_name("simple.wav") == "simple.wav"

    def test_get_file_name_no_suffix(self):
        """测试获取文件名（不带扩展名）"""
        assert get_file_name_no_suffix("/path/to/video.mp4") == "video"
        assert get_file_name_no_suffix("archive.tar.gz") == "archive.tar"

    def test_get_file_suffix(self):
        """测试获取文件扩展名"""
        assert get_file_suffix("video.mp4") == ".mp4"
        assert get_file_suffix("document.pdf") == ".pdf"
        assert get_file_suffix("no_extension") == ""

    def test_format_windows_path(self):
        """测试Windows路径格式化"""
        assert "\\" not in format_windows_path("C:\\Users\\test\\file.txt")
        assert format_windows_path("C:/Users/test") == "C:/Users/test"


class TestAudioToBase64:
    """音频转Base64测试"""

    def test_audio_to_base64_valid_file(self, tmp_path):
        """测试有效音频文件转Base64"""
        # 创建临时音频文件
        audio_file = tmp_path / "test.wav"
        audio_content = b"RIFF" + b"\x00" * 100  # 简化的WAV文件头
        audio_file.write_bytes(audio_content)

        result = audio_to_base64(str(audio_file))

        assert isinstance(result, str)
        assert len(result) > 0
        # Base64编码的字符串应该只包含有效字符
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
        assert all(c in valid_chars for c in result)

    def test_audio_to_base64_nonexistent_file(self):
        """测试不存在的文件"""
        with pytest.raises(FileNotFoundError):
            audio_to_base64("nonexistent.wav")


@pytest.mark.parametrize("input_path,expected_name", [
    ("/home/user/videos/movie.mp4", "movie.mp4"),
    ("C:\\Users\\Test\\video.avi", "video.avi"),
    ("simple.mov", "simple.mov"),
])
def test_get_file_name_parametrized(input_path, expected_name):
    """参数化测试：获取文件名"""
    assert get_file_name(input_path) == expected_name

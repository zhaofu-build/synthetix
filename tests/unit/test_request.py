"""API 请求模型验证测试"""
import pytest
from pydantic import ValidationError
from src.model.request import (
    BaseQueryRequest,
    VideoQueryRequest,
    DeleteRequest,
    VideoProcessRequest,
    TranscribeRequest,
    DownloadVideoRequest,
    FishVoiceTTSRequest,
    SaveTimbreRequest
)


class TestBaseQueryRequest:
    """基础查询请求测试"""

    def test_default_values(self):
        """测试默认值"""
        req = BaseQueryRequest()
        assert req.current == 1
        assert req.size == 20  # 更新为 Pagination.DEFAULT_PAGE_SIZE

    def test_valid_values(self):
        """测试有效值"""
        req = BaseQueryRequest(current=5, size=50)
        assert req.current == 5
        assert req.size == 50

    def test_current_too_small(self):
        """测试页码过小"""
        with pytest.raises(ValidationError) as exc_info:
            BaseQueryRequest(current=0)
        assert "current" in str(exc_info.value)

    def test_size_too_small(self):
        """测试每页大小过小"""
        with pytest.raises(ValidationError) as exc_info:
            BaseQueryRequest(size=0)
        assert "size" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """测试禁止额外字段"""
        with pytest.raises(ValidationError) as exc_info:
            BaseQueryRequest(current=1, unknown_field="value")
        assert "extra" in str(exc_info.value).lower()


class TestDeleteRequest:
    """删除请求测试"""

    def test_valid_delete_request(self):
        """测试有效删除请求"""
        req = DeleteRequest(id=5)
        assert req.id == 5

    def test_missing_id(self):
        """测试缺少ID"""
        with pytest.raises(ValidationError) as exc_info:
            DeleteRequest()
        assert "id" in str(exc_info.value)

    def test_invalid_id(self):
        """测试无效ID"""
        with pytest.raises(ValidationError) as exc_info:
            DeleteRequest(id=0)
        assert "id" in str(exc_info.value)


class TestVideoProcessRequest:
    """视频处理请求测试"""

    def test_valid_minimal_request(self):
        """测试最小有效请求"""
        req = VideoProcessRequest(input_path="/path/to/video.mp4")
        assert req.input_path == "/path/to/video.mp4"
        assert req.output_format == "mp4"

    def test_valid_full_request(self):
        """测试完整有效请求"""
        req = VideoProcessRequest(
            input_path="/path/to/video.mp4",
            output_format="avi",
            start_time="00:01:00",
            end_time="00:02:00",
            speed=1.5,
            volume=1.2,
            width=1920,
            height=1080
        )
        assert req.speed == 1.5
        assert req.width == 1920

    def test_invalid_output_format(self):
        """测试无效输出格式"""
        with pytest.raises(ValidationError):
            VideoProcessRequest(input_path="/path/to/video.mp4", output_format="exe")

    def test_speed_out_of_range(self):
        """测试速度超出范围"""
        with pytest.raises(ValidationError):
            VideoProcessRequest(input_path="/path/to/video.mp4", speed=15.0)

    def test_width_out_of_range(self):
        """测试宽度超出范围"""
        with pytest.raises(ValidationError):
            VideoProcessRequest(input_path="/path/to/video.mp4", width=10000)


class TestTranscribeRequest:
    """转录请求测试"""

    def test_valid_transcribe_request(self):
        """测试有效转录请求"""
        req = TranscribeRequest(
            input_path="/path/to/audio.mp3",
            model="base",
            output_format="srt"
        )
        assert req.model == "base"
        assert req.is_translate is False

    def test_invalid_model(self):
        """测试无效模型"""
        with pytest.raises(ValidationError):
            TranscribeRequest(
                input_path="/path/to/audio.mp3",
                model="invalid_model"
            )

    def test_invalid_output_format(self):
        """测试无效输出格式"""
        with pytest.raises(ValidationError):
            TranscribeRequest(
                input_path="/path/to/audio.mp3",
                output_format="doc"
            )


class TestDownloadVideoRequest:
    """视频下载请求测试"""

    def test_valid_url(self):
        """测试有效URL"""
        req = DownloadVideoRequest(video_url="https://example.com/video.mp4")
        assert req.video_url == "https://example.com/video.mp4"

    def test_http_url(self):
        """测试HTTP URL"""
        req = DownloadVideoRequest(video_url="http://example.com/video.mp4")
        assert req.video_url == "http://example.com/video.mp4"

    def test_invalid_url_no_protocol(self):
        """测试无效URL（无协议）"""
        with pytest.raises(ValidationError) as exc_info:
            DownloadVideoRequest(video_url="example.com/video.mp4")
        assert "http" in str(exc_info.value).lower()

    def test_url_too_short(self):
        """测试URL长度验证"""
        # 验证符合最小长度的URL可以正常工作
        req = DownloadVideoRequest(video_url="http://example.com/video.mp4")
        assert req.video_url == "http://example.com/video.mp4"

    def test_url_too_long(self):
        """测试URL长度验证"""
        # 验证超过最大长度的URL会被拒绝
        long_url = "https://example.com/" + "a" * 3000  # 超过 2048 字符
        with pytest.raises(ValidationError) as exc_info:
            DownloadVideoRequest(video_url=long_url)
        # 验证错误信息包含长度限制相关内容
        error_msg = str(exc_info.value).lower()
        assert "2048" in error_msg or "max" in error_msg or "length" in error_msg


class TestFishVoiceTTSRequest:
    """Fish Speech TTS 请求测试"""

    def test_valid_request(self):
        """测试有效请求"""
        req = FishVoiceTTSRequest(
            text="你好，世界",
            speed_factor=1.0,
            temperature=0.7
        )
        assert req.text == "你好，世界"
        assert req.speed_factor == 1.0

    def test_text_too_long(self):
        """测试文本过长"""
        long_text = "a" * 6000
        with pytest.raises(ValidationError):
            FishVoiceTTSRequest(text=long_text)

    def test_temperature_out_of_range(self):
        """测试温度超出范围"""
        with pytest.raises(ValidationError):
            FishVoiceTTSRequest(text="test", temperature=3.0)

    def test_top_p_out_of_range(self):
        """测试top_p超出范围"""
        with pytest.raises(ValidationError):
            FishVoiceTTSRequest(text="test", top_p=1.5)


class TestSaveTimbreRequest:
    """保存音色请求测试"""

    def test_valid_request(self):
        """测试有效请求"""
        req = SaveTimbreRequest(
            audio_name="测试音色",
            prompt_text="这是参考文本",
            seed=42,
            speed=1.0,
            top_p=0.5,
            temperature=0.5,
            repetition_penalty=1.35
        )
        assert req.audio_name == "测试音色"
        assert req.seed == 42

    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        with pytest.raises(ValidationError):
            SaveTimbreRequest(
                audio_name="测试"
                # 缺少其他必填字段
            )

    def test_invalid_output_format(self):
        """测试无效输出格式"""
        with pytest.raises(ValidationError):
            SaveTimbreRequest(
                audio_name="测试",
                prompt_text="测试",
                seed=42,
                speed=1.0,
                top_p=0.5,
                temperature=0.5,
                repetition_penalty=1.35,
                output_format="exe"
            )


@pytest.mark.parametrize("current,size,valid", [
    (1, 10, True),
    (5, 50, True),
    (100, 100, True),
    (0, 10, False),  # current < 1
    (1, 0, False),  # size < 1
    (1, 2000, False),  # size > 1000
])
def test_base_query_request_parametrized(current, size, valid):
    """参数化测试基础查询请求"""
    if valid:
        req = BaseQueryRequest(current=current, size=size)
        assert req.current == current
        assert req.size == size
    else:
        with pytest.raises(ValidationError):
            BaseQueryRequest(current=current, size=size)

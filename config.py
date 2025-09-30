import sys
from pathlib import Path


# 获取程序执行目录
def _get_executable_path():
    if getattr(sys, 'frozen', False):
        # 如果程序是被“冻结”打包的，使用这个路径
        return Path(sys.executable).parent.as_posix()
    else:
        return Path(__file__).parent.parent.parent.as_posix()


ROOT_DIR_WIN = Path(__file__).parent.resolve()

# 程序根目录
ROOT_DIR = _get_executable_path()
_root_path = Path(ROOT_DIR)


api_host = 9527
web_host = 9528
listenport = 9529

UPLOAD_DIR = "static/uploads/"
source_videos_dir = "static/source_videos/"
source_bgm_dir = "static/source_bgm/"
source_audios_dir = "static/source_timbre/"

llm_model = 'deepseek'
model_name = 'deepseek-chat'
llm_key = 'sk-'

video_type = 'pexels'
video_api_keys = 'AQanz5J1ptLpe8EzANVz4fFN9R0friFxQLnvzpTjTLFbwKjpR3eL6XLA'


#
# # 数字人设置
# human_model = "wav2lip"  # musetalk wav2lip ultralight
# fps = 50  # 50
# l = 10  # 10
# m = 8  # 8
# r = 10  # 10
# avatar_id = "wav2lip256_zf"  # avator_1
# batch_size = 16  # 16
# customvideo_config = ""  # custom action json
# tts = "edgetts"  # edgetts xtts gpt-sovits cosyvoice
# REF_FILE = "zh-CN-YunxiaNeural"  # zh-CN-YunxiaNeural
# REF_TEXT = None
# TTS_SERVER = "http://127.0.0.1:9880"  # http://localhost:9880
# transport = "webrtc"  # rtmp webrtc rtcpush
# push_url = "http://localhost:1985/rtc/v1/whip/?app=live&stream=livestream"  # rtmp://localhost/live/livestream
# max_session = 1  # multi session count
#
# sessionid = 330688
# customopt = []

from audio_separator.separator import Separator
from pydub import AudioSegment
import config


# 分离人声与伴奏
def do_s(audio, output):
    model_path = config.ROOT_DIR_WIN / "models/separated_model"
    separator = Separator(model_file_dir=model_path, output_dir=output)
    separator.load_model()
    outfiles = separator.separate(audio)
    print(outfiles)
    return f"{outfiles[1]}", f"{outfiles[0]}"


def do_m(vocalUrl, sourceAudioPath, output_dir):
    # 加载背景音乐和人声文件
    background_music = AudioSegment.from_file(sourceAudioPath)
    vocal = AudioSegment.from_file(vocalUrl)
    # 合并音频文件
    combined_audio = background_music.overlay(vocal)
    # 导出合并后的音频文件
    combined_audio.export(f"{output_dir}combined_audio.wav", format="wav")
    return "combined_audio.wav"

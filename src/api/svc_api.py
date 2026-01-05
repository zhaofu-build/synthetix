from fastapi import APIRouter, UploadFile, Form, File, Depends
import soundfile as sf
from src.service import dh_live
from src.util import string_util, file_util
import config
from src.model.base import BaseReq
from src.model.entity.audio_source import AudioSource
from src.db.session import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import uuid

router = APIRouter()


@router.post("/get_source_audio")
def get_source_audio(db: Session = Depends(get_db)):
    # 获取音色列表
    all_objs = db.query(AudioSource).limit(1000).all()
    all_files = []
    for obj in all_objs:
        file_dict = {
            "id": obj.id,
            "audio_name": obj.audio_name,
            "prompt_text": obj.prompt_text,
            "web_path": obj.web_path,
            "seed": obj.seed,
            "speed": obj.speed,
            "top_p": obj.top_p,
            "temperature": obj.temperature,
            "repetition_penalty": obj.repetition_penalty,
            "create_time": obj.create_time,
        }
        file_dict["web_path"] = os.path.join(config.source_audios_dir, file_dict.get("web_path"))
        all_files.append(file_dict)
    return all_files


@router.post("/del_source_audio")
def del_source_audio(req: BaseReq, db: Session = Depends(get_db)):
    # 删除音色
    audio_obj = db.query(AudioSource).filter(AudioSource.id == req.id).first()
    if audio_obj:
        web_path = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir, audio_obj.web_path)
        file_util.del_file(web_path)
        db.delete(audio_obj)
        db.commit()
        return True
    return False


# 保存音色
@router.post("/save_timbre")
async def save_timbre(file: UploadFile = File(...),
                      audio_name: str = Form(...),
                      prompt_text: str = Form(...),
                      seed: int = Form(...),
                      speed: float = Form(...),
                      top_p: float = Form(...),
                      temperature: float = Form(...),
                      repetition_penalty: float = Form(...),
                      output_format: str = Form(...),
                      db: Session = Depends(get_db)
                      ):
    filename = f"{uuid.uuid4().hex}.{output_format}"
    web_path = os.path.join(config.ROOT_DIR_WIN,config.source_audios_dir, filename)
    # 分块写入文件（适合大文件）
    with open(web_path, "wb") as buffer:
        while content := await file.read(1024 * 1024):  # 每次读取1MB
            buffer.write(content)

    # 插入数据库记录
    audio_obj = AudioSource(
        audio_name=audio_name,
        prompt_text=prompt_text,
        web_path=filename,
        seed=seed,
        speed=speed,
        top_p=top_p,
        temperature=temperature,
        repetition_penalty=repetition_penalty,
    )
    db.add(audio_obj)
    db.commit()
    db.refresh(audio_obj)
    return True


# 语音克隆
@router.post("/sovits_v4")
async def tts_endpoint(req: BaseReq):
    from src.service.sovits_v4 import use_sovits_v4
    # 获取字段，如果字段为空则返回None
    req_dict = req.dict()
    if req_dict.get("prompt_language", None) is None:
        language = string_util.detect_prompt_language(req_dict.get("prompt_text", None))
        req_dict["prompt_language"] = language
    if req_dict.get("text_language", None) is None:
        language = string_util.detect_prompt_language(req_dict.get("text", None))
        req_dict["text_language"] = language
    opt_sr, audio_opt = use_sovits_v4.get_tts_wav(
        ref_wav_path=req_dict.get("ref_wav_path", None),
        prompt_text=req_dict.get("prompt_text", None),
        prompt_language=req_dict.get("prompt_language", None),
        text=req_dict.get("text", None),
        text_language=req_dict.get("text_language", None),
        how_to_cut=req_dict.get("how_to_cut", None),
        top_k=req_dict.get("top_k", None),
        top_p=req_dict.get("top_p", None),
        temperature=req_dict.get("temperature", None),
        # ref_free=ref_free,
        speed=req_dict.get("speed", None),
        # if_freeze=if_freeze,
        # inp_refs=inp_refs,
        # sample_steps=sample_steps,
        # if_sr=if_sr,
        # pause_second=pause_second,
    )
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / 'sovits_v4_audio.wav'
    sf.write(access_url_path, audio_opt, opt_sr)
    return {
        "vitsV4WebUrl": 'static/uploads/sovits_v4_audio.wav',
        "vitsV4Url": access_url_path,
    }


# 分离音频和伴奏
@router.post("/separate_audio")
async def separate_audio(req: BaseReq):
    vocalUrl, accompanimentUrl = dh_live.do_s(req.audio_path, config.UPLOAD_DIR)
    return {
        "vocalUrl": config.UPLOAD_DIR + vocalUrl,
        "vocalWebUrl": config.UPLOAD_DIR + vocalUrl,
        "accompanimentUrl": config.UPLOAD_DIR + accompanimentUrl,
        "accompanimentWebUrl": config.UPLOAD_DIR + accompanimentUrl
    }


# 合并伴奏
@router.post("/merge_audio")
async def merge_audio(req: BaseReq):
    # 转换 歌曲人声req.vocalUrl  素材人声req.sourceAudioPath
    final_vocal = req.sourceAudioPath
    finalUrl = dh_live.do_m(final_vocal, req.accompanimentUrl, config.UPLOAD_DIR)
    return {
        "finalUrl": config.UPLOAD_DIR + finalUrl,
        "finalWebUrl": config.UPLOAD_DIR + finalUrl,
    }


from src.service import fish_voice


# # 语音克隆
@router.post("/fish_voice")
async def fish_voice_tts_endpoint(req: BaseReq, db: Session = Depends(get_db)):
    """
      生成语音
      :param req.text: 要合成的文本
      :param req.seed: 随机种子
      :param req.speed_factor: 语速因子 (1.0为正常语速)
      :param req.output_format: 输出格式 (wav/pcm/mp3)
      :param req.top_p: 采样概率阈值 (控制生成多样性)
      :param req.temperature: 温度参数 (控制随机性)
      :param req.repetition_penalty: 重复惩罚因子 (避免重复)
      :param req.references_audio: 参考音频(base64编码的音频字符串)
      :param req.references_text: 参考音频文本
      """
    references  = []
    output_format = "wav"
    if req.audio_source_id == -1:
        if req.references_audio is not None:
            references = [{
                # 实际使用base64编码的音频字符串
                "audio": req.references_audio,
                "text": req.references_text
            }]
        audio_data = fish_voice.fish_voice(req.text, output_format, references, req.seed, req.speed_factor, req.top_p,
                                           req.temperature, req.repetition_penalty)
    else:
        audio_obj = db.query(AudioSource).filter(AudioSource.id == req.audio_source_id).first()
        if not audio_obj:
            raise ValueError("Audio source not found")
        web_path = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir, audio_obj.web_path)

        references = [{
            # 实际使用base64编码的音频字符串
            "audio": file_util.audio_to_base64(web_path),
            "text": audio_obj.prompt_text
        }]
        audio_data = fish_voice.fish_voice(req.text, output_format, references, audio_obj.seed, audio_obj.speed, audio_obj.top_p,
                                           audio_obj.temperature, audio_obj.repetition_penalty)

    filename = f"{uuid.uuid4().hex}.{output_format}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)
    # 保存结果
    with open(file_path, "wb") as f:
        f.write(audio_data)
    return {"webPath": config.UPLOAD_DIR + filename}


# 获取随机音色
@router.get("/get_random_audio")
def get_random_audio(db: Session = Depends(get_db)):
    audio_obj = db.query(AudioSource).filter(
        AudioSource.del_flag == False
    ).order_by(func.random()).limit(1).first()
    if audio_obj:
        audio_dict = {
            "id": audio_obj.id,
            "audio_name": audio_obj.audio_name,
            "prompt_text": audio_obj.prompt_text,
            "web_path": audio_obj.web_path,
            "seed": audio_obj.seed,
            "speed": audio_obj.speed,
            "top_p": audio_obj.top_p,
            "temperature": audio_obj.temperature,
            "repetition_penalty": audio_obj.repetition_penalty,
            "create_time": audio_obj.create_time,
        }
        return audio_dict
    return None

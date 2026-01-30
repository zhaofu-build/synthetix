from src.service import video_downloader
from src.service import use_langchain_llm, use_ffmpeg
from src.util import string_util, prompt_config
import config
from fastapi import APIRouter, Depends
from src.model.base import BaseReq
from src.model.entity.video_source import VideoSource
from src.db.session import get_db
from sqlalchemy.orm import Session
import logging as logger

router = APIRouter()


@router.post("/llm_get_source")
def llm_get_source(req: BaseReq):
    logger.info("=================================llm获取搜索关键词=================================")
    keywords_prompt = prompt_config.keywords_prompt(req.creative)
    messages = [{"role": "user", "content": keywords_prompt}]
    keywords_resp = use_langchain_llm.generate_response(messages)
    keywords_resp = string_util.remove_think_tags(keywords_resp)
    keywords = keywords_resp.split(",")
    logger.info(keywords)
    logger.info("=================================下载关键词对应视频=================================")
    return video_downloader.keywords_download(keywords)


@router.post("/videos_transitions")
def videos_transitions(req: BaseReq, db: Session = Depends(get_db)):
    audioUrl = req.dict().get("audioUrl", None)
    logger.info("=================================视频处理=================================")
    # save_dir = config.ROOT_DIR_WIN / config.source_videos_dir
    # folder_file_names = file_util.get_folder_file_name(save_dir)
    # source_infos = []
    video_objs = db.query(VideoSource).filter(VideoSource.video_type == 1).all()
    source_infos = [{"id": obj.id, "duration": obj.duration, "description": obj.description} 
                    for obj in video_objs]
    # for video_source in video_source_use:
    #     source_info = {
    #         "source_name": folder_file_name,
    #         "video_duration": video_source["duration"],
    #         "video_describe": video_source["description"]
    #     }
    #     source_infos.append(source_info)
    duration = 30
    if audioUrl is not None:
        video_info = use_ffmpeg.get_video_info(req.audioUrl)
        duration = video_info['duration']
    logger.info("=================================llm获取剪辑视频提示词=================================")
    clip_prompt = prompt_config.clip_prompt(req.creative, source_infos, duration)
    logger.info(clip_prompt)
    messages = [{"role": "user", "content": clip_prompt}]
    clip_resp = use_langchain_llm.generate_response(messages)
    keywords_resp = string_util.remove_think_tags(clip_resp)
    logger.info("=================================根据llm返回视频信息进行剪辑=================================")
    logger.info(keywords_resp)
    bracket_json = string_util.get_bracket_json(keywords_resp)
    final_video = config.UPLOAD_DIR + "concatenate_videos.mp4"
    use_ffmpeg.concatenate_videos_with_transitions(bracket_json, final_video)

    if audioUrl is not None:
        logger.info("=================================合并文案音频=================================")
        use_ffmpeg.add_audio_to_video(final_video, audioUrl, config.UPLOAD_DIR + "final_video.mp4")
        final_video = config.UPLOAD_DIR + "final_video.mp4"
    return {
        "concatenate_web_url": final_video
    }


@router.get("/llm_conversation")
def llm_conversation(keywords_prompt,prompt_type):
    """
    keywords_prompt:提示词
    type：类型 1：文生图 ，2：图生图 3：图生视频
    """
    logger.info("=================================调用大模型================================")
    messages = [{"role": "system", "content": f"现在用户正在进行{prompt_type},请你优化提示词，使生成结果更丰富，效果更好"},{"role": "user", "content": keywords_prompt}]
    keywords_resp = use_langchain_llm.generate_response(messages)
    keywords_resp = string_util.remove_think_tags(keywords_resp)
    return keywords_resp
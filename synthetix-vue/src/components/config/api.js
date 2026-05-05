// @deprecated 新代码请使用 src/api/modules/ 下的 API 模块 + src/api/request.js (axios)
// 此文件仅保留向后兼容，供 VideoStitching.vue 等旧组件使用
import { API_HOST } from '@/utils/request'
const HOST = API_HOST
const api = {
    // 设置的请求host地址
    HOST,

    // ========== 工具服务 ==========
    // 打开下载文件夹
    OPEN_FOLDER: `${HOST}/open_folder`,
    // 获取数据
    GET_DATA: `${HOST}/get_data`,

    // ========== 视频服务 (/api/videos) ==========
    // 下载视频
    download_video: `${HOST}/api/videos/download`,
    // 视频处理
    process_video: `${HOST}/api/videos/process`,
    // 上传文件（视频）
    upload_video: `${HOST}/api/tools/upload/video`,
    // 上传文件（图片，音频）
    upload_all_file_stream: `${HOST}/api/tools/upload/file`,
    // 上传视频素材文件
    upload_source_videos_stream: `${HOST}/api/videos`,
    // 获取视频描述（AI分析）
    get_description: `${HOST}/api/videos`,  // 使用 /api/videos/{id}/description
    // 字幕生成
    transcribe: `${HOST}/api/videos/transcribe`,
    // 视频添加字幕
    video_add_subtitle: `${HOST}/api/videos/subtitle`,
    // 提取音频
    get_audio: `${HOST}/api/videos/extract-audio`,
    // 添加音频到视频
    add_audio_to_video: `${HOST}/api/videos/add-audio`,
    // 提取视频帧图片
    extract_frame: `${HOST}/api/videos/extract-frame`,
    // 开始压缩
    start_compression: `${HOST}/api/videos/compress`,

    // ========== 音频服务 (/api/audios) ==========
    // 分离音频和伴奏
    separate_audio: `${HOST}/api/audios/separate`,
    // 语音克隆（Fish Speech）
    fish_voice: `${HOST}/api/audios/tts/fish-speech`,
    // 保存音色
    save_timbre: `${HOST}/api/audios`,
    // 获取已存在本地音色素材
    get_source_audio: `${HOST}/api/audios`,
    // 删除本地音色素材（使用 DELETE /api/audios/{id}）
    del_source_audio: `${HOST}/api/audios`,
    // 获取随机音色
    get_random_audio: `${HOST}/api/audios/random`,

    // ========== 视频素材库 (/api/videos) ==========
    // 获取视频素材库list
    get_source_videos: `${HOST}/api/videos`,
    // 删除本地视频素材（使用 DELETE /api/videos/{id}）
    del_source_videos: `${HOST}/api/videos`,
    // 更新本地视频字段（使用 PATCH /api/videos/{id}）
    update_video_source: `${HOST}/api/videos`,
    // 删除本地素材
    del_all_source_videos: `${HOST}/api/videos`,
    // 获取随机视频
    get_random_video: `${HOST}/api/videos/random`,

    // ========== AI 服务 (/api/ai) ==========
    // LLM获取素材
    llm_get_source: `${HOST}/api/ai/keywords`,
    // 生成视频转场
    videos_transitions: `${HOST}/api/ai/video-transitions`,
    // Frame Pack生成视频
    frame_pack_generate: `${HOST}/frame_pack_generate`,

    // ========== 工具服务 (/api/tools) ==========
    // 获取日志
    loadLog: `${HOST}/api/tools/logs`,
    // 获取设置
    get_config: `${HOST}/api/tools/config`,
    // 保存设置
    save_config: `${HOST}/api/tools/config`,

    // ========== 聊天服务（保留旧路由） ==========
    // 获取记录列表
    chat_list: `${HOST}/chat_list`,
    // 删除记录
    chat_del: `${HOST}/chat_del`,
    // 根据id查询详细记录
    chat_info: `${HOST}/chat_info`,
    // 聊天交互
    chat: `${HOST}/chat`,
    // 角色列表
    chat_role: `${HOST}/chat_role`,
    // 保存修改角色
    chat_role_save: `${HOST}/chat_role_save`,
    // 根据id查询角色
    chat_role_info: `${HOST}/chat_role_info`,
    // 删除角色
    chat_role_del: `${HOST}/chat_role_del`,
    // 数字人连接控制
    offer: `${HOST}/offer`,
}
export default api

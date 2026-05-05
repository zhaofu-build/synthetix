import request from '../request'

export const videoApi = {
  // 获取素材库素材（分页）
  // 参数: { page, page_size, video_type }
  getSourceVideos: (params) => request.get('/api/videos', params),

  // 更新视频源信息
  // PATCH /api/videos/{id}
  updateVideoSource: (id, params) => request.patch(`/api/videos/${id}`, params),

  // 删除本地素材
  // DELETE /api/videos/{id}
  deleteSourceVideos: (id) => request.delete(`/api/videos/${id}`),

  // 上传视频素材到数据库
  uploadSourceVideos: (formData, extraConfig = {}) => request.post('/api/videos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...extraConfig,
  }),

  // 获取视频描述（通过AI分析）
  // GET /api/videos/{id}/description
  getVideoDescription: (id) => request.get(`/api/videos/${id}/description`, { timeout: 120000 }),

  // 上传视频文件并获取视频信息
  uploadVideo: (formData) => request.post('/api/tools/upload/video', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }),

  // 下载视频
  downloadVideo: (params) => request.post('/api/videos/download', params),

  // 处理视频（剪辑、变速、调整音量等）
  processVideo: (params) => request.post('/api/videos/process', params),

  // 提取视频帧为图片
  extractFrame: (params) => request.post('/api/videos/extract-frame', params),

  // 从视频中提取音频
  extractAudio: (params) => request.post('/api/videos/extract-audio', params),

  // 添加音频到视频
  addAudioToVideo: (params) => request.post('/api/videos/add-audio', params),

  // 音视频转录生成字幕
  transcribe: (params) => request.post('/api/videos/transcribe', params),

  // 为视频添加字幕
  addSubtitle: (params) => request.post('/api/videos/subtitle', params),

  // 启动批量视频压缩任务
  startCompression: (params) => request.post('/api/videos/compress', params),

  // 获取随机视频
  getRandomVideo: (params) => request.get('/api/videos/random', params),

  // 上传视频文件（简单上传）
  upload: (file) => {
    const formData = new FormData()
    formData.append('file_stream', file)
    return request.post('/api/tools/upload/video', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 保存临时资产到素材库（转为正式）
  saveToLibrary: (videoId) => request.post('/api/projects/save-to-library', { video_id: videoId }),

  // 删除临时素材（旧）
  deleteTempMaterial: (videoId) => request.delete(`/api/projects/temp-material/${videoId}`),

  // 删除项目临时文件
  deleteTempFile: (tempFileId) => request.delete(`/api/projects/temp-files/${tempFileId}`),

  // 临时文件转正式素材（存入素材库）
  saveTempToLibrary: (tempFileId) => request.post(`/api/projects/temp-files/${tempFileId}/save-to-library`),

  // 上传通用文件（图片/视频/音频）到项目临时目录
  uploadFile: (file, projectId = null, sessionId = null) => {
    const formData = new FormData()
    formData.append('file_stream', file)
    if (projectId) formData.append('project_id', projectId)
    if (sessionId) formData.append('session_id', sessionId)
    return request.post('/api/tools/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
}

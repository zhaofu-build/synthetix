import request from '../request'

export const audioApi = {
  // 获取音色列表（分页）
  // 参数: { page, page_size }
  getSourceAudio: (params) => request.get('/api/audios', params),

  // 删除音色
  // DELETE /api/audios/{id}
  deleteSourceAudio: (id) => request.delete(`/api/audios/${id}`),

  // 更新音色
  // PUT /api/audios/{id}
  updateAudio: (id, params) => request.put(`/api/audios/${id}`, params),

  // 设为默认音色
  // POST /api/audios/{id}/set-default
  setDefaultVoice: (id) => request.post(`/api/audios/${id}/set-default`),

  // 保存音色文件到数据库
  saveTimbre: (formData) => request.post('/api/audios', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }),

  // 分离音频和伴奏
  separateAudio: (params) => request.post('/api/audios/separate', params),

  // 合并伴奏
  mergeAudio: (params) => request.post('/api/audios/merge', params),

  // 生成语音（Fish Speech TTS）
  fishVoice: (params) => request.post('/api/audios/tts/fish-speech', params),

  // 获取随机音色
  getRandomAudio: () => request.get('/api/audios/random')
}

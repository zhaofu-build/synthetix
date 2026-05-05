import request from '../request'

export const aiApi = {
  // 根据关键词获取素材
  llmGetSource: (params) => request.post('/api/ai/keywords', params),

  // 视频转场
  videosTransitions: (params) => request.post('/api/ai/video-transitions', params),

  // 优化提示词
  // 参数: { prompt, prompt_type }
  llmConversation: (params) => request.get('/api/ai/optimize-prompt', params),

  // ==================== Core-Nexus-AI 接口 ====================

  // 文本生成音乐（支持 generate/retake/repaint/edit/extend/cover 模式）
  // 参数: { prompt, duration?, style?, model?, mode?, lyrics?, audio?, variance?, start_time?, end_time?, extend_left?, extend_right?, generation? }
  textToMusic: (params) => request.post('/api/nexus/music', params, { responseType: 'blob' }),

  // 音乐风格迁移
  // 参数: { audio (base64), prompt?, style?, model?, generation? }
  musicToMusic: (params) => request.post('/api/nexus/music-to-music', params, { responseType: 'blob' }),

  // 获取 BGM 音频 base64（供音乐编辑模式使用）
  getBgmAudio: (bgmId) => request.get(`/api/nexus/music/bgm-audio/${bgmId}`),

  // TTS 语音合成
  // 参数: { text, model?, speaker?, language?, refAudio?, refText? }
  tts: (params) => request.post('/api/nexus/tts', params, { responseType: 'blob' }),

  // ASR 语音识别
  // 参数: { audio (base64), language? }
  asr: (params) => request.post('/api/nexus/asr', params),

  // VL 视觉理解
  // 参数: { prompt, image?, images?, messages? }
  vl: (params) => request.post('/api/nexus/vl', params),

  // LLM 文本生成
  // 参数: { prompt?, messages?, model?, generation? }
  llm: (params) => request.post('/api/nexus/llm', params)
}

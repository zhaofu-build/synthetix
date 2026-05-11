import request from '../request'

export const proxyApi = {
  generateProxy: (videoId) =>
    request.post('/api/agent/execute', {
      tool: 'analyze_video',
      params: { video_id: videoId },
    }),
}

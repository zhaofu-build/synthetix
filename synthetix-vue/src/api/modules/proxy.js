import { API_HOST } from '../../utils/request'

export const proxyApi = {
  async generateProxy(videoId) {
    const res = await fetch(`${API_HOST}/api/agent/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: 'analyze_video', params: { video_id: videoId } }),
    }).then(r => r.json())
    return res.data
  },
}

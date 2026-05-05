import { API_HOST } from '../../utils/request'

export const qualityApi = {
  async check(videoPath, clips, targetDuration) {
    const res = await fetch(`${API_HOST}/api/projects/quality-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: videoPath, clips, target_duration: targetDuration }),
    }).then(r => r.json())
    return res.data
  },
}

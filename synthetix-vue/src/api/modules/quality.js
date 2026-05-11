import request from '../request'

export const qualityApi = {
  check: (videoPath, clips, targetDuration) =>
    request.post('/api/projects/quality-check', {
      video_path: videoPath,
      clips,
      target_duration: targetDuration,
    }),
}

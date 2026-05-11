import request from '../request'

export const publishApi = {
  getPlatforms: () => request.get('/api/platform-presets'),
  getSnapshots: (projectId) => request.get(`/api/projects/${projectId}/plan/snapshots`),
  createSnapshot: (projectId, label, data) => request.post(`/api/projects/${projectId}/plan/snapshot`, { label, data }),
}

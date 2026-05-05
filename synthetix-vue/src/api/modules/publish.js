import { API_HOST } from '../../utils/request'

export const publishApi = {
  async getPlatforms() {
    const res = await fetch(`${API_HOST}/api/platform-presets`).then(r => r.json())
    return res.data
  },

  async getSnapshots(projectId) {
    const res = await fetch(`${API_HOST}/api/projects/${projectId}/plan/snapshots`).then(r => r.json())
    return res.data
  },

  async createSnapshot(projectId, label, data) {
    const res = await fetch(`${API_HOST}/api/projects/${projectId}/plan/snapshot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, data }),
    }).then(r => r.json())
    return res.data
  },
}

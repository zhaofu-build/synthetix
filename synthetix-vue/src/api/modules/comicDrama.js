import request from '../request'

export const comicDramaApi = {
  create: (data) => request.post('/api/comic-projects', data),
  list: (params = {}) => request.get('/api/comic-projects', { params }),
  get: (id) => request.get(`/api/comic-projects/${id}`),
  update: (id, data) => request.patch(`/api/comic-projects/${id}`, data),
  remove: (id) => request.delete(`/api/comic-projects/${id}`),

  generateScript: (id, data) => request.post(`/api/comic-projects/${id}/generate-script`, data),
  updateCharacters: (id, characters) => request.put(`/api/comic-projects/${id}/characters`, characters),
  updatePanels: (id, panels) => request.put(`/api/comic-projects/${id}/panels`, panels),
  generatePanelImage: (id, data) => request.post(`/api/comic-projects/${id}/panels/generate-image`, data),
  generatePanelVideo: (id, data) => request.post(`/api/comic-projects/${id}/panels/generate-video`, data),
  generatePanelAudio: (id, data) => request.post(`/api/comic-projects/${id}/panels/generate-audio`, data),
  uploadCharRefImage: (id, charIndex, formData) => request.post(`/api/comic-projects/${id}/characters/${charIndex}/reference-image`, formData),
  generateCharRefImage: (id, charIndex) => request.post(`/api/comic-projects/${id}/characters/${charIndex}/generate-reference`),
  updateBgmConfig: (id, bgmConfig) => request.put(`/api/comic-projects/${id}/bgm`, bgmConfig),
  compose: (id) => request.post(`/api/comic-projects/${id}/compose`),
}

export const comicSeriesApi = {
  create: (data) => request.post('/api/comic-series', data),
  list: (params = {}) => request.get('/api/comic-series', { params }),
  get: (id) => request.get(`/api/comic-series/${id}`),
  update: (id, data) => request.patch(`/api/comic-series/${id}`, data),
  remove: (id) => request.delete(`/api/comic-series/${id}`),

  createEpisode: (seriesId, data) => request.post(`/api/comic-series/${seriesId}/episodes`, data),
  listEpisodes: (seriesId) => request.get(`/api/comic-series/${seriesId}/episodes`),
  syncCharacters: (seriesId) => request.post(`/api/comic-series/${seriesId}/sync-characters`),
  syncStyle: (seriesId) => request.post(`/api/comic-series/${seriesId}/sync-style`),
}

import request from '../request'

export const subtitleApi = {
  save: (projectId, data) => request.post(`/api/projects/${projectId}/subtitles`, data),
  load: (projectId) => request.get(`/api/projects/${projectId}/subtitles`),
}

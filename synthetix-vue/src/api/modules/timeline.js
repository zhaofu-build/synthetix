import request from '../request'

export const timelineApi = {
  save: (projectId, data) => request.post(`/api/projects/${projectId}/timeline`, data),
}

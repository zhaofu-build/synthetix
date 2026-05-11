import request from '../request'

export const extensionApi = {
  list: () => request.get('/api/extensions'),
  toggle: (name) => request.post(`/api/extensions/${name}/toggle`),
  remove: (name) => request.delete(`/api/extensions/${name}`),
  create: (data) => request.post('/api/extensions', data),
  update: (name, data) => request.put(`/api/extensions/${name}`, data),
  reload: () => request.post('/api/extensions/reload'),
}

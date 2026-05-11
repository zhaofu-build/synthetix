import request from '../request'

export const mcpApi = {
  listServers: () => request.get('/api/mcp/servers'),
  listTools: () => request.get('/api/mcp/tools'),
  register: (data) => request.post('/api/mcp/servers', data),
  remove: (name) => request.delete(`/api/mcp/servers/${name}`),
}

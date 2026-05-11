import request from '../request'

export const agentApi = {
  // 发送同步消息
  chat: (data) => request.post('/api/agent/chat', data),

  // 删除项目会话
  deleteProjectSessions: (projectId) => request.delete(`/api/agent/sessions/project/${projectId}`),

  // 生成方案
  generatePlan: (data) => request.post('/api/agent/plan', data),

  // 执行工具
  execute: (data) => request.post('/api/agent/execute', data),
}

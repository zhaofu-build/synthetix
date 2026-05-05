import request from '../request'

export const systemApi = {
  // 获取配置
  getConfig: () => request.get('/api/tools/config'),

  // 保存配置
  saveConfig: (data) => request.patch('/api/tools/config', data),

  // 获取日志
  getLog: () => request.get('/api/tools/logs'),

  // 上传通用文件
  uploadFile: (formData) => request.post('/api/tools/upload/file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }),

  // 获取可用模型列表（代理 core-nexus-ai）
  getModels: (taskType, baseUrl) => request.get('/api/nexus/models', { params: { task_type: taskType, base_url: baseUrl || undefined } }),

  // 测试 core-nexus-ai 连接
  testConnection: (baseUrl) => request.post('/api/nexus/test-connection', { base_url: baseUrl }),

  // Cookie 管理
  getCookies: () => request.get('/api/tools/cookies'),
  saveCookies: (content) => request.put('/api/tools/cookies', { content }),
  deleteCookies: () => request.delete('/api/tools/cookies'),
}

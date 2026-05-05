import request from '../request'
import { assetUrl, API_HOST } from '../../utils/request'

export const projectApi = {
  // 创建项目
  create: (data) => request.post('/api/projects', data),

  // 获取项目列表（分页）
  list: (params = {}) => request.get('/api/projects', { params }),

  // 获取项目详情
  get: (id) => request.get(`/api/projects/${id}`),

  // 获取项目完整状态（含关联素材/音色/BGM）
  getFull: (id) => request.get(`/api/projects/${id}/full`),

  // 更新项目（通用自动保存）
  update: (id, data) => request.patch(`/api/projects/${id}`, data),

  // 删除项目
  remove: (id) => request.delete(`/api/projects/${id}`),

  // 导出项目为JSON
  exportProject: (id) => request.get(`/api/projects/${id}/export`),

  // 导入项目
  importProject: (formData) => request.post('/api/projects/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 生成剪辑方案
  generatePlan: (id, data) => request.post(`/api/projects/${id}/plan/generate`, data),

  // 应用方案到时间线
  applyPlan: (id) => request.post(`/api/projects/${id}/plan/apply`),

  // 渲染视频
  render: (id, data = {}) => request.post(`/api/projects/${id}/render`, data),

  // 生成TTS语音
  generateTts: (data) => request.post('/api/projects/generate-tts', data),

  // 获取BGM列表
  listBgm: () => request.get('/api/projects/bgm'),

  // 上传BGM
  uploadBgm: (formData) => request.post('/api/projects/bgm', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 删除BGM
  deleteBgm: (id) => request.delete(`/api/projects/bgm/${id}`),

  // AI选曲
  aiSelectBgm: (data) => request.post('/api/projects/bgm/ai-select', data),

  // AI生成BGM
  aiGenerateBgm: (data) => request.post('/api/projects/bgm/ai-generate', data),
}

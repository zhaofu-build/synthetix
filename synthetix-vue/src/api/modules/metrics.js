import request from '../request'

export const metricsApi = {
  getAiMetrics: () => request.get('/api/metrics/ai'),
  health: () => request.get('/health'),
}

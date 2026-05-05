import axios from 'axios'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import { API_HOST } from '@/utils/request'

// 创建 axios 实例
const request = axios.create({
  baseURL: API_HOST,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 全局 loading 计数器，防止并发请求闪烁
let loadingCount = 0

function startLoading() {
  if (loadingCount === 0) NProgress.start()
  loadingCount++
}

function stopLoading() {
  loadingCount--
  if (loadingCount <= 0) {
    loadingCount = 0
    NProgress.done()
  }
}

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 跳过静默请求（如 debounce save）
    if (!config._silent) startLoading()
    return config
  },
  error => {
    stopLoading()
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    if (!response.config._silent) stopLoading()
    const { data } = response

    // 业务错误处理
    if (data.success === false) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message || '请求失败'))
    }

    // 自动提取 data 字段（后端已转换为 camelCase）
    return data.data ?? data
  },
  error => {
    stopLoading()
    console.error('Response error:', error)
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    } else {
      ElMessage.error(error.response?.data?.message || '请求失败')
    }
    return Promise.reject(error)
  }
)

export default request
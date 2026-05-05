/**
 * 统一 HTTP 请求封装
 *
 * 提供统一的 API 调用方式，自动处理：
 * - 响应数据解析
 * - 错误处理
 * - camelCase 转换（后端已自动转换）
 */

const API_HOST = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:9527'

/**
 * 发送 HTTP 请求
 * @param {string} url - 请求 URL
 * @param {Object} options - 请求选项
 * @param {string} options.method - HTTP 方法
 * @param {Object} options.data - 请求体数据
 * @param {Object} options.headers - 请求头
 * @returns {Promise<Object>} 响应数据
 */
export async function request(url, options = {}) {
  const {
    method = 'GET',
    data = null,
    headers = {},
    isFormData = false
  } = options

  const config = {
    method,
    headers: {
      ...headers,
      ...(isFormData ? {} : { 'Content-Type': 'application/json' })
    }
  }

  if (data) {
    if (isFormData) {
      config.body = data
    } else {
      config.body = JSON.stringify(data)
    }
  }

  try {
    const response = await fetch(url, config)

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || `HTTP ${response.status}`)
    }

    const result = await response.json()

    // 检查业务状态
    if (result.success === false) {
      throw new Error(result.message || '请求失败')
    }

    // 返回 data 部分（后端已转换为 camelCase）
    return result.data || {}
  } catch (error) {
    console.error(`请求失败 [${method} ${url}]:`, error)
    throw error
  }
}

/**
 * GET 请求
 */
export async function get(url, params = {}) {
  const queryString = new URLSearchParams(params).toString()
  const fullUrl = queryString ? `${url}?${queryString}` : url
  return request(fullUrl, { method: 'GET' })
}

/**
 * POST JSON 请求
 */
export async function post(url, data = {}) {
  return request(url, { method: 'POST', data })
}

/**
 * POST FormData 请求
 */
export async function postForm(url, formData) {
  return request(url, { method: 'POST', data: formData, isFormData: true })
}

/**
 * PATCH 请求
 */
export async function patch(url, data = {}) {
  return request(url, { method: 'PATCH', data })
}

/**
 * DELETE 请求
 */
export async function del(url) {
  return request(url, { method: 'DELETE' })
}

/**
 * 构建静态资源 URL
 * @param {string} webPath - 相对路径
 * @returns {string} 完整 URL
 */
export function assetUrl(webPath) {
  if (!webPath) return ''
  if (webPath.startsWith('http')) return webPath
  // 移除开头的 / 避免 //static/uploads/... 的双斜杠
  const cleanPath = webPath.replace(/^\/+/, '')
  return `${API_HOST}/${cleanPath}`
}

export { API_HOST }

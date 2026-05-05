import { ref, watch } from 'vue'

/**
 * 项目配置前端缓存 — localStorage 持久化，减少网络请求。
 * 用于缓存用户偏好、UI 状态等非关键数据。
 */
const CACHE_PREFIX = 'synthetix_cache_'
const TTL = 30 * 60 * 1000 // 30 分钟

function keyOf(projectId, field) {
  return `${CACHE_PREFIX}${projectId}_${field}`
}

function read(projectId, field) {
  try {
    const raw = localStorage.getItem(keyOf(projectId, field))
    if (!raw) return null
    const { value, ts } = JSON.parse(raw)
    if (Date.now() - ts > TTL) {
      localStorage.removeItem(keyOf(projectId, field))
      return null
    }
    return value
  } catch {
    return null
  }
}

function write(projectId, field, value) {
  try {
    localStorage.setItem(keyOf(projectId, field), JSON.stringify({ value, ts: Date.now() }))
  } catch { /* quota exceeded — ignore */ }
}

/**
 * @param {string|import('vue').Ref<string>} projectId
 * @param {string} field 缓存字段名
 * @param {*} defaultValue 默认值
 */
export function useProjectCache(projectId, field, defaultValue = null) {
  const pid = typeof projectId === 'object' ? projectId : ref(projectId)
  const cached = ref(read(pid.value, field) ?? defaultValue)

  watch(pid, (newId) => {
    cached.value = read(newId, field) ?? defaultValue
  })

  const save = (value) => {
    cached.value = value
    write(pid.value, field, value)
  }

  return { cached, save }
}

/**
 * 批量缓存辅助：缓存一组 key-value 到单个 localStorage 条目。
 */
export function useProjectCacheBatch(projectId, field) {
  const pid = typeof projectId === 'object' ? projectId : ref(projectId)
  const cached = ref(read(pid.value, field) || {})

  watch(pid, (newId) => {
    cached.value = read(newId, field) || {}
  })

  const save = (updates) => {
    cached.value = { ...cached.value, ...updates }
    write(pid.value, field, cached.value)
  }

  const remove = (key) => {
    delete cached.value[key]
    write(pid.value, field, cached.value)
  }

  return { cached, save, remove }
}

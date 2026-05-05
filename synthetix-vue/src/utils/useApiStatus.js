import { ref, onMounted, onUnmounted } from 'vue'

export function useApiStatus() {
  const connected = ref(true)
  const showReconnectBar = ref(false)
  let checkInterval = null
  let failCount = 0

  const check = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:9527'}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      })
      if (res.ok) {
        failCount = 0
        connected.value = true
        showReconnectBar.value = false
      } else {
        throw new Error('not ok')
      }
    } catch {
      failCount++
      if (failCount >= 2) {
        connected.value = false
        showReconnectBar.value = true
      }
    }
  }

  onMounted(() => {
    checkInterval = setInterval(check, 15000)
  })

  onUnmounted(() => {
    if (checkInterval) clearInterval(checkInterval)
  })

  return { connected, showReconnectBar, check }
}

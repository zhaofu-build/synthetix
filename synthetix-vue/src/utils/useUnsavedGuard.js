import { onMounted, onBeforeUnmount } from 'vue'
import { ElMessageBox } from 'element-plus'

export function useUnsavedGuard(isDirty, options = {}) {
  const { message = '有未保存的更改，确定要离开吗？', confirmText = '离开', cancelText = '留下' } = options

  function onBeforeUnload(e) {
    if (isDirty()) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', onBeforeUnload)
  })

  async function confirmLeave() {
    if (!isDirty()) return true
    try {
      await ElMessageBox.confirm(message, '提示', {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type: 'warning',
      })
      return true
    } catch {
      return false
    }
  }

  return { confirmLeave }
}

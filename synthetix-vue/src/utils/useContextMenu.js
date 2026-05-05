import { ref, onMounted, onUnmounted } from 'vue'

export function useContextMenu() {
  const visible = ref(false)
  const position = ref({ x: 0, y: 0 })
  const contextData = ref(null)

  const open = (e, data = null) => {
    e.preventDefault()
    position.value = { x: e.clientX, y: e.clientY }
    contextData.value = data
    visible.value = true
  }

  const close = () => {
    visible.value = false
    contextData.value = null
  }

  const onClickOutside = (e) => {
    if (visible.value) close()
  }

  onMounted(() => document.addEventListener('click', onClickOutside))
  onUnmounted(() => document.removeEventListener('click', onClickOutside))

  return { visible, position, contextData, open, close }
}

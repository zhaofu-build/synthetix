import { ref, onMounted, onBeforeUnmount } from 'vue'
import { storage } from '@/utils/storage'
import { APP_CONSTANTS } from '@/constants'

const STORAGE_KEY = APP_CONSTANTS.STORAGE_KEYS.PANEL_STATE

const DEFAULT_RATIOS = [35, 65]
const MIN_PANEL_PX = {
  left: 250,
  center: 200,
  right: 200,
}
const HANDLE_WIDTH = 6

export function useResizable(containerRef) {
  const ratios = ref([...DEFAULT_RATIOS])
  const dragging = ref(null)
  const startX = ref(0)
  const startRatios = ref([])

  const containerWidth = () => containerRef.value?.offsetWidth || 0

  function pxToFr(px) {
    const w = containerWidth()
    return w > 0 ? (px / w) * 100 : 0
  }

  function onMouseDown(e, handle) {
    e.preventDefault()
    dragging.value = handle
    startX.value = e.clientX
    startRatios.value = [...ratios.value]
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  function onMouseMove(e) {
    if (!dragging.value) return
    const dx = e.clientX - startX.value
    const dFr = pxToFr(dx)

    if (dragging.value === 'right') {
      const newRight = Math.max(pxToFr(MIN_PANEL_PX.right), startRatios.value[1] - dFr)
      const newCenter = startRatios.value[0] - (newRight - startRatios.value[1])
      if (newCenter >= pxToFr(MIN_PANEL_PX.center)) {
        ratios.value[0] = newCenter
        ratios.value[1] = newRight
      }
    }
  }

  function onMouseUp() {
    if (!dragging.value) return
    dragging.value = null
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    saveRatios()
  }

  function saveRatios() {
    const saved = storage.get(STORAGE_KEY, {})
    saved.panelRatios = [...ratios.value]
    storage.set(STORAGE_KEY, saved)
  }

  function loadRatios() {
    const saved = storage.get(STORAGE_KEY, {})
    if (saved.panelRatios && saved.panelRatios.length === 2) {
      ratios.value = saved.panelRatios
    }
  }

  const gridStyle = (_leftCollapsed, rightCollapsed) => {
    const r = ratios.value
    if (rightCollapsed) {
      return { gridTemplateColumns: '1fr 48px' }
    }
    return {
      gridTemplateColumns: `${r[0]}fr ${HANDLE_WIDTH}px ${r[1]}fr`,
    }
  }

  onMounted(() => {
    loadRatios()
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  })

  return {
    ratios,
    dragging,
    gridStyle,
    onHandleDown: onMouseDown,
    resetRatios() {
      ratios.value = [...DEFAULT_RATIOS]
      saveRatios()
    },
    handleWidth: HANDLE_WIDTH,
  }
}

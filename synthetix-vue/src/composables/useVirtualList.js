import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

/**
 * 虚拟列表 composable — 只渲染可视区域内的 DOM 节点。
 * @param {import('vue').Ref<Array>} items  响应式数据源
 * @param {object} opts
 * @param {number} opts.itemHeight  每行高度（px），默认 40
 * @param {number} opts.buffer      上下缓冲行数，默认 5
 */
export function useVirtualList(items, opts = {}) {
  const itemHeight = opts.itemHeight || 40
  const buffer = opts.buffer || 5

  const containerEl = ref(null)
  const scrollTop = ref(0)
  const containerHeight = ref(400)

  const totalHeight = computed(() => items.value.length * itemHeight)

  const startIndex = computed(() => {
    const raw = Math.floor(scrollTop.value / itemHeight) - buffer
    return Math.max(0, raw)
  })

  const endIndex = computed(() => {
    const visibleCount = Math.ceil(containerHeight.value / itemHeight)
    const raw = startIndex.value + visibleCount + buffer * 2
    return Math.min(items.value.length, raw)
  })

  const visibleItems = computed(() => {
    const slice = items.value.slice(startIndex.value, endIndex.value)
    return slice.map((item, i) => ({
      data: item,
      index: startIndex.value + i,
      style: { transform: `translateY(${(startIndex.value + i) * itemHeight}px)` },
    }))
  })

  const offsetY = computed(() => startIndex.value * itemHeight)

  let resizeObs = null

  const onScroll = (e) => {
    scrollTop.value = e.target.scrollTop
  }

  onMounted(() => {
    if (containerEl.value) {
      containerHeight.value = containerEl.value.clientHeight
      resizeObs = new ResizeObserver((entries) => {
        for (const entry of entries) {
          containerHeight.value = entry.contentRect.height
        }
      })
      resizeObs.observe(containerEl.value)
    }
  })

  onUnmounted(() => {
    resizeObs?.disconnect()
  })

  const scrollToIndex = (idx) => {
    if (containerEl.value) {
      containerEl.value.scrollTop = idx * itemHeight
    }
  }

  return {
    containerEl,
    totalHeight,
    visibleItems,
    offsetY,
    startIndex,
    endIndex,
    onScroll,
    scrollToIndex,
  }
}

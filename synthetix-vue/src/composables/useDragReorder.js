import { ref } from 'vue'

/**
 * Unified drag-reorder composable for sortable lists.
 * Returns event handlers and reactive drag state.
 */
export function useDragReorder(options = {}) {
  const {
    onReorder,
    itemType = 'item',
  } = options

  const dragIndex = ref(-1)
  const dropIndex = ref(-1)
  const isDragging = ref(false)

  const onDragStart = (e, index) => {
    dragIndex.value = index
    isDragging.value = true
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(index))
    if (e.target) {
      e.target.style.opacity = '0.5'
    }
  }

  const onDragOver = (e, index) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    dropIndex.value = index
  }

  const onDragEnd = (e) => {
    if (e?.target) {
      e.target.style.opacity = '1'
    }
    dragIndex.value = -1
    dropIndex.value = -1
    isDragging.value = false
  }

  const onDrop = (e, targetIndex) => {
    e.preventDefault()
    const from = dragIndex.value
    if (from >= 0 && from !== targetIndex && onReorder) {
      onReorder(from, targetIndex)
    }
    onDragEnd(e)
  }

  const isDragTarget = (index) => dropIndex.value === index && dragIndex.value !== index

  return {
    dragIndex,
    dropIndex,
    isDragging,
    onDragStart,
    onDragOver,
    onDragEnd,
    onDrop,
    isDragTarget,
  }
}

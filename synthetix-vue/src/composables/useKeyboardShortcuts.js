/**
 * 全局键盘快捷键 composable
 *
 * 注册编辑器快捷键：Space(播放/暂停), I/O(入出点), Delete(删除),
 * Ctrl+S(保存), Ctrl+Z/Y(撤销重做), +/- (时间线缩放) 等
 */
import { onMounted, onUnmounted } from 'vue'
import { useProjectStore } from '@/store/modules/project'

export function useKeyboardShortcuts(opts = {}) {
  const store = useProjectStore()
  const handlers = new Map()

  const on = (key, fn) => {
    handlers.set(key.toLowerCase(), fn)
  }

  const handleKeydown = (e) => {
    // Ignore when typing in input/textarea
    const tag = (e.target.tagName || '').toLowerCase()
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) {
      // Only handle Ctrl+S, Ctrl+Z etc. even in inputs
      if (!e.ctrlKey && !e.metaKey) return
    }

    const ctrl = e.ctrlKey || e.metaKey
    const shift = e.shiftKey
    const key = e.key.toLowerCase()

    let combo = ''
    if (ctrl) combo += 'ctrl+'
    if (shift) combo += 'shift+'
    combo += key

    const fn = handlers.get(combo)
    if (fn) {
      e.preventDefault()
      e.stopPropagation()
      fn(e)
    }
  }

  // Register global shortcuts
  on('ctrl+s', () => {
    if (store.isLoaded) {
      store.saveProject()
      opts.onSave?.()
    }
  })

  on('ctrl+z', () => opts.onUndo?.())
  on('ctrl+y', () => opts.onRedo?.())
  on('ctrl+shift+z', () => opts.onRedo?.())

  on('ctrl+n', () => opts.onNewProject?.())
  on('ctrl+o', () => opts.onOpenProject?.())
  on('ctrl+e', () => opts.onExport?.())
  on('ctrl+f', () => opts.onSearch?.())
  on('ctrl+,', () => opts.onSettings?.())

  on('space', () => opts.onPlayPause?.())
  on('arrowleft', () => opts.onStepBack?.())
  on('arrowright', () => opts.onStepForward?.())
  on('shift+arrowleft', () => opts.onJumpBack?.())
  on('shift+arrowright', () => opts.onJumpForward?.())
  on('home', () => opts.onGoStart?.())
  on('end', () => opts.onGoEnd?.())
  on('i', () => opts.onSetIn?.())
  on('o', () => opts.onSetOut?.())
  on('delete', () => opts.onDelete?.())
  on('m', () => opts.onAddMarker?.())
  on('s', () => opts.onSplit?.())
  on('=', () => opts.onZoomIn?.())
  on('-', () => opts.onZoomOut?.())
  on('ctrl+a', () => opts.onSelectAll?.())
  on('escape', () => opts.onCancel?.())

  // Panel shortcuts Ctrl+1-6
  for (let i = 1; i <= 6; i++) {
    on(`ctrl+${i}`, () => opts.onPanel?.(i))
  }

  onMounted(() => document.addEventListener('keydown', handleKeydown))
  onUnmounted(() => document.removeEventListener('keydown', handleKeydown))

  return { on }
}

import { onMounted, onBeforeUnmount } from 'vue'

export function useHotkeys(keyMap) {
  // keyMap: { 'ctrl+s': (e) => {...}, 'ctrl+b': (e) => {...}, ... }

  function normalizeKey(key) {
    return key.toLowerCase().replace(/\s+/g, '')
  }

  function buildMatcher(shortcut) {
    const parts = normalizeKey(shortcut).split('+')
    return (e) => {
      const needCtrl = parts.includes('ctrl') || parts.includes('meta')
      const needShift = parts.includes('shift')
      const needAlt = parts.includes('alt')
      const key = parts.filter(p => !['ctrl', 'meta', 'shift', 'alt'].includes(p))[0]

      if (needCtrl && !e.ctrlKey && !e.metaKey) return false
      if (needShift && !e.shiftKey) return false
      if (needAlt && !e.altKey) return false
      if (key && e.key.toLowerCase() !== key) return false

      // Ensure no extra modifiers that aren't in the shortcut
      if (!needCtrl && (e.ctrlKey || e.metaKey)) return false
      if (!needShift && e.shiftKey) return false
      if (!needAlt && e.altKey) return false

      return true
    }
  }

  const handlers = Object.entries(keyMap).map(([shortcut, handler]) => ({
    match: buildMatcher(shortcut),
    handler,
  }))

  function onKeyDown(e) {
    // Skip if focus is in input/textarea (except for specific combos)
    const tag = e.target.tagName?.toLowerCase()
    const isInput = tag === 'input' || tag === 'textarea' || e.target.isContentEditable

    for (const { match, handler } of handlers) {
      if (match(e)) {
        // Allow Ctrl+S/Ctrl+N even in inputs
        if (isInput && !e.ctrlKey && !e.metaKey) continue
        e.preventDefault()
        handler(e)
        return
      }
    }
  }

  onMounted(() => document.addEventListener('keydown', onKeyDown))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKeyDown))
}

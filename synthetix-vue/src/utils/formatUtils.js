/**
 * Shared formatting utilities used across multiple components.
 *
 * Each function is the most complete implementation found among:
 *   UnifiedEditor.vue, VideoStitching.vue, ProjectList.vue,
 *   ClipPlanPanel.vue, PreviewPanel.vue
 */

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

/**
 * Map project status to a human-readable Chinese label.
 * Covers: draft / ready / processing / completed / error
 */
export function getStatusText(status) {
  const map = {
    draft: '草稿',
    ready: '就绪',
    processing: '处理中',
    completed: '完成',
    error: '错误',
  }
  return map[status] || status || '草稿'
}

/** @deprecated Use getStatusText – kept for backward compatibility with UnifiedEditor */
export const statusText = getStatusText

/**
 * Map project status to an Element Plus el-tag type.
 * Covers: draft / ready / processing / completed / error
 */
export function getStatusType(status) {
  const map = {
    draft: 'info',
    ready: 'warning',
    processing: 'primary',
    completed: 'success',
    error: 'danger',
  }
  return map[status] || 'info'
}

/** @deprecated Use getStatusType – kept for backward compatibility with UnifiedEditor */
export const statusType = getStatusType

// ---------------------------------------------------------------------------
// Time / duration formatting
// ---------------------------------------------------------------------------

/**
 * Format an ISO date string to a short Chinese locale string.
 * e.g. "2025-04-16T14:30:00" -> "04/16 14:30"
 */
export function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Alias used by UnifiedEditor / ProjectList / PreviewPanel.
 * They call formatTime(…) with an ISO date string.
 */
export const formatTime = formatDate

/**
 * Format a duration in seconds to "MM:SS".
 * e.g. 125 -> "02:05"
 */
export function formatDuration(seconds) {
  if (!seconds) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// ---------------------------------------------------------------------------
// Time-code parsing
// ---------------------------------------------------------------------------

/**
 * Parse a time-code string (HH:MM:SS or MM:SS) or number to seconds.
 * e.g. "01:02:03" -> 3723,  "05:30" -> 330
 */
export function parseSeconds(t) {
  if (!t) return 0
  if (typeof t === 'number') return t
  const parts = String(t).split(':').map(Number)
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return Number(t) || 0
}

/** Alias used by PreviewPanel */
export const parseSec = parseSeconds

// ---------------------------------------------------------------------------
// Clip helpers
// ---------------------------------------------------------------------------

const CLIP_COLORS = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#00D1B2']

/**
 * Return a color from the palette for the given index.
 */
export function clipColor(index) {
  return CLIP_COLORS[index % CLIP_COLORS.length]
}

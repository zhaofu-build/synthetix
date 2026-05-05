<template>
  <div class="clip-card" :class="{ selected, hovered }" :style="cardStyle"
       @mouseenter="$emit('hover', index)"
       @mouseleave="$emit('hover', -1)"
       @click="$emit('select', index)">
    <div class="card-color-bar" :style="{ background: color }"></div>
    <div class="card-content">
      <div class="card-header">
        <span class="card-index">{{ index + 1 }}</span>
        <span class="card-purpose">{{ clip.purpose || clip.materialName || '未命名片段' }}</span>
        <el-tag v-if="clip.speakerId" size="small" type="info">{{ clip.speakerName || clip.speakerId }}</el-tag>
      </div>
      <div class="card-meta">
        <span class="card-time">{{ clip.start_time || formatSec(clip.start) }} → {{ clip.end_time || formatSec(clip.end) }}</span>
        <span class="card-duration">{{ duration }}s</span>
      </div>
      <div v-if="clip.tags?.length" class="card-tags">
        <el-tag v-for="tag in clip.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
      </div>
    </div>
    <div class="card-actions">
      <el-button text size="small" @click.stop="$emit('edit', index)" title="编辑"><el-icon><Edit /></el-icon></el-button>
      <el-button text size="small" @click.stop="$emit('delete', index)" title="删除"><el-icon><Delete /></el-icon></el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Edit, Delete } from '@element-plus/icons-vue'
import { clipColor } from '@/utils/formatUtils'

const props = defineProps({
  clip: { type: Object, required: true },
  index: { type: Number, required: true },
  selected: { type: Boolean, default: false },
  hovered: { type: Boolean, default: false },
})

defineEmits(['select', 'hover', 'edit', 'delete'])

const color = computed(() => clipColor(props.index))

const duration = computed(() => {
  const start = parseSecVal(props.clip.start_time || props.clip.start)
  const end = parseSecVal(props.clip.end_time || props.clip.end)
  return Math.round((end - start) * 10) / 10
})

const cardStyle = computed(() => ({
  borderLeftColor: color.value,
}))

function formatSec(val) {
  if (typeof val === 'number') {
    const m = Math.floor(val / 60)
    const s = Math.floor(val % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }
  return val || '0:00'
}

function parseSecVal(val) {
  if (typeof val === 'number') return val
  if (!val) return 0
  const parts = String(val).split(':')
  if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2])
  if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1])
  return parseFloat(val) || 0
}
</script>

<style scoped>
.clip-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-extra-light);
  border-left: 3px solid;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 4px;
}
.clip-card:hover { background: var(--el-fill-color-lighter); }
.clip-card.selected { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary); }
.card-content { flex: 1; min-width: 0; }
.card-header { display: flex; align-items: center; gap: 6px; }
.card-index {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}
.card-purpose { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.card-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
.card-time { font-family: monospace; }
.card-duration { color: var(--el-text-color-placeholder); }
.card-tags { display: flex; gap: 3px; margin-top: 4px; }
.card-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.clip-card:hover .card-actions { opacity: 1; }
</style>

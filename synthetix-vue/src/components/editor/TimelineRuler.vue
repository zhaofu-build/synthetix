<template>
  <div class="timeline-ruler" ref="rulerRef" @click="onRulerClick" @mousemove="onRulerHover" @mouseleave="hoverTime = null">
    <div v-for="tick in ticks" :key="tick.time" class="ruler-tick" :style="{ left: tick.position + '%' }">
      <div class="tick-line" :class="{ major: tick.isMajor }"></div>
      <span v-if="tick.isMajor" class="tick-label">{{ formatTickTime(tick.time) }}</span>
    </div>
    <!-- 播放头 -->
    <div class="playhead" :style="{ left: playheadPercent + '%' }" @mousedown.stop="onPlayheadDrag">
      <div class="playhead-line"></div>
      <div class="playhead-head"></div>
    </div>
    <!-- 悬浮时间 -->
    <div v-if="hoverTime !== null" class="hover-tooltip" :style="{ left: hoverPercent + '%' }">
      {{ formatTickTime(hoverTime) }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onUnmounted } from 'vue'
import { useTimelineStore } from '@/store/modules/timeline'

const props = defineProps({
  duration: { type: Number, default: 0 },
  zoom: { type: Number, default: 1 },
})

const timelineStore = useTimelineStore()
const rulerRef = ref(null)
const hoverTime = ref(null)

const playheadPercent = computed(() => {
  const d = Math.max(props.duration, 1)
  return (timelineStore.playheadPosition / d) * 100
})

const hoverPercent = computed(() => {
  if (hoverTime.value === null) return 0
  return (hoverTime.value / Math.max(props.duration, 1)) * 100
})

// 计算刻度
const ticks = computed(() => {
  const d = Math.max(props.duration, 60)
  const step = getTickStep(d, props.zoom)
  const result = []
  for (let t = 0; t <= d; t += step) {
    result.push({
      time: t,
      position: (t / d) * 100,
      isMajor: t % (step * 5) === 0 || step >= 30,
    })
  }
  return result
})

function getTickStep(duration, zoom) {
  const pixelsPerSec = zoom
  const targetGap = 80 // 目标刻度间距（像素对应的秒数）
  const rawStep = targetGap / pixelsPerSec
  // 找最近的"好看"步长
  const niceSteps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
  return niceSteps.find(s => s >= rawStep) || 600
}

function formatTickTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}:${s.toString().padStart(2, '0')}` : `${s}s`
}

function onRulerClick(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  timelineStore.setPlayheadPosition(pct * Math.max(props.duration, 1))
}

function onRulerHover(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  hoverTime.value = pct * Math.max(props.duration, 1)
}

let _dragCleanup = null

function onPlayheadDrag(e) {
  const ruler = rulerRef.value
  if (!ruler) return
  const onMove = (ev) => {
    const rect = ruler.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width))
    timelineStore.setPlayheadPosition(pct * Math.max(props.duration, 1))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    _dragCleanup = null
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  _dragCleanup = onUp
}

onUnmounted(() => {
  if (_dragCleanup) _dragCleanup()
})
</script>

<style scoped>
.timeline-ruler {
  position: relative;
  height: 24px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-extra-light);
  cursor: pointer;
  user-select: none;
  overflow: hidden;
}
.ruler-tick {
  position: absolute;
  top: 0;
  height: 100%;
}
.tick-line {
  position: absolute;
  bottom: 0;
  width: 1px;
  background: var(--el-border-color);
  height: 8px;
}
.tick-line.major { height: 14px; background: var(--el-text-color-secondary); }
.tick-label {
  position: absolute;
  top: 1px;
  left: 3px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.playhead {
  position: absolute;
  top: 0;
  height: 100%;
  z-index: 10;
  transform: translateX(-50%);
}
.playhead-head {
  width: 10px;
  height: 10px;
  background: var(--el-color-danger);
  border-radius: 2px;
  margin: 0 auto;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}
.playhead-line {
  width: 2px;
  height: 14px;
  background: var(--el-color-danger);
  margin: 0 auto;
}
.hover-tooltip {
  position: absolute;
  top: -20px;
  transform: translateX(-50%);
  font-size: 10px;
  background: var(--el-bg-color-overlay);
  color: var(--el-color-white);
  padding: 1px 6px;
  border-radius: 3px;
  pointer-events: none;
  white-space: nowrap;
}
</style>

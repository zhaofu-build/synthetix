<template>
  <div class="timeline-track" :class="{ muted: track.muted }" :style="{ height: trackHeight + 'px' }">
    <div class="track-label">
      <el-icon :size="12"><component :is="trackIcon" /></el-icon>
      <span class="track-name">{{ track.name }}</span>
      <el-button text size="small" class="mute-btn" @click="track.muted = !track.muted">
        <el-icon :size="12"><span v-if="track.muted">🔇</span><span v-else>🔊</span></el-icon>
      </el-button>
    </div>
    <div class="track-content" ref="contentRef" @click="onTrackClick" @scroll="onContentScroll">
      <div v-for="clip in visibleClips" :key="clip.id"
           class="timeline-clip"
           :class="{
             selected: selectedClipId === clip.id,
             dragging: dragClipId === clip.id,
             [track.type]: true,
           }"
           :style="dragClipId === clip.id ? dragStyle(clip) : clipStyle(clip)"
           @click.stop="$emit('select-clip', clip.id)"
           @mousedown.stop="onClipDragStart($event, clip)">
        <span class="clip-name">{{ clip.materialName }}</span>
      </div>
      <!-- AI 建议片段（虚线） -->
      <div v-for="clip in visibleSuggestedClips" :key="'sug-' + clip.id"
           class="timeline-clip suggested"
           :style="clipStyle(clip)">
        <span class="clip-name">{{ clip.materialName || clip.description }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { VideoCamera, Headset, Document, Flag } from '@element-plus/icons-vue'
import { useTimelineStore } from '@/store/modules/timeline'

const props = defineProps({
  track: { type: Object, required: true },
  zoom: { type: Number, default: 1 },
  duration: { type: Number, default: 0 },
  suggestedClips: { type: Array, default: () => [] },
})

defineEmits(['select-clip'])

const timelineStore = useTimelineStore()
const contentRef = ref(null)

let trackResizeObs = null
onMounted(() => {
  if (contentRef.value) {
    contentWidth.value = contentRef.value.clientWidth
    trackResizeObs = new ResizeObserver(entries => {
      for (const e of entries) contentWidth.value = e.contentRect.width
    })
    trackResizeObs.observe(contentRef.value)
  }
})
onUnmounted(() => {
  trackResizeObs?.disconnect()
  if (_trackDragCleanup) _trackDragCleanup()
})
const selectedClipId = computed(() => timelineStore.selectedClipId)

const trackHeight = computed(() => {
  const map = { video: 50, audio: 35, subtitle: 30, marker: 25 }
  return map[props.track.type] || 40
})

const trackIcon = computed(() => {
  const map = { video: VideoCamera, audio: Headset, subtitle: Document, marker: Flag }
  return map[props.track.type] || Document
})

const clipStyle = (clip) => {
  const totalWidth = Math.max(props.duration, 60) * props.zoom
  const left = (clip.start / Math.max(props.duration, 1)) * 100
  const width = ((clip.end - clip.start) / Math.max(props.duration, 1)) * 100
  return {
    left: `${left}%`,
    width: `${Math.max(width, 0.5)}%`,
  }
}

const onTrackClick = (e) => {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const time = pct * Math.max(props.duration, 1)
  timelineStore.setPlayheadPosition(time)
}

const onClipDragStart = (e, clip) => {
  timelineStore.selectClip(clip.id)
  // Start drag
  dragClipId.value = clip.id
  dragStartX.value = e.clientX
  dragOrigStart.value = clip.start
  dragOrigEnd.value = clip.end

  const onMouseMove = (ev) => {
    if (!contentRef.value) return
    const rect = contentRef.value.getBoundingClientRect()
    const dx = ev.clientX - dragStartX.value
    const totalWidth = rect.width
    const dt = (dx / totalWidth) * Math.max(props.duration, 1)
    const clipDuration = dragOrigEnd.value - dragOrigStart.value
    let newStart = dragOrigStart.value + dt
    // Snap to 0.5s grid
    if (timelineStore.snapEnabled) {
      newStart = Math.round(newStart * 2) / 2
    }
    newStart = Math.max(0, Math.min(newStart, Math.max(props.duration, 1) - clipDuration))
    dragNewStart.value = newStart
  }

  const onMouseUp = () => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    _trackDragCleanup = null
    if (dragNewStart.value !== null && dragNewStart.value !== dragOrigStart.value) {
      const clipDuration = dragOrigEnd.value - dragOrigStart.value
      const clip = props.track.clips.find(c => c.id === dragClipId.value)
      if (clip) {
        clip.start = dragNewStart.value
        clip.end = dragNewStart.value + clipDuration
      }
    }
    dragClipId.value = null
    dragNewStart.value = null
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  _trackDragCleanup = onMouseUp
}

let _trackDragCleanup = null

const dragClipId = ref(null)
const dragStartX = ref(0)
const dragOrigStart = ref(0)
const dragOrigEnd = ref(0)
const dragNewStart = ref(null)

const dragStyle = (clip) => {
  const start = dragNewStart.value ?? clip.start
  const dur = clip.end - clip.start
  const left = (start / Math.max(props.duration, 1)) * 100
  const width = (dur / Math.max(props.duration, 1)) * 100
  return {
    left: `${left}%`,
    width: `${Math.max(width, 0.5)}%`,
    opacity: '0.7',
    zIndex: 10,
  }
}

// --- 虚拟渲染：超过 50 片段时只渲染可见区域的 ---
const scrollLeft = ref(0)
const contentWidth = ref(800)

const onContentScroll = (e) => {
  scrollLeft.value = e.target.scrollLeft
}

const VIRTUAL_THRESHOLD = 50

const visibleClips = computed(() => {
  const clips = props.track.clips
  if (clips.length <= VIRTUAL_THRESHOLD) return clips

  const totalPx = Math.max(props.duration, 60) * props.zoom
  const viewLeft = scrollLeft.value
  const viewRight = viewLeft + contentWidth.value
  const buffer = totalPx * 0.05 // 5% buffer on each side

  return clips.filter(clip => {
    const leftPct = clip.start / Math.max(props.duration, 1)
    const rightPct = clip.end / Math.max(props.duration, 1)
    const leftPx = leftPct * totalPx
    const rightPx = rightPct * totalPx
    return rightPx >= viewLeft - buffer && leftPx <= viewRight + buffer
  })
})

// Also filter suggested clips the same way
const visibleSuggestedClips = computed(() => {
  const clips = props.suggestedClips
  if (clips.length <= VIRTUAL_THRESHOLD) return clips
  const totalPx = Math.max(props.duration, 60) * props.zoom
  const viewLeft = scrollLeft.value
  const viewRight = viewLeft + contentWidth.value
  const buffer = totalPx * 0.05
  return clips.filter(clip => {
    const leftPx = (clip.start / Math.max(props.duration, 1)) * totalPx
    const rightPx = (clip.end / Math.max(props.duration, 1)) * totalPx
    return rightPx >= viewLeft - buffer && leftPx <= viewRight + buffer
  })
})
</script>

<style scoped>
.timeline-track {
  display: flex;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  min-height: 25px;
}
.timeline-track.muted { opacity: 0.5; }
.track-label {
  width: 80px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  border-right: 1px solid var(--el-border-color-extra-light);
  background: var(--el-fill-color-lighter);
}
.track-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mute-btn { padding: 0 !important; min-height: auto; }
.track-content {
  flex: 1;
  position: relative;
  min-height: 100%;
}
.timeline-clip {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 6px;
  font-size: 11px;
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.timeline-clip:hover { box-shadow: 0 0 0 1px var(--el-color-primary); }
.timeline-clip.selected { box-shadow: 0 0 0 2px var(--el-color-primary); z-index: 1; }
.timeline-clip.dragging { cursor: grabbing; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
.timeline-clip.video { background: var(--el-color-primary-light-7); border: 1px solid var(--el-color-primary-light-5); }
.timeline-clip.audio { background: var(--el-color-success-light-7); border: 1px solid var(--el-color-success-light-5); }
.timeline-clip.subtitle { background: var(--el-color-warning-light-7); border: 1px solid var(--el-color-warning-light-5); }
.timeline-clip.marker { background: var(--el-color-info-light-7); border: 1px solid var(--el-color-info-light-5); }
.timeline-clip.suggested {
  border: 2px dashed var(--el-color-primary-light-3);
  background: var(--el-color-primary-light-9);
  opacity: 0.7;
}
.clip-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>

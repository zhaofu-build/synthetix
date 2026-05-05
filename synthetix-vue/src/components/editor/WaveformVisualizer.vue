<template>
  <div class="waveform-visualizer" ref="containerRef">
    <canvas ref="canvasRef" :width="canvasWidth" :height="canvasHeight" @click="onCanvasClick" />
    <div v-if="regions.length" class="waveform-regions">
      <div v-for="(r, i) in regions" :key="i" class="region-label"
           :style="{ left: r.startPct + '%', width: (r.endPct - r.startPct) + '%' }">
        {{ r.label }}
      </div>
    </div>
    <div v-if="hoverTime !== null" class="waveform-tooltip" :style="{ left: hoverX + 'px' }">
      {{ formatSec(hoverTime) }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  audioUrl: { type: String, default: '' },
  regions: { type: Array, default: () => [] },
  height: { type: Number, default: 60 },
})

const emit = defineEmits(['seek', 'regionClick'])

const containerRef = ref(null)
const canvasRef = ref(null)
const canvasWidth = ref(400)
const canvasHeight = ref(props.height)
const hoverTime = ref(null)
const hoverX = ref(0)

let audioCtx = null
let audioBuffer = null
let waveData = []
let animFrame = null

const formatSec = (s) => {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

const drawWaveform = (playheadPct = -1) => {
  const canvas = canvasRef.value
  if (!canvas || !waveData.length) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height
  const dpr = window.devicePixelRatio || 1

  ctx.clearRect(0, 0, w, h)

  const barWidth = Math.max(1, w / waveData.length)
  const midY = h / 2

  // Draw silence threshold
  ctx.strokeStyle = 'rgba(144,147,153,0.2)'
  ctx.lineWidth = 1
  ctx.setLineDash([2, 2])
  ctx.beginPath()
  ctx.moveTo(0, midY - 4)
  ctx.lineTo(w, midY - 4)
  ctx.moveTo(0, midY + 4)
  ctx.lineTo(w, midY + 4)
  ctx.stroke()
  ctx.setLineDash([])

  // Draw bars
  for (let i = 0; i < waveData.length; i++) {
    const amp = waveData[i]
    const x = i * barWidth
    const barH = Math.max(1, amp * midY * 0.9)

    if (playheadPct >= 0 && (i / waveData.length) * 100 <= playheadPct) {
      ctx.fillStyle = '#409eff'
    } else {
      const isSilent = amp < 0.02
      ctx.fillStyle = isSilent ? 'rgba(144,147,153,0.3)' : 'rgba(64,158,255,0.5)'
    }
    ctx.fillRect(x, midY - barH, Math.max(1, barWidth - 1), barH * 2)
  }

  // Playhead
  if (playheadPct >= 0) {
    const px = (playheadPct / 100) * w
    ctx.strokeStyle = '#f56c6c'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(px, 0)
    ctx.lineTo(px, h)
    ctx.stroke()
  }
}

const loadAudio = async (url) => {
  if (!url) { waveData = []; drawWaveform(); return }
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const resp = await fetch(url)
    const arrayBuf = await resp.arrayBuffer()
    audioBuffer = await audioCtx.decodeAudioData(arrayBuf)
    const rawData = audioBuffer.getChannelData(0)
    const samples = Math.min(canvasWidth.value, 400)
    const blockSize = Math.floor(rawData.length / samples)
    waveData = []
    for (let i = 0; i < samples; i++) {
      let sum = 0
      for (let j = 0; j < blockSize; j++) {
        sum += Math.abs(rawData[i * blockSize + j])
      }
      waveData.push(sum / blockSize)
    }
    drawWaveform()
  } catch (e) {
    console.warn('Waveform load failed:', e)
  }
}

const onCanvasClick = (e) => {
  const rect = canvasRef.value.getBoundingClientRect()
  const pct = ((e.clientX - rect.left) / rect.width) * 100
  const time = (pct / 100) * (audioBuffer?.duration || 0)
  emit('seek', { pct, time })
}

const updateSize = () => {
  if (containerRef.value) {
    canvasWidth.value = containerRef.value.clientWidth
    const dpr = window.devicePixelRatio || 1
    canvasHeight.value = props.height * dpr
  }
}

watch(() => props.audioUrl, (url) => { loadAudio(url) })

onMounted(() => {
  updateSize()
  window.addEventListener('resize', updateSize)
  if (props.audioUrl) loadAudio(props.audioUrl)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateSize)
  if (animFrame) cancelAnimationFrame(animFrame)
  if (audioCtx) audioCtx.close()
})

defineExpose({ drawWaveform, loadAudio })
</script>

<style scoped>
.waveform-visualizer {
  position: relative;
  cursor: crosshair;
}
.waveform-visualizer canvas {
  width: 100%;
  height: auto;
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
}
.waveform-tooltip {
  position: absolute;
  top: -18px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  background: var(--el-bg-color);
  padding: 0 4px;
  border-radius: 2px;
  transform: translateX(-50%);
  pointer-events: none;
}
.waveform-regions {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}
.region-label {
  position: absolute;
  top: 2px;
  height: 14px;
  font-size: 9px;
  color: #fff;
  background: rgba(103,194,58,0.5);
  border-radius: 2px;
  padding: 0 3px;
  line-height: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>

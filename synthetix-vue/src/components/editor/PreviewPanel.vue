<template>
  <div class="preview-panel">
    <!-- 渲染中 -->
    <div v-if="store.rendering" class="render-overlay">
      <div class="render-card">
        <el-icon class="is-loading render-spin" :size="32"><Loading /></el-icon>
        <div class="render-title">正在渲染</div>
        <div class="render-desc">请稍候，渲染可能需要几分钟...</div>
        <el-progress :percentage="renderProgress" :stroke-width="6" :format="() => renderProgress + '%'" />
      </div>
    </div>

    <!-- 视频列表为空 -->
    <template v-if="!store.rendering">
    <div v-if="!videoList.length" class="empty-state">
      <el-icon size="40"><VideoPlay /></el-icon>
      <p>暂无输出内容</p>
      <el-button type="primary" size="small" :loading="store.rendering" :disabled="!canRender" @click="handleRender">
        <el-icon><VideoCamera /></el-icon> 渲染
      </el-button>
    </div>

    <!-- 视频列表 -->
    <template v-else>
      <!-- 播放器 -->
      <div class="video-container" @dblclick="toggleFullscreen">
        <video ref="playerRef" v-if="currentSrc && currentType === 'video'" :src="currentSrc" controls class="video-player"
               @timeupdate="updatePlayhead" />
        <audio v-else-if="currentSrc && currentType === 'audio'" :src="currentSrc" controls style="width:100%;padding:40px 20px" />
        <img v-else-if="currentSrc && currentType === 'image'" :src="currentSrc" style="width:100%;max-height:100%;object-fit:contain" />
        <div v-else class="video-placeholder">
          <el-icon size="36"><VideoPlay /></el-icon>
          <p>选择内容播放</p>
        </div>
      </div>

      <!-- 多轨时间线 -->
      <div v-if="timelineStore.duration > 0 || (plan && plan.clips && plan.clips.length)" class="multi-track-timeline">
        <div class="timeline-toolbar">
          <el-button-group size="small">
            <el-button @click="timelineStore.zoomIn()" title="放大"><el-icon><ZoomIn /></el-icon></el-button>
            <el-button @click="timelineStore.zoomOut()" title="缩小"><el-icon><ZoomOut /></el-icon></el-button>
          </el-button-group>
          <span class="zoom-label">{{ Math.round(timelineStore.zoom * 100) }}%</span>
          <span class="time-label">{{ formatTime(timelineStore.playheadPosition) }} / {{ formatTime(timelineStore.duration) }}</span>
        </div>
        <TimelineRuler :duration="timelineStore.duration" :zoom="timelineStore.zoom" />
        <div class="timeline-tracks">
          <TimelineTrack v-for="track in timelineStore.tracks" :key="track.id"
                         :track="track"
                         :zoom="timelineStore.zoom"
                         :duration="timelineStore.duration"
                         :suggested-clips="getSuggestedForTrack(track.type)"
                         @select-clip="timelineStore.selectClip" />
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="preview-actions">
        <el-button type="primary" size="small" :loading="store.rendering" :disabled="!canRender"
                   @click="showRenderParams = true" style="flex: 1">
          <el-icon><VideoCamera /></el-icon> 渲染
        </el-button>
        <el-button size="small" @click="handleDownload" :disabled="!currentSrc" style="flex: 1">
          <el-icon><Download /></el-icon> 下载
        </el-button>
        <el-button size="small" @click="toggleFullscreen" :disabled="!currentSrc" title="全屏">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </div>

      <!-- 渲染参数弹窗 -->
      <el-dialog v-model="showRenderParams" title="渲染参数" width="360" append-to-body>
        <el-form label-width="80px" size="small">
          <el-form-item label="分辨率">
            <el-select v-model="renderOpts.resolution">
              <el-option label="1080p (1920x1080)" value="1080p" />
              <el-option label="720p (1280x720)" value="720p" />
              <el-option label="480p (854x480)" value="480p" />
            </el-select>
          </el-form-item>
          <el-form-item label="格式">
            <el-select v-model="renderOpts.format">
              <el-option label="MP4" value="mp4" />
              <el-option label="GIF" value="gif" />
              <el-option label="WebM" value="webm" />
            </el-select>
          </el-form-item>
          <el-form-item label="帧率">
            <el-select v-model="renderOpts.fps">
              <el-option label="30 fps" :value="30" />
              <el-option label="60 fps" :value="60" />
              <el-option label="24 fps" :value="24" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showRenderParams = false">取消</el-button>
          <el-button type="primary" :loading="store.rendering" @click="handleRender">开始渲染</el-button>
        </template>
      </el-dialog>

      <!-- 质量报告 -->
      <QualityReport v-if="qualityReport" :report="qualityReport" style="margin: 0 12px 8px" />

      <!-- 渲染进度时间线 -->
      <CheckpointTimeline v-if="renderStages.length" :stages="renderStages" style="margin: 0 12px 8px" />

      <!-- 视频列表 -->
      <div class="video-list">
        <div class="video-list-header">
          <span>生成记录 ({{ videoList.length }})</span>
          <div class="video-list-header-actions">
            <el-button v-if="videoList.length >= 2" text size="small" @click="showCompare = !showCompare">
              {{ showCompare ? '退出对比' : '对比' }}
            </el-button>
            <el-button text size="small" type="danger" @click="clearAll" v-if="videoList.length > 1">清空</el-button>
          </div>
        </div>

        <!-- 对比视图 -->
        <div v-if="showCompare && videoList.length >= 2" class="compare-view">
          <div class="compare-video">
            <video :src="compareSrc(0)" controls style="width:100%;max-height:25vh" />
            <span class="compare-label">版本 {{ compareIdxs[0] + 1 }}</span>
          </div>
          <div class="compare-video">
            <video :src="compareSrc(1)" controls style="width:100%;max-height:25vh" />
            <span class="compare-label">版本 {{ compareIdxs[1] + 1 }}</span>
          </div>
        </div>
        <div class="video-list-body">
          <div v-for="(v, i) in videoList" :key="i"
               class="video-item" :class="{ active: selectedIndex === i }"
               @click="selectVideo(i)">
            <div class="video-thumb">
              <el-icon v-if="outputType(v) === 'audio'"><Headset /></el-icon>
              <el-icon v-else-if="outputType(v) === 'image'"><Picture /></el-icon>
              <el-icon v-else><VideoPlay /></el-icon>
            </div>
            <div class="video-item-info">
              <span class="video-item-name">{{ videoName(v, i) }}</span>
              <span class="video-item-time">{{ formatTime(v.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { VideoPlay, VideoCamera, Download, Loading, FullScreen, ZoomIn, ZoomOut, Headset, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { useTimelineStore } from '@/store/modules/timeline'
import { useQualityStore } from '@/store/modules/quality'
import { assetUrl } from '@/api/modules'
import { formatTime, parseSec, clipColor } from '@/utils/formatUtils'
import { useHotkeys } from '@/utils/useHotkeys'
import TimelineRuler from './TimelineRuler.vue'
import TimelineTrack from './TimelineTrack.vue'
import QualityReport from './QualityReport.vue'
import CheckpointTimeline from './CheckpointTimeline.vue'

const store = useProjectStore()
const timelineStore = useTimelineStore()
const qualityStore = useQualityStore()
const selectedIndex = ref(0)
const playerRef = ref(null)
const renderProgress = ref(0)
const hoverTime = ref('')
const playheadPct = ref(null)
const showRenderParams = ref(false)
const renderOpts = ref({ resolution: '1080p', format: 'mp4', fps: 30 })
const showCompare = ref(false)
const compareIdxs = ref([0, 1])
let progressTimer = null

const qualityReport = computed(() => {
  return store.projectId ? qualityStore.getReport(store.projectId) : null
})

const renderStages = computed(() => {
  if (!store.rendering && renderProgress.value === 0) return []
  return [
    { name: '准备素材', status: renderProgress.value > 5 ? 'done' : renderProgress.value > 0 ? 'running' : 'pending' },
    { name: '提取片段', status: renderProgress.value > 30 ? 'done' : renderProgress.value > 5 ? 'running' : 'pending' },
    { name: '合并视频', status: renderProgress.value > 70 ? 'done' : renderProgress.value > 30 ? 'running' : 'pending' },
    { name: '混入音频', status: renderProgress.value > 90 ? 'done' : renderProgress.value > 70 ? 'running' : 'pending' },
    { name: '完成', status: renderProgress.value >= 100 ? 'done' : renderProgress.value > 90 ? 'running' : 'pending' },
  ]
})

const compareSrc = (slot) => {
  const idx = compareIdxs.value[slot]
  const path = videoList.value[idx]?.path
  return path ? assetUrl(path) : ''
}

const plan = computed(() => store.project.planData || null)
const videoList = computed(() => store.project.outputVideos || [])
const canRender = computed(() => store.projectId && (plan.value?.clips?.length || store.materials?.length))

// 同步 planData 到时间线 store
watch(plan, (newPlan) => {
  if (newPlan && newPlan.clips && newPlan.clips.length) {
    timelineStore.loadFromPlanData(newPlan)
  }
}, { immediate: true })

// 同步 timeline_data（如果有）
watch(() => store.project.timelineData, (td) => {
  if (td) timelineStore.loadFromTimelineData(td)
}, { immediate: true })

const getSuggestedForTrack = (type) => {
  return timelineStore.suggestedClips.filter(c => c.trackType === type)
}

const currentSrc = computed(() => {
  const list = videoList.value
  if (!list.length) return ''
  const idx = selectedIndex.value >= list.length ? 0 : selectedIndex.value
  const path = list[idx]?.path
  return path ? assetUrl(path) : ''
})

const _AUDIO_EXT = new Set(['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma'])
const _IMAGE_EXT = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'])

const currentType = computed(() => {
  const list = videoList.value
  if (!list.length) return 'video'
  const idx = selectedIndex.value >= list.length ? 0 : selectedIndex.value
  const path = (list[idx]?.path || '').toLowerCase()
  const ext = path.substring(path.lastIndexOf('.'))
  if (_AUDIO_EXT.has(ext)) return 'audio'
  if (_IMAGE_EXT.has(ext)) return 'image'
  return 'video'
})

const outputType = (v) => {
  const path = (v.path || '').toLowerCase()
  const ext = path.substring(path.lastIndexOf('.'))
  if (_AUDIO_EXT.has(ext)) return 'audio'
  if (_IMAGE_EXT.has(ext)) return 'image'
  return 'video'
}

const videoName = (v, i) => v.name || `输出 ${i + 1}`
const selectVideo = (i) => { selectedIndex.value = i }

const handleRender = async () => {
  showRenderParams.value = false
  renderProgress.value = 0
  progressTimer = setInterval(() => {
    if (renderProgress.value < 90) renderProgress.value += Math.random() * 15
  }, 1000)
  await store.applyAndRender({
    ttsPath: store.project.ttsPath,
    bgmId: store.project.bgmId,
    bgmVolume: (store.project.bgmVolume || 0.3),
  })
  clearInterval(progressTimer)
  renderProgress.value = 100
  selectedIndex.value = Math.max(0, videoList.value.length - 1)
  // 渲染完成通知
  if (Notification.permission === 'granted') {
    new Notification('Synthetix', { body: '渲染完成！' })
  }
}

const handleDownload = () => {
  const path = videoList.value[selectedIndex.value]?.path
  if (path) window.open(assetUrl(path), '_blank')
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm('确定要清除所有输出记录吗？', '提示', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  await store.saveFields({ output_videos: [] })
  store.project.outputVideos = []
  selectedIndex.value = 0
}

const toggleFullscreen = () => {
  if (playerRef.value) {
    if (document.fullscreenElement) document.exitFullscreen()
    else playerRef.value.requestFullscreen?.()
  }
}

const getClipWidth = (clip) => {
  const total = plan.value?.totalDuration || store.project.targetDuration || 30
  const s = parseSec(clip.start_time)
  const e = parseSec(clip.end_time)
  return Math.max(3, ((e - s) / total) * 100)
}

const onTimelineClick = (e) => {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const total = plan.value?.totalDuration || store.project.targetDuration || 30
  const seekTime = pct * total
  if (playerRef.value) {
    playerRef.value.currentTime = seekTime
    playheadPct.value = pct * 100
  }
}

const onTimelineHover = (e) => {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  const total = plan.value?.totalDuration || store.project.targetDuration || 30
  const t = Math.round(pct * total)
  const m = Math.floor(t / 60)
  const s = t % 60
  hoverTime.value = `${m}:${String(s).padStart(2, '0')}`
}

// Update playhead on video timeupdate
const updatePlayhead = () => {
  if (!playerRef.value) return
  const total = timelineStore.duration || plan.value?.totalDuration || store.project.targetDuration || 30
  playheadPct.value = (playerRef.value.currentTime / total) * 100
  timelineStore.setPlayheadPosition(playerRef.value.currentTime)
}

const color = clipColor

// 请求通知权限
if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
  Notification.requestPermission()
}

useHotkeys({
  ' ': (e) => {
    e.preventDefault()
    if (playerRef.value) {
      playerRef.value.paused ? playerRef.value.play() : playerRef.value.pause()
    }
  },
  'arrowleft': () => {
    if (playerRef.value) playerRef.value.currentTime = Math.max(0, playerRef.value.currentTime - 5)
  },
  'arrowright': () => {
    if (playerRef.value) playerRef.value.currentTime += 5
  },
})
</script>

<style scoped>
.preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--el-bg-color);
}

/* 渲染覆盖 */
.render-overlay {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.render-card {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  max-width: 280px;
}
.render-spin { color: var(--el-color-primary); }
.render-title { font-size: 16px; font-weight: 600; }
.render-desc { font-size: 12px; color: var(--el-text-color-secondary); }
.render-card :deep(.el-progress) { width: 100%; }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--el-text-color-secondary);
  animation: breathe 3s ease-in-out infinite;
}
.empty-state p { margin: 0; font-size: 13px; }
@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.02); }
}

.video-container {
  flex-shrink: 0;
  background: #000;
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.video-player { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder { text-align: center; color: #666; }
.video-placeholder p { margin-top: 6px; font-size: 13px; }

/* 多轨时间线 */
.multi-track-timeline {
  flex-shrink: 0;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}
.timeline-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.zoom-label, .time-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}
.timeline-tracks {
  overflow-x: auto;
  overflow-y: hidden;
}

.timeline-strip {
  flex-shrink: 0;
  display: flex;
  height: 14px;
  gap: 1px;
  padding: 3px 8px;
  background: var(--el-fill-color-lighter);
  position: relative;
  cursor: pointer;
}
.strip-clip { border-radius: 2px; min-width: 8px; }
.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #fff;
  box-shadow: 0 0 4px rgba(0,0,0,0.5);
  z-index: 2;
  pointer-events: none;
}
.timeline-tooltip {
  position: absolute;
  top: -24px;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.75);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  pointer-events: none;
  z-index: 3;
  white-space: nowrap;
}

.preview-actions { flex-shrink: 0; display: flex; gap: 8px; padding: 8px 12px; }

.video-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-top: 1px solid var(--el-border-color-lighter);
}
.video-list-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
.video-list-header-actions { display: flex; gap: 4px; }

/* 对比视图 */
.compare-view {
  display: flex;
  gap: 4px;
  padding: 0 8px 8px;
}
.compare-video {
  flex: 1;
  position: relative;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}
.compare-label {
  position: absolute;
  top: 4px;
  left: 4px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 2px;
}
.video-list-body { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.video-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.15s;
}
.video-item:hover { background: var(--el-fill-color-light); }
.video-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }

.video-thumb {
  width: 40px;
  height: 24px;
  background: var(--el-fill-color-lighter);
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.video-item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.video-item-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.video-item-time { font-size: 11px; color: var(--el-text-color-placeholder); }
</style>

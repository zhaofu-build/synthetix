<template>
  <div class="temp-asset-card" :class="{ saved: isSaved }">
    <!-- 内联媒体预览 -->
    <div v-if="outputType === 'image' && fullUrl" class="asset-preview" @click="$emit('preview', fullUrl, outputType)">
      <img :src="fullUrl" class="preview-image" />
      <div class="preview-overlay"><el-icon :size="18"><ZoomIn /></el-icon></div>
    </div>
    <div v-else-if="outputType === 'video' && fullUrl" class="asset-preview" @click="$emit('preview', fullUrl, outputType)">
      <video :src="fullUrl" class="preview-video-thumb" muted />
      <div class="preview-overlay"><el-icon :size="18"><ZoomIn /></el-icon></div>
    </div>
    <audio v-else-if="outputType === 'audio' && fullUrl" :src="fullUrl" class="preview-audio" controls />
    <div v-else class="asset-icon">
      <el-icon :size="22">
        <Document />
      </el-icon>
    </div>
    <!-- 文件信息 + 操作 -->
    <div class="asset-info">
      <span class="asset-name" :title="fileName">{{ fileName }}</span>
      <span v-if="mediaInfo.duration" class="asset-duration">{{ formatDuration(mediaInfo.duration) }}</span>
    </div>
    <div class="asset-actions">
      <template v-if="hasId && !isSaved">
        <el-button text size="small" :loading="saving" @click="saveToLib">
          <el-icon><FolderAdd /></el-icon> 存入库
        </el-button>
      </template>
      <span v-if="isSaved" class="saved-label">已入库</span>
      <el-button v-if="!isSaved" text size="small" @click="downloadFile">
        <el-icon><Download /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Headset, Document, FolderAdd, Download, ZoomIn } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { assetUrl } from '../../utils/request'
import { videoApi } from '../../api/modules/video'
import { useProjectStore } from '@/store/modules/project'

const props = defineProps({
  mediaInfo: { type: Object, required: true }
})

const emit = defineEmits(['preview', 'refresh'])

const store = useProjectStore()
const saving = ref(false)
const isSaved = ref(false)

const outputType = computed(() => props.mediaInfo.output_type || props.mediaInfo.outputType || 'video')
const fullUrl = computed(() => assetUrl(props.mediaInfo.web_path || props.mediaInfo.webPath))
const videoId = computed(() => props.mediaInfo.video_id || props.mediaInfo.videoId)
const tempFileId = computed(() => props.mediaInfo.temp_file_id || props.mediaInfo.tempFileId)
const hasId = computed(() => tempFileId.value || videoId.value)

const fileName = computed(() => {
  const wp = props.mediaInfo.web_path || props.mediaInfo.webPath || ''
  const parts = wp.split('/')
  return decodeURIComponent(parts[parts.length - 1] || 'output')
})

function formatDuration(sec) {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

async function saveToLib() {
  saving.value = true
  try {
    if (tempFileId.value) {
      await videoApi.saveTempToLibrary(tempFileId.value)
    } else {
      await videoApi.saveToLibrary(videoId.value)
    }
    isSaved.value = true
    ElMessage.success('已存入素材库')
    emit('refresh')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function downloadFile() {
  const a = document.createElement('a')
  a.href = fullUrl.value
  a.download = fileName.value
  a.target = '_blank'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>

<style scoped>
.temp-asset-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  margin-top: 6px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 6px;
  font-size: 12px;
}
.temp-asset-card.saved {
  opacity: 0.6;
  background: var(--el-fill-color-light);
  border-color: var(--el-border-color-lighter);
}

/* 内联媒体预览 */
.asset-preview {
  position: relative;
  flex-shrink: 0;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
}
.preview-image {
  width: 120px;
  height: 80px;
  object-fit: cover;
  display: block;
  border-radius: 4px;
}
.preview-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.3);
  opacity: 0;
  transition: opacity 0.2s;
  color: #fff;
}
.asset-preview:hover .preview-overlay {
  opacity: 1;
}
.preview-video-thumb {
  width: 120px;
  height: 80px;
  object-fit: cover;
  display: block;
  border-radius: 4px;
}
.preview-audio {
  height: 36px;
  flex-shrink: 0;
}

.asset-icon { flex-shrink: 0; color: var(--el-color-primary); }
.asset-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.asset-name { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-duration { font-size: 11px; color: var(--el-text-color-secondary); font-family: monospace; }
.asset-actions { display: flex; gap: 2px; flex-shrink: 0; align-items: center; }
.saved-label { font-size: 11px; color: var(--el-color-success); }
</style>

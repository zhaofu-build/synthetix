<template>
  <div class="publish-panel">
    <div class="publish-header">
      <span class="title">多平台发布</span>
      <el-button size="small" type="primary" @click="startExport" :loading="exporting"
                 :disabled="!store.isLoaded || !store.materials.length">
        导出适配
      </el-button>
    </div>

    <!-- 平台选择 -->
    <div class="platform-grid">
      <div v-for="(preset, key) in platforms" :key="key"
           class="platform-card" :class="{ active: selectedPlatform === key }"
           @click="selectedPlatform = key">
        <div class="platform-name">{{ preset.name }}</div>
        <div class="platform-meta">{{ preset.aspect }} · {{ preset.width }}×{{ preset.height }}</div>
        <div class="platform-tip">{{ preset.tips }}</div>
      </div>
    </div>

    <!-- 选中平台详情 -->
    <div v-if="currentPreset" class="preset-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="分辨率">{{ currentPreset.width }}×{{ currentPreset.height }}</el-descriptions-item>
        <el-descriptions-item label="宽高比">{{ currentPreset.aspect }}</el-descriptions-item>
        <el-descriptions-item label="最大时长">{{ formatDuration(currentPreset.max_duration) }}</el-descriptions-item>
        <el-descriptions-item label="编码">{{ currentPreset.codec }} / {{ currentPreset.bitrate }}</el-descriptions-item>
        <el-descriptions-item label="帧率">{{ currentPreset.fps }} fps</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 导出历史 -->
    <div v-if="exportHistory.length" class="export-history">
      <div class="history-title">导出记录</div>
      <div v-for="item in exportHistory" :key="item.id" class="history-item">
        <span class="history-platform">{{ item.platform }}</span>
        <el-tag :type="item.status === 'done' ? 'success' : item.status === 'failed' ? 'danger' : 'warning'" size="small">
          {{ item.status === 'done' ? '完成' : item.status === 'failed' ? '失败' : '处理中' }}
        </el-tag>
        <span class="history-time">{{ item.time }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { publishApi, projectApi } from '@/api/modules'

const store = useProjectStore()
const publishStore = usePublishStore()
const selectedPlatform = ref('douyin')
const exporting = ref(false)
const exportHistory = ref([])
const platforms = ref({})

const currentPreset = computed(() => platforms.value[selectedPlatform.value])

const formatDuration = (sec) => {
  if (sec >= 3600) return `${Math.floor(sec / 3600)}小时${Math.floor((sec % 3600) / 60)}分`
  if (sec >= 60) return `${Math.floor(sec / 60)}分${sec % 60}秒`
  return `${sec}秒`
}

const fetchPresets = async () => {
  try {
    const data = await publishApi.getPlatforms()
    if (data) platforms.value = data
  } catch (e) {
    console.error('获取平台预设失败:', e)
  }
}

const startExport = async () => {
  if (!store.projectId || !selectedPlatform.value) return
  exporting.value = true
  try {
    const preset = currentPreset.value
    await projectApi.render(store.projectId, {
      platform: selectedPlatform.value,
      width: preset.width,
      height: preset.height,
      bitrate: preset.bitrate,
      fps: preset.fps,
      codec: preset.codec,
    })
    ElMessage.success('导出任务已提交')
    exportHistory.value.unshift({
      id: Date.now(),
      platform: preset.name,
      status: 'processing',
      time: new Date().toLocaleTimeString(),
    })
  } catch (e) {
    ElMessage.error('导出请求失败')
  } finally {
    exporting.value = false
  }
}

onMounted(fetchPresets)
</script>

<style scoped>
.publish-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  overflow-y: auto;
  padding: 8px;
}
.publish-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.publish-header .title { font-size: 14px; font-weight: 600; }
.platform-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}
.platform-card {
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.platform-card:hover { border-color: var(--el-color-primary-light-5); }
.platform-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.platform-name { font-size: 13px; font-weight: 600; }
.platform-meta { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }
.platform-tip { font-size: 10px; color: var(--el-text-color-placeholder); margin-top: 4px; }
.preset-detail { margin-top: 4px; }
.export-history { margin-top: 8px; }
.history-title { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.history-platform { flex: 1; }
.history-time { color: var(--el-text-color-placeholder); font-size: 11px; }
</style>

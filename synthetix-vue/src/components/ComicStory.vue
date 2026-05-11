<template>
  <div class="comic-story">
    <div class="story-scroll">
      <!-- 风格设置行 -->
      <div class="settings-row">
        <div class="setting-item">
          <span class="setting-label">风格</span>
          <el-select v-model="localStyle" size="default" @change="onFieldChange('style', $event)">
            <el-option v-for="s in styleOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </div>
      </div>

      <!-- 故事描述 -->
      <div class="story-input-section">
        <div class="section-label">故事描述</div>
        <el-input
          v-model="localDescription"
          type="textarea"
          :rows="6"
          placeholder="描述你的漫剧故事..."
          resize="vertical"
          @input="onDescriptionInput"
        />
      </div>

      <!-- 尺寸控制 -->
      <div class="size-controls">
        <el-radio-group v-model="sizeMode" size="default">
          <el-radio-button value="duration">按时长</el-radio-button>
          <el-radio-button value="panels">按分镜数</el-radio-button>
        </el-radio-group>
        <el-input-number
          v-model="sizeValue"
          size="default"
          :min="sizeMode === 'duration' ? 10 : 4"
          :max="sizeMode === 'duration' ? 300 : 60"
          :step="sizeMode === 'duration' ? 10 : 1"
          controls-position="right"
        />
        <span class="size-unit">{{ sizeMode === 'duration' ? '秒' : '个分镜' }}</span>
      </div>

      <!-- 生成按钮 -->
      <el-button
        type="primary"
        size="large"
        class="generate-btn"
        :loading="generating"
        :disabled="!localDescription.trim()"
        @click="generateScript"
      >
        {{ generating ? '正在生成脚本...' : 'AI 生成脚本' }}
      </el-button>

      <!-- 脚本概览 -->
      <div v-if="scriptData" class="script-overview">
        <div class="overview-header">
          <h4 class="overview-title">{{ scriptData.title || '脚本概览' }}</h4>
        </div>
        <p class="synopsis-text">{{ scriptData.synopsis }}</p>

        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-value">{{ panels.length || scriptData.panelCount || 0 }}</span>
            <span class="stat-label">分镜</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ characters.length || scriptData.characterCount || 0 }}</span>
            <span class="stat-label">角色</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatDuration(scriptData.totalDuration) }}</span>
            <span class="stat-label">总时长</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { comicDramaApi } from '@/api/modules'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  project: { type: Object, required: true },
  characters: { type: Array, default: () => [] },
  panels: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:project', 'script-generated'])

// ==================== Options ====================
const styleOptions = [
  { label: '动漫', value: '动漫' },
  { label: '写实', value: '写实' },
  { label: '水墨', value: '水墨' },
  { label: '像素', value: '像素' },
  { label: '美漫', value: '美漫' },
  { label: '水彩', value: '水彩' },
  { label: '赛博朋克', value: '赛博朋克' },
  { label: '古风', value: '古风' },
  { label: '暗黑哥特', value: '暗黑哥特' },
  { label: '日系清新', value: '日系清新' },
]

// ==================== Local state ====================
const generating = ref(false)

const localStyle = ref(props.project.style || '动漫')
const localDescription = ref(props.project.scriptData?.description || props.project.description || '')
const sizeMode = ref('panels')
const sizeValue = ref(12)

// Derive scriptData from project prop
const scriptData = computed(() => props.project.scriptData || null)

// ==================== Debounce timers ====================
const _timers = {}
onUnmounted(() => {
  Object.values(_timers).forEach(t => clearTimeout(t))
})

function debounceSave(field, value, delay = 300) {
  if (!props.projectId) return
  if (_timers[field]) clearTimeout(_timers[field])
  _timers[field] = setTimeout(async () => {
    try {
      await comicDramaApi.update(props.projectId, { [field]: value })
    } catch { /* silent */ }
  }, delay)
}

// ==================== Watchers ====================
watch(() => props.project.style, (val) => { if (val) localStyle.value = val })
watch(() => props.project.scriptData?.description, (val) => {
  if (val && !localDescription.value) localDescription.value = val
})
watch(() => props.project.description, (val) => {
  if (val && !localDescription.value) localDescription.value = val
})

// ==================== Handlers ====================
function onFieldChange(field, value) {
  emit('update:project', { [field]: value })
  debounceSave(field, value)
}

let _descTimer = null
function onDescriptionInput() {
  if (_descTimer) clearTimeout(_descTimer)
  _descTimer = setTimeout(() => {
    debounceSave('description', localDescription.value)
  }, 300)
}

async function generateScript() {
  if (!localDescription.value.trim()) {
    ElMessage.warning('请先输入故事描述')
    return
  }
  generating.value = true
  try {
    const payload = {
      description: localDescription.value,
      style: localStyle.value,
      characters: props.characters,
    }
    if (sizeMode.value === 'duration') {
      payload.target_duration = sizeValue.value
    } else {
      payload.num_panels = sizeValue.value
    }
    const res = await comicDramaApi.generateScript(props.projectId, payload)
    emit('script-generated', res)
    const charCount = res.characters?.length || 0
    const panelCount = res.panels?.length || 0
    ElMessage.success({
      message: `脚本生成成功！已生成 ${charCount} 个角色描述、${panelCount} 个分镜描述，请在各页面查看并生成/上传图片`,
      duration: 5000,
    })
  } catch (e) {
    ElMessage.error(e?.message || '脚本生成失败')
  } finally {
    generating.value = false
  }
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}
</script>

<style scoped>
.comic-story {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.story-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Header / name */
.story-header {
  flex-shrink: 0;
}
.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.name-icon {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  flex-shrink: 0;
}
.name-icon:hover {
  color: var(--el-color-primary);
}
.project-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  line-height: 1.4;
}
.name-input {
  flex: 1;
}

/* Settings row */
.settings-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.setting-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.setting-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.setting-item .el-select {
  width: 120px;
}

/* Story input */
.story-input-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.section-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

/* Size controls */
.size-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  min-width: 0;
}
.size-unit {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* Generate button */
.generate-btn {
  width: 100%;
  font-size: 15px;
  height: 42px;
}

/* Script overview */
.script-overview {
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.overview-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.synopsis-text {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.stats-row {
  display: flex;
  gap: 24px;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>

<template>
  <div class="vl-page">
    <!-- 上半区：输入 -->
    <div class="vl-input">
      <div class="upload-zone">
        <el-upload
          :auto-upload="false"
          :on-change="handleFileChange"
          :show-file-list="false"
          accept="image/*,video/*"
          drag
          class="upload-dragger"
        >
          <div v-if="!previewUrl" class="upload-empty">
            <el-icon class="upload-icon"><upload-filled /></el-icon>
            <p class="upload-title">拖拽图片/视频到此处，或点击上传</p>
            <p class="upload-hint">支持 JPG、PNG、GIF、MP4、WebM</p>
          </div>
          <div v-else class="preview-wrap">
            <img v-if="fileType === 'image'" :src="previewUrl" alt="preview" class="preview-img" />
            <video v-else :src="previewUrl" class="preview-video" controls></video>
            <div class="preview-mask">
              <el-icon :size="20"><refresh /></el-icon>
              <span>重新上传</span>
            </div>
          </div>
        </el-upload>
      </div>

      <div class="prompt-zone">
        <div class="mode-selector">
          <el-tag v-for="m in analysisModes" :key="m.value" size="small"
                  :type="selectedMode === m.value ? '' : 'info'"
                  :effect="selectedMode === m.value ? 'dark' : 'plain'"
                  @click="selectedMode = m.value; prompt = m.defaultPrompt" class="mode-tag">
            {{ m.label }}
          </el-tag>
        </div>
        <el-input
          v-model="prompt"
          type="textarea"
          :rows="4"
          resize="none"
          placeholder="描述你想了解的内容..."
          class="prompt-input"
        />
        <div class="quick-prompts">
          <el-tag
            v-for="q in quickPrompts"
            :key="q"
            size="small"
            effect="plain"
            class="quick-tag"
            @click="prompt = q"
          >{{ q }}</el-tag>
        </div>
        <el-button
          type="primary"
          class="analyze-btn"
          :loading="loading"
          :disabled="!fileBase64 || !prompt.trim()"
          @click="analyze"
        >{{ loading ? '分析中...' : '开始分析' }}</el-button>
      </div>
    </div>

    <!-- 分析历史 -->
    <div v-if="history.length" class="vl-history">
      <div class="history-header">
        <span class="history-title">分析历史 ({{ history.length }})</span>
        <el-button text size="small" type="danger" @click="history = []">清空</el-button>
      </div>
      <div class="history-list">
        <div v-for="(h, i) in history" :key="i" class="history-item" @click="loadHistory(h)">
          <span class="history-mode">{{ h.mode }}</span>
          <span class="history-prompt">{{ h.prompt.slice(0, 40) }}{{ h.prompt.length > 40 ? '...' : '' }}</span>
          <span class="history-time">{{ h.time }}</span>
        </div>
      </div>
    </div>

    <!-- 下半区：结果 -->
    <div v-if="result || loading" class="vl-result">
      <div class="result-header">
        <span class="result-title">分析结果</span>
        <div class="result-view-toggle">
          <el-radio-group v-model="resultView" size="small">
            <el-radio-button value="formatted">格式化</el-radio-button>
            <el-radio-button value="raw">原始</el-radio-button>
          </el-radio-group>
          <el-button v-if="result" type="primary" size="small" text @click="copyResult">
            <el-icon><document-copy /></el-icon> 复制
          </el-button>
        </div>
      </div>
      <div class="result-body">
        <template v-if="loading">
          <div class="loading-state">
            <el-icon class="loading-icon" :size="28"><loading /></el-icon>
            <span>正在分析，请稍候...</span>
          </div>
        </template>
        <template v-else-if="resultView === 'formatted'">
          <div class="result-text" v-html="formatResult(result)"></div>
        </template>
        <template v-else>
          <pre class="result-raw">{{ result }}</pre>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Refresh, DocumentCopy, Loading } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/sanitize'
import { aiApi } from '@/api/modules'

const prompt = ref('')
const loading = ref(false)
const fileBase64 = ref('')
const previewUrl = ref('')
const fileType = ref('image')
const result = ref('')
const resultView = ref('formatted')

const selectedMode = ref('general')
const analysisModes = [
  { label: '通用', value: 'general', defaultPrompt: '请详细描述这张图片/视频的内容' },
  { label: 'OCR', value: 'ocr', defaultPrompt: '提取图片中的所有文字，保持原始格式' },
  { label: '场景分析', value: 'scene', defaultPrompt: '分析视频中的场景变化，列出每个场景的时间戳和描述' },
  { label: '物体检测', value: 'object', defaultPrompt: '列出图片/视频中包含的所有物体及其位置' },
]

const quickPrompts = [
  '请描述这张图片的内容',
  '提取图片中的文字',
  '分析视频中的场景变化',
  '这张图片包含哪些物体？',
]

const handleFileChange = (file) => {
  const raw = file.raw
  const type = raw.type || ''

  if (type.startsWith('video/')) {
    fileType.value = 'video'
  } else {
    fileType.value = 'image'
  }

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = URL.createObjectURL(raw)

  const reader = new FileReader()
  reader.onload = (e) => {
    fileBase64.value = e.target.result
  }
  reader.readAsDataURL(raw)
}

const analyze = async () => {
  if (!fileBase64.value) {
    ElMessage.warning('请先上传图片或视频')
    return
  }
  if (!prompt.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  result.value = ''

  try {
    const payload = {
      prompt: prompt.value,
      generation: { temperature: 0.7, max_tokens: 2048 },
    }
    if (fileType.value === 'video') {
      payload.video = fileBase64.value
    } else {
      payload.image = fileBase64.value
    }

    const data = await aiApi.vl(payload)
    result.value = data?.text || ''
    ElMessage.success('分析完成')
    // Save to history
    const mode = analysisModes.find(m => m.value === selectedMode.value)
    history.value.unshift({
      mode: mode?.label || '通用',
      prompt: prompt.value,
      result: result.value,
      time: new Date().toLocaleTimeString(),
    })
    if (history.value.length > 20) history.value.length = 20
  } catch (error) {
    console.error('VL 分析失败:', error)
    ElMessage.error(`分析失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

const copyResult = () => {
  if (result.value) {
    navigator.clipboard.writeText(result.value)
    ElMessage.success('已复制到剪贴板')
  }
}

const history = ref([])

const loadHistory = (h) => {
  result.value = h.result
  resultView.value = 'formatted'
}

const formatResult = (text) => {
  if (!text) return ''
  return renderMarkdown(text)
}
</script>

<style scoped>
.vl-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 400px;
}

/* 输入区 */
.vl-input {
  display: flex;
  gap: 16px;
}

.upload-zone {
  flex-shrink: 0;
  width: 320px;
}

.upload-dragger :deep(.el-upload-dragger) {
  width: 100%;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  padding: 0;
  transition: border-color .2s;
}

.upload-empty {
  text-align: center;
  color: var(--el-text-color-secondary);
}

.upload-icon {
  font-size: 36px;
  margin-bottom: 8px;
  color: var(--el-color-primary);
}

.upload-title {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin: 4px 0;
}

.upload-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.preview-wrap {
  position: relative;
  width: 100%;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-img,
.preview-video {
  max-width: 100%;
  max-height: 210px;
  object-fit: contain;
  border-radius: 6px;
}

.preview-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #fff;
  font-size: 13px;
  opacity: 0;
  transition: opacity .2s;
}

.preview-wrap:hover .preview-mask {
  opacity: 1;
}

/* 提问区 */
.prompt-zone {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.prompt-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-tag {
  cursor: pointer;
  transition: color .15s;
}

.quick-tag:hover {
  color: var(--el-color-primary);
}

.analyze-btn {
  align-self: flex-end;
  min-width: 120px;
}

/* 结果区 */
.vl-result {
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  overflow: hidden;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.result-title {
  font-weight: 600;
  font-size: 14px;
}

.result-body {
  padding: 16px;
  max-height: 320px;
  overflow-y: auto;
}

.result-text {
  font-size: 14px;
  line-height: 1.8;
}
.mode-selector { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
.mode-tag { cursor: pointer; }
.result-view-toggle { display: flex; gap: 8px; align-items: center; }
.result-raw { font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; background: var(--el-fill-color-lighter); padding: 12px; border-radius: 6px; }
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--el-text-color-secondary);
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .vl-input {
    flex-direction: column;
  }
  .upload-zone {
    width: 100%;
  }
}

.vl-history {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-extra-light);
  font-size: 13px;
  font-weight: 600;
}
.history-list {
  max-height: 150px;
  overflow-y: auto;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  transition: background 0.15s;
}
.history-item:hover { background: var(--el-fill-color-light); }
.history-item:last-child { border-bottom: none; }
.history-mode {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}
.history-prompt {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-regular);
}
.history-time {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
  flex-shrink: 0;
}
</style>

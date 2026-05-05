<template>
  <div class="tts-page">
    <div class="tts-input">
      <!-- 文本区 -->
      <div class="text-zone">
        <el-input
          v-model="text"
          type="textarea"
          :rows="8"
          resize="none"
          placeholder="请输入要合成的文本..."
          class="text-input"
        />
        <div class="text-footer">
          <span class="char-count">{{ text.length }} 字</span>
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!text.trim()"
            @click="generate"
          >{{ loading ? '合成中...' : '开始合成' }}</el-button>
        </div>
      </div>

      <!-- 参数区 -->
      <div class="params-zone">
        <div class="param-group">
          <label class="param-label">音色</label>
          <el-select v-model="selectedVoice" placeholder="选择音色" clearable class="full-width">
            <el-option v-for="v in voiceList" :key="v.id"
              :label="(v.audioName || v.audio_name) + (v.isDefault ? ' ★' : '')"
              :value="v.id" />
          </el-select>
        </div>

        <div class="param-group">
          <label class="param-label">语速 <span class="param-value">{{ speed.toFixed(1) }}x</span></label>
          <el-slider v-model="speed" :min="0.5" :max="2.0" :step="0.1" :show-tooltip="false" />
        </div>

        <div class="param-group">
          <label class="param-label">情感风格</label>
          <div class="emotion-tags">
            <el-tag v-for="e in emotions" :key="e.value" size="small"
                    :type="emotion === e.value ? '' : 'info'"
                    :effect="emotion === e.value ? 'dark' : 'plain'"
                    @click="emotion = e.value" class="emotion-tag">{{ e.label }}</el-tag>
          </div>
        </div>

        <div class="param-group">
          <label class="param-label">批量模式</label>
          <el-switch v-model="batchMode" />
          <span v-if="batchMode" class="param-hint">按段落分割，逐段合成</span>
        </div>
      </div>
    </div>

    <!-- 播放区 -->
    <div v-if="audioUrl || batchResults.length || loading" class="tts-result">
      <div class="result-header">
        <span class="result-title">{{ batchMode ? `批量结果 (${batchResults.length})` : '合成结果' }}</span>
        <div class="result-actions">
          <el-button v-if="audioUrl && !batchMode" type="primary" size="small" text @click="downloadAudio">
            <el-icon><Download /></el-icon> 下载
          </el-button>
          <el-button v-if="batchResults.length > 1" type="primary" size="small" text @click="mergeAndDownload">
            合并下载
          </el-button>
        </div>
      </div>
      <div class="result-body">
        <template v-if="loading">
          <div class="loading-state">
            <el-icon class="loading-icon" :size="24"><Loading /></el-icon>
            <span>{{ batchMode ? `批量合成中 ${batchProgress}/${batchTotal}...` : '正在合成语音，请稍候...' }}</span>
          </div>
        </template>
        <template v-else-if="batchMode && batchResults.length">
          <div v-for="(r, i) in batchResults" :key="i" class="batch-item">
            <span class="batch-label">段落 {{ i + 1 }}</span>
            <audio :src="r.url" controls class="audio-player-small" />
          </div>
        </template>
        <template v-else-if="audioUrl">
          <audio :src="audioUrl" controls class="audio-player"></audio>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Loading } from '@element-plus/icons-vue'
import { API_HOST } from '@/api/modules'
import { useProjectStore } from '@/store/modules/project'

const store = useProjectStore()
const voiceList = computed(() => store.voiceList)

const text = ref('')
const selectedVoice = ref(null)
const loading = ref(false)
const audioUrl = ref('')
const speed = ref(1.0)
const emotion = ref('default')
const batchMode = ref(false)
const batchResults = ref([])
const batchProgress = ref(0)
const batchTotal = ref(0)

const emotions = [
  { label: '默认', value: 'default' },
  { label: '欢快', value: 'cheerful' },
  { label: '温柔', value: 'gentle' },
  { label: '严肃', value: 'serious' },
  { label: '激昂', value: 'upbeat' },
]

// 自动选中默认音色
watch(voiceList, (list) => {
  if (selectedVoice.value) return
  const def = list.find(v => v.isDefault)
  if (def) selectedVoice.value = def.id
}, { immediate: true })

onMounted(() => {
  store.refreshVoiceList()
})

const generate = async () => {
  if (!text.value.trim()) {
    ElMessage.warning('请输入要合成的文本')
    return
  }

  loading.value = true
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = ''
  }
  batchResults.value = []

  const doGenerate = async (segment) => {
    const payload = {
      text: segment,
      audio_source_id: selectedVoice.value || -1,
      speed_factor: speed.value,
    }
    const response = await fetch(`${API_HOST}/api/audios/tts/fish-speech`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.message || `HTTP ${response.status}`)
    }
    const json = await response.json()
    const webPath = json?.data?.web_path
    if (webPath) return `${API_HOST}/${webPath}`
    throw new Error('未返回音频')
  }

  try {
    if (batchMode.value) {
      const segments = text.value.split(/\n+/).filter(s => s.trim())
      batchTotal.value = segments.length
      batchProgress.value = 0
      for (const seg of segments) {
        const url = await doGenerate(seg)
        batchResults.value.push({ text: seg, url })
        batchProgress.value++
      }
      ElMessage.success(`批量合成完成，共 ${batchResults.value.length} 段`)
    } else {
      audioUrl.value = await doGenerate(text.value)
      ElMessage.success('语音合成完成')
    }
  } catch (error) {
    console.error('TTS 生成失败:', error)
    ElMessage.error(`合成失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

const mergeAndDownload = () => {
  for (let i = 0; i < batchResults.value.length; i++) {
    const a = document.createElement('a')
    a.href = batchResults.value[i].url
    a.download = `tts_part${i + 1}.wav`
    a.click()
  }
}

const downloadAudio = () => {
  if (!audioUrl.value) return
  const a = document.createElement('a')
  a.href = audioUrl.value
  a.download = 'tts_output.wav'
  a.click()
}
</script>

<style scoped>
.tts-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 360px;
}

.tts-input {
  display: flex;
  gap: 20px;
}

.text-zone {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.text-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}

.text-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.char-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.params-zone {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 10px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-value {
  font-weight: 400;
  color: var(--el-color-primary);
  font-family: monospace;
}

.param-hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-left: 8px;
}

.emotion-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.emotion-tag { cursor: pointer; }

.batch-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.batch-item:last-child { border-bottom: none; }

.batch-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  min-width: 50px;
}

.audio-player-small {
  flex: 1;
  height: 32px;
  border-radius: 4px;
}

.full-width {
  width: 100%;
}

/* 结果区 */
.tts-result {
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

.result-actions {
  display: flex;
  gap: 4px;
}

.result-body {
  padding: 20px 16px;
}

.audio-player {
  width: 100%;
  border-radius: 6px;
  outline: none;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 30px 0;
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
  .tts-input {
    flex-direction: column;
  }
  .params-zone {
    width: 100%;
  }
}
</style>

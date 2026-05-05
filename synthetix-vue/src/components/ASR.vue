<template>
  <div class="asr-container">
    <el-card>
      <template #header>
        <span>语音识别 (ASR)</span>
      </template>

      <el-form :model="form" label-width="100px">
        <el-form-item label="音频文件">
          <el-upload
            :auto-upload="false"
            :on-change="handleAudioChange"
            :show-file-list="false"
            accept="audio/*"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽音频文件到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 WAV、MP3、FLAC、OGG、M4A 格式</div>
            </template>
          </el-upload>
          <div v-if="audioName" class="audio-preview">
            <span>{{ audioName }}</span>
            <audio v-if="audioPreviewUrl" :src="audioPreviewUrl" controls style="margin-left: 10px"></audio>
          </div>
        </el-form-item>

        <el-form-item label="语言">
          <el-select v-model="form.language" style="width: 200px" clearable placeholder="自动检测">
            <el-option label="自动检测" value="" />
            <el-option label="中文" value="zh" />
            <el-option label="英文" value="en" />
            <el-option label="日文" value="ja" />
            <el-option label="韩文" value="ko" />
          </el-select>
        </el-form-item>

        <el-form-item label="识别模型">
          <el-radio-group v-model="form.modelQuality">
            <el-radio value="fast">快速</el-radio>
            <el-radio value="standard">标准</el-radio>
            <el-radio value="accurate">高精度</el-radio>
          </el-radio-group>
          <span class="model-hint">
            {{ form.modelQuality === 'fast' ? '速度快，适合实时场景' : form.modelQuality === 'accurate' ? '精度高，耗时较长' : '平衡速度与精度' }}
          </span>
        </el-form-item>

        <el-form-item label="输出格式">
          <el-radio-group v-model="form.outputFormat">
            <el-radio value="text">纯文本</el-radio>
            <el-radio value="srt">SRT 字幕</el-radio>
            <el-radio value="vtt">VTT 字幕</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="说话人分离">
          <el-switch v-model="form.enableDiarization" />
          <span v-if="form.enableDiarization" style="margin-left: 8px">
            <el-input-number v-model="form.numSpeakers" :min="0" :max="10" size="small" placeholder="说话人数(0=自动)" style="width: 150px" />
          </span>
        </el-form-item>

        <el-form-item label="热词">
          <el-select v-model="form.hotwords" multiple filterable allow-create default-first-option
                     size="small" placeholder="添加热词提升识别率" style="width: 300px">
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="transcribe" :loading="loading" :disabled="!audioBase64">
            开始识别
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 结果区域 -->
    <el-card v-if="result" class="result-card">
      <template #header>
        <div class="result-header">
          <span>识别结果</span>
          <div class="result-actions">
            <el-radio-group v-model="resultView" size="small">
              <el-radio-button value="text">文本</el-radio-button>
              <el-radio-button value="srt" :disabled="!result.subtitle">SRT</el-radio-button>
              <el-radio-button value="segments">分段</el-radio-button>
            </el-radio-group>
            <el-button type="primary" size="small" @click="copyResult">复制</el-button>
          </div>
        </div>
      </template>

      <div class="result-content">
        <div v-if="resultView === 'text'" class="result-text">{{ result.text }}</div>
        <pre v-else-if="resultView === 'srt' && result.subtitle" class="result-srt">{{ result.subtitle }}</pre>
        <div v-else-if="result.segments && result.segments.length" class="segments">
          <div v-for="(seg, idx) in result.segments" :key="idx" class="segment-item">
            <span class="time">[{{ formatTime(seg.start) }} - {{ formatTime(seg.end) }}]</span>
            <span v-if="seg.speaker" class="seg-speaker">{{ seg.speaker }}</span>
            <span class="seg-text">{{ seg.text }}</span>
          </div>
        </div>
        <div v-if="result.language" class="result-meta">
          检测语言: {{ result.language }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { API_HOST } from '@/api/modules'

const form = ref({
  language: '',
  outputFormat: 'text',
  enableDiarization: false,
  numSpeakers: 0,
  hotwords: [],
  modelQuality: 'standard',
})

const loading = ref(false)
const audioBase64 = ref('')
const audioName = ref('')
const audioPreviewUrl = ref('')
const result = ref(null)
const resultView = ref('text')

// 处理音频上传
const handleAudioChange = (file) => {
  audioName.value = file.name

  // 创建预览 URL
  if (audioPreviewUrl.value) {
    URL.revokeObjectURL(audioPreviewUrl.value)
  }
  audioPreviewUrl.value = URL.createObjectURL(file.raw)

  // 读取 base64
  const reader = new FileReader()
  reader.onload = (e) => {
    const base64 = e.target.result.split(',')[1]
    audioBase64.value = base64
  }
  reader.readAsDataURL(file.raw)
}

// 开始识别
const transcribe = async () => {
  if (!audioBase64.value) {
    ElMessage.warning('请先上传音频文件')
    return
  }

  loading.value = true
  result.value = null

  try {
    const payload = {
      audio: audioBase64.value,
      output_format: form.value.outputFormat,
    }
    if (form.value.modelQuality !== 'standard') {
      payload.model_quality = form.value.modelQuality
    }
    if (form.value.language) {
      payload.language = form.value.language
    }
    if (form.value.hotwords.length) {
      payload.hotwords = form.value.hotwords
    }
    if (form.value.enableDiarization) {
      payload.diarize = true
      if (form.value.numSpeakers > 0) payload.num_speakers = form.value.numSpeakers
    }

    const response = await fetch(`${API_HOST}/api/nexus/asr`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await response.json()

    if (data?.data) {
      result.value = data.data
      ElMessage.success('识别完成')
    } else {
      throw new Error(data.message || '识别失败')
    }
  } catch (error) {
    console.error('ASR 识别失败:', error)
    ElMessage.error(`识别失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// 复制结果
const copyResult = () => {
  if (result.value?.text) {
    navigator.clipboard.writeText(result.value.text)
    ElMessage.success('已复制到剪贴板')
  }
}

// 格式化时间
const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(1)
  return `${mins}:${secs.padStart(4, '0')}`
}
</script>

<style scoped>
.asr-container {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.audio-preview {
  margin-top: 10px;
  display: flex;
  align-items: center;
}

.result-card {
  margin-top: 20px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-text {
  font-size: 16px;
  line-height: 1.8;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}
.result-actions { display: flex; gap: 8px; align-items: center; }
.result-srt {
  font-size: 13px;
  line-height: 1.6;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
  font-family: monospace;
}
.seg-speaker {
  font-size: 11px;
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  padding: 0 6px;
  border-radius: 8px;
  margin-right: 4px;
}
.result-meta {
  margin-top: 10px;
  color: #909399;
  font-size: 14px;
}

.segments {
  margin-top: 15px;
}

.segment-item {
  padding: 8px 0;
  border-bottom: 1px dashed #e4e7ed;
}

.segment-item:last-child {
  border-bottom: none;
}

.time {
  color: #409eff;
  font-size: 12px;
  margin-right: 10px;
}

.seg-text {
  color: #333;
}

.model-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>

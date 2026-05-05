<template>
  <div class="dashboard">
    <!-- 音乐生成区域 -->
    <div class="card">
      <h2 class="card-title">
        <i class="fas fa-music"></i> AI 音乐工坊
      </h2>

      <el-form label-width="90px">
        <!-- 模式选择 -->
        <el-form-item label="生成模式：">
          <el-radio-group v-model="musicForm.mode" size="small">
            <el-radio-button v-for="m in musicModes" :key="m.value" :value="m.value">{{ m.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 音乐描述 -->
        <el-form-item label="描述：">
          <el-input v-model="musicForm.prompt" type="textarea" :rows="2"
            :placeholder="currentModeDesc" resize="none" class="prompt-input" />
        </el-form-item>

        <!-- 风格 + 时长 -->
        <div style="display: flex; gap: 12px;">
          <el-form-item label="风格：" style="flex: 1;">
            <el-select v-model="musicForm.style" placeholder="选择风格" clearable style="width: 200px;">
              <el-option v-for="s in musicStyles" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="!currentModeNeedsAudio" label="时长：" style="flex: 1;">
            <el-slider v-model="musicForm.duration" :min="5" :max="240" :step="5" show-input />
          </el-form-item>
        </div>

        <!-- 生成模式：歌词 -->
        <el-form-item v-if="musicForm.mode === 'generate'" label="歌词：">
          <el-input v-model="musicForm.lyrics" type="textarea" :rows="3"
            placeholder="可选，不填为纯音乐。支持 [verse] [chorus] [bridge] 结构标签" resize="none" class="prompt-input" />
        </el-form-item>

        <!-- 变奏：变化程度 -->
        <el-form-item v-if="musicForm.mode === 'retake'" label="变化程度：">
          <el-slider v-model="musicForm.variance" :min="0" :max="1" :step="0.1" show-input style="width: 300px;" />
        </el-form-item>

        <!-- 需要音频输入的模式：BGM 选择 -->
        <el-form-item v-if="currentModeNeedsAudio" label="选择 BGM：">
          <el-select v-model="musicForm.bgmId" placeholder="从曲库中选择" filterable clearable style="width: 100%">
            <el-option v-for="b in bgmList" :key="b.id" :label="b.name || b.filename || '-'" :value="b.id" />
          </el-select>
        </el-form-item>

        <!-- 重绘：起止时间 -->
        <div v-if="musicForm.mode === 'repaint'" style="display: flex; gap: 12px;">
          <el-form-item label="起始时间：" style="flex: 1;">
            <el-input-number v-model="musicForm.startTime" :min="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="结束时间：" style="flex: 1;">
            <el-input-number v-model="musicForm.endTime" :min="0" :step="1" style="width: 100%" />
          </el-form-item>
        </div>

        <!-- 编辑歌词 -->
        <el-form-item v-if="musicForm.mode === 'edit'" label="新歌词：">
          <el-input v-model="musicForm.lyrics" type="textarea" :rows="3"
            placeholder="替换的歌词，支持 [verse] [chorus] 结构标签" resize="none" class="prompt-input" />
        </el-form-item>

        <!-- 扩展 -->
        <div v-if="musicForm.mode === 'extend'" style="display: flex; gap: 12px;">
          <el-form-item label="向前延长：" style="flex: 1;">
            <el-slider v-model="musicForm.extendLeft" :min="0" :max="60" :step="5" show-input />
          </el-form-item>
          <el-form-item label="向后延长：" style="flex: 1;">
            <el-slider v-model="musicForm.extendRight" :min="0" :max="60" :step="5" show-input />
          </el-form-item>
        </div>

        <!-- 翻唱：歌词 -->
        <el-form-item v-if="musicForm.mode === 'cover'" label="翻唱歌词：">
          <el-input v-model="musicForm.lyrics" type="textarea" :rows="2"
            placeholder="可选，不填则保持原歌词" resize="none" class="prompt-input" />
        </el-form-item>

        <!-- 风格迁移：强度 -->
        <el-form-item v-if="musicForm.mode === 'style_transfer'" label="风格强度：">
          <el-slider v-model="musicForm.editStrength" :min="0" :max="1" :step="0.1" show-input style="width: 300px;" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="generateMusic" :loading="generating" :disabled="!canGenerate">
            <i class="fas fa-music"></i> 生成音乐
          </el-button>
          <el-button v-if="generatedAudio" type="success" @click="addToBgmLibrary">
            添加到曲库
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 生成音乐展示区域 -->
    <div class="card">
      <h2 class="card-title">
        <i class="fas fa-headphones"></i> 生成结果
      </h2>
      <div v-if="!generatedAudio" class="empty-placeholder">
        暂无生成音乐
      </div>
      <div v-else class="audio-container">
        <audio :src="generatedAudio" controls class="audio-element"/>
        <el-button type="success" size="small" @click="downloadAudio" style="margin-left: 10px;">
          <i class="fas fa-download"></i> 下载
        </el-button>
      </div>
    </div>

    <!-- 高级设置（ComfyUI 原生模式） -->
    <el-collapse class="card">
      <el-collapse-item title="高级设置（ComfyUI 原生模式）" name="advanced">
        <el-form-item>
          <el-input
              v-model="serverUrl"
              placeholder="输入 ComfyUI 服务器地址 (例如: http://localhost:8188)"
              clearable>
            <template #prepend><i class="fas fa-link"></i></template>
          </el-input>
        </el-form-item>

        <div class="action-buttons">
          <span :class="serverStatus ? 'badge-success' : 'badge-warning'">
            {{ serverStatus ? '在线' : '离线' }}
          </span>
          <el-button type="primary" @click="testConnection" :loading="testingConnection">
            <i class="fas fa-plug"></i> 测试连接
          </el-button>
        </div>

        <el-tabs type="border-card" style="margin-top: 15px;">
          <el-tab-pane label="文生歌">
            <el-form-item label="风格标签：">
              <el-input
                  v-model="tags_prompt"
                  type="textarea"
                  :rows="2"
                  placeholder="如：anime, soft female vocals, kawaii pop, j-pop"
                  resize="none"
                  class="prompt-input"/>
            </el-form-item>
            <el-form-item label="歌词：">
              <el-input
                  v-model="lyrics_prompt"
                  type="textarea"
                  :rows="9"
                  placeholder="歌词"
                  resize="none"
                  class="prompt-input"/>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitPrompt" :loading="submittingPrompt">
                <i class="fas fa-paper-plane"></i> 运行工作流
              </el-button>
              <el-button type="warning" @click="interruptExecution">
                <i class="fas fa-stop-circle"></i> 中断执行
              </el-button>
            </el-form-item>
          </el-tab-pane>
        </el-tabs>

        <el-form-item style="margin-top: 15px;">
          <el-checkbox v-model="freeOptions.unload_models">卸载模型</el-checkbox>
          <el-checkbox v-model="freeOptions.free_memory">释放内存</el-checkbox>
          <el-button type="danger" @click="freeResources">
            <i class="fas fa-broom"></i> 释放资源
          </el-button>
        </el-form-item>
      </el-collapse-item>
    </el-collapse>

    <!-- ComfyUI 生成结果 -->
    <div class="card" v-if="comfyuiAudio">
      <h2 class="card-title">
        <i class="fas fa-music"></i> ComfyUI 生成结果
      </h2>
      <div class="audio-container">
        <audio :src="comfyuiAudio" controls class="audio-element"/>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { aiApi, projectApi } from '@/api/modules'
import { useProjectStore } from '@/store/modules/project'

const store = useProjectStore()

// ==================== 音乐模式定义 ====================
const musicModes = [
  { value: 'generate', label: '生成', needsAudio: false, isMusicToMusic: false, desc: '描述你想要的音乐，不填歌词为纯音乐' },
  { value: 'retake', label: '变奏', needsAudio: false, isMusicToMusic: false, desc: '基于相同描述生成不同变体' },
  { value: 'repaint', label: '重绘', needsAudio: true, isMusicToMusic: false, desc: '选择曲库中的 BGM，重绘指定时间段' },
  { value: 'edit', label: '编辑歌词', needsAudio: true, isMusicToMusic: false, desc: '替换曲库中 BGM 的歌词并重新生成' },
  { value: 'extend', label: '延长', needsAudio: true, isMusicToMusic: false, desc: '在曲库中的 BGM 前后扩展时长' },
  { value: 'cover', label: '翻唱', needsAudio: true, isMusicToMusic: false, desc: '基于曲库中的 BGM 进行翻唱' },
  { value: 'style_transfer', label: '风格迁移', needsAudio: true, isMusicToMusic: true, desc: '将曲库中的 BGM 转换为新风格' },
]

const musicStyles = [
  { label: '流行', value: 'pop' },
  { label: '古典', value: 'classical' },
  { label: '电子', value: 'electronic' },
  { label: '爵士', value: 'jazz' },
  { label: '摇滚', value: 'rock' },
  { label: '氛围', value: 'ambient' },
  { label: '嘻哈', value: 'hiphop' },
]

const musicForm = ref({
  mode: 'generate', prompt: '', style: '', duration: 15,
  lyrics: '', bgmId: null, variance: 0.5,
  startTime: 0, endTime: 5, extendLeft: 0, extendRight: 10,
  editStrength: 0.5,
})

const currentMode = computed(() => musicModes.find(m => m.value === musicForm.value.mode) || musicModes[0])
const currentModeNeedsAudio = computed(() => currentMode.value.needsAudio)
const currentModeDesc = computed(() => currentMode.value.desc)

const bgmList = computed(() => store.bgmList || [])

const canGenerate = computed(() => {
  const form = musicForm.value
  if (!form.prompt.trim() && form.mode !== 'cover') return false
  if (currentModeNeedsAudio.value && !form.bgmId) return false
  if (form.mode === 'repaint' && (form.startTime == null || form.endTime == null)) return false
  if (form.mode === 'edit' && !form.lyrics.trim()) return false
  return true
})

// ==================== Core-Nexus 音乐生成 ====================
const generating = ref(false)
const generatedAudio = ref(null)
const generatedBlob = ref(null)

const fetchBgmAudioBase64 = async (bgmId) => {
  const res = await aiApi.getBgmAudio(bgmId)
  return res.audio || res?.data?.audio || ''
}

const generateMusic = async () => {
  const form = musicForm.value
  if (!canGenerate.value) return

  try {
    generating.value = true
    if (generatedAudio.value) { URL.revokeObjectURL(generatedAudio.value); generatedAudio.value = null }
    generatedBlob.value = null

    let response
    const mode = currentMode.value

    if (mode.isMusicToMusic) {
      const audioBase64 = await fetchBgmAudioBase64(form.bgmId)
      const params = { audio: audioBase64, prompt: form.prompt }
      if (form.style) params.style = form.style
      if (form.editStrength) params.generation = { edit_strength: form.editStrength }
      response = await aiApi.musicToMusic(params)
    } else if (mode.needsAudio) {
      const audioBase64 = await fetchBgmAudioBase64(form.bgmId)
      const bgm = bgmList.value.find(b => b.id === form.bgmId)
      const params = { prompt: form.prompt, mode: form.mode, audio: audioBase64 }
      if (form.style) params.style = form.style
      if (bgm?.duration) params.duration = bgm.duration
      if (form.mode === 'repaint') { params.start_time = form.startTime; params.end_time = form.endTime }
      if (form.mode === 'edit') { params.lyrics = form.lyrics }
      if (form.mode === 'extend') { params.extend_left = form.extendLeft; params.extend_right = form.extendRight }
      if (form.mode === 'cover' && form.lyrics) { params.lyrics = form.lyrics }
      response = await aiApi.textToMusic(params)
    } else {
      const params = { prompt: form.prompt, mode: form.mode, duration: form.duration }
      if (form.style) params.style = form.style
      if (form.mode === 'generate' && form.lyrics) params.lyrics = form.lyrics
      if (form.mode === 'retake') {
        params.variance = form.variance
        if (form.lyrics) params.lyrics = form.lyrics
      }
      response = await aiApi.textToMusic(params)
    }

    const blob = new Blob([response], { type: 'audio/wav' })
    generatedBlob.value = blob
    generatedAudio.value = URL.createObjectURL(blob)
    ElMessage.success('音乐生成成功')
  } catch (error) {
    console.error('音乐生成失败:', error)
    ElMessage.error('音乐生成失败: ' + (error.message || '未知错误'))
  } finally {
    generating.value = false
  }
}

const downloadAudio = () => {
  if (!generatedAudio.value) return
  const link = document.createElement('a')
  link.href = generatedAudio.value
  link.download = `music_${Date.now()}.wav`
  link.click()
}

const addToBgmLibrary = async () => {
  if (!generatedBlob.value) return
  try {
    const file = new File([generatedBlob.value], `ai_music_${Date.now()}.wav`, { type: 'audio/wav' })
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', musicForm.value.prompt.slice(0, 30) || 'AI 生成音乐')
    await projectApi.uploadBgm(formData)
    ElMessage.success('已添加到曲库')
    store.refreshBgmList()
  } catch (error) {
    ElMessage.error('添加失败: ' + error.message)
  }
}

// ==================== ComfyUI 原生模式 ====================
const serverUrl = ref('http://localhost:8188')
const serverStatus = ref(false)
const testingConnection = ref(false)

const tags_prompt = ref('anime, soft female vocals, kawaii pop, j-pop, childish, piano, guitar, synthesizer, fast, happy, cheerful, lighthearted')
const lyrics_prompt = ref('[inst]\n\n[verse]\nふわふわ　おみみが\nゆれるよ　かぜのなか\nきらきら　あおいめ\nみつめる　せかいを\n')
const submittingPrompt = ref(false)
const comfyuiAudio = ref(null)

const freeOptions = reactive({
  unload_models: true,
  free_memory: true
})

const testConnection = async () => {
  if (!serverUrl.value) {
    ElMessage.warning('请输入服务器地址')
    return
  }
  testingConnection.value = true
  try {
    const response = await axios.get(`${serverUrl.value}/prompt`)
    serverStatus.value = true
    ElMessage.success('连接成功')
  } catch (error) {
    serverStatus.value = false
    ElMessage.error('连接失败: ' + (error.message || '服务器未响应'))
  } finally {
    testingConnection.value = false
  }
}

const submitPrompt = async () => {
  if (!tags_prompt.value) {
    ElMessage.warning('请输入风格标签')
    return
  }
  if (!lyrics_prompt.value) {
    ElMessage.warning('请输入歌词')
    return
  }
  try {
    submittingPrompt.value = true
    comfyuiAudio.value = null

    const fluxModule = await import('@/components/config/fluxJson.js')
    let fluxData = fluxModule.default.ace_step_t2a_song_json
    fluxData['14'].inputs.tags = tags_prompt.value
    fluxData['14'].inputs.lyrics = lyrics_prompt.value

    const payload = { prompt: fluxData }
    const response = await axios.post(`${serverUrl.value}/prompt`, payload)

    ElMessage.success('提示提交成功')
    await pollForGeneratedImages(response.data.prompt_id)
  } catch (error) {
    ElMessage.error('提交提示失败: ' + error.message)
  } finally {
    submittingPrompt.value = false
  }
}

const pollForGeneratedImages = async (promptId) => {
  const maxAttempts = 300
  let attempts = 0

  const poll = async () => {
    attempts++
    try {
      const response = await axios.get(`${serverUrl.value}/history/${promptId}`)
      const historyData = response.data[promptId]

      if (historyData && historyData.status.completed) {
        extractImagesFromHistory(historyData)
        return true
      }
    } catch (error) {
      console.error('轮询历史记录时出错:', error)
    }

    if (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      return poll()
    } else {
      ElMessage.warning('生成歌曲超时')
      return false
    }
  }

  return poll()
}

const extractImagesFromHistory = (historyData) => {
  comfyuiAudio.value = null

  for (const nodeId in historyData.outputs) {
    const nodeOutput = historyData.outputs[nodeId]
    if (nodeOutput && Array.isArray(nodeOutput.audio)) {
      nodeOutput.audio.forEach(imageInfo => {
        const url = `${serverUrl.value}/view?filename=${encodeURIComponent(imageInfo.filename)}&type=output&subfolder=audio`
        comfyuiAudio.value = url
      })
    }
  }

  if (comfyuiAudio.value) {
    ElMessage.success('生成成功')
  } else {
    ElMessage.warning('未找到生成结果')
  }
}

const interruptExecution = async () => {
  try {
    await axios.post(`${serverUrl.value}/interrupt`)
    ElMessage.success('已发送中断执行请求')
  } catch (error) {
    ElMessage.error('中断执行失败')
  }
}

const freeResources = async () => {
  try {
    await axios.post(`${serverUrl.value}/free`, freeOptions)
    ElMessage.success('已释放资源')
  } catch (error) {
    ElMessage.error('释放资源失败')
  }
}

// 初始化
onMounted(() => {
  const savedUrl = localStorage.getItem('comfyui_server_url')
  if (savedUrl) {
    serverUrl.value = savedUrl
  }
  store.refreshBgmList()
})
</script>

<style scoped src="@/styles/components/comfy-ui-audio.css"></style>

<style scoped>
.card {
  margin-bottom: 20px;
  padding: 20px;
  background: var(--el-bg-color);
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.card-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.prompt-input {
  width: 100%;
}

.duration-unit {
  margin-left: 10px;
  color: var(--el-text-color-secondary);
}

.empty-placeholder {
  padding: 40px;
  text-align: center;
  color: var(--el-text-color-placeholder);
}

.audio-container {
  display: flex;
  align-items: center;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.audio-element {
  width: 100%;
  max-width: 500px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge-success {
  padding: 4px 12px;
  background: #67c23a;
  color: white;
  border-radius: 4px;
  font-size: 12px;
}

.badge-warning {
  padding: 4px 12px;
  background: #e6a23c;
  color: white;
  border-radius: 4px;
  font-size: 12px;
}

:deep(.el-radio-group) {
  flex-wrap: wrap;
  gap: 4px;
}
:deep(.el-radio-button__inner) {
  font-size: 12px;
  padding: 4px 10px;
}
</style>

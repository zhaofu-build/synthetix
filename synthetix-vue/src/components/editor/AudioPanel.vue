<template>
  <div class="audio-panel">
    <!-- 音色区域 -->
    <div v-if="activeTab === 'tts'" class="section">
      <div class="section-header">
        <span class="section-title">音色管理</span>
        <el-button type="primary" size="small" @click="openAddVoice" text>
          <el-icon><Plus /></el-icon> 添加
        </el-button>
      </div>
      <div v-if="store.voiceList.length === 0" class="list-empty">暂无音色，点击上方添加</div>
      <div v-for="v in store.voiceList" :key="v.id" class="voice-item" :class="{ 'is-default': v.isDefault }" @click="setDefaultVoice(v)">
        <div class="voice-info">
          <span class="voice-name">{{ v.audioName || v.audio_name || '未命名' }}</span>
          <span v-if="v.isDefault" class="default-tag">默认</span>
        </div>
        <div class="voice-actions">
          <el-button text size="small" @click.stop="editVoice(v)">编辑</el-button>
          <el-button text size="small" type="danger" @click.stop="deleteVoice(v)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- BGM 区域 -->
    <div v-if="activeTab === 'bgm'" class="section">
      <div class="section-header">
        <span class="section-title">BGM</span>
        <div class="list-actions">
          <el-button size="small" @click="triggerBgmUpload">上传</el-button>
          <el-button size="small" @click="showMusicGenDialog = true">AI 生成</el-button>
        </div>
      </div>
      <div v-if="store.bgmList.length === 0" class="list-empty">暂无 BGM，点击上方上传或生成</div>
      <div v-for="b in store.bgmList" :key="b.id" class="bgm-item" :class="{ 'is-selected': selectedBgm === b.id }" @click="selectBgmFromList(b)">
        <div class="bgm-info">
          <span class="bgm-name">{{ b.name || b.filename || '-' }}</span>
        </div>
        <div class="bgm-actions">
          <el-button text size="small" type="danger" @click.stop="deleteBgm(b)">删除</el-button>
        </div>
      </div>
      <template v-if="selectedBgmUrl">
        <div class="bgm-player">
          <WaveformVisualizer :audio-url="selectedBgmUrl" :height="40" @seek="onBgmSeek" />
          <audio ref="bgmAudioRef" :src="selectedBgmUrl" controls style="width: 100%" />
        </div>
        <el-form label-position="top" size="small">
          <el-form-item label="音量">
            <el-slider v-model="bgmVolume" :min="0" :max="100" :step="5" show-input size="small" />
          </el-form-item>
        </el-form>
      </template>
    </div>

    <!-- 添加/编辑音色弹窗 -->
    <el-dialog v-model="showVoiceForm" :title="editingVoiceId ? '编辑音色' : '添加音色'" width="400" destroy-on-close append-to-body>
      <el-form label-position="top" size="small">
        <el-form-item label="音色名称">
          <el-input v-model="voiceForm.name" />
        </el-form-item>
        <el-form-item v-if="!editingVoiceId" label="参考音频">
          <el-button size="small" @click="triggerVoiceUpload">上传音频</el-button>
          <span v-if="voiceForm.audioName" style="margin-left: 8px">{{ voiceForm.audioName }}</span>
        </el-form-item>
        <el-form-item label="参考文本">
          <el-input v-model="voiceForm.text" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showVoiceForm = false">取消</el-button>
        <el-button type="primary" @click="saveVoice">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI 音乐生成弹窗 -->
    <el-dialog v-model="showMusicGenDialog" title="AI 音乐工坊" width="520" destroy-on-close append-to-body
               @open="onMusicGenDialogOpen" @close="onMusicGenDialogClose">
      <el-form label-position="top" size="small">
        <!-- 模式选择 -->
        <el-form-item label="生成模式">
          <el-radio-group v-model="musicGenForm.mode" size="small">
            <el-radio-button v-for="m in musicModes" :key="m.value" :value="m.value">{{ m.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 通用：音乐描述 -->
        <el-form-item label="音乐描述">
          <el-input v-model="musicGenForm.prompt" type="textarea" :rows="2"
            :placeholder="currentModeDesc" />
        </el-form-item>

        <!-- 通用：风格 -->
        <div style="display: flex; gap: 12px;">
          <el-form-item label="风格" style="flex: 1;">
            <el-select v-model="musicGenForm.style" placeholder="选择风格" clearable>
              <el-option v-for="s in musicStyles" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <!-- 生成/变奏：时长 -->
          <el-form-item v-if="!currentModeNeedsAudio" label="时长 (秒)" style="flex: 1;">
            <el-slider v-model="musicGenForm.duration" :min="5" :max="240" :step="5" show-input />
          </el-form-item>
        </div>

        <!-- 生成模式：歌词 -->
        <el-form-item v-if="musicGenForm.mode === 'generate'" label="歌词（可选，不填为纯音乐）">
          <el-input v-model="musicGenForm.lyrics" type="textarea" :rows="3"
            placeholder="可使用 [verse] [chorus] [bridge] 结构标签" />
        </el-form-item>

        <!-- 变奏：变化程度 -->
        <el-form-item v-if="musicGenForm.mode === 'retake'" label="变化程度">
          <el-slider v-model="musicGenForm.variance" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>

        <!-- 需要音频输入的模式：BGM 选择 -->
        <el-form-item v-if="currentModeNeedsAudio" label="选择 BGM">
          <el-select v-model="musicGenForm.bgmId" placeholder="从曲库中选择" filterable clearable style="width: 100%">
            <el-option v-for="b in store.bgmList" :key="b.id" :label="b.name || b.filename || '-'" :value="b.id" />
          </el-select>
        </el-form-item>

        <!-- 重绘：起止时间 -->
        <div v-if="musicGenForm.mode === 'repaint'" style="display: flex; gap: 12px;">
          <el-form-item label="起始时间 (秒)" style="flex: 1;">
            <el-input-number v-model="musicGenForm.startTime" :min="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="结束时间 (秒)" style="flex: 1;">
            <el-input-number v-model="musicGenForm.endTime" :min="0" :step="1" style="width: 100%" />
          </el-form-item>
        </div>

        <!-- 编辑歌词：新歌词 -->
        <el-form-item v-if="musicGenForm.mode === 'edit'" label="新歌词">
          <el-input v-model="musicGenForm.lyrics" type="textarea" :rows="3"
            placeholder="替换的歌词，支持 [verse] [chorus] 结构标签" />
        </el-form-item>

        <!-- 扩展：左右秒数 -->
        <div v-if="musicGenForm.mode === 'extend'" style="display: flex; gap: 12px;">
          <el-form-item label="向前延长 (秒)" style="flex: 1;">
            <el-slider v-model="musicGenForm.extendLeft" :min="0" :max="60" :step="5" show-input />
          </el-form-item>
          <el-form-item label="向后延长 (秒)" style="flex: 1;">
            <el-slider v-model="musicGenForm.extendRight" :min="0" :max="60" :step="5" show-input />
          </el-form-item>
        </div>

        <!-- 翻唱：歌词（可选） -->
        <el-form-item v-if="musicGenForm.mode === 'cover'" label="翻唱歌词（可选）">
          <el-input v-model="musicGenForm.lyrics" type="textarea" :rows="2" placeholder="不填则保持原歌词" />
        </el-form-item>

        <!-- 风格迁移：强度 -->
        <el-form-item v-if="musicGenForm.mode === 'style_transfer'" label="风格强度">
          <el-slider v-model="musicGenForm.editStrength" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>

        <!-- 预览 -->
        <div v-if="musicGenPreviewUrl" class="music-preview">
          <audio :src="musicGenPreviewUrl" controls style="width: 100%" />
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showMusicGenDialog = false">关闭</el-button>
        <el-button type="primary" :loading="musicGenerating" @click="generateMusic"
          :disabled="!canGenerate">
          {{ musicGenerating ? '生成中...' : '生成' }}
        </el-button>
        <el-button v-if="musicGenPreviewUrl" type="success" @click="addToBgmLibrary">添加到曲库</el-button>
      </template>
    </el-dialog>

    <input ref="bgmUpload" type="file" accept="audio/*" style="display:none" @change="handleBgmUpload" />
    <input ref="voiceUpload" type="file" accept="audio/*" style="display:none" @change="handleVoiceUpload" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
const props = defineProps({ initialTab: { type: String, default: 'tts' } })
const activeTab = computed(() => props.initialTab)
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { audioApi, projectApi, aiApi } from '@/api/modules'
import { assetUrl } from '@/api/modules'

const store = useProjectStore()

const bgmAudioRef = ref(null)

const onBgmSeek = ({ time }) => {
  if (bgmAudioRef.value) { bgmAudioRef.value.currentTime = time; bgmAudioRef.value.play() }
}

// BGM
const selectedBgm = ref(null)
const selectedBgmUrl = ref('')
const bgmVolume = ref(30)

// 弹窗
const showVoiceForm = ref(false)
const showMusicGenDialog = ref(false)

// 音乐模式定义
const musicModes = [
  { value: 'generate', label: '生成', needsAudio: false, isMusicToMusic: false, desc: '描述你想要的音乐，不填歌词为纯音乐' },
  { value: 'retake', label: '变奏', needsAudio: false, isMusicToMusic: false, desc: '基于相同描述生成不同变体' },
  { value: 'repaint', label: '重绘', needsAudio: true, isMusicToMusic: false, desc: '选择曲库中的 BGM，重绘指定时间段' },
  { value: 'edit', label: '编辑歌词', needsAudio: true, isMusicToMusic: false, desc: '替换曲库中 BGM 的歌词并重新生成' },
  { value: 'extend', label: '延长', needsAudio: true, isMusicToMusic: false, desc: '在曲库中的 BGM 前后扩展时长' },
  { value: 'cover', label: '翻唱', needsAudio: true, isMusicToMusic: false, desc: '基于曲库中的 BGM 进行翻唱' },
  { value: 'style_transfer', label: '风格迁移', needsAudio: true, isMusicToMusic: true, desc: '将曲库中的 BGM 转换为新风格' },
]

const currentMode = computed(() => musicModes.find(m => m.value === musicGenForm.value.mode) || musicModes[0])
const currentModeNeedsAudio = computed(() => currentMode.value.needsAudio)
const currentModeDesc = computed(() => currentMode.value.desc)

const canGenerate = computed(() => {
  const form = musicGenForm.value
  if (!form.prompt.trim() && form.mode !== 'cover') return false
  if (currentModeNeedsAudio.value && !form.bgmId) return false
  if (form.mode === 'repaint' && (form.startTime == null || form.endTime == null)) return false
  if (form.mode === 'edit' && !form.lyrics.trim()) return false
  return true
})

// 音乐生成表单
const musicGenerating = ref(false)
const musicGenPreviewUrl = ref('')
const musicGenBlob = ref(null)
const musicGenForm = ref({
  mode: 'generate',
  prompt: '',
  style: '',
  duration: 15,
  lyrics: '',
  bgmId: null,
  variance: 0.5,
  startTime: 0,
  endTime: 5,
  extendLeft: 0,
  extendRight: 10,
  editStrength: 0.5,
})
const musicStyles = [
  { label: '流行', value: 'pop' },
  { label: '古典', value: 'classical' },
  { label: '电子', value: 'electronic' },
  { label: '爵士', value: 'jazz' },
  { label: '摇滚', value: 'rock' },
  { label: '氛围', value: 'ambient' },
  { label: '嘻哈', value: 'hiphop' },
]

// 编辑状态
const editingVoiceId = ref(null)
const voiceForm = ref({ name: '', text: '', audioFile: null, audioName: '' })

// refs
const bgmUpload = ref(null)
const voiceUpload = ref(null)

onMounted(() => {
  store.refreshBgmList()
  store.refreshVoiceList()
})

// ==================== 音色管理 ====================

const openAddVoice = () => {
  editingVoiceId.value = null
  voiceForm.value = { name: '', text: '', audioFile: null, audioName: '' }
  showVoiceForm.value = true
}

const editVoice = (row) => {
  editingVoiceId.value = row.id
  voiceForm.value = {
    name: row.audioName || row.audio_name || '',
    text: row.promptText || row.prompt_text || '',
    audioFile: null,
    audioName: '',
  }
  showVoiceForm.value = true
}

const saveVoice = async () => {
  try {
    if (editingVoiceId.value) {
      await audioApi.updateAudio(editingVoiceId.value, {
        audio_name: voiceForm.value.name,
        prompt_text: voiceForm.value.text,
      })
      ElMessage.success('更新成功')
    } else {
      const formData = new FormData()
      formData.append('audio_name', voiceForm.value.name)
      if (voiceForm.value.audioFile) formData.append('file', voiceForm.value.audioFile)
      if (voiceForm.value.text) formData.append('prompt_text', voiceForm.value.text)
      await audioApi.saveTimbre(formData)
      ElMessage.success('添加成功')
    }
    showVoiceForm.value = false
    store.refreshVoiceList()
  } catch (error) {
    ElMessage.error('保存失败: ' + error.message)
  }
}

const deleteVoice = async (row) => {
  try {
    await audioApi.deleteSourceAudio(row.id)
    ElMessage.success('删除成功')
    store.refreshVoiceList()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

const setDefaultVoice = async (row) => {
  try {
    await audioApi.setDefaultVoice(row.id)
    ElMessage.success('已设为默认音色')
    store.refreshVoiceList()
  } catch (error) {
    ElMessage.error('设置失败')
  }
}

const triggerVoiceUpload = () => {
  voiceUpload.value?.click()
}

const handleVoiceUpload = (e) => {
  const file = e.target.files[0]
  if (!file) return
  voiceForm.value.audioFile = file
  voiceForm.value.audioName = file.name
  e.target.value = ''
}

// ==================== BGM ====================

const onMusicGenDialogOpen = () => {
  if (musicGenPreviewUrl.value) URL.revokeObjectURL(musicGenPreviewUrl.value)
  musicGenPreviewUrl.value = ''
  musicGenBlob.value = null
  musicGenForm.value = {
    mode: 'generate', prompt: '', style: '', duration: 15,
    lyrics: '', bgmId: null, variance: 0.5,
    startTime: 0, endTime: 5, extendLeft: 0, extendRight: 10,
    editStrength: 0.5,
  }
}

const onMusicGenDialogClose = () => {
  if (musicGenPreviewUrl.value) URL.revokeObjectURL(musicGenPreviewUrl.value)
  musicGenPreviewUrl.value = ''
  musicGenBlob.value = null
}

const onBgmChange = (id) => {
  const bgm = store.bgmList.find(b => b.id === id)
  if (bgm) {
    selectedBgmUrl.value = bgm.web_path ? assetUrl(bgm.web_path) : bgm.local_path || ''
    store.project.bgmId = id
  }
}

const selectBgmFromList = (row) => {
  selectedBgm.value = row.id
  onBgmChange(row.id)
}

// ==================== AI 音乐生成 ====================

const fetchBgmAudioBase64 = async (bgmId) => {
  const res = await aiApi.getBgmAudio(bgmId)
  return res.audio || res?.data?.audio || ''
}

const generateMusic = async () => {
  const form = musicGenForm.value
  if (!canGenerate.value) return
  musicGenerating.value = true
  if (musicGenPreviewUrl.value) {
    URL.revokeObjectURL(musicGenPreviewUrl.value)
    musicGenPreviewUrl.value = ''
  }
  musicGenBlob.value = null
  try {
    let response
    const mode = currentMode.value

    if (mode.isMusicToMusic) {
      // 风格迁移 → /music-to-music
      const audioBase64 = await fetchBgmAudioBase64(form.bgmId)
      const params = { audio: audioBase64, prompt: form.prompt }
      if (form.style) params.style = form.style
      if (form.editStrength) params.generation = { edit_strength: form.editStrength }
      response = await aiApi.musicToMusic(params)
    } else if (mode.needsAudio) {
      // 重绘/编辑/扩展/翻唱 → /text-to-music with mode + audio
      const audioBase64 = await fetchBgmAudioBase64(form.bgmId)
      const bgm = store.bgmList.find(b => b.id === form.bgmId)
      const params = { prompt: form.prompt, mode: form.mode, audio: audioBase64 }
      if (form.style) params.style = form.style
      if (bgm?.duration) params.duration = bgm.duration
      if (form.mode === 'repaint') { params.start_time = form.startTime; params.end_time = form.endTime }
      if (form.mode === 'edit') { params.lyrics = form.lyrics }
      if (form.mode === 'extend') { params.extend_left = form.extendLeft; params.extend_right = form.extendRight }
      if (form.mode === 'cover' && form.lyrics) { params.lyrics = form.lyrics }
      response = await aiApi.textToMusic(params)
    } else {
      // 生成/变奏 → /text-to-music
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
    musicGenBlob.value = blob
    musicGenPreviewUrl.value = URL.createObjectURL(blob)
    ElMessage.success('音乐生成成功')
  } catch (error) {
    ElMessage.error('生成失败: ' + (error.message || '未知错误'))
  } finally {
    musicGenerating.value = false
  }
}

const addToBgmLibrary = async () => {
  if (!musicGenBlob.value) return
  try {
    const file = new File([musicGenBlob.value], `ai_music_${Date.now()}.wav`, { type: 'audio/wav' })
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', musicGenForm.value.prompt.slice(0, 30) || 'AI 生成音乐')
    await projectApi.uploadBgm(formData)
    ElMessage.success('已添加到曲库')
    musicGenPreviewUrl.value = ''
    musicGenBlob.value = null
    showMusicGenDialog.value = false
    store.refreshBgmList()
  } catch (error) {
    ElMessage.error('添加失败: ' + error.message)
  }
}

const triggerBgmUpload = () => {
  bgmUpload.value?.click()
}

const handleBgmUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', file.name.replace(/\.[^/.]+$/, ''))
    await projectApi.uploadBgm(formData)
    ElMessage.success('上传成功')
    store.refreshBgmList()
  } catch (error) {
    ElMessage.error('上传失败')
  }
  e.target.value = ''
}

const deleteBgm = async (row) => {
  try {
    await projectApi.deleteBgm(row.id)
    ElMessage.success('删除成功')
    store.refreshBgmList()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.audio-panel {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
}

.list-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 12px 0;
}

.voice-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}
.voice-item:hover { background: var(--el-fill-color-light); }
.voice-item:last-child { border-bottom: none; }
.voice-item.is-default {
  background: var(--el-color-primary-light-9);
  border-left: 3px solid var(--el-color-primary);
  padding-left: 5px;
}
.voice-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.default-tag {
  font-size: 10px;
  background: var(--el-color-primary);
  color: #fff;
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
  line-height: 1.6;
}
.voice-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.voice-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

/* BGM */
.list-actions {
  display: flex;
  gap: 4px;
}
.bgm-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}
.bgm-item:hover { background: var(--el-fill-color-light); }
.bgm-item:last-child { border-bottom: none; }
.bgm-item.is-selected {
  background: var(--el-color-primary-light-9);
}
.bgm-info { min-width: 0; }
.bgm-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bgm-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}
.bgm-player {
  margin-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
}

.music-preview {
  margin-top: 8px;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

/* AI 音乐工坊模式选择 */
:deep(.el-radio-group) {
  flex-wrap: wrap;
  gap: 4px;
}
:deep(.el-radio-button__inner) {
  font-size: 11px;
  padding: 4px 8px;
}
</style>

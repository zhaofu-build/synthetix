<template>
  <div class="comic-storyboard">
    <!-- Main area -->
    <div class="main-area">
      <!-- Left panel: storyboard grid (40%) -->
      <div class="left-panel">
        <div class="panel-grid">
          <div
            v-for="(panel, idx) in panels"
            :key="idx"
            class="panel-card"
            :class="{ selected: selectedIdx === idx }"
            @click="selectedIdx = idx"
          >
            <div class="panel-thumb">
              <img
                v-if="panel.generatedImagePath"
                :src="assetUrl(panel.generatedImagePath)"
                class="thumb-img"
              />
              <div v-else class="thumb-placeholder">
                <el-icon :size="24"><Picture /></el-icon>
              </div>
              <span class="panel-seq">#{{ panel.sequence || idx + 1 }}</span>
              <span class="panel-duration">{{ panel.duration || 3 }}s</span>
              <span
                v-if="panel.generatedVideoPath"
                class="panel-status status-done"
                title="视频已生成"
              >&#10003;</span>
              <span
                v-else-if="panel.generatedImagePath"
                class="panel-status status-image"
                title="图片已生成"
              >&#9679;</span>
            </div>
          </div>
          <!-- Add panel button -->
          <div class="panel-card add-card" @click="addPanel">
            <el-icon :size="28"><Plus /></el-icon>
            <span>添加分镜</span>
          </div>
        </div>
        <div class="total-duration">总时长: {{ formatDuration(totalDuration) }}</div>
      </div>

      <!-- Right panel: selected panel editor (60%) -->
      <div class="right-panel">
        <template v-if="selectedPanel">
          <div class="editor-section">
            <h4 class="section-title">分镜 #{{ selectedPanel.sequence || selectedIdx + 1 }}</h4>

            <!-- Image + info side by side -->
            <div class="editor-body">
              <!-- Left: image -->
              <div class="editor-image-col">
                <div v-if="selectedPanel.generatedImagePath" class="image-preview" @click="openPreview(assetUrl(selectedPanel.generatedImagePath))">
                  <img :src="assetUrl(selectedPanel.generatedImagePath)" />
                </div>
                <div v-else class="image-empty">
                  <el-icon :size="36"><Picture /></el-icon>
                  <span>暂无图片</span>
                </div>
                <div class="image-actions">
                  <el-button
                    size="small"
                    type="primary"
                    @click="generateImage(selectedIdx)"
                    :loading="selectedPanel._imageLoading"
                  >
                    AI 生成
                  </el-button>
                  <el-upload
                    action="#"
                    :auto-upload="false"
                    :show-file-list="false"
                    :on-change="(f) => handleImageUpload(f, selectedIdx)"
                    accept="image/*"
                  >
                    <el-button size="small">上传</el-button>
                  </el-upload>
                </div>
              </div>

              <!-- Right: fields -->
              <div class="editor-fields-col">
                <!-- Scene description -->
                <el-input
                  v-model="selectedPanel.sceneDescription"
                  type="textarea"
                  :rows="3"
                  placeholder="画面场景描述..."
                  @input="debounceSavePanels"
                />

                <!-- Parameters inline -->
                <div class="params-row">
                  <div class="param-item">
                    <label>时长</label>
                    <el-input-number
                      v-model="selectedPanel.duration"
                      :min="1"
                      :max="30"
                      :step="0.5"
                      size="small"
                      @change="debounceSavePanels"
                    />
                  </div>
                  <div class="param-item">
                    <label>转场</label>
                    <el-select
                      v-model="selectedPanel.transition"
                      size="small"
                      @change="debounceSavePanels"
                    >
                      <el-option label="Cut" value="cut" />
                      <el-option label="Fade" value="fade" />
                      <el-option label="Dissolve" value="dissolve" />
                    </el-select>
                  </div>
                  <div class="param-item">
                    <label>情绪</label>
                    <el-select
                      v-model="selectedPanel.emotion"
                      size="small"
                      @change="debounceSavePanels"
                    >
                      <el-option label="中性" value="neutral" />
                      <el-option label="开心" value="happy" />
                      <el-option label="悲伤" value="sad" />
                      <el-option label="紧张" value="tense" />
                      <el-option label="浪漫" value="romantic" />
                    </el-select>
                  </div>
                </div>

                <!-- Dialogues -->
                <div v-if="selectedPanel.dialogues && selectedPanel.dialogues.length" class="dialogue-list">
                  <div
                    v-for="(dlg, dIdx) in selectedPanel.dialogues"
                    :key="dIdx"
                    class="dialogue-item"
                  >
                    <el-tag size="small" type="info">{{ getCharacterName(dlg.characterId) }}</el-tag>
                    <span class="dialogue-text">{{ dlg.text }}</span>
                    <el-button
                      size="small"
                      text
                      @click="generateAudio(selectedIdx, dIdx, dlg.text)"
                      :loading="dlg._audioLoading"
                    >
                      语音
                    </el-button>
                    <div v-if="getAudioPath(selectedIdx, dIdx)" class="audio-player">
                      <audio :src="assetUrl(getAudioPath(selectedIdx, dIdx))" controls />
                    </div>
                  </div>
                </div>
                <div v-else class="empty-hint-inline">暂无对白</div>

                <!-- Video + delete -->
                <div class="bottom-actions">
                  <el-button
                    v-if="selectedPanel.generatedImagePath"
                    size="small"
                    @click="generateVideo(selectedIdx)"
                    :loading="selectedPanel._videoLoading"
                  >
                    {{ selectedPanel.generatedVideoPath ? '重新生成视频' : '生成视频' }}
                  </el-button>
                  <span v-else class="empty-hint-inline">生成图片后可制作视频</span>
                  <el-button
                    type="danger"
                    size="small"
                    text
                    @click="deletePanel(selectedIdx)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
            </div>

            <!-- Video preview (full width, only if exists) -->
            <div v-if="selectedPanel.generatedVideoPath" class="video-preview">
              <video :src="assetUrl(selectedPanel.generatedVideoPath)" controls />
            </div>
          </div>
        </template>
        <template v-else>
          <div class="empty-state">
            <el-icon :size="48"><VideoCamera /></el-icon>
            <p>选择一个分镜开始编辑</p>
          </div>
        </template>
      </div>
    </div>

    <!-- Bottom bar -->
    <div class="bottom-bar">
      <div class="bottom-bar-inner">
        <!-- Left: BGM -->
        <div class="bgm-section">
          <label class="bgm-label">BGM</label>
          <el-select
            v-model="bgmId"
            placeholder="选择BGM"
            size="small"
            clearable
            style="width: 160px;"
            @change="saveBgmConfig"
          >
            <el-option
              v-for="b in bgmList"
              :key="b.id"
              :label="b.name"
              :value="b.id"
            />
          </el-select>
          <div class="volume-control">
            <label>音量</label>
            <el-slider
              v-model="bgmVolume"
              :min="0"
              :max="1"
              :step="0.05"
              :show-tooltip="false"
              style="width: 100px;"
              @change="saveBgmConfig"
            />
          </div>
          <audio
            v-if="bgmPreviewPath"
            :src="assetUrl(bgmPreviewPath)"
            controls
            class="bgm-player"
          />
        </div>

        <!-- Center: compose -->
        <el-button
          type="primary"
          @click="composeVideo"
          :loading="composing"
        >
          合成漫剧视频
        </el-button>

        <!-- Right: output videos -->
        <div class="output-section">
          <template v-if="project.outputVideos && project.outputVideos.length">
            <span class="output-label">输出:</span>
            <el-button
              v-for="(vid, vIdx) in project.outputVideos"
              :key="vIdx"
              size="small"
              text
              type="primary"
              @click="playOutputVideo(vid)"
            >
              {{ vid.created_at ? formatDurationShort(vid.created_at) : `视频 ${vIdx + 1}` }}
            </el-button>
          </template>
        </div>
      </div>
    </div>

    <!-- Image preview dialog -->
    <el-dialog v-model="previewVisible" width="auto" class="preview-dialog" @close="previewVisible = false">
      <img :src="previewUrl" class="preview-image" />
    </el-dialog>

    <!-- Output video dialog -->
    <el-dialog v-model="showOutputDialog" title="输出视频" width="640px" destroy-on-close>
      <video
        v-if="outputVideoUrl"
        :src="outputVideoUrl"
        controls
        style="width: 100%;"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Plus, VideoCamera } from '@element-plus/icons-vue'
import { comicDramaApi, assetUrl } from '@/api/modules'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  project: { type: Object, required: true },
  panels: { type: Array, required: true },
  characters: { type: Array, default: () => [] },
  bgmList: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:panels', 'update:project', 'refresh'])

// ==================== State ====================
const selectedIdx = ref(-1)
const composing = ref(false)
const showOutputDialog = ref(false)
const outputVideoUrl = ref('')
const previewVisible = ref(false)
const previewUrl = ref('')

function openPreview(url) {
  previewUrl.value = url
  previewVisible.value = true
}

// BGM state from project.bgmConfig
const bgmId = ref(null)
const bgmVolume = ref(0.5)

// Debounce timers
const _timers = {}

// Initialize BGM config from project
watch(
  () => props.project.bgmConfig,
  (cfg) => {
    if (cfg) {
      bgmId.value = cfg.bgmId || cfg.bgm_id || null
      bgmVolume.value = cfg.volume ?? 0.5
    }
  },
  { immediate: true }
)

// Auto-select first panel if none selected
watch(
  () => props.panels.length,
  (len) => {
    if (len > 0 && selectedIdx.value < 0) {
      selectedIdx.value = 0
    }
  },
  { immediate: true }
)

// ==================== Computed ====================
const selectedPanel = computed(() => {
  const idx = selectedIdx.value
  return idx >= 0 && idx < props.panels.length ? props.panels[idx] : null
})

const totalDuration = computed(() => {
  return props.panels.reduce((sum, p) => sum + (p.duration || 3), 0)
})

const bgmPreviewPath = computed(() => {
  if (!bgmId.value) return null
  const found = props.bgmList.find((b) => b.id === bgmId.value)
  return found ? found.webPath : null
})

// ==================== Utilities ====================
function formatDuration(seconds) {
  const s = Math.round(seconds || 0)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function formatDurationShort(val) {
  if (!val) return ''
  // If it's a timestamp string, try to extract a short version
  if (typeof val === 'string' && val.length > 10) return val.slice(5, 16)
  return val
}

function getCharacterName(characterId) {
  if (!characterId) return '旁白'
  const ch = props.characters.find((c) => c.id === characterId || c.name === characterId)
  return ch ? ch.name : characterId
}

function getAudioPath(panelIdx, dialogueIdx) {
  const panel = props.panels[panelIdx]
  if (!panel || !panel.generatedAudioPaths) return null
  return panel.generatedAudioPaths[dialogueIdx] || null
}

function cleanPanels(panels) {
  return panels.map((p) => {
    const clean = { ...p }
    Object.keys(clean).forEach((k) => {
      if (k.startsWith('_')) delete clean[k]
    })
    // Also clean _audioLoading from nested dialogues
    if (clean.dialogues) {
      clean.dialogues = clean.dialogues.map((d) => {
        const dc = { ...d }
        Object.keys(dc).forEach((k) => {
          if (k.startsWith('_')) delete dc[k]
        })
        return dc
      })
    }
    return clean
  })
}

// ==================== Debounce save ====================
function debounce(key, fn, delay = 500) {
  if (_timers[key]) clearTimeout(_timers[key])
  _timers[key] = setTimeout(fn, delay)
}

function debounceSavePanels() {
  debounce('panels', () => {
    if (!props.projectId) return
    comicDramaApi
      .updatePanels(props.projectId, cleanPanels(props.panels))
      .catch(() => { /* silent */ })
  }, 500)
}

// Re-fetch panels from server to ensure display updates
async function refreshPanels() {
  if (!props.projectId) return
  try {
    const fresh = await comicDramaApi.get(props.projectId)
    if (fresh?.panels) {
      emit('update:panels', fresh.panels.map(p => ({ ...p, _imageLoading: false })))
    }
  } catch { /* silent */ }
}

// ==================== Panel operations ====================
function addPanel() {
  const newPanels = [
    ...props.panels,
    {
      sequence: props.panels.length + 1,
      sceneDescription: '',
      duration: 3,
      transition: 'cut',
      emotion: 'neutral',
      dialogues: [],
      generatedImagePath: null,
      generatedVideoPath: null,
      generatedAudioPaths: [],
      _imageLoading: false,
      _videoLoading: false,
    },
  ]
  emit('update:panels', newPanels)
  nextTick(() => {
    selectedIdx.value = newPanels.length - 1
    debounceSavePanels()
  })
}

async function deletePanel(idx) {
  try {
    await ElMessageBox.confirm('确定删除该分镜？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const newPanels = [...props.panels]
    newPanels.splice(idx, 1)
    // Re-sequence
    newPanels.forEach((p, i) => {
      p.sequence = i + 1
    })
    emit('update:panels', newPanels)
    if (selectedIdx.value >= newPanels.length) {
      selectedIdx.value = Math.max(0, newPanels.length - 1)
    }
    debounceSavePanels()
  } catch {
    // cancelled
  }
}

// ==================== Image generation ====================
async function generateImage(idx) {
  const panel = props.panels[idx]
  if (!panel || !props.projectId) return

  panel._imageLoading = true
  try {
    const res = await comicDramaApi.generatePanelImage(props.projectId, {
      panel_index: idx,
      scene_description: panel.sceneDescription,
    })
    if (res && res.stub) {
      ElMessage.info('图片生成中，请稍后刷新查看')
    } else {
      await refreshPanels()
    }
    ElMessage.success('分镜图片生成完成')
  } catch (e) {
    ElMessage.error('图片生成失败')
  } finally {
    panel._imageLoading = false
  }
}

async function handleImageUpload(file, idx) {
  if (!file || !file.raw) return
  const panel = props.panels[idx]
  if (!panel || !props.projectId) return

  panel._imageLoading = true
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    await comicDramaApi.uploadPanelImage(props.projectId, idx, formData)
    await refreshPanels()
    ElMessage.success('图片上传成功')
  } catch (e) {
    ElMessage.error('图片上传失败')
  } finally {
    panel._imageLoading = false
  }
}

// ==================== Video generation ====================
async function generateVideo(idx) {
  const panel = props.panels[idx]
  if (!panel || !props.projectId) return

  panel._videoLoading = true
  try {
    await comicDramaApi.generatePanelVideo(props.projectId, {
      panel_index: idx,
      duration: panel.duration || 3,
    })
    await refreshPanels()
    ElMessage.success('视频生成完成')
  } catch (e) {
    ElMessage.error('视频生成失败')
  } finally {
    panel._videoLoading = false
  }
}

// ==================== Audio generation ====================
async function generateAudio(panelIdx, dialogueIdx, text) {
  const panel = props.panels[panelIdx]
  if (!panel || !props.projectId || !text) return

  if (panel.dialogues[dialogueIdx]) {
    panel.dialogues[dialogueIdx]._audioLoading = true
  }
  try {
    await comicDramaApi.generatePanelAudio(props.projectId, {
      panel_index: panelIdx,
      text,
    })
    await refreshPanels()
    ElMessage.success('语音生成完成')
  } catch (e) {
    ElMessage.error('语音生成失败')
  } finally {
    if (panel.dialogues[dialogueIdx]) {
      panel.dialogues[dialogueIdx]._audioLoading = false
    }
  }
}

// ==================== BGM ====================
function saveBgmConfig() {
  if (!props.projectId) return
  debounce('bgm', () => {
    const config = {
      bgmId: bgmId.value,
      volume: bgmVolume.value,
    }
    comicDramaApi
      .updateBgmConfig(props.projectId, config)
      .then(() => {
        emit('update:project', { bgmConfig: config })
      })
      .catch(() => {
        ElMessage.error('保存BGM配置失败')
      })
  }, 300)
}

// ==================== Compose ====================
async function composeVideo() {
  if (!props.projectId) return

  composing.value = true
  try {
    await comicDramaApi.compose(props.projectId)
    ElMessage.success('合成任务已提交')
    // Reload project to get updated output videos
    const data = await comicDramaApi.get(props.projectId)
    if (data) {
      emit('update:project', data)
    }
  } catch (e) {
    ElMessage.error('合成失败')
  } finally {
    composing.value = false
  }
}

// ==================== Output videos ====================
function playOutputVideo(vid) {
  const path = vid.path || vid.webPath || vid.web_path || vid
  if (path) {
    outputVideoUrl.value = assetUrl(path)
    showOutputDialog.value = true
  }
}

// ==================== Cleanup ====================
onUnmounted(() => {
  Object.values(_timers).forEach((t) => clearTimeout(t))
})
</script>

<style scoped>
.comic-storyboard {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.main-area {
  flex: 1;
  display: flex;
  gap: 12px;
  overflow: hidden;
  min-height: 0;
}

/* Left panel - storyboard grid */
.left-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 10px;
  padding: 10px;
  overflow-y: auto;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.panel-card {
  border: 2px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  overflow: hidden;
}

.panel-card:hover { border-color: var(--el-border-color); }

.panel-card.selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}

.panel-thumb {
  position: relative;
  aspect-ratio: 16 / 9;
  background: var(--el-fill-color-lighter);
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-img { width: 100%; height: 100%; object-fit: cover; }
.thumb-placeholder { color: var(--el-text-color-placeholder); }

.panel-seq {
  position: absolute; top: 3px; left: 3px;
  background: rgba(0,0,0,0.6); color: #fff;
  font-size: 10px; padding: 0 5px; border-radius: 3px;
}

.panel-duration {
  position: absolute; bottom: 3px; right: 3px;
  background: rgba(0,0,0,0.6); color: #fff;
  font-size: 10px; padding: 0 5px; border-radius: 3px;
}

.panel-status {
  position: absolute; top: 3px; right: 3px;
  font-size: 10px; padding: 0 5px; border-radius: 3px; color: #fff;
}
.status-done { background: var(--el-color-success); }
.status-image { background: var(--el-color-primary); }

.add-card {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 4px;
  border-style: dashed;
  color: var(--el-text-color-secondary);
  font-size: 12px; min-height: 50px; aspect-ratio: auto;
}
.add-card:hover { border-color: var(--el-color-primary-light-5); color: var(--el-color-primary); }

.total-duration {
  margin-top: 8px; font-size: 12px;
  color: var(--el-text-color-secondary); text-align: center;
}

/* Right panel - editor */
.right-panel {
  flex: 1;
  background: var(--el-bg-color);
  border-radius: 10px;
  padding: 12px;
  overflow-y: auto;
  min-width: 0;
}

.empty-state {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; color: var(--el-text-color-placeholder);
}
.empty-state p { margin: 0; font-size: 14px; }

.editor-section {
  display: flex; flex-direction: column; gap: 8px;
}

.section-title {
  margin: 0; font-size: 14px; font-weight: 600;
  color: var(--el-text-color-primary);
}

/* Editor body: image left, fields right */
.editor-body {
  display: flex; gap: 12px; min-height: 0;
}

.editor-image-col {
  width: 45%; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 6px;
}

.image-preview {
  flex: 1; min-height: 0;
  border-radius: 6px; overflow: hidden;
  background: var(--el-fill-color-lighter);
  cursor: pointer; display: flex;
  align-items: center; justify-content: center;
}
.image-preview:hover { opacity: 0.9; }
.image-preview img {
  width: 100%; height: 100%;
  max-height: 320px; object-fit: contain;
}

.image-empty {
  flex: 1; min-height: 120px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 4px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  color: var(--el-text-color-placeholder); font-size: 12px;
}

.image-actions { display: flex; gap: 6px; }

.editor-fields-col {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 8px;
}

/* Parameters inline */
.params-row {
  display: flex; gap: 10px; flex-wrap: wrap;
}

.param-item { display: flex; flex-direction: column; gap: 2px; }
.param-item > label { font-size: 11px; color: var(--el-text-color-secondary); }

/* Dialogue */
.dialogue-list { display: flex; flex-direction: column; gap: 4px; }

.dialogue-item {
  padding: 6px 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 5px;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}

.dialogue-text {
  flex: 1; font-size: 13px;
  color: var(--el-text-color-regular); line-height: 1.3;
}

.audio-player audio { width: 100%; height: 28px; }

.empty-hint-inline {
  font-size: 12px; color: var(--el-text-color-placeholder);
}

/* Bottom actions */
.bottom-actions {
  display: flex; gap: 8px; align-items: center;
}

/* Video preview */
.video-preview {
  border-radius: 6px; overflow: hidden; background: #000;
}
.video-preview video { width: 100%; max-height: 240px; }

/* Bottom bar */
.bottom-bar {
  flex-shrink: 0; margin-top: 10px;
  background: var(--el-bg-color);
  border-radius: 10px; padding: 8px 14px;
}

.bottom-bar-inner {
  display: flex; align-items: center; gap: 12px;
}

.bgm-section {
  display: flex; align-items: center; gap: 8px;
  flex: 1; min-width: 0;
}

.bgm-label {
  font-size: 13px; font-weight: 600;
  color: var(--el-text-color-secondary); white-space: nowrap;
}

.volume-control { display: flex; align-items: center; gap: 4px; }
.volume-control > label { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; }

.bgm-player { height: 28px; max-width: 180px; }

.output-section { display: flex; align-items: center; gap: 6px; }
.output-label { font-size: 12px; color: var(--el-text-color-secondary); }

/* Preview dialog */
.preview-dialog :deep(.el-dialog__body) {
  padding: 0; display: flex; justify-content: center;
}
.preview-image {
  max-width: 80vw; max-height: 80vh;
  object-fit: contain; border-radius: 4px;
}
</style>

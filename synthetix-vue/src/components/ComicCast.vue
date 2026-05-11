<template>
  <div class="comic-cast">
    <div class="cast-columns">
      <!-- Left column: Characters (60%) -->
      <div class="cast-col cast-col-left">
        <div class="col-header">
          <span class="col-title">角色 ({{ pureCharacters.length }})</span>
          <el-button size="small" type="primary" @click="addCharacter">
            <el-icon><Plus /></el-icon> 添加角色
          </el-button>
        </div>
        <div class="col-body">
          <div
            v-for="(char, idx) in pureCharacters"
            :key="char._localIdx"
            class="character-card"
            :class="{ expanded: expandedCharIdx === idx }"
          >
            <!-- Collapsed header: thumbnail + name -->
            <div class="char-header" @click="toggleExpand(idx)">
              <div class="char-thumb" @click.stop="char.referenceImage && openPreview(assetUrl(char.referenceImage))">
                <img
                  v-if="char.referenceImage"
                  :src="assetUrl(char.referenceImage)"
                  alt=""
                  class="clickable-img"
                />
                <el-icon v-else :size="24" class="thumb-placeholder"><User /></el-icon>
              </div>
              <span class="char-name-display">{{ char.name || '未命名角色' }}</span>
              <el-icon class="expand-icon" :class="{ rotated: expandedCharIdx === idx }">
                <ArrowDown />
              </el-icon>
            </div>

            <!-- Expanded edit area -->
            <div v-if="expandedCharIdx === idx" class="char-edit" @click.stop>
              <div class="char-edit-row">
                <div class="char-thumb-large" @click="char.referenceImage && openPreview(assetUrl(char.referenceImage))">
                  <img
                    v-if="char.referenceImage"
                    :src="assetUrl(char.referenceImage)"
                    alt=""
                    class="clickable-img"
                  />
                  <el-icon v-else :size="32" class="thumb-placeholder"><User /></el-icon>
                </div>
                <div class="char-edit-fields">
                  <el-input
                    v-model="char.name"
                    placeholder="角色名称"
                    size="small"
                    class="field-name"
                    @input="debounceSaveCharacters"
                  />
                  <el-input
                    v-model="char.appearance"
                    type="textarea"
                    :rows="2"
                    placeholder="外貌描述"
                    size="small"
                    @input="debounceSaveCharacters"
                  />
                  <el-input
                    v-model="char.personality"
                    placeholder="性格特征"
                    size="small"
                    @input="debounceSaveCharacters"
                  />
                  <el-input
                    v-model="char.voiceDescription"
                    placeholder="音色描述（用于 TTS 语音生成）"
                    size="small"
                    @input="debounceSaveCharacters"
                  />
                </div>
              </div>
              <div class="char-actions">
                <el-button
                  size="small"
                  :loading="imageLoadingMap[char._localIdx] || false"
                  @click="generateCharImage(idx)"
                >
                  AI 生成图
                </el-button>
                <el-button size="small" @click="triggerUploadCharImage(idx)">
                  上传图片
                </el-button>
                <input
                  :ref="el => setCharInputRef(idx, el)"
                  type="file"
                  accept="image/*"
                  style="display: none"
                  @change="onCharImageSelected(idx, $event)"
                />
                <el-button size="small" type="danger" text @click="removeCharacter(idx)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <div v-if="pureCharacters.length === 0" class="empty-hint">
            还没有角色，点击上方按钮添加
          </div>
        </div>
      </div>

      <!-- Right column: Scenes (40%) -->
      <div class="cast-col cast-col-right">
        <div class="col-header">
          <span class="col-title">场景库</span>
          <el-button size="small" type="primary" @click="showAddScene = true">
            <el-icon><Plus /></el-icon> 添加场景
          </el-button>
        </div>
        <div class="col-body">
          <div class="scene-grid">
            <div
              v-for="(scene, idx) in scenes"
              :key="scene._localIdx"
              class="scene-card"
            >
              <div class="scene-thumb" @click="scene.image && openPreview(assetUrl(scene.image))">
                <img
                  v-if="scene.image"
                  :src="assetUrl(scene.image)"
                  alt=""
                  class="clickable-img"
                />
                <el-icon v-else :size="24" class="thumb-placeholder"><Picture /></el-icon>
              </div>
              <div class="scene-info">
                <span class="scene-desc">{{ scene.description || '未描述场景' }}</span>
              </div>
              <div class="scene-actions">
                <el-button
                  size="small"
                  :loading="imageLoadingMap[scene._localIdx] || false"
                  @click="generateSceneImage(idx)"
                >
                  AI 生成
                </el-button>
                <el-button size="small" @click="triggerUploadSceneImage(idx)">
                  上传
                </el-button>
                <input
                  :ref="el => setSceneInputRef(idx, el)"
                  type="file"
                  accept="image/*"
                  style="display: none"
                  @change="onSceneImageSelected(idx, $event)"
                />
                <el-button size="small" type="danger" text @click="removeScene(idx)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <div v-if="scenes.length === 0 && !showAddScene" class="empty-hint">
            还没有场景，点击上方按钮添加
          </div>

          <!-- Add scene form -->
          <div v-if="showAddScene" class="add-scene-form">
            <el-input
              v-model="newSceneDesc"
              type="textarea"
              :rows="2"
              placeholder="场景描述（如：深夜的森林、城市天台...）"
              size="small"
            />
            <div class="add-scene-actions">
              <el-button
                size="small"
                @click="generateNewSceneImage"
                :loading="newSceneLoading"
              >
                AI 生成
              </el-button>
              <el-button size="small" @click="triggerUploadNewSceneImage">
                上传图片
              </el-button>
              <input
                ref="newSceneInputRef"
                type="file"
                accept="image/*"
                style="display: none"
                @change="onNewSceneImageSelected"
              />
              <el-button size="small" type="primary" @click="confirmAddScene">
                确定
              </el-button>
              <el-button size="small" @click="cancelAddScene">取消</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Image preview dialog -->
    <el-dialog
      v-model="previewVisible"
      :show-close="true"
      width="auto"
      class="preview-dialog"
      @close="previewVisible = false"
    >
      <img :src="previewUrl" class="preview-image" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete, User, Picture, ArrowDown } from '@element-plus/icons-vue'
import { comicDramaApi } from '@/api/modules'
import { assetUrl } from '@/api/modules'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  project: { type: Object, default: () => ({}) },
  characters: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:characters', 'refresh'])

// ==================== Local state ====================
const expandedCharIdx = ref(-1)
const showAddScene = ref(false)
const newSceneDesc = ref('')
const newSceneLoading = ref(false)
const newSceneInputRef = ref(null)
const imageLoadingMap = reactive({})
const previewVisible = ref(false)
const previewUrl = ref('')

function openPreview(url) {
  previewUrl.value = url
  previewVisible.value = true
}

// File input refs stored by index
const charInputRefs = {}
const sceneInputRefs = {}

// Debounce timers
const _saveTimers = {}

// Local index counter for stable keys
let _localIdxCounter = 0
function assignLocalIdx(item) {
  if (item._localIdx === undefined) {
    item._localIdx = ++_localIdxCounter
  }
  return item
}

// ==================== Computed ====================
const pureCharacters = computed(() =>
  props.characters.filter(c => c._type !== 'scene').map(assignLocalIdx)
)

const scenes = computed(() =>
  props.characters.filter(c => c._type === 'scene').map(assignLocalIdx)
)

// ==================== Helpers ====================
function setCharInputRef(idx, el) {
  if (el) charInputRefs[idx] = el
}

function setSceneInputRef(idx, el) {
  if (el) sceneInputRefs[idx] = el
}

function buildUpdatedCharacters(newChars) {
  emit('update:characters', newChars)
  debounceSaveCharacters()
}

function debounceSaveCharacters() {
  if (!props.projectId) return
  if (_saveTimers.characters) clearTimeout(_saveTimers.characters)
  _saveTimers.characters = setTimeout(async () => {
    try {
      // Send without internal _localIdx and _type marker
      const cleanChars = props.characters.map(c => {
        const { _localIdx, ...rest } = c
        return rest
      })
      await comicDramaApi.update(props.projectId, { characters: cleanChars })
    } catch {
      // silent
    }
  }, 300)
}

// ==================== Character actions ====================
function addCharacter() {
  const newChar = {
    name: '',
    appearance: '',
    personality: '',
    voiceDescription: '',
    referenceImage: '',
    _localIdx: ++_localIdxCounter,
  }
  const updated = [...props.characters, newChar]
  emit('update:characters', updated)
  expandedCharIdx.value = pureCharacters.value.length - 1
}

function removeCharacter(idx) {
  const char = pureCharacters.value[idx]
  const updated = props.characters.filter(c => c._localIdx !== char._localIdx)
  expandedCharIdx.value = -1
  buildUpdatedCharacters(updated)
}

function toggleExpand(idx) {
  expandedCharIdx.value = expandedCharIdx.value === idx ? -1 : idx
}

async function generateCharImage(idx) {
  const char = pureCharacters.value[idx]
  if (!props.projectId) return
  imageLoadingMap[char._localIdx] = true
  try {
    const origIdx = findOriginalCharIndex(char._localIdx)
    const res = await comicDramaApi.generateCharRefImage(props.projectId, origIdx)
    if (res?.stub) {
      ElMessage.warning('图片生成服务暂未就绪')
      return
    }
    await refreshCharacters()
    ElMessage.success('角色图片生成成功')
  } catch (e) {
    ElMessage.error('生成失败：' + (e.message || '未知错误'))
  } finally {
    imageLoadingMap[char._localIdx] = false
  }
}

function triggerUploadCharImage(idx) {
  const input = charInputRefs[idx]
  if (input) input.click()
}

async function onCharImageSelected(idx, event) {
  const file = event.target.files?.[0]
  if (!file) return
  const char = pureCharacters.value[idx]
  imageLoadingMap[char._localIdx] = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const origIdx = findOriginalCharIndex(char._localIdx)
    await comicDramaApi.uploadCharRefImage(props.projectId, origIdx, formData)
    await refreshCharacters()
    ElMessage.success('图片上传成功')
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    imageLoadingMap[char._localIdx] = false
    event.target.value = ''
  }
}

// ==================== Scene actions ====================
function generateSceneImage(idx) {
  const scene = scenes.value[idx]
  const origIdx = findOriginalCharIndex(scene._localIdx)
  imageLoadingMap[scene._localIdx] = true

  comicDramaApi.generateCharRefImage(props.projectId, origIdx)
    .then(async res => {
      if (res?.stub) {
        ElMessage.warning('图片生成服务暂未就绪')
        return
      }
      await refreshCharacters()
      ElMessage.success('场景图片生成成功')
    })
    .catch(e => {
      ElMessage.error('生成失败：' + (e.message || '未知错误'))
    })
    .finally(() => {
      imageLoadingMap[scene._localIdx] = false
    })
}

function triggerUploadSceneImage(idx) {
  const input = sceneInputRefs[idx]
  if (input) input.click()
}

async function onSceneImageSelected(idx, event) {
  const file = event.target.files?.[0]
  if (!file) return
  const scene = scenes.value[idx]
  const origIdx = findOriginalCharIndex(scene._localIdx)
  imageLoadingMap[scene._localIdx] = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await comicDramaApi.uploadCharRefImage(props.projectId, origIdx, formData)
    await refreshCharacters()
    ElMessage.success('场景图片上传成功')
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    imageLoadingMap[scene._localIdx] = false
    event.target.value = ''
  }
}

function removeScene(idx) {
  const scene = scenes.value[idx]
  const updated = props.characters.filter(c => c._localIdx !== scene._localIdx)
  buildUpdatedCharacters(updated)
}

function triggerUploadNewSceneImage() {
  newSceneInputRef.value?.click()
}

async function onNewSceneImageSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  newSceneLoading.value = true
  try {
    // First create the scene, then upload
    const newScene = {
      _type: 'scene',
      description: newSceneDesc.value,
      image: '',
      _localIdx: ++_localIdxCounter,
    }
    const updated = [...props.characters, newScene]
    const newOrigIdx = updated.length - 1
    emit('update:characters', updated)

    // Wait for the characters to update, then upload
    await nextTick()
    const formData = new FormData()
    formData.append('file', file)
    await comicDramaApi.uploadCharRefImage(props.projectId, newOrigIdx, formData)
    await refreshCharacters()
    showAddScene.value = false
    newSceneDesc.value = ''
    ElMessage.success('场景添加成功')
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || '未知错误'))
  } finally {
    newSceneLoading.value = false
    event.target.value = ''
  }
}

async function generateNewSceneImage() {
  if (!newSceneDesc.value.trim()) {
    ElMessage.warning('请先输入场景描述')
    return
  }
  newSceneLoading.value = true
  try {
    // Create the scene entry first
    const newScene = {
      _type: 'scene',
      description: newSceneDesc.value,
      image: '',
      _localIdx: ++_localIdxCounter,
    }
    const updated = [...props.characters, newScene]
    const newOrigIdx = updated.length - 1
    emit('update:characters', updated)
    await nextTick()

    const res = await comicDramaApi.generateCharRefImage(props.projectId, newOrigIdx)
    if (res?.stub) {
      ElMessage.warning('图片生成服务暂未就绪')
      showAddScene.value = false
      newSceneDesc.value = ''
      return
    }
    await refreshCharacters()
    showAddScene.value = false
    newSceneDesc.value = ''
    ElMessage.success('场景添加成功')
  } catch (e) {
    ElMessage.error('生成失败：' + (e.message || '未知错误'))
  } finally {
    newSceneLoading.value = false
  }
}

function confirmAddScene() {
  if (!newSceneDesc.value.trim()) {
    ElMessage.warning('请输入场景描述')
    return
  }
  const newScene = {
    _type: 'scene',
    description: newSceneDesc.value,
    image: '',
    _localIdx: ++_localIdxCounter,
  }
  const updated = [...props.characters, newScene]
  buildUpdatedCharacters(updated)
  showAddScene.value = false
  newSceneDesc.value = ''
}

function cancelAddScene() {
  showAddScene.value = false
  newSceneDesc.value = ''
}

// ==================== Utility ====================
function findOriginalCharIndex(localIdx) {
  return props.characters.findIndex(c => c._localIdx === localIdx)
}

// Backend returns full project dict with characters array.
// Normalize (Type→_type) and emit update.
function applyCharactersFromResponse(res) {
  if (!res?.characters) return false
  const normalized = res.characters.map(c => {
    if (c.Type === 'scene' || c.type === 'scene') return { ...c, _type: 'scene' }
    return c
  })
  emit('update:characters', normalized)
  return true
}

// Re-fetch project from server to ensure display updates (same as page reload)
async function refreshCharacters() {
  if (!props.projectId) return
  try {
    const fresh = await comicDramaApi.get(props.projectId)
    applyCharactersFromResponse(fresh)
  } catch { /* silent */ }
}

// Ensure all existing characters have _localIdx
watch(
  () => props.characters,
  (chars) => {
    chars.forEach(c => {
      if (c._localIdx === undefined) {
        c._localIdx = ++_localIdxCounter
      }
    })
  },
  { immediate: true, deep: false }
)

// Cleanup on unmount
onUnmounted(() => {
  Object.values(_saveTimers).forEach(t => clearTimeout(t))
})
</script>

<style scoped>
.comic-cast {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cast-columns {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
}

.cast-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.cast-col-left {
  flex: 3;
  min-width: 0;
}

.cast-col-right {
  flex: 2;
  min-width: 0;
}

.col-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  flex-shrink: 0;
}

.col-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--el-text-color-primary);
}

.col-body {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

/* Character cards */
.character-card {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  margin-bottom: 8px;
  transition: all 0.2s;
}

.character-card:hover {
  background: var(--el-fill-color);
}

.char-header {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  gap: 10px;
}

.char-thumb {
  width: 56px;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--el-fill-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.char-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  color: var(--el-text-color-placeholder);
}

.char-name-display {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.expand-icon {
  transition: transform 0.2s;
  color: var(--el-text-color-secondary);
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

/* Expanded edit */
.char-edit {
  padding: 0 12px 12px;
}

.char-edit-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.char-thumb-large {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-fill-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.char-thumb-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.char-edit-fields {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-name {
  font-weight: 500;
}

.char-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
  flex-wrap: wrap;
}

/* Scene grid */
.scene-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-card {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.scene-card:hover {
  background: var(--el-fill-color);
}

.scene-thumb {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--el-fill-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scene-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scene-info {
  flex: 1;
  min-width: 0;
}

.scene-desc {
  font-size: 13px;
  color: var(--el-text-color-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.scene-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* Add scene form */
.add-scene-form {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 12px;
  margin-top: 10px;
}

.add-scene-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

/* Empty hint */
.empty-hint {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 24px 0;
}

/* Clickable images */
.clickable-img {
  cursor: pointer;
  transition: opacity 0.2s;
}
.clickable-img:hover {
  opacity: 0.8;
}

/* Preview dialog */
.preview-dialog :deep(.el-dialog__body) {
  padding: 0;
  display: flex;
  justify-content: center;
}
.preview-image {
  max-width: 80vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 4px;
}

</style>

<template>
  <div class="comic-drama">
    <!-- 加载中 -->
    <div v-if="loading" class="loading-view">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 未创建项目：直接创建并进入故事页 -->
    <div v-else-if="!projectId" class="welcome-view">
      <div class="welcome-content">
        <h2>漫剧创作</h2>
        <p>输入你的故事，AI 帮你生成分镜漫剧</p>
        <el-button type="primary" size="large" @click="quickCreate" :loading="creating">
          开始创作
        </el-button>
      </div>
    </div>

    <!-- 已有项目：3 页导航 -->
    <template v-else>
      <!-- 顶部栏：项目名 + 导航 -->
      <div class="top-bar">
        <div class="top-bar-left">
          <span class="project-name" @click="openRenameDialog">{{ project.name }}</span>
        </div>
        <div class="page-nav">
          <div
            v-for="(page, idx) in pages"
            :key="idx"
            class="page-nav-item"
            :class="{ active: currentPage === idx }"
            @click="currentPage = idx"
          >
            {{ page.label }}
          </div>
        </div>
        <div class="top-bar-right">
          <el-tag size="small" :type="statusTagType">{{ project.status === 'completed' ? '已完成' : '创作中' }}</el-tag>
        </div>
      </div>

      <!-- 页面内容 -->
      <div class="page-content">
        <ComicStory
          v-show="currentPage === 0"
          :project-id="projectId"
          :project="project"
          :characters="characters"
          :panels="panels"
          @update:project="onProjectUpdate"
          @script-generated="onScriptGenerated"
        />

        <ComicCast
          v-show="currentPage === 1"
          :project-id="projectId"
          :project="project"
          :characters="characters"
          @update:characters="characters = $event"
        />

        <ComicStoryboard
          v-show="currentPage === 2"
          :project-id="projectId"
          :project="project"
          :panels="panels"
          :characters="characters"
          :bgm-list="bgmList"
          @update:panels="panels = $event"
          @update:project="onProjectUpdate"
        />
      </div>

      <!-- 重命名弹窗 -->
      <el-dialog v-model="showRenameDialog" title="重命名" width="360px">
        <el-input v-model="renameInput" maxlength="50" show-word-limit />
        <template #footer>
          <el-button @click="showRenameDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmRename">确定</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { comicDramaApi, projectApi } from '@/api/modules'
import ComicStory from './ComicStory.vue'
import ComicCast from './ComicCast.vue'
import ComicStoryboard from './ComicStoryboard.vue'

const route = useRoute()
const router = useRouter()

const pages = [
  { key: 'story', label: '故事' },
  { key: 'cast', label: '角色 & 场景' },
  { key: 'storyboard', label: '分镜 & 合成' },
]

const loading = ref(false)
const creating = ref(false)
const projectId = ref(null)
const currentPage = ref(0)
const project = reactive({
  name: '',
  status: 'draft',
  style: '动漫',
  genre: 'drama',
  scriptData: null,
  outputVideos: [],
})
const characters = ref([])
const panels = ref([])
const bgmList = ref([])

const showRenameDialog = ref(false)
const renameInput = ref('')

const statusTagType = computed(() => {
  const map = { draft: 'info', scripting: 'warning', generating: 'warning', compositing: 'warning', completed: 'success' }
  return map[project.status] || 'info'
})

// ==================== Lifecycle ====================
onMounted(async () => {
  const pid = route.query.projectId
  if (pid) {
    await loadProject(pid)
  }
  loadBgmList()
})

onUnmounted(() => {
  Object.values(_saveTimers).forEach(t => clearTimeout(t))
})

// ==================== Debounce save ====================
const _saveTimers = {}
function debounceSave(field, value, delay = 300) {
  if (!projectId.value) return
  if (_saveTimers[field]) clearTimeout(_saveTimers[field])
  _saveTimers[field] = setTimeout(async () => {
    try {
      await comicDramaApi.update(projectId.value, { [field]: value })
    } catch { /* silent */ }
  }, delay)
}

watch(currentPage, (val) => debounceSave('current_step', val))

// ==================== Project ops ====================
async function quickCreate() {
  creating.value = true
  try {
    const timestamp = new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    const res = await comicDramaApi.create({ name: `漫剧 ${timestamp}` })
    projectId.value = res.id
    await loadProject(res.id)
    router.replace({ path: '/comic-drama', query: { projectId: res.id } })
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

// Backend convert_keys_to_camel turns _type into Type, normalize back
function normalizeCharacters(chars) {
  if (!chars) return []
  return chars.map(c => {
    if (c.Type === 'scene' || c.type === 'scene') {
      return { ...c, _type: 'scene' }
    }
    return c
  })
}

async function loadProject(pid) {
  loading.value = true
  try {
    const data = await comicDramaApi.get(pid)
    projectId.value = data.id
    Object.assign(project, data)
    if (data.characters) characters.value = normalizeCharacters(data.characters)
    if (data.panels) panels.value = data.panels.map(p => ({ ...p, _imageLoading: false }))
    if (data.scriptData) project.scriptData = data.scriptData
    if (data.currentStep !== undefined) {
      currentPage.value = Math.min(data.currentStep, 2)
    }
  } catch (e) {
    ElMessage.error('加载项目失败')
  } finally {
    loading.value = false
  }
}

function onProjectUpdate(updates) {
  Object.assign(project, updates)
}

function onScriptGenerated(data) {
  Object.assign(project, data)
  if (data.characters) characters.value = normalizeCharacters(data.characters)
  if (data.panels) panels.value = data.panels.map(p => ({ ...p, _imageLoading: false }))
  if (data.scriptData) project.scriptData = data.scriptData

  // Extract unique scene descriptions from panels and populate scene library
  if (data.panels?.length) {
    const existingDescs = new Set(
      characters.value
        .filter(c => c._type === 'scene')
        .map(c => (c.description || '').trim())
        .filter(Boolean)
    )
    const sceneDescs = []
    const seen = new Set()
    for (const p of data.panels) {
      const desc = (p.sceneDescription || p.backgroundDescription || '').trim()
      if (desc && !seen.has(desc) && !existingDescs.has(desc)) {
        seen.add(desc)
        sceneDescs.push(desc)
      }
    }
    if (sceneDescs.length > 0) {
      const newScenes = sceneDescs.map(desc => ({
        _type: 'scene',
        description: desc,
        image: '',
      }))
      characters.value = [...characters.value, ...newScenes]
      saveCharacters()
    }
  }
}

function saveCharacters() {
  if (!projectId.value) return
  const cleanChars = characters.value.map(c => {
    const { _localIdx, ...rest } = c
    return rest
  })
  comicDramaApi.update(projectId.value, { characters: cleanChars }).catch(() => {})
}

function openRenameDialog() {
  renameInput.value = project.name
  showRenameDialog.value = true
}

async function confirmRename() {
  if (!renameInput.value.trim()) return
  try {
    await comicDramaApi.update(projectId.value, { name: renameInput.value.trim() })
    project.name = renameInput.value.trim()
    showRenameDialog.value = false
    ElMessage.success('重命名成功')
  } catch (e) {
    ElMessage.error('重命名失败')
  }
}

async function loadBgmList() {
  try {
    const data = await projectApi.listBgm()
    bgmList.value = data?.items || data || []
  } catch { /* ignore */ }
}
</script>

<style scoped>
.comic-drama {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.loading-view, .welcome-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  color: var(--el-text-color-secondary);
}

.welcome-content {
  text-align: center;
}
.welcome-content h2 { margin: 0 0 8px; font-size: 22px; color: var(--el-text-color-primary); }
.welcome-content p { margin: 0 0 24px; color: var(--el-text-color-secondary); }

/* Top bar */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--el-bg-color);
  border-radius: 10px;
  gap: 16px;
  flex-shrink: 0;
}
.top-bar-left { display: flex; align-items: center; gap: 8px; }
.top-bar-divider { color: var(--el-border-color); }
.project-name {
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}
.project-name:hover { background: var(--el-fill-color); }
.top-bar-right { display: flex; align-items: center; gap: 8px; }

/* Page navigation */
.page-nav {
  display: flex;
  gap: 2px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 3px;
}
.page-nav-item {
  padding: 6px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  color: var(--el-text-color-secondary);
}
.page-nav-item:hover { color: var(--el-text-color-primary); }
.page-nav-item.active {
  background: var(--el-color-primary);
  color: #fff;
}

/* Page content */
.page-content {
  flex: 1;
  overflow: hidden;
  margin-top: 12px;
}
</style>

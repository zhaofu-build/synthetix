<template>
  <div class="unified-editor">
    <!-- ==================== 欢迎/选项目视图 ==================== -->
    <template v-if="!store.isLoaded">
      <div class="welcome-view">
        <div class="welcome-card">
          <h2 class="welcome-title">AI 剪辑工作台</h2>
          <p class="welcome-desc">选择或创建一个项目开始创作</p>

          <!-- 模式选择入口 -->
          <div class="mode-cards">
            <div class="mode-card mode-card-edit" @click="openCreate">
              <span class="mode-card-icon">🎬</span>
              <span class="mode-card-title">AI 剪辑</span>
              <span class="mode-card-desc">对话式 / 工作流视频剪辑</span>
            </div>
            <div class="mode-card mode-card-comic" @click="openComicCreate">
              <span class="mode-card-icon">🎨</span>
              <span class="mode-card-title">漫剧制作</span>
              <span class="mode-card-desc">AI 分镜脚本 · 角色配音 · 合成</span>
            </div>
          </div>

          <div v-if="allProjects.length" class="project-list-section">
            <!-- 今日 -->
            <template v-if="todayProjects.length">
              <el-divider>今日编辑</el-divider>
              <div class="project-grid">
                <div v-for="row in todayProjects" :key="row._key" class="project-card"
                     @click="openProject(row)">
                  <div class="project-card-header">
                    <span class="project-card-name">{{ row.name }}</span>
                    <div class="project-card-tags">
                      <el-tag size="small" :type="row._type === 'comic' ? 'warning' : 'primary'" class="type-tag">{{ row._type === 'comic' ? '漫剧' : '剪辑' }}</el-tag>
                      <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
                    </div>
                  </div>
                  <div class="project-card-meta">
                    <span v-if="row.duration">{{ row.duration }}s</span>
                    <span>{{ formatTime(row.updatedAt || row.updated_at) }}</span>
                  </div>
                  <div class="project-card-footer">
                    <el-button text size="small" @click.stop="openProject(row)">打开</el-button>
                    <el-button text size="small" @click.stop="exportProject(row)">导出</el-button>
                    <el-button text size="small" type="danger" @click.stop="deleteProject(row)">删除</el-button>
                  </div>
                </div>
              </div>
            </template>
            <!-- 昨日 -->
            <template v-if="yesterdayProjects.length">
              <el-divider>昨日编辑</el-divider>
              <div class="project-grid">
                <div v-for="row in yesterdayProjects" :key="row._key" class="project-card"
                     @click="openProject(row)">
                  <div class="project-card-header">
                    <span class="project-card-name">{{ row.name }}</span>
                    <div class="project-card-tags">
                      <el-tag size="small" :type="row._type === 'comic' ? 'warning' : 'primary'" class="type-tag">{{ row._type === 'comic' ? '漫剧' : '剪辑' }}</el-tag>
                      <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
                    </div>
                  </div>
                  <div class="project-card-meta">
                    <span v-if="row.duration">{{ row.duration }}s</span>
                    <span>{{ formatTime(row.updatedAt || row.updated_at) }}</span>
                  </div>
                  <div class="project-card-footer">
                    <el-button text size="small" @click.stop="openProject(row)">打开</el-button>
                    <el-button text size="small" @click.stop="exportProject(row)">导出</el-button>
                    <el-button text size="small" type="danger" @click.stop="deleteProject(row)">删除</el-button>
                  </div>
                </div>
              </div>
            </template>
            <!-- 更早 -->
            <template v-if="olderProjects.length">
              <el-divider>更早</el-divider>
              <div class="project-grid">
                <div v-for="row in olderProjects" :key="row._key" class="project-card"
                     @click="openProject(row)">
                  <div class="project-card-header">
                    <span class="project-card-name">{{ row.name }}</span>
                    <div class="project-card-tags">
                      <el-tag size="small" :type="row._type === 'comic' ? 'warning' : 'primary'" class="type-tag">{{ row._type === 'comic' ? '漫剧' : '剪辑' }}</el-tag>
                      <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
                    </div>
                  </div>
                  <div class="project-card-meta">
                    <span v-if="row.duration">{{ row.duration }}s</span>
                    <span>{{ formatTime(row.updatedAt || row.updated_at) }}</span>
                  </div>
                  <div class="project-card-footer">
                    <el-button text size="small" @click.stop="openProject(row)">打开</el-button>
                    <el-button text size="small" @click.stop="exportProject(row)">导出</el-button>
                    <el-button text size="small" type="danger" @click.stop="deleteProject(row)">删除</el-button>
                  </div>
                </div>
              </div>
            </template>
          </div>
          <el-skeleton v-else-if="listLoading" :rows="5" animated />
          <el-empty v-else description="暂无项目，点击上方卡片创建" />
        </div>
      </div>
    </template>

    <!-- ==================== 创建AI剪辑项目弹窗 ==================== -->
    <el-dialog v-model="showCreateDialog" title="创建 AI 剪辑项目" width="460" :close-on-click-modal="false">
      <!-- 快速模板 -->
      <div class="template-quick-pick">
        <div class="template-quick-title">快速模板</div>
        <div class="template-quick-grid">
          <div v-for="tpl in quickTemplates" :key="tpl.name" class="template-quick-card"
               :class="{ active: selectedTemplate === tpl.name }" @click="applyQuickTemplate(tpl)">
            <span class="tq-icon">{{ tpl.icon }}</span>
            <span class="tq-name">{{ tpl.name }}</span>
          </div>
        </div>
      </div>
      <el-divider style="margin: 12px 0" />
      <el-form @submit.prevent="confirmCreate">
        <el-form-item label="项目名称">
          <el-input ref="nameInput" v-model="projectName" placeholder="请输入项目名称"
                    @keydown.enter="confirmCreate" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="projectDesc" type="textarea" :rows="2" placeholder="可选描述" />
        </el-form-item>
        <div class="config-row">
          <el-form-item label="项目类型">
            <el-select v-model="projectType" placeholder="选择类型">
              <el-option label="短视频" value="short" />
              <el-option label="长视频" value="long" />
              <el-option label="混剪" value="mix" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标平台">
            <el-select v-model="projectPlatform" placeholder="选择平台">
              <el-option label="不限" value="" />
              <el-option label="抖音 (9:16)" value="douyin" />
              <el-option label="B站 (16:9)" value="bilibili" />
              <el-option label="YouTube (16:9)" value="youtube" />
              <el-option label="小红书 (3:4)" value="xiaohongshu" />
            </el-select>
          </el-form-item>
        </div>
        <div v-if="createError" class="el-form-item__error">{{ createError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="confirmCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- ==================== 编辑器主布局 ==================== -->
    <template v-if="store.isLoaded">
      <div ref="editorBodyRef" class="editor-body"
           :style="gridStyle(true, store.rightPanelCollapsed)">

        <!-- 中：AI 剪辑助手 -->
        <ChatSidebar />

        <!-- 右分割手柄 -->
        <div v-if="!store.rightPanelCollapsed"
             class="resize-handle"
             :class="{ active: dragging === 'right' }"
             @mousedown.prevent="onHandleDown($event, 'right')"
             @dblclick="store.toggleRightPanel()" />

        <!-- 右：素材库 / 语音 / 音乐 -->
        <div class="right-panel" :class="{ collapsed: store.rightPanelCollapsed }">
          <!-- 折叠态 -->
          <div v-if="store.rightPanelCollapsed" class="right-collapsed-bar">
            <el-button text circle @click="store.toggleRightPanel()" title="展开">
              <el-icon><DArrowLeft /></el-icon>
            </el-button>
          </div>
          <!-- 展开态 -->
          <template v-else>
            <div class="right-toolbar">
              <el-radio-group v-model="rightTab" size="small">
                <el-radio-button value="materials">素材</el-radio-button>
                <el-radio-button value="tts">音色</el-radio-button>
                <el-radio-button value="bgm">BGM</el-radio-button>
              </el-radio-group>
              <el-button text size="small" @click="store.toggleRightPanel()" title="收起">
                <el-icon><DArrowRight /></el-icon>
              </el-button>
            </div>
            <div class="right-top">
              <MaterialsPanel v-if="rightTab === 'materials'" />
              <AudioPanel v-else :initial-tab="rightTab" />
            </div>
          </template>
        </div>
      </div>
      <!-- 移动端底部导航 -->
      <MobileNav />

      <!-- 浮动 AI 按钮 -->
      <div v-if="store.isLoaded && store.rightPanelCollapsed"
           class="floating-ai" @click="store.toggleRightPanel()">
        <el-icon size="18"><DArrowLeft /></el-icon>
        <span>素材</span>
      </div>

      <!-- 底部状态栏 -->
      <StatusBar v-if="store.isLoaded" @edit-name="startEditName" />
    </template>

    <!-- 素材预览弹窗 -->
    <el-dialog v-model="showPreview" title="素材预览" width="640" top="6vh" destroy-on-close append-to-body>
      <video v-if="previewingUrl && previewingType === 'video'" :src="previewingUrl" controls style="width: 100%; max-height: 70vh" />
      <audio v-else-if="previewingUrl && previewingType === 'audio'" :src="previewingUrl" controls style="width: 100%" />
      <img v-else-if="previewingUrl && previewingType === 'image'" :src="previewingUrl" style="width: 100%; max-height: 70vh; object-fit: contain" />
      <div v-else-if="previewingUrl" style="text-align: center; padding: 40px">
        <el-button type="primary" @click="window.open(previewingUrl, '_blank')">打开文件</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, provide, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { projectApi, comicDramaApi } from '@/api/modules'
import { Plus, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import { formatTime, statusText, statusType } from '@/utils/formatUtils'
import { useResizable } from '@/utils/useResizable'
import { useHotkeys } from '@/utils/useHotkeys'
import { useUnsavedGuard } from '@/utils/useUnsavedGuard'

import ChatSidebar from './ChatSidebar.vue'
import MaterialsPanel from './MaterialsPanel.vue'
import AudioPanel from './AudioPanel.vue'
import MobileNav from './MobileNav.vue'
import StatusBar from './StatusBar.vue'

const router = useRouter()
const route = useRoute()
const store = useProjectStore()

// ==================== 可拖拽分割面板 ====================
const editorBodyRef = ref(null)
const { gridStyle, onHandleDown, dragging } = useResizable(editorBodyRef)
const rightTab = ref('materials')

// ==================== 面板快捷键 ====================
useHotkeys({
  'ctrl+b': () => store.toggleRightPanel(),
  'ctrl+s': () => { if (store.isLoaded) store.saveProject() },
  'ctrl+n': () => openCreate(),
  'ctrl+e': () => { if (store.isLoaded) exportProject({ id: store.projectId, name: store.project.name }) },
  'ctrl+,': () => document.dispatchEvent(new CustomEvent('open-settings')),
  'ctrl+z': () => document.dispatchEvent(new CustomEvent('editor-undo')),
  'ctrl+y': () => document.dispatchEvent(new CustomEvent('editor-redo')),
  'ctrl+shift+z': () => document.dispatchEvent(new CustomEvent('editor-redo')),
  'space': () => document.dispatchEvent(new CustomEvent('editor-playpause')),
  'i': () => document.dispatchEvent(new CustomEvent('editor-set-in')),
  'o': () => document.dispatchEvent(new CustomEvent('editor-set-out')),
  'delete': () => document.dispatchEvent(new CustomEvent('editor-delete')),
  'm': () => document.dispatchEvent(new CustomEvent('editor-add-marker')),
  '=': () => document.dispatchEvent(new CustomEvent('editor-zoom-in')),
  '-': () => document.dispatchEvent(new CustomEvent('editor-zoom-out')),
  'arrowleft': () => document.dispatchEvent(new CustomEvent('editor-step-back')),
  'arrowright': () => document.dispatchEvent(new CustomEvent('editor-step-forward')),
  'shift+arrowleft': () => document.dispatchEvent(new CustomEvent('editor-jump-back')),
  'shift+arrowright': () => document.dispatchEvent(new CustomEvent('editor-jump-forward')),
  'escape': () => {
    if (showPreview.value) showPreview.value = false
    if (showCreateDialog.value) showCreateDialog.value = false
  },
})

// ==================== 未保存离开提示 ====================
const { confirmLeave } = useUnsavedGuard(() => store.hasUnsavedChanges)

// ==================== 项目列表 ====================
const projectList = ref([])
const comicList = ref([])
const listLoading = ref(false)

const allProjects = computed(() => {
  const editProjects = (projectList.value || []).map(p => ({ ...p, _type: 'edit', _key: `e-${p.id}` }))
  const comicProjects = (comicList.value || []).map(p => ({ ...p, _type: 'comic', _key: `c-${p.id}` }))
  return [...editProjects, ...comicProjects].sort((a, b) => {
    const ta = new Date(a.updatedAt || a.updated_at || 0).getTime()
    const tb = new Date(b.updatedAt || b.updated_at || 0).getTime()
    return tb - ta
  })
})

const loadProjectList = async () => {
  listLoading.value = true
  try {
    const [editData, comicData] = await Promise.all([
      projectApi.list({ page: 1, page_size: 50 }).catch(() => ({ items: [] })),
      comicDramaApi.list({ page: 1, page_size: 50 }).catch(() => ({ items: [] })),
    ])
    projectList.value = editData.items || []
    comicList.value = comicData.items || []
  } catch {
    ElMessage.error('获取项目列表失败')
  } finally {
    listLoading.value = false
  }
}

const todayProjects = computed(() => {
  const now = new Date()
  return allProjects.value.filter(p => {
    const d = new Date(p.updatedAt || p.updated_at)
    return d.toDateString() === now.toDateString()
  })
})
const yesterdayProjects = computed(() => {
  const now = new Date()
  const yday = new Date(now); yday.setDate(yday.getDate() - 1)
  return allProjects.value.filter(p => {
    const d = new Date(p.updatedAt || p.updated_at)
    return d.toDateString() === yday.toDateString()
  })
})
const olderProjects = computed(() => {
  const now = new Date()
  const yday = new Date(now); yday.setDate(yday.getDate() - 1)
  return allProjects.value.filter(p => {
    const d = new Date(p.updatedAt || p.updated_at)
    return d.toDateString() !== now.toDateString() && d.toDateString() !== yday.toDateString()
  })
})

const openProject = async (row) => {
  if (row._type === 'comic') {
    router.push({ path: '/comic-drama', query: { projectId: row.id } })
    return
  }
  if (!(await confirmLeave())) return
  router.replace({ path: '/editor', query: { projectId: row.id || row.projectId } })
}

const deleteProject = async (row) => {
  try {
    await ElMessageBox.prompt(`请输入 "${row.name}" 确认删除`, '删除项目', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
      inputPattern: new RegExp(`^${row.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`),
      inputErrorMessage: '项目名称不匹配',
      type: 'warning',
    })
    if (row._type === 'comic') {
      await comicDramaApi.remove(row.id)
    } else {
      await projectApi.remove(row.id || row.projectId)
    }
    ElMessage.success('已删除')
    loadProjectList()
  } catch { /* cancelled */ }
}

const exportProject = async (row) => {
  try {
    let data
    if (row._type === 'comic') {
      const res = await comicDramaApi.get(row.id)
      data = res
    } else {
      data = await projectApi.exportProject(row.id || row.projectId)
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${row.name || 'project'}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}


// ==================== 创建项目 ====================
const showCreateDialog = ref(false)
const projectName = ref('')
const projectDesc = ref('')
const projectType = ref('short')
const projectPlatform = ref('')
const createError = ref('')
const creating = ref(false)
const nameInput = ref(null)
const selectedTemplate = ref('')

const quickTemplates = [
  { name: '短视频', icon: '🎬', type: 'short', platform: 'douyin', desc: '15-60秒竖屏短视频' },
  { name: 'Vlog', icon: '✈️', type: 'mix', platform: '', desc: '旅行/日常 Vlog 混剪' },
  { name: '教学', icon: '📚', type: 'long', platform: 'bilibili', desc: '教学视频，知识讲解' },
  { name: '产品', icon: '💎', type: 'short', platform: '', desc: '产品展示/宣传' },
  { name: '空白', icon: '📝', type: 'short', platform: '', desc: '从空白项目开始' },
]

const applyQuickTemplate = (tpl) => {
  selectedTemplate.value = tpl.name
  projectName.value = tpl.name === '空白' ? '' : `我的${tpl.name}项目`
  projectType.value = tpl.type
  projectPlatform.value = tpl.platform
  projectDesc.value = tpl.desc
}

const openCreate = () => {
  projectName.value = ''
  projectDesc.value = ''
  projectType.value = 'short'
  projectPlatform.value = ''
  createError.value = ''
  selectedTemplate.value = ''
  showCreateDialog.value = true
  nextTick(() => nameInput.value?.focus())
}

const startEditName = () => {
  if (!store.isLoaded) return
  projectName.value = store.project.name
  projectDesc.value = store.project.description || ''
  showCreateDialog.value = true
  nextTick(() => nameInput.value?.focus())
}

const openComicCreate = () => {
  router.push('/comic-drama')
}

const quickCreate = async (name) => {
  creating.value = true
  try {
    // 如果已存在同名项目，直接打开
    const existing = projectList.value.find(p => p.name === name)
    if (existing) {
      await store.loadProject(existing.id || existing.projectId)
    } else {
      await store.createProject({ name, description: '', mode: 'conversation' })
    }
    router.replace({ path: '/editor', query: { projectId: store.projectId } })
    store.refreshMaterials()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    creating.value = false
  }
}

const confirmCreate = async () => {
  const name = projectName.value.trim()
  if (!name) { createError.value = '请输入项目名称'; return }

  creating.value = true
  createError.value = ''
  try {
    await store.createProject({ name, description: projectDesc.value, mode: 'conversation' })
    showCreateDialog.value = false
    router.replace({ path: '/editor', query: { projectId: store.projectId } })
    store.refreshMaterials()
  } catch (error) {
    createError.value = error.message
  } finally {
    creating.value = false
  }
}

// ==================== 素材预览弹窗 ====================
const showPreview = ref(false)
const previewingUrl = ref('')
const previewingType = ref('video')

const openMaterialPreview = (url, fileType = 'video') => {
  previewingUrl.value = url
  previewingType.value = fileType
  showPreview.value = true
}

// provide 给子组件调用
provide('openMaterialPreview', openMaterialPreview)

// ==================== 初始化 ====================
const initFromRoute = async (projectId) => {
  if (projectId) {
    if (store.projectId === Number(projectId)) return
    await store.loadProject(Number(projectId))
    store.refreshMaterials()
  } else {
    loadProjectList()
  }
}

onMounted(() => initFromRoute(route.query.projectId))

watch(() => route.query.projectId, (newId, oldId) => {
  if (newId === oldId) return
  initFromRoute(newId)
})
</script>

<style scoped>
.unified-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* ==================== 欢迎视图 ==================== */
.welcome-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-bg-color-page);
  padding: 24px;
}

.welcome-card {
  width: 100%;
  max-width: 1200px;
  background: var(--el-bg-color);
  border-radius: 12px;
  padding: 48px 56px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.welcome-title {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  text-align: center;
}

.welcome-desc {
  margin: 0 0 32px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 15px;
}

/* 快捷入口卡片 */
.quick-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 8px;
}
.mode-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  max-width: 640px;
  margin: 0 auto 28px;
}
.mode-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 36px 24px;
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}
.mode-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}
.mode-card-edit:hover {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
}
.mode-card-comic:hover {
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-5);
}
.mode-card-icon {
  font-size: 48px;
}
.mode-card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.mode-card-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.project-list-section {
  margin-top: 4px;
}

/* 项目卡片网格 */
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.project-card {
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
  padding: 16px 18px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.project-card:hover {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.project-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  min-width: 0;
}
.project-card-tags {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.type-tag {
  border-radius: 4px;
}
.project-card-name {
  font-weight: 600;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}
.project-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.project-card-footer {
  display: flex;
  gap: 4px;
}

.config-row { display: flex; gap: 12px; }
.config-row .el-form-item { flex: 1; }

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

/* ==================== 编辑器布局 ==================== */
.layout-presets {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 4px 12px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.editor-body {
  flex: 1;
  display: grid;
  overflow: hidden;
}

/* 拖拽分割手柄 */
.resize-handle {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  z-index: 10;
  transition: background 0.15s;
}
.resize-handle:hover,
.resize-handle.active {
  background: var(--el-color-primary-light-7);
}
.resize-handle.active {
  background: var(--el-color-primary-light-5);
}

/* 响应式布局：窄屏时堆叠 */
@media (max-width: 900px) {
  .editor-body {
    grid-template-columns: 1fr !important;
    grid-template-rows: auto 1fr auto;
  }
  .resize-handle {
    display: none;
  }
  .quick-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .project-grid {
    grid-template-columns: 1fr;
  }
  .welcome-card {
    padding: 24px 20px;
  }
  .layout-presets {
    display: none;
  }
}

@media (max-width: 500px) {
  .quick-cards {
    grid-template-columns: 1fr;
  }
  .welcome-title {
    font-size: 20px;
  }
}

.right-panel {
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  overflow: hidden;
}
.right-panel.collapsed {
  width: 48px;
  min-width: 48px;
}
.right-collapsed-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 12px;
}
.right-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px 4px;
  font-weight: 600;
  font-size: 13px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.right-top {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

/* 浮动 AI 按钮 */
.floating-ai {
  position: absolute;
  bottom: 60px;
  right: 20px;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 16px;
  background: var(--el-color-primary);
  color: #fff;
  border-radius: 24px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s, box-shadow 0.2s;
}
.floating-ai:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* 列表动画 */
.list-enter-active, .list-leave-active {
  transition: all 0.3s ease;
}
.list-enter-from, .list-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
.list-move {
  transition: transform 0.3s ease;
}

/* Quick template picker */
.template-quick-pick { margin-bottom: 4px; }
.template-quick-title { font-size: 12px; font-weight: 600; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.template-quick-grid { display: flex; gap: 6px; flex-wrap: wrap; }
.template-quick-card {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 8px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  cursor: pointer; transition: all 0.15s; min-width: 64px;
}
.template-quick-card:hover { border-color: var(--el-color-primary-light-5); }
.template-quick-card.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tq-icon { font-size: 20px; }
.tq-name { font-size: 11px; font-weight: 500; }
</style>

<template>
  <div class="app-layout">
    <!-- 顶部菜单栏 -->
    <header class="top-bar">
      <!-- Logo -->
      <div class="brand" @click="goHome">
        <span class="brand-zf">ZF</span>
        <span class="brand-sep">|</span>
        <span class="brand-name">Synthetix</span>
      </div>

      <!-- 菜单项 -->
      <nav class="top-nav">
        <!-- 文件 -->
        <el-dropdown trigger="hover" @command="handleFile">
          <span class="nav-item">{{ t('nav.file') }}<el-icon class="nav-arrow"><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="new">
                <el-icon><Plus /></el-icon>{{ t('nav.newProject') }}
                <span class="menu-shortcut">Ctrl+N</span>
              </el-dropdown-item>
              <el-dropdown-item command="switch">
                <el-icon><FolderOpened /></el-icon>{{ t('nav.switchProject') }}
              </el-dropdown-item>
              <el-dropdown-item command="save" divided>
                <el-icon><Document /></el-icon>{{ t('nav.saveProject') }}
                <span class="menu-shortcut">Ctrl+S</span>
              </el-dropdown-item>
              <el-dropdown-item command="export">
                <el-icon><Download /></el-icon>{{ t('nav.exportProject') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- 工具 -->
        <el-dropdown trigger="hover" @command="openDialog">
          <span class="nav-item">{{ t('nav.tools') }}<el-icon class="nav-arrow"><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled class="menu-group-title">{{ t('mainLayout.menuGroupAi') }}</el-dropdown-item>
              <el-dropdown-item command="tts">
                <el-icon><Headset /></el-icon>{{ t('nav.tts') }}
              </el-dropdown-item>
              <el-dropdown-item command="asr">
                <el-icon><Microphone /></el-icon>{{ t('nav.asr') }}
              </el-dropdown-item>
              <el-dropdown-item command="vl">
                <el-icon><Picture /></el-icon>{{ t('nav.vl') }}
              </el-dropdown-item>
              <el-dropdown-item command="comfyAudio">
                <el-icon><Headset /></el-icon>{{ t('nav.aiSongs') }}
              </el-dropdown-item>
              <el-dropdown-item command="llmChat">
                <el-icon><ChatDotRound /></el-icon>{{ t('nav.llmChat') }}
              </el-dropdown-item>
              <el-dropdown-item divided disabled class="menu-group-title">{{ t('mainLayout.menuGroupVideo') }}</el-dropdown-item>
              <el-dropdown-item command="videoProc">
                <el-icon><VideoPlay /></el-icon>{{ t('nav.videoProcessing') }}
              </el-dropdown-item>
              <el-dropdown-item command="videoEffects">
                <el-icon><Sunny /></el-icon>{{ t('nav.videoEffects') }}
              </el-dropdown-item>
              <el-dropdown-item command="videoAnalysis">
                <el-icon><DataAnalysis /></el-icon>{{ t('nav.videoAnalysis') }}
              </el-dropdown-item>
              <el-dropdown-item divided disabled class="menu-group-title">{{ t('mainLayout.menuGroupAudio') }}</el-dropdown-item>
              <el-dropdown-item command="audioProc">
                <el-icon><Headset /></el-icon>{{ t('nav.audioProcessing') }}
              </el-dropdown-item>
              <el-dropdown-item command="advancedAudio">
                <el-icon><Headset /></el-icon>{{ t('nav.advancedAudio') }}
              </el-dropdown-item>
              <el-dropdown-item divided disabled class="menu-group-title">{{ t('mainLayout.menuGroupImage') }}</el-dropdown-item>
              <el-dropdown-item command="imageProcessing">
                <el-icon><PictureFilled /></el-icon>{{ t('nav.imageProcessing') }}
              </el-dropdown-item>
              <el-dropdown-item divided disabled class="menu-group-title">{{ t('mainLayout.menuGroupTranslation') }}</el-dropdown-item>
              <el-dropdown-item command="translation">
                <el-icon><Sort /></el-icon>{{ t('nav.translation') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- 系统管理 -->
        <el-dropdown trigger="hover" @command="openDialog">
          <span class="nav-item">{{ t('nav.system') }}<el-icon class="nav-arrow"><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="mcpManager">
                <el-icon><Connection /></el-icon>{{ t('nav.mcpManager') }}
              </el-dropdown-item>
              <el-dropdown-item command="extManager">
                <el-icon><Grid /></el-icon>{{ t('nav.extManager') }}
              </el-dropdown-item>
              <el-dropdown-item command="knowledgeBase">
                <el-icon><Notebook /></el-icon>{{ t('nav.knowledgeBase') }}
              </el-dropdown-item>
              <el-dropdown-item command="cookieManager">
                <el-icon><Present /></el-icon>{{ t('mainLayout.cookieManager') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- 设置 -->
        <span class="nav-item" @click="openDialog('settings')">
          <el-icon><Setting /></el-icon>{{ t('nav.settings') }}
        </span>

        <!-- 关于 -->
        <span class="nav-item" @click="openDialog('systemStatus')">
          <el-icon><Cpu /></el-icon>{{ t('nav.systemStatus') }}
        </span>

        <!-- 项目名（编辑器模式下显示） -->
        <template v-if="store.isLoaded">
          <span class="nav-sep">|</span>
          <span class="nav-project-name" @click="handleRename">
            <span v-if="store.hasUnsavedChanges" class="unsaved-dot"></span>
            {{ store.project.name || t('project.unnamed') }}
          </span>
          <el-button text size="small" @click="handleRename" class="nav-edit-btn">
            <el-icon><Edit /></el-icon>
          </el-button>
        </template>
      </nav>

      <!-- 全局搜索 / 面包屑 -->
      <template v-if="store.isLoaded">
        <span class="nav-sep">|</span>
        <span class="breadcrumb">
          <span class="bc-link" @click="goHome">{{ t('mainLayout.breadcrumbProject') }}</span>
          <span class="bc-sep">/</span>
          <span class="bc-current">{{ store.project.name || t('mainLayout.breadcrumbUnnamed') }}</span>
        </span>
      </template>
      <template v-else-if="isComicPage && comicProjectName">
        <span class="nav-sep">|</span>
        <span class="breadcrumb">
          <span class="bc-link" @click="goHome">{{ t('mainLayout.breadcrumbHome') }}</span>
          <span class="bc-sep">/</span>
          <span class="bc-current">{{ comicProjectName }}</span>
        </span>
      </template>
      <template v-else>
        <el-input v-model="globalSearch" :placeholder="t('mainLayout.searchProjects')" size="small" class="global-search"
                  prefix-icon="Search" clearable />
      </template>
      <!-- 右侧区域 -->
      <el-button text size="small" @click="toggleTheme" class="theme-toggle" :title="theme === 'dark' ? t('mainLayout.switchToLight') : t('mainLayout.switchToDark')">
        <el-icon><Sunny v-if="theme === 'dark'" /><Moon v-else /></el-icon>
      </el-button>
      <span class="top-version">v3.0</span>
      <el-button v-if="updateAvailable" text size="small" type="warning" class="update-btn" @click="doUpdate">
        <el-icon><Upload /></el-icon> {{ updateInfo || t('mainLayout.newVersionAvailable') }}
      </el-button>
    </header>

    <!-- API 断线提示 -->
    <Transition name="slide-down">
      <div v-if="apiStatus.showReconnectBar.value" class="reconnect-bar">
        <el-icon class="is-loading"><Connection /></el-icon>
        <span>{{ t('mainLayout.reconnectBar') }}</span>
      </div>
    </Transition>

    <!-- 主内容 -->
    <main class="main-area">
      <ErrorBoundary>
        <router-view />
      </ErrorBoundary>
    </main>

    <!-- ==================== 工具弹窗 ==================== -->
    <el-dialog v-model="dialogs.tts" :title="t('nav.tts')" width="80%" top="3vh" append-to-body>
      <ToolTts />
    </el-dialog>
    <el-dialog v-model="dialogs.asr" :title="t('nav.asr')" width="80%" top="3vh" append-to-body>
      <ToolAsr />
    </el-dialog>
    <el-dialog v-model="dialogs.vl" :title="t('nav.vl')" width="80%" top="3vh" append-to-body>
      <ToolVl />
    </el-dialog>
    <el-dialog v-model="dialogs.comfyAudio" :title="t('nav.aiSongs')" width="85%" top="3vh" append-to-body>
      <ToolComfyAudio />
    </el-dialog>
    <el-dialog v-model="dialogs.audioProc" :title="t('nav.audioProcessing')" width="80%" top="3vh" append-to-body>
      <ToolAudioProc />
    </el-dialog>
    <el-dialog v-model="dialogs.videoProc" :title="t('nav.videoProcessing')" width="80%" top="3vh" append-to-body>
      <ToolVideoProc />
    </el-dialog>
    <el-dialog v-model="dialogs.aiClip" :title="t('nav.aiClip')" width="90%" top="3vh" append-to-body>
      <ToolAiClip />
    </el-dialog>
    <el-dialog v-model="dialogs.llmChat" :title="t('nav.llmChat')" width="70%" top="5vh" append-to-body>
      <ToolLlmChat />
    </el-dialog>
    <el-dialog v-model="dialogs.videoStitching" :title="t('nav.videoStitching')" width="90%" top="3vh" append-to-body>
      <ToolVideoStitching />
    </el-dialog>
    <el-dialog v-model="dialogs.videoEffects" :title="t('nav.videoEffects')" width="80%" top="3vh" append-to-body>
      <ToolVideoEffects />
    </el-dialog>
    <el-dialog v-model="dialogs.videoAnalysis" :title="t('nav.videoAnalysis')" width="80%" top="3vh" append-to-body>
      <ToolVideoAnalysis />
    </el-dialog>
    <el-dialog v-model="dialogs.comicDrama" :title="t('nav.comicDrama')" width="90%" top="3vh" append-to-body>
      <ToolComicDrama />
    </el-dialog>
    <el-dialog v-model="dialogs.advancedAudio" :title="t('nav.advancedAudio')" width="80%" top="3vh" append-to-body>
      <ToolAdvancedAudio />
    </el-dialog>
    <el-dialog v-model="dialogs.imageProcessing" :title="t('nav.imageProcessing')" width="80%" top="3vh" append-to-body>
      <ToolImageProcessing />
    </el-dialog>
    <el-dialog v-model="dialogs.translation" :title="t('nav.translation')" width="700px" top="5vh" append-to-body>
      <ToolTranslation />
    </el-dialog>
    <el-dialog v-model="dialogs.settings" :title="t('nav.settings')" width="720px" top="4vh" append-to-body>
      <ToolSettings />
    </el-dialog>
    <el-dialog v-model="dialogs.mcpManager" :title="t('nav.mcpManager')" width="70%" top="5vh" append-to-body>
      <McpManager />
    </el-dialog>
    <el-dialog v-model="dialogs.extManager" :title="t('nav.extManager')" width="70%" top="5vh" append-to-body>
      <ExtensionManager />
    </el-dialog>
    <el-dialog v-model="dialogs.knowledgeBase" :title="t('nav.knowledgeBase')" width="70%" top="5vh" append-to-body>
      <KnowledgeBase />
    </el-dialog>
    <el-dialog v-model="dialogs.systemStatus" :title="t('nav.systemStatus')" width="560px" top="8vh" append-to-body>
      <SystemStatus />
    </el-dialog>
    <el-dialog v-model="dialogs.cookieManager" :title="t('mainLayout.cookieManager')" width="600px" top="8vh" append-to-body>
      <CookieManager />
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameVisible" :title="t('mainLayout.renameDialog')" width="360" append-to-body>
      <el-input v-model="renameInput" @keydown.enter="confirmRename" />
      <template #footer>
        <el-button @click="renameVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmRename">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- 命令面板 -->
    <CommandPalette v-model:visible="showCommandPalette" :commands="commandList" @execute="handleCommand" />

    <!-- 新手引导 -->
    <OnboardingTour :active="onboarding.active.value" :current-step="onboarding.currentStep.value"
                    :steps="tourSteps" @next="onboarding.nextStep()" @prev="onboarding.prevStep()"
                    @dismiss="onboarding.dismiss()" />
  </div>
</template>

<script setup>
import { reactive, defineAsyncComponent, ref, computed, h, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useNotification } from '@/composables/useNotification'

const notification = useNotification()
import {
  ArrowDown, Plus, FolderOpened, Document, Download,
  Setting, Headset, Microphone, Picture, PictureFilled, VideoPlay, Edit,
  Connection, Cpu, Notebook, Grid, Sunny, Moon, Upload, UploadFilled,
  MagicStick, ChatDotRound, Film, DataAnalysis, Sort, Present,
} from '@element-plus/icons-vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import { useProjectStore } from '@/store/modules/project'
import { projectApi, comicDramaApi } from '@/api/modules'
import { useHotkeys } from '@/utils/useHotkeys'
import { useTheme } from '@/utils/useTheme'
import { useOnboarding } from '@/utils/useOnboarding'
import { useApiStatus } from '@/utils/useApiStatus'
import CommandPalette from '@/components/CommandPalette.vue'
import OnboardingTour from '@/components/OnboardingTour.vue'

const router = useRouter()
const route = useRoute()
const store = useProjectStore()
const { t } = useI18n()
const { theme, toggleTheme } = useTheme()
const apiStatus = useApiStatus()
const globalSearch = ref('')

// 漫剧页面面包屑
const isComicPage = computed(() => route.path === '/comic-drama')
const comicProjectName = ref('')
const loadComicProjectName = async () => {
  const pid = route.query.projectId
  if (!pid) { comicProjectName.value = ''; return }
  try {
    const data = await comicDramaApi.get(pid)
    comicProjectName.value = data.name || t('mainLayout.breadcrumbUnnamed')
  } catch { comicProjectName.value = '' }
}
watch(() => isComicPage.value ? route.query.projectId : null, loadComicProjectName, { immediate: true })
watch(isComicPage, (v) => { if (v) loadComicProjectName() })

// 新手引导
const tourSteps = [
  { icon: '🎬', title: t('mainLayout.tourStep1Title'), desc: t('mainLayout.tourStep1Desc') },
  { icon: '🤖', title: t('mainLayout.tourStep2Title'), desc: t('mainLayout.tourStep2Desc') },
  { icon: '📂', title: t('mainLayout.tourStep3Title'), desc: t('mainLayout.tourStep3Desc') },
]
const onboarding = useOnboarding(tourSteps)
onMounted(() => {
  onboarding.startTour(); initTauriUpdater()
  window.addEventListener('open-dialog', (e) => { if (e.detail) openDialog(e.detail) })
})

// ==================== Tauri 自动更新 ====================
const updateAvailable = ref(false)
const updateInfo = ref('')

async function initTauriUpdater() {
  try {
    // Only runs inside Tauri desktop app
    const { listen } = await import('@tauri-apps/api/event')
    const { check } = await import('@tauri-apps/plugin-updater')
    const { relaunch } = await import('@tauri-apps/plugin-process')

    listen('update-available', (event) => {
      updateInfo.value = event.payload
      updateAvailable.value = true
    })

    // 监听后端崩溃事件
    listen('backend-crashed', (event) => {
      ElMessage({ type: 'error', duration: 0, showClose: true, message: event.payload || t('mainLayout.backendCrashed') })
    })

    // Also proactively check
    const update = await check()
    if (update?.isUpdateAvailable) {
      updateAvailable.value = true
      updateInfo.value = t('mainLayout.newVersionAvailable')
    }
  } catch {
    // Not running in Tauri — ignore
  }
}

async function doUpdate() {
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const { relaunch } = await import('@tauri-apps/plugin-process')
    const update = await check()
    if (update) {
      await update.downloadAndInstall()
      await relaunch()
    }
  } catch (e) {
    ElMessage.error(t('mainLayout.updateFailed') + ': ' + e.message)
  }
}

// ==================== 全局快捷键 ====================
const showCommandPalette = ref(false)

useHotkeys({
  'ctrl+s': async (e) => {
    if (!store.projectId) {
      ElMessage.warning(t('mainLayout.noOpenProject'))
      return
    }
    try {
      await projectApi.update(store.projectId, store.project)
      ElMessage.success(t('mainLayout.saveSuccess'))
      notification.push('success', t('mainLayout.projectSaved'), store.project.name || t('mainLayout.breadcrumbProject'))
    } catch {
      ElMessage.error(t('mainLayout.saveFailed'))
    }
  },
  'ctrl+n': () => {
    store.resetProject()
    router.push('/editor')
  },
  'ctrl+shift+p': (e) => { e.preventDefault(); showCommandPalette.value = true },
})

// ==================== 命令面板 ====================
const commandList = computed(() => [
  { label: t('mainLayout.cmdNewProject'), icon: '📄', shortcut: 'Ctrl+N', action: 'newProject', keywords: 'new create' },
  { label: t('mainLayout.cmdSaveProject'), icon: '💾', shortcut: 'Ctrl+S', action: 'saveProject', keywords: 'save' },
  { label: t('mainLayout.cmdExportProject'), icon: '📦', action: 'exportProject', keywords: 'export' },
  { label: t('mainLayout.cmdToggleWorkspace'), icon: '📊', shortcut: 'Ctrl+B', action: 'toggleWorkspace', keywords: 'panel workspace' },
  { label: t('mainLayout.cmdTts'), icon: '🎙️', action: 'tts', keywords: 'tts voice speech' },
  { label: t('mainLayout.cmdAsr'), icon: '🎤', action: 'asr', keywords: 'asr transcribe' },
  { label: t('mainLayout.cmdVl'), icon: '🖼️', action: 'vl', keywords: 'vl vision image' },
  { label: t('mainLayout.cmdMusicGen'), icon: '🎵', action: 'comfyAudio', keywords: 'music audio song' },
  { label: t('mainLayout.cmdAiClip'), icon: '✂️', action: 'aiClip', keywords: 'ai clip smart edit' },
  { label: t('mainLayout.cmdLlmChat'), icon: '💬', action: 'llmChat', keywords: 'llm chat gpt' },
  { label: t('mainLayout.cmdAudioProc'), icon: '🎧', action: 'audioProc', keywords: 'audio process' },
  { label: t('mainLayout.cmdAdvAudio'), icon: '🎛️', action: 'advancedAudio', keywords: 'audio advanced normalize equalize denoise' },
  { label: t('mainLayout.cmdVideoProc'), icon: '🎬', action: 'videoProc', keywords: 'video process' },
  { label: t('mainLayout.cmdVideoStitch'), icon: '🎞️', action: 'videoStitching', keywords: 'video stitch merge' },
  { label: t('mainLayout.cmdVideoEffects'), icon: '🎨', action: 'videoEffects', keywords: 'video effect blur sharpen rotate filter' },
  { label: t('mainLayout.cmdVideoAnalysis'), icon: '🔍', action: 'videoAnalysis', keywords: 'video analyze quality silence scene' },
  { label: t('mainLayout.cmdComicDrama'), icon: '🎭', action: 'comicDrama', keywords: 'comic drama motion' },
  { label: t('mainLayout.cmdImageProc'), icon: '🖼️', action: 'imageProcessing', keywords: 'image resize crop convert' },
  { label: t('mainLayout.cmdTranslation'), icon: '🌐', action: 'translation', keywords: 'translate language' },


  { label: t('mainLayout.cmdSettings'), icon: '⚙️', action: 'settings', keywords: 'settings config' },
  { label: t('mainLayout.cmdToggleTheme'), icon: '🌓', action: 'toggleTheme', keywords: 'theme dark light' },
])

const handleCommand = (cmd) => {
  if (cmd.action === 'toggleTheme') { toggleTheme(); return }
  if (cmd.action === 'newProject') { handleFile('new'); return }
  if (cmd.action === 'saveProject') { handleFile('save'); return }
  if (cmd.action === 'exportProject') { handleFile('export'); return }
  if (cmd.action === 'toggleWorkspace') { store.toggleWorkspace(); return }
  if (dialogs[cmd.action] !== undefined) { dialogs[cmd.action] = true; return }
}

// 异步组件错误回退
const AsyncError = {
  render() {
    return h('div', {
      style: 'padding:20px;text-align:center;color:#f56c6c;',
    }, t('mainLayout.asyncLoadFailed'))
  },
}

// 懒加载工具组件（带错误处理）
const asyncOpts = (loader) => ({
  loader,
  errorComponent: AsyncError,
  timeout: 10000,
})
const ToolTts = defineAsyncComponent(asyncOpts(() => import('@/components/TTS.vue')))
const ToolAsr = defineAsyncComponent(asyncOpts(() => import('@/components/ASR.vue')))
const ToolVl = defineAsyncComponent(asyncOpts(() => import('@/components/VL.vue')))
const ToolComfyAudio = defineAsyncComponent(asyncOpts(() => import('@/components/ComfyUIAudio.vue')))
const ToolAudioProc = defineAsyncComponent(asyncOpts(() => import('@/components/AudioProcessing.vue')))
const ToolVideoProc = defineAsyncComponent(asyncOpts(() => import('@/components/VideoProcessing.vue')))
const ToolSettings = defineAsyncComponent(asyncOpts(() => import('@/components/SystemSetting.vue')))

const McpManager = defineAsyncComponent(asyncOpts(() => import('@/components/McpManager.vue')))
const ExtensionManager = defineAsyncComponent(asyncOpts(() => import('@/components/ExtensionManager.vue')))
const KnowledgeBase = defineAsyncComponent(asyncOpts(() => import('@/components/KnowledgeBase.vue')))
const SystemStatus = defineAsyncComponent(asyncOpts(() => import('@/components/SystemStatus.vue')))
const CookieManager = defineAsyncComponent(asyncOpts(() => import('@/components/CookieManager.vue')))
const ToolAiClip = defineAsyncComponent(asyncOpts(() => import('@/components/AIClip.vue')))
const ToolLlmChat = defineAsyncComponent(asyncOpts(() => import('@/components/LLMChat.vue')))
const ToolVideoStitching = defineAsyncComponent(asyncOpts(() => import('@/components/VideoStitching.vue')))
const ToolVideoEffects = defineAsyncComponent(asyncOpts(() => import('@/components/VideoEffects.vue')))
const ToolVideoAnalysis = defineAsyncComponent(asyncOpts(() => import('@/components/VideoAnalysis.vue')))
const ToolComicDrama = defineAsyncComponent(asyncOpts(() => import('@/components/ComicDrama.vue')))
const ToolAdvancedAudio = defineAsyncComponent(asyncOpts(() => import('@/components/AdvancedAudio.vue')))
const ToolImageProcessing = defineAsyncComponent(asyncOpts(() => import('@/components/ImageProcessing.vue')))
const ToolTranslation = defineAsyncComponent(asyncOpts(() => import('@/components/Translation.vue')))

// 弹窗状态
const dialogs = reactive({
  tts: false,
  asr: false,
  vl: false,
  comfyAudio: false,
  audioProc: false,
  videoProc: false,
  aiClip: false,
  llmChat: false,
  videoStitching: false,
  videoEffects: false,
  videoAnalysis: false,
  comicDrama: false,
  advancedAudio: false,
  imageProcessing: false,
  translation: false,
  settings: false,
  mcpManager: false,
  extManager: false,
  knowledgeBase: false,
  systemStatus: false,
  cookieManager: false,
})

const openDialog = (key) => {
  dialogs[key] = true
  trackRecentTool(key)
}

// 最近使用的工具
const toolMeta = {
  tts: { label: t('mainLayout.toolLabelTts'), icon: Headset },
  asr: { label: t('mainLayout.toolLabelAsr'), icon: Microphone },
  vl: { label: t('mainLayout.toolLabelVl'), icon: Picture },
  comfyAudio: { label: t('mainLayout.toolLabelMusic'), icon: Headset },
  aiClip: { label: t('mainLayout.toolLabelAiClip'), icon: MagicStick },
  llmChat: { label: t('mainLayout.toolLabelLlmChat'), icon: ChatDotRound },
  audioProc: { label: t('mainLayout.toolLabelAudioProc'), icon: Headset },
  advancedAudio: { label: t('mainLayout.toolLabelAdvAudio'), icon: Headset },
  videoProc: { label: t('mainLayout.toolLabelVideoProc'), icon: VideoPlay },
  videoStitching: { label: t('mainLayout.toolLabelVideoStitch'), icon: Film },
  videoEffects: { label: t('mainLayout.toolLabelVideoEffects'), icon: Sunny },
  videoAnalysis: { label: t('mainLayout.toolLabelVideoAnalysis'), icon: DataAnalysis },
  comicDrama: { label: t('mainLayout.toolLabelComicDrama'), icon: Film },
  imageProcessing: { label: t('mainLayout.toolLabelImageProc'), icon: PictureFilled },
  translation: { label: t('mainLayout.toolLabelTranslation'), icon: Sort },
  mcpManager: { label: t('mainLayout.toolLabelMcpManager'), icon: Connection },
  extManager: { label: t('mainLayout.toolLabelExtManager'), icon: Grid },
  knowledgeBase: { label: t('mainLayout.toolLabelKnowledgeBase'), icon: Notebook },
  systemStatus: { label: t('mainLayout.toolLabelSystemStatus'), icon: Cpu },
}
const recentTools = ref([])
const RECENT_KEY = 'synthetix_recent_tools'

const loadRecentTools = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
    recentTools.value = saved.map(k => ({ key: k, ...toolMeta[k] })).filter(Boolean).slice(0, 3)
  } catch { recentTools.value = [] }
}
loadRecentTools()

const trackRecentTool = (key) => {
  if (!toolMeta[key]) return
  let saved = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  saved = saved.filter(k => k !== key)
  saved.unshift(key)
  saved = saved.slice(0, 3)
  localStorage.setItem(RECENT_KEY, JSON.stringify(saved))
  loadRecentTools()
}

// 文件菜单
const handleFile = async (cmd) => {
  if (cmd === 'new' || cmd === 'switch') {
    store.resetProject()
    router.push('/editor')
  } else if (cmd === 'save') {
    if (!store.projectId) {
      ElMessage.warning(t('mainLayout.noOpenProject'))
      return
    }
    try {
      await projectApi.update(store.projectId, store.project)
      ElMessage.success(t('mainLayout.saveSuccess'))
    } catch {
      ElMessage.error(t('mainLayout.saveFailed'))
    }
  } else if (cmd === 'export') {
    if (!store.projectId) {
      ElMessage.warning(t('mainLayout.noOpenProject'))
      return
    }
    await store.exportProject()
  }
}

const goHome = () => {
  store.resetProject()
  router.push('/editor')
}

// ==================== 重命名 ====================
const renameVisible = ref(false)
const renameInput = ref('')

const handleRename = () => {
  renameInput.value = store.project.name || ''
  renameVisible.value = true
}

const confirmRename = async () => {
  const name = renameInput.value.trim()
  if (!name) return
  await store.saveField('name', name)
  store.project.name = name
  renameVisible.value = false
}
</script>

<style scoped>
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ===== 顶部菜单栏 ===== */
.top-bar {
  height: 40px;
  display: flex;
  align-items: center;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0 12px;
  flex-shrink: 0;
  user-select: none;
  gap: 4px;
  z-index: 100;
}

/* Logo */
.brand {
  display: flex;
  align-items: center;
  padding: 0 12px 0 4px;
  cursor: pointer;
  margin-right: 4px;
}
.brand-zf {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 1px;
  background: linear-gradient(135deg, var(--el-color-primary), #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.brand-sep {
  margin: 0 6px;
  color: var(--el-text-color-secondary);
  font-weight: 300;
}
.brand-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  letter-spacing: 0.5px;
}
.brand:hover .brand-name {
  color: var(--el-color-primary);
}

/* 导航菜单 */
.top-nav {
  display: flex;
  align-items: center;
  height: 100%;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 0 12px;
  height: 100%;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-regular);
  transition: background 0.15s, color 0.15s;
  border-radius: 4px;
}
.nav-item:hover {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}

.nav-arrow {
  font-size: 11px;
  margin-left: 1px;
}

.nav-sep {
  color: var(--el-border-color);
  margin: 0 4px;
}

.nav-project-name {
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: var(--el-text-color-primary);
}
.nav-project-name:hover {
  color: var(--el-color-primary);
}

.nav-edit-btn {
  padding: 4px;
}

/* 主题切换 */
.theme-toggle {
  margin-left: auto;
  margin-right: 4px;
}

/* 版本号 */
.top-version {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.update-btn {
  font-size: 11px;
  animation: pulse-update 2s ease-in-out infinite;
}
@keyframes pulse-update {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* 面包屑 */
.breadcrumb { font-size: 12px; color: var(--el-text-color-secondary); }
.bc-link { cursor: pointer; color: var(--el-text-color-regular); }
.bc-link:hover { color: var(--el-color-primary); }
.bc-sep { margin: 0 4px; }
.bc-current { color: var(--el-text-color-primary); font-weight: 600; }

/* 全局搜索 */
.global-search { width: 160px; margin-left: 8px; }

/* 断线提示 */
.reconnect-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px;
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning-dark-2);
  font-size: 13px;
  border-bottom: 1px solid var(--el-color-warning-light-5);
}
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.25s ease; }
.slide-down-enter-from, .slide-down-leave-to { transform: translateY(-100%); opacity: 0; }

/* 快捷键标注 */
.menu-shortcut {
  margin-left: auto;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  padding-left: 24px;
}

/* 菜单分组标题 */
:deep(.menu-group-title) {
  font-size: 11px !important;
  color: var(--el-text-color-secondary) !important;
  font-weight: 600;
  cursor: default !important;
  padding-bottom: 2px !important;
}

/* 未保存圆点 */
.unsaved-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-warning);
  margin-right: 4px;
  vertical-align: middle;
}

/* ===== 主内容区 ===== */
.main-area {
  flex: 1;
  overflow: hidden;
  background: var(--el-bg-color-page);
}

/* ===== 弹窗内容高度自适应 ===== */
:deep(.el-dialog__body) {
  max-height: calc(80vh - 100px);
  overflow-y: auto;
}

/* ===== 移动端适配 ===== */
@media (max-width: 768px) {
  .top-bar {
    height: 36px;
    padding: 0 8px;
  }
  .brand { padding: 0 6px 0 2px; }
  .brand-zf { font-size: 15px; }
  .brand-name { display: none; }
  .brand-sep { display: none; }
  .nav-item { padding: 0 8px; font-size: 12px; }
  .nav-project-name { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .top-version { display: none; }
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 2vh auto !important;
  }
}
</style>

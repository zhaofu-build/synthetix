<template>
  <div class="workspace-panel" :class="{ collapsed: store.workspaceCollapsed }">
    <!-- 折叠态 -->
    <div v-if="store.workspaceCollapsed" class="collapsed-bar">
      <el-button text circle @click="store.toggleWorkspace()" title="展开">
        <el-icon><DArrowRight /></el-icon>
      </el-button>
    </div>

    <!-- 展开态 -->
    <template v-else>
      <div class="panel-toolbar" @dblclick="store.toggleWorkspace()">
        <span class="toolbar-title">工作面板</span>
        <el-button text size="small" @click="store.toggleWorkspace()" title="收起">
          <el-icon><DArrowLeft /></el-icon>
        </el-button>
      </div>

      <!-- 可拖拽分割内容 -->
      <div class="panel-content" ref="panelContentRef"
           :style="{ gridTemplateRows: contentGridStyle }">
        <!-- 剪辑方案 -->
        <div class="panel-section plan-section">
          <div class="section-header">
            <div class="section-title">
              <el-icon><Scissor /></el-icon>
              <span>剪辑方案</span>
              <el-tag v-if="clipCount" size="small" class="section-count">{{ clipCount }} 片段</el-tag>
            </div>
          </div>
          <div class="section-body">
            <ClipPlanPanel />
          </div>
        </div>

        <!-- 拖拽手柄 -->
        <div class="inner-resize-handle" @mousedown.prevent="onInnerDragStart"></div>

        <!-- 音频 -->
        <div class="panel-section audio-section">
          <div class="section-header">
            <div class="section-title">
              <el-icon><Headset /></el-icon>
              <span>音频</span>
            </div>
          </div>
          <div class="section-body">
            <AudioPanel />
          </div>
        </div>

        <!-- 字幕 -->
        <div class="panel-section subtitle-section" v-if="showSubtitle">
          <div class="section-header" @click="showSubtitle = !showSubtitle">
            <div class="section-title">
              <el-icon><Document /></el-icon>
              <span>字幕</span>
              <el-tag v-if="subtitleStore.entries.length" size="small" class="section-count">{{ subtitleStore.entries.length }} 条</el-tag>
            </div>
          </div>
          <div class="section-body" v-show="showSubtitle">
            <SubtitlePanel />
          </div>
        </div>

        <!-- 多平台发布 -->
        <div class="panel-section publish-section" v-if="showPublish">
          <div class="section-header" @click="showPublish = !showPublish">
            <div class="section-title">
              <el-icon><Upload /></el-icon>
              <span>发布</span>
            </div>
          </div>
          <div class="section-body" v-show="showPublish">
            <PublishPanel />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onUnmounted } from 'vue'
import { Scissor, Headset, DArrowLeft, DArrowRight, Document, Upload } from '@element-plus/icons-vue'
import { useProjectStore } from '@/store/modules/project'
import { useSubtitleStore } from '@/store/modules/subtitle'
import ClipPlanPanel from './ClipPlanPanel.vue'
import AudioPanel from './AudioPanel.vue'
import SubtitlePanel from './SubtitlePanel.vue'
import PublishPanel from './PublishPanel.vue'

const store = useProjectStore()
const subtitleStore = useSubtitleStore()
const showSubtitle = ref(true)
const showPublish = ref(false)
const clipCount = computed(() => store.project.planData?.clips?.length || 0)

const panelContentRef = ref(null)
const planRatio = ref(66) // 默认 plan 占 66%

const contentGridStyle = computed(() => `${planRatio.value}fr 4px ${100 - planRatio.value}fr`)

let _dragCleanup = null

const onInnerDragStart = (e) => {
  const container = panelContentRef.value
  if (!container) return
  const startY = e.clientY
  const startRatio = planRatio.value
  const totalH = container.getBoundingClientRect().height

  const onMove = (ev) => {
    const delta = ev.clientY - startY
    let newRatio = startRatio + (delta / totalH) * 100
    newRatio = Math.max(30, Math.min(80, newRatio))
    planRatio.value = newRatio
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    _dragCleanup = null
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  _dragCleanup = onUp
}

onUnmounted(() => {
  if (_dragCleanup) _dragCleanup()
})
</script>

<style scoped>
.workspace-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--el-bg-color-page);
  padding: 8px 12px;
  gap: 6px;
}
.workspace-panel.collapsed {
  width: 48px;
  min-width: 48px;
  padding: 0;
  align-items: center;
}
.collapsed-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 12px;
}
.panel-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 4px;
  font-weight: 600;
  font-size: 13px;
}

.panel-content {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
  overflow: hidden;
}

.inner-resize-handle {
  height: 4px;
  cursor: row-resize;
  background: transparent;
  position: relative;
  z-index: 5;
  transition: background 0.15s;
}
.inner-resize-handle:hover {
  background: var(--el-color-primary-light-7);
}

.panel-section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--el-bg-color);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  min-height: 0;
}

.section-header {
  flex-shrink: 0;
  padding: 0 12px;
  height: 36px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  font-size: 13px;
}

.section-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-count {
  margin-left: 4px;
}
</style>

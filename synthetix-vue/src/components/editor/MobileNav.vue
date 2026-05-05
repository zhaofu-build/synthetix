<template>
  <!-- 仅在移动端显示 -->
  <div v-if="isMobile" class="mobile-nav"
       @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd">
    <div class="mobile-tab" :class="{ active: activeTab === 'workspace' }" @click="switchTab('workspace')">
      <el-icon><Scissor /></el-icon>
      <span>工作区</span>
    </div>
    <div class="mobile-tab" :class="{ active: activeTab === 'chat' }" @click="switchTab('chat')">
      <el-icon><ChatDotRound /></el-icon>
      <span>对话</span>
    </div>
    <div class="mobile-tab" :class="{ active: activeTab === 'materials' }" @click="switchTab('materials')">
      <el-icon><FolderOpened /></el-icon>
      <span>素材</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Scissor, FolderOpened, ChatDotRound } from '@element-plus/icons-vue'
import { useProjectStore } from '@/store/modules/project'

const store = useProjectStore()
const activeTab = ref('workspace')
const touchStartX = ref(0)

const tabs = ['workspace', 'chat', 'materials']

const isMobile = computed(() => window.innerWidth < 900)

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab === 'workspace') {
    store.workspaceCollapsed = false
    store.rightPanelCollapsed = true
  } else if (tab === 'chat') {
    store.workspaceCollapsed = true
    store.rightPanelCollapsed = true
  } else if (tab === 'materials') {
    store.workspaceCollapsed = true
    store.rightPanelCollapsed = false
  }
}

// 滑动手势支持
const onTouchStart = (e) => {
  touchStartX.value = e.touches[0].clientX
}
const onTouchMove = () => {} // prevent scroll
const onTouchEnd = (e) => {
  const deltaX = e.changedTouches[0].clientX - touchStartX.value
  if (Math.abs(deltaX) < 50) return
  const currentIdx = tabs.indexOf(activeTab.value)
  if (deltaX < 0 && currentIdx < tabs.length - 1) {
    switchTab(tabs[currentIdx + 1])
  } else if (deltaX > 0 && currentIdx > 0) {
    switchTab(tabs[currentIdx - 1])
  }
}
</script>

<style scoped>
.mobile-nav {
  display: none;
}

@media (max-width: 900px) {
  .mobile-nav {
    display: flex;
    height: 48px;
    background: var(--el-bg-color);
    border-top: 1px solid var(--el-border-color-lighter);
    flex-shrink: 0;
  }
  .mobile-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    font-size: 10px;
    color: var(--el-text-color-secondary);
    cursor: pointer;
    transition: color 0.15s;
  }
  .mobile-tab.active {
    color: var(--el-color-primary);
  }
  .mobile-tab .el-icon {
    font-size: 18px;
  }
}
</style>

<template>
  <div class="status-bar">
    <div class="status-left">
      <span v-if="store.isLoaded" class="status-item project-name" @click="$emit('editName')">
        {{ store.project.name || '未命名项目' }}
      </span>
      <span class="status-item separator">|</span>
      <span class="status-item">{{ store.materials.length }} 素材</span>
      <span class="status-item">{{ clipCount }} 片段</span>
      <span v-if="store.chatLoading" class="status-item ai-status thinking">
        <el-icon class="is-loading" :size="12"><Loading /></el-icon> AI 思考中
      </span>
      <span v-else class="status-item ai-status idle">AI 就绪</span>
    </div>
    <div class="status-right">
      <AiCostTracker />
      <span v-if="store.hasUnsavedChanges" class="status-item unsaved">未保存</span>
      <span class="status-item shortcut-hint">Ctrl+S 保存</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { useProjectStore } from '@/store/modules/project'
import AiCostTracker from './AiCostTracker.vue'

defineEmits(['editName'])

const store = useProjectStore()
const clipCount = computed(() => store.project.planData?.clips?.length || 0)
</script>

<style scoped>
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 24px;
  padding: 0 12px;
  background: var(--el-bg-color-page);
  border-top: 1px solid var(--el-border-color-extra-light);
  font-size: 11px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
  user-select: none;
}
.status-left, .status-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-item { white-space: nowrap; }
.separator { color: var(--el-border-color); }
.project-name { cursor: pointer; font-weight: 500; color: var(--el-text-color-primary); }
.project-name:hover { text-decoration: underline; }
.ai-status { display: flex; align-items: center; gap: 2px; }
.ai-status.thinking { color: var(--el-color-primary); }
.ai-status.idle { color: var(--el-text-color-placeholder); }
.unsaved { color: var(--el-color-warning); font-weight: 500; }
.shortcut-hint { color: var(--el-text-color-placeholder); }
</style>

<template>
  <div class="ffmpeg-preview">
    <div class="preview-header" @click="collapsed = !collapsed">
      <el-icon :size="14"><component :is="collapsed ? ArrowRight : ArrowDown" /></el-icon>
      <span class="label">FFmpeg</span>
      <el-button text size="small" @click.stop="copyCommand" class="copy-btn">
        <el-icon><DocumentCopy /></el-icon>
      </el-button>
    </div>
    <div v-show="!collapsed" class="code-block">
      <span v-for="(part, i) in command" :key="i">
        <span :class="partClass(part)">{{ part }}</span>{{ i < command.length - 1 ? ' ' : '' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, ArrowDown, DocumentCopy } from '@element-plus/icons-vue'

const props = defineProps({
  command: { type: Array, default: () => [] },
})

const collapsed = ref(false)

function partClass(p) {
  if (p.startsWith('-')) return 'flag'
  if (p === 'ffmpeg') return 'cmd'
  return 'arg'
}

async function copyCommand() {
  try {
    await navigator.clipboard.writeText(props.command.join(' '))
    ElMessage.success('已复制')
  } catch { ElMessage.error('复制失败') }
}
</script>

<style scoped>
.ffmpeg-preview { border: 1px solid var(--el-border-color-extra-light); border-radius: 6px; overflow: hidden; }
.preview-header {
  display: flex; align-items: center; gap: 6px; padding: 6px 10px;
  background: var(--el-fill-color-lighter); cursor: pointer; user-select: none;
}
.label { font-size: 12px; font-weight: 500; flex: 1; }
.copy-btn { padding: 2px; }
.code-block {
  padding: 8px 10px; font-family: 'Consolas', monospace; font-size: 12px;
  line-height: 1.6; background: var(--el-bg-color); overflow-x: auto;
}
.flag { color: var(--el-color-primary); font-weight: 500; }
.cmd { color: var(--el-color-success); }
.arg { color: var(--el-text-color-regular); }
</style>

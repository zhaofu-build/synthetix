<template>
  <el-dialog v-model="visible" title="选择剪辑方案模板" width="500" append-to-body>
    <div class="template-grid">
      <div v-for="tpl in templates" :key="tpl.name" class="template-card"
           :class="{ selected: selected === tpl.name }"
           @click="selected = tpl.name">
        <div class="tpl-icon">{{ tpl.icon }}</div>
        <div class="tpl-info">
          <div class="tpl-name">{{ tpl.name }}</div>
          <div class="tpl-desc">{{ tpl.description }}</div>
          <div class="tpl-meta">目标时长: {{ tpl.duration }}s · 风格: {{ tpl.style }}</div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!selected" @click="applyTemplate">应用</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'apply'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

import { computed } from 'vue'

const selected = ref(null)

const templates = [
  {
    name: '短视频高光',
    icon: '🎬',
    description: '提取最精彩的 60 秒精华片段',
    duration: 60,
    style: '动感',
    creative: '提取视频中最精彩、最有看点的高光片段，组合成一段节奏紧凑的短视频',
  },
  {
    name: '教学摘要',
    icon: '📚',
    description: '提取教学视频的核心知识点',
    duration: 120,
    style: '舒缓',
    creative: '提取教学视频中的关键知识点和重要讲解片段，去除冗余内容',
  },
  {
    name: '产品展示',
    icon: '💎',
    description: '突出产品功能和亮点的展示视频',
    duration: 45,
    style: '电影感',
    creative: '提取产品展示的最佳角度和功能演示片段，突出产品亮点',
  },
  {
    name: '会议纪要',
    icon: '📋',
    description: '提取会议中的关键决策和讨论要点',
    duration: 180,
    style: '纪录片',
    creative: '提取会议中的关键决策、重要讨论和结论性发言',
  },
  {
    name: 'Vlog 精选',
    icon: '✈️',
    description: 'Vlog 旅行视频的精彩瞬间',
    duration: 90,
    style: '动感',
    creative: '提取旅行中最精彩的画面和体验片段，制作成精彩的 Vlog',
  },
]

const applyTemplate = () => {
  const tpl = templates.find(t => t.name === selected.value)
  if (tpl) {
    emit('apply', tpl)
    visible.value = false
  }
}
</script>

<style scoped>
.template-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.template-card {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.template-card:hover { border-color: var(--el-color-primary-light-5); }
.template-card.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tpl-icon { font-size: 24px; flex-shrink: 0; }
.tpl-name { font-size: 14px; font-weight: 500; }
.tpl-desc { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.tpl-meta { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 4px; }
</style>

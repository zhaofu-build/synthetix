<template>
  <div class="plan-operation-card" :class="[`risk-${operation.risk || 'safe'}`, { expanded }]" @click="expanded = !expanded">
    <div class="card-header">
      <div class="card-left">
        <el-icon :size="18" class="op-icon">
          <component :is="typeIcon" />
        </el-icon>
        <span class="op-description">{{ operation.description }}</span>
      </div>
      <div class="card-right">
        <el-tag :type="riskTagType" size="small">{{ riskLabel }}</el-tag>
        <el-checkbox
          v-if="selectable"
          :model-value="selected"
          @update:model-value="$emit('toggle', operation.id)"
          @click.stop
        />
      </div>
    </div>

    <div v-if="expanded" class="card-body" @click.stop>
      <div class="param-list">
        <div v-for="(value, key) in operation.params" :key="key" class="param-item">
          <span class="param-key">{{ formatParamKey(key) }}</span>
          <span class="param-value" :class="{ highlight: isHighlightKey(key) }">{{ value }}</span>
        </div>
      </div>
      <div v-if="operation.tool" class="tool-name">
        <el-tag size="small" type="info">{{ operation.tool }}</el-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Scissor as IconCut,
  Connection as IconMerge,
  Document as IconSubtitle,
  Microphone as IconAudio,
  VideoPlay as IconSpeed,
  ChatDotRound as IconTts,
  MagicStick as IconSmart,
  Film as IconDefault,
} from '@element-plus/icons-vue'

const props = defineProps({
  operation: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: true },
})
defineEmits(['toggle'])

const expanded = ref(false)

const typeIconMap = {
  cut: IconCut,
  merge: IconMerge,
  add_subtitle: IconSubtitle,
  add_audio: IconAudio,
  change_speed: IconSpeed,
  generate_tts: IconTts,
  smart_clip: IconSmart,
}
const typeIcon = computed(() => typeIconMap[props.operation.type] || IconDefault)

const riskTagType = computed(() => {
  const map = { safe: 'success', needs_confirm: 'warning', destructive: 'danger' }
  return map[props.operation.risk] || 'info'
})

const riskLabel = computed(() => {
  const map = { safe: '安全', needs_confirm: '需确认', destructive: '高风险' }
  return map[props.operation.risk] || '未知'
})

const highlightKeys = ['video_id', 'start_time', 'end_time', 'output_path', 'video_ids']
const isHighlightKey = (key) => highlightKeys.includes(key)

const paramKeyLabels = {
  video_id: '视频ID', start_time: '开始', end_time: '结束',
  video_ids: '视频IDs', speed_factor: '速度', description: '描述',
  subtitle_content: '字幕内容', audio_url: '音频',
}
const formatParamKey = (key) => paramKeyLabels[key] || key
</script>

<style scoped>
.plan-operation-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.plan-operation-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.plan-operation-card.risk-destructive {
  border-left: 3px solid var(--el-color-danger);
}
.plan-operation-card.risk-needs_confirm {
  border-left: 3px solid var(--el-color-warning);
}
.plan-operation-card.risk-safe {
  border-left: 3px solid var(--el-color-success);
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.op-icon { flex-shrink: 0; color: var(--el-color-primary); }
.op-description {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.card-body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--el-border-color-extra-light);
}
.param-list { display: flex; flex-wrap: wrap; gap: 6px 16px; }
.param-item { font-size: 12px; }
.param-key { color: var(--el-text-color-secondary); }
.param-value { margin-left: 4px; font-family: monospace; }
.param-value.highlight { color: var(--el-color-danger); font-weight: 600; }
.tool-name { margin-top: 8px; }
</style>

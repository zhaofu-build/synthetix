<template>
  <span class="speaker-tag" :class="{ compact }" :style="tagStyle" @click="$emit('click', speakerId)">
    <span class="dot" :style="{ background: color }"></span>
    <template v-if="!compact">
      <input v-if="editing" class="speaker-name-input" :value="name"
             @blur="finishRename" @keyup.enter="finishRename" ref="nameInput" />
      <span v-else class="speaker-label" @dblclick.stop="startRename">{{ name }}</span>
      <span v-if="count" class="speaker-count">{{ count }}</span>
    </template>
    <template v-else>
      <span class="speaker-label">{{ name }}</span>
    </template>
  </span>
</template>

<script setup>
import { computed, ref, nextTick } from 'vue'

const props = defineProps({
  speakerId: { type: [String, Number], default: '' },
  name: { type: String, default: '' },
  color: { type: String, default: '#409eff' },
  count: { type: Number, default: 0 },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['click', 'rename'])

const editing = ref(false)
const nameInput = ref(null)

const tagStyle = computed(() => ({
  borderColor: props.color,
  color: props.color,
}))

const startRename = () => {
  editing.value = true
  nextTick(() => nameInput.value?.focus())
}

const finishRename = (e) => {
  editing.value = false
  const newName = e.target.value?.trim()
  if (newName && newName !== props.name) {
    emit('rename', newName)
  }
}
</script>

<style scoped>
.speaker-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border: 1px solid; border-radius: 12px;
  font-size: 12px; cursor: pointer; user-select: none;
  transition: background 0.15s;
}
.speaker-tag:hover { background: var(--el-fill-color-light); }
.speaker-tag.compact { padding: 1px 6px; font-size: 10px; border-radius: 8px; }
.dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.speaker-label { white-space: nowrap; }
.speaker-count { font-size: 10px; opacity: 0.6; margin-left: 2px; }
.speaker-name-input {
  border: none; background: transparent; font-size: 12px; width: 60px;
  outline: none; color: inherit; font-family: inherit;
  border-bottom: 1px solid currentColor;
}
</style>

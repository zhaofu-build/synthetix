<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="cmd-overlay" @click.self="close">
        <div class="cmd-palette">
          <div class="cmd-header">
            <el-input ref="searchRef" v-model="query" placeholder="输入命令搜索..." size="large"
                      prefix-icon="Search" @keydown.escape="close" @keydown.enter.prevent="executeSelected"
                      @keydown.down.prevent="selectNext" @keydown.up.prevent="selectPrev" />
          </div>
          <div class="cmd-list" ref="listRef">
            <div v-for="(cmd, i) in filtered" :key="cmd.label" class="cmd-item"
                 :class="{ active: selectedIdx === i }" @click="execute(cmd)" @mouseenter="selectedIdx = i">
              <span class="cmd-icon">{{ cmd.icon || '' }}</span>
              <span class="cmd-label">{{ cmd.label }}</span>
              <span v-if="cmd.shortcut" class="cmd-shortcut">{{ cmd.shortcut }}</span>
            </div>
            <div v-if="!filtered.length" class="cmd-empty">无匹配命令</div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  visible: Boolean,
  commands: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:visible', 'execute'])

const query = ref('')
const selectedIdx = ref(0)
const searchRef = ref(null)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.commands
  return props.commands.filter(c => c.label.toLowerCase().includes(q) || (c.keywords || '').toLowerCase().includes(q))
})

watch(() => props.visible, (v) => {
  if (v) {
    query.value = ''
    selectedIdx.value = 0
    nextTick(() => searchRef.value?.focus())
  }
})

watch(filtered, () => { selectedIdx.value = 0 })

const close = () => emit('update:visible', false)
const selectNext = () => { selectedIdx.value = Math.min(selectedIdx.value + 1, filtered.value.length - 1) }
const selectPrev = () => { selectedIdx.value = Math.max(selectedIdx.value - 1, 0) }
const executeSelected = () => {
  if (filtered.value[selectedIdx.value]) execute(filtered.value[selectedIdx.value])
}
const execute = (cmd) => {
  emit('execute', cmd)
  close()
}
</script>

<style scoped>
.cmd-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  padding-top: 15vh;
}
.cmd-palette {
  width: 520px;
  max-height: 400px;
  background: var(--el-bg-color-overlay);
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.cmd-header { padding: 12px; border-bottom: 1px solid var(--el-border-color-lighter); }
.cmd-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.cmd-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.1s;
}
.cmd-item:hover, .cmd-item.active { background: var(--el-fill-color-light); }
.cmd-item.active { background: var(--el-color-primary-light-9); }
.cmd-icon { font-size: 16px; width: 20px; text-align: center; flex-shrink: 0; }
.cmd-label { flex: 1; }
.cmd-shortcut {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: monospace;
}
.cmd-empty { padding: 20px; text-align: center; color: var(--el-text-color-secondary); font-size: 13px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

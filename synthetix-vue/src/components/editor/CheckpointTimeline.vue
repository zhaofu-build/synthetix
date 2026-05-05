<template>
  <div class="checkpoint-timeline">
    <div v-for="(stage, i) in stages" :key="i" class="stage">
      <div class="rail">
        <span class="dot" :class="stage.status" :style="dotStyle(stage.status)"></span>
        <span v-if="i < stages.length - 1" class="line"></span>
      </div>
      <div class="stage-info">
        <span class="stage-name">{{ stage.name }}</span>
        <span v-if="stage.time" class="stage-time">{{ stage.time }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  stages: { type: Array, default: () => [] },
})

function dotStyle(status) {
  const map = {
    done: '#67c23a', running: '#409eff', failed: '#f56c6c', pending: '#c0c4cc',
  }
  return { background: map[status] || map.pending }
}
</script>

<style scoped>
.checkpoint-timeline { display: flex; flex-direction: column; }
.stage { display: flex; gap: 10px; min-height: 36px; }
.rail { display: flex; flex-direction: column; align-items: center; width: 14px; flex-shrink: 0; }
.dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
  border: 2px solid #fff; box-shadow: 0 0 0 1px var(--el-border-color);
}
.dot.running { animation: pulse 1.2s infinite; }
.line { width: 1px; flex: 1; background: var(--el-border-color); }
.stage-info { padding-bottom: 8px; display: flex; flex-direction: column; gap: 2px; }
.stage-name { font-size: 13px; font-weight: 500; }
.stage-time { font-size: 11px; color: var(--el-text-color-secondary); font-family: monospace; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 1px var(--el-border-color); } 50% { box-shadow: 0 0 0 3px rgba(64,158,255,0.3); } }
</style>

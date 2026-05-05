<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="active" class="tour-overlay">
        <div class="tour-card" :style="cardStyle">
          <div class="tour-step-indicator">
            <span v-for="(_, i) in steps" :key="i" class="tour-dot" :class="{ active: currentStep === i }" />
          </div>
          <div class="tour-icon">{{ steps[currentStep]?.icon || '' }}</div>
          <div class="tour-title">{{ steps[currentStep]?.title }}</div>
          <div class="tour-desc">{{ steps[currentStep]?.desc }}</div>
          <div class="tour-actions">
            <el-button v-if="currentStep > 0" size="small" @click="$emit('prev')">上一步</el-button>
            <span v-else />
            <div class="tour-right">
              <el-button text size="small" @click="$emit('dismiss')">跳过</el-button>
              <el-button type="primary" size="small" @click="$emit('next')">
                {{ currentStep === steps.length - 1 ? '开始使用' : '下一步' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  active: Boolean,
  currentStep: { type: Number, default: 0 },
  steps: { type: Array, default: () => [] },
})

defineEmits(['next', 'prev', 'dismiss'])

const cardStyle = computed(() => ({
  top: '20vh',
}))
</script>

<style scoped>
.tour-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  justify-content: center;
}
.tour-card {
  width: 380px;
  background: var(--el-bg-color-overlay);
  border-radius: 12px;
  padding: 28px 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}
.tour-step-indicator {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
}
.tour-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-fill-color);
  transition: all 0.2s;
}
.tour-dot.active {
  background: var(--el-color-primary);
  transform: scale(1.3);
}
.tour-icon { font-size: 40px; }
.tour-title { font-size: 18px; font-weight: 700; }
.tour-desc { font-size: 13px; color: var(--el-text-color-secondary); line-height: 1.6; }
.tour-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  margin-top: 8px;
}
.tour-right { display: flex; gap: 4px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

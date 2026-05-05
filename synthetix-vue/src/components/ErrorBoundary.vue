<template>
  <div v-if="errorInfo" class="error-boundary">
    <h2>出错了</h2>
    <details>
      <summary>错误详情</summary>
      <p>{{ errorInfo.message }}</p>
      <p>{{ errorInfo.stack }}</p>
    </details>
    <button @click="handleReset">重试</button>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'

const errorInfo = ref(null)

onErrorCaptured((err, instance, info) => {
  errorInfo.value = {
    message: err.message,
    stack: err.stack,
    info
  }
  console.error('Error captured:', err)
})

const handleReset = () => {
  errorInfo.value = null
}
</script>

<style scoped>
.error-boundary {
  padding: 20px;
  background-color: #fef0f0;
  border: 1px solid #f56c6c;
  border-radius: 4px;
  color: #f56c6c;
}
</style>
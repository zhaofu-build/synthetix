<template>
  <div class="ai-cost-tracker">
    <div v-if="loading" class="loading"><el-icon class="is-loading"><Loading /></el-icon></div>
    <template v-else>
      <el-statistic title="API 调用" :value="metrics.calls" />
      <el-statistic title="Token 总量" :value="metrics.tokens" />
      <el-statistic title="预估费用">
        <template #default>
          <span class="cost">${{ metrics.cost }}</span>
        </template>
      </el-statistic>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { API_HOST } from '@/api/modules'

const COST_PER_1K = 0.002
const loading = ref(true)
const metrics = ref({ calls: 0, tokens: 0, cost: '0.00' })

onMounted(async () => {
  try {
    const res = await fetch(`${API_HOST}/api/metrics/ai`)
    const json = await res.json()
    const data = json.data || json
    const tokens = data.total_tokens ?? data.tokens ?? 0
    const calls = data.total_calls ?? data.calls ?? 0
    metrics.value = {
      calls,
      tokens,
      cost: ((tokens / 1000) * COST_PER_1K).toFixed(4),
    }
  } catch { /* metrics stay at defaults */ }
  finally { loading.value = false }
})
</script>

<style scoped>
.ai-cost-tracker {
  display: flex; gap: 20px; align-items: center; padding: 10px;
}
.loading { padding: 10px; }
.cost { font-size: 18px; font-weight: 600; color: var(--el-color-primary); }
</style>

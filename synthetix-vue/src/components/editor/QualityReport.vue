<template>
  <div class="quality-report" v-if="report">
    <el-progress type="circle" :percentage="report.score ?? 0" :width="64"
      :color="scoreColor" :stroke-width="5">
      <template #default="{ percentage }">
        <span class="score-value">{{ percentage }}</span>
      </template>
    </el-progress>
    <div class="report-body">
      <div v-if="report.issues?.length" class="issues">
        <el-tag v-for="(issue, i) in report.issues" :key="i" size="small"
          :type="issue.severity === 'error' ? 'danger' : 'warning'" class="issue-tag">
          {{ issue.message || issue }}
        </el-tag>
      </div>
      <el-descriptions v-if="report.checks" :column="2" size="small" border>
        <el-descriptions-item v-for="(val, key) in report.checks" :key="key" :label="key">
          <el-icon :color="val ? '#67c23a' : '#f56c6c'">
            <component :is="val ? Check : CloseBold" />
          </el-icon>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Check, CloseBold } from '@element-plus/icons-vue'

const props = defineProps({
  report: { type: Object, default: () => ({ score: 0, issues: [], checks: {} }) },
})

const scoreColor = computed(() => {
  const s = props.report.score ?? 0
  if (s >= 80) return '#67c23a'
  if (s >= 50) return '#e6a23c'
  return '#f56c6c'
})
</script>

<style scoped>
.quality-report { display: flex; gap: 16px; align-items: flex-start; }
.score-value { font-size: 16px; font-weight: 600; }
.report-body { flex: 1; min-width: 0; }
.issues { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.issue-tag { font-size: 11px; }
</style>

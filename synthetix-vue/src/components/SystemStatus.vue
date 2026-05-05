<template>
  <div class="system-status" v-loading="loading">
    <el-tabs v-model="activeTab">
      <!-- 关于 -->
      <el-tab-pane label="关于" name="about">
        <div class="about-info">
          <div class="about-row"><span class="about-label">版本</span><span>{{ health.version || '-' }}</span></div>
          <div class="about-row"><span class="about-label">架构</span><span>Tauri 2.0 + Vue 3 + FastAPI</span></div>
          <div class="about-row"><span class="about-label">AI 推理</span><span>Core Nexus AI</span></div>
          <div class="about-row"><span class="about-label">视频处理</span><span>FFmpeg (本地)</span></div>
        </div>
      </el-tab-pane>

      <!-- 服务状态 -->
      <el-tab-pane label="服务状态" name="health">
        <el-descriptions :column="1" border size="default">
          <el-descriptions-item :label="t('health.overall')">
            <el-tag :type="statusTag" size="small">{{ health.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('health.version')">
            {{ health.version || '-' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('health.database')">
            <el-tag :type="health.database === 'ok' ? 'success' : 'danger'" size="small">
              {{ health.database === 'ok' ? t('health.ok') : health.database || t('health.unknown') }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="FFmpeg">
            <el-tag :type="health.ffmpeg === 'ok' ? 'success' : 'warning'" size="small">
              {{ health.ffmpeg === 'ok' ? t('health.available') : t('health.unavailable') }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Core-Nexus AI">
            <el-tag :type="nexusTag" size="small">{{ nexusLabel }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('health.activeSessions')">
            {{ health.active_sessions ?? 0 }}
          </el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- AI 调用统计 -->
      <el-tab-pane label="AI 统计" name="ai">
        <div v-if="aiStats.total_calls" class="ai-stats">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="总调用次数">{{ aiStats.total_calls }}</el-descriptions-item>
            <el-descriptions-item label="成功率">
              <el-tag :type="aiStats.success_rate >= 95 ? 'success' : aiStats.success_rate >= 80 ? 'warning' : 'danger'" size="small">
                {{ aiStats.success_rate }}%
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="输入 Token">{{ aiStats.total_tokens_in?.toLocaleString() }}</el-descriptions-item>
            <el-descriptions-item label="输出 Token">{{ aiStats.total_tokens_out?.toLocaleString() }}</el-descriptions-item>
            <el-descriptions-item label="平均延迟">{{ aiStats.avg_latency_ms }}ms</el-descriptions-item>
          </el-descriptions>
          <div v-if="Object.keys(aiStats.by_service || {}).length" class="stats-breakdown">
            <h4>按服务</h4>
            <div class="stats-grid">
              <div v-for="(info, svc) in aiStats.by_service" :key="svc" class="stat-card">
                <div class="stat-label">{{ svc }}</div>
                <div class="stat-value">{{ info.calls }} 次</div>
                <div class="stat-sub">Token: {{ info.tokens?.toLocaleString() }}</div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无 AI 调用数据" :image-size="40" />
      </el-tab-pane>

      <!-- 资源监控 -->
      <el-tab-pane label="资源监控" name="resources">
        <div v-if="resInfo" class="resource-grid">
          <div class="res-card">
            <div class="res-label">CPU</div>
            <el-progress type="dashboard" :percentage="resInfo.cpu_percent || 0" :width="80" :stroke-width="6">
              <template #default="{ percentage }">
                <span class="res-pct">{{ percentage }}%</span>
              </template>
            </el-progress>
            <div class="res-detail">{{ resInfo.cpu_count }} 核心</div>
          </div>
          <div class="res-card">
            <div class="res-label">内存</div>
            <el-progress type="dashboard" :percentage="resInfo.memory_percent || 0" :width="80" :stroke-width="6"
                         :color="resInfo.memory_percent > 85 ? '#f56c6c' : undefined">
              <template #default="{ percentage }">
                <span class="res-pct">{{ percentage }}%</span>
              </template>
            </el-progress>
            <div class="res-detail">{{ resInfo.memory_used_gb }} / {{ resInfo.memory_total_gb }} GB</div>
          </div>
          <div class="res-card">
            <div class="res-label">磁盘</div>
            <el-progress type="dashboard" :percentage="resInfo.disk_percent || 0" :width="80" :stroke-width="6">
              <template #default="{ percentage }">
                <span class="res-pct">{{ percentage }}%</span>
              </template>
            </el-progress>
            <div class="res-detail">{{ resInfo.disk_free_gb }} GB 可用</div>
          </div>
          <div class="res-card">
            <div class="res-label">GPU</div>
            <div class="res-value">{{ resInfo.gpu_available ? resInfo.gpu_name || '已检测' : '不可用' }}</div>
            <div v-if="resInfo.gpu_memory_total" class="res-detail">{{ resInfo.gpu_memory_total }} MB</div>
          </div>
        </div>
        <el-empty v-else description="资源信息加载中..." :image-size="40" />
      </el-tab-pane>
    </el-tabs>

    <div style="margin-top: 12px; text-align: right">
      <el-button size="small" @click="fetchAll" :loading="loading">{{ t('common.refresh') }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { API_HOST } from '@/api/modules'

const { t } = useI18n()
const loading = ref(false)
const health = ref({ status: 'unknown' })
const aiStats = ref({})
const resInfo = ref(null)
const activeTab = ref('about')

const statusTag = computed(() => {
  if (health.value.status === 'ok') return 'success'
  if (health.value.status === 'degraded') return 'warning'
  return 'danger'
})

const nexusTag = computed(() => {
  const v = health.value.core_nexus
  if (v === 'configured') return 'success'
  if (v === 'not_configured') return 'info'
  return 'danger'
})

const nexusLabel = computed(() => {
  const v = health.value.core_nexus
  if (v === 'configured') return t('health.configured')
  if (v === 'not_configured') return t('health.notConfigured')
  return v || t('health.unknown')
})

const fetchHealth = async () => {
  try {
    const res = await fetch(`${API_HOST}/health`).then(r => r.json())
    health.value = res
  } catch {
    health.value = { status: 'error' }
  }
}

const fetchAiStats = async () => {
  try {
    const res = await fetch(`${API_HOST}/api/metrics/ai`).then(r => r.json())
    aiStats.value = res
  } catch {
    aiStats.value = {}
  }
}

const fetchResources = async () => {
  try {
    const res = await fetch(`${API_HOST}/health`).then(r => r.json())
    if (res.resource_profile) {
      const rp = res.resource_profile
      resInfo.value = {
        cpu_count: rp.cpu_count || '-',
        cpu_percent: rp.cpu_percent || 0,
        memory_total_gb: ((rp.memory_total || 0) / 1024).toFixed(1),
        memory_used_gb: ((rp.memory_used || 0) / 1024).toFixed(1),
        memory_percent: rp.memory_percent || 0,
        disk_free_gb: ((rp.disk_free || 0) / 1024).toFixed(1),
        disk_percent: rp.disk_percent || 0,
        gpu_available: rp.gpu_available || false,
        gpu_name: rp.gpu_name || '',
        gpu_memory_total: rp.gpu_memory_total || '',
      }
    }
  } catch {}
}

const fetchAll = async () => {
  loading.value = true
  try {
    await Promise.all([fetchHealth(), fetchAiStats(), fetchResources()])
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
</script>

<style scoped>
.system-status { padding: 4px; }
.ai-stats { display: flex; flex-direction: column; gap: 12px; }
.stats-breakdown h4 { font-size: 12px; color: var(--el-text-color-secondary); margin: 0 0 6px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
.stat-card {
  padding: 8px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  text-align: center;
}
.stat-label { font-size: 11px; color: var(--el-text-color-secondary); }
.stat-value { font-size: 16px; font-weight: 600; margin: 2px 0; }
.stat-sub { font-size: 10px; color: var(--el-text-color-placeholder); }
.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.res-card {
  text-align: center;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.res-label { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 6px; font-weight: 600; }
.res-pct { font-size: 14px; font-weight: 600; }
.res-detail { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 4px; }
.res-value { font-size: 13px; font-weight: 500; margin-top: 8px; }
.about-info { display: flex; flex-direction: column; gap: 12px; }
.about-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.about-row:last-child { border-bottom: none; }
.about-label { color: var(--el-text-color-secondary); font-size: 13px; }
</style>

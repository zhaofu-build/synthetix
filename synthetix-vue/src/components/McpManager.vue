<template>
  <div class="mcp-manager">
    <!-- 注册新 Server -->
    <el-card shadow="never" class="register-card">
      <template #header>
        <span>注册 MCP Server</span>
      </template>
      <el-form :inline="true" @submit.prevent="registerServer">
        <el-form-item label="名称">
          <el-input v-model="newServer.name" placeholder="my-server" style="width: 140px" />
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="newServer.url" placeholder="http://localhost:3000" style="width: 260px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="registering" @click="registerServer">注册</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 已注册 Server 列表 -->
    <el-table :data="servers" stripe style="margin-top: 16px" v-loading="loading">
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column prop="url" label="URL" min-width="200" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.healthy ? 'success' : 'danger'" size="small">
            {{ row.healthy ? '正常' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="70">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" size="small" @change="toggleServer(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" text size="small" @click="removeServer(row.name)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 已发现工具 -->
    <div v-if="tools.length" style="margin-top: 16px">
      <h4>已发现工具 ({{ tools.length }})</h4>
      <el-table :data="tools" stripe size="small">
        <el-table-column prop="name" label="工具名" width="220" />
        <el-table-column prop="description" label="描述" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_HOST } from '@/api/modules'

const { t } = useI18n()
const loading = ref(false)
const registering = ref(false)
const servers = ref([])
const tools = ref([])
const newServer = ref({ name: '', url: '' })

const fetchData = async () => {
  loading.value = true
  try {
    const [srvRes, toolRes] = await Promise.all([
      fetch(`${API_HOST}/api/mcp/servers`).then(r => r.json()),
      fetch(`${API_HOST}/api/mcp/tools`).then(r => r.json()),
    ])
    const serverList = srvRes.data || []
    // Health check each server
    for (const srv of serverList) {
      try {
        const resp = await fetch(srv.url + '/health', { signal: AbortSignal.timeout(3000) })
        srv.healthy = resp.ok
      } catch {
        srv.healthy = false
      }
      if (srv.enabled === undefined) srv.enabled = true
    }
    servers.value = serverList
    const toolData = toolRes.data || {}
    tools.value = toolData.tools || []
  } catch (e) {
    ElMessage.error('加载 MCP 数据失败')
  } finally {
    loading.value = false
  }
}

const toggleServer = (row) => {
  // Enabled/disabled is managed client-side
  ElMessage.info(`${row.name} 已${row.enabled ? '启用' : '禁用'}`)
}

const registerServer = async () => {
  const { name, url } = newServer.value
  if (!name || !url) return ElMessage.warning('请填写名称和 URL')
  registering.value = true
  try {
    const res = await fetch(`${API_HOST}/api/mcp/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url }),
    }).then(r => r.json())
    if (res.success) {
      ElMessage.success(`注册成功，发现 ${res.data?.tools_count || 0} 个工具`)
      newServer.value = { name: '', url: '' }
      await fetchData()
    } else {
      ElMessage.error(res.message || '注册失败')
    }
  } catch (e) {
    ElMessage.error('注册失败: ' + e.message)
  } finally {
    registering.value = false
  }
}

const removeServer = async (name) => {
  try {
    await ElMessageBox.confirm(`确定移除 MCP Server "${name}"？`, '确认')
    await fetch(`${API_HOST}/api/mcp/servers/${name}`, { method: 'DELETE' })
    ElMessage.success('已移除')
    await fetchData()
  } catch { /* cancel */ }
}

onMounted(fetchData)
</script>

<style scoped>
.register-card :deep(.el-card__header) {
  padding: 10px 16px;
  font-weight: 600;
}
</style>

<template>
  <div class="extension-manager">
    <div class="toolbar">
      <el-button type="primary" @click="showCreate = true">新建扩展</el-button>
      <el-button :loading="reloading" @click="reload">重新加载</el-button>
    </div>
    <el-table :data="extensions" stripe v-loading="loading">
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip />
      <el-table-column label="适用模式" width="100">
        <template #default="{ row }">
          <el-tag :type="modeTagType(row.mode || 'all')" size="small">
            {{ modeLabel(row.mode || 'all') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button type="primary" text size="small" @click="openEdit(row)">编辑</el-button>
          <el-button
            :type="row.enabled ? 'warning' : 'success'"
            text size="small"
            @click="toggle(row.name, !row.enabled)">
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" text size="small" @click="remove(row.name)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建扩展弹窗 -->
    <el-dialog v-model="showCreate" title="新建扩展" width="560" append-to-body destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="英文标识，如 video_workflow" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="扩展用途说明" />
        </el-form-item>
        <el-form-item label="适用模式">
          <el-select v-model="form.mode">
            <el-option label="智能剪辑" value="video" />
            <el-option label="漫剧创作" value="comic" />
            <el-option label="通用（所有模式）" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="form.system_prompt" type="textarea" :rows="10" placeholder="注入给 AI Agent 的提示词内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑扩展弹窗 -->
    <el-dialog v-model="showEdit" :title="`编辑扩展: ${editForm.name}`" width="640" append-to-body destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input :model-value="editForm.name" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" placeholder="扩展用途说明" />
        </el-form-item>
        <el-form-item label="适用模式">
          <el-select v-model="editForm.mode">
            <el-option label="智能剪辑" value="video" />
            <el-option label="漫剧创作" value="comic" />
            <el-option label="通用（所有模式）" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="editForm.system_prompt" type="textarea" :rows="14" placeholder="注入给 AI Agent 的提示词内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_HOST } from '@/api/modules'

const loading = ref(false)
const reloading = ref(false)
const creating = ref(false)
const saving = ref(false)
const extensions = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const form = ref({ name: '', description: '', system_prompt: '', mode: 'all' })
const editForm = ref({ name: '', description: '', system_prompt: '', mode: 'all' })

const modeLabel = (mode) => ({ video: '智能剪辑', comic: '漫剧', all: '通用' }[mode] || '通用')
const modeTagType = (mode) => ({ video: '', comic: 'warning', all: 'info' }[mode] || 'info')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await fetch(`${API_HOST}/api/extensions`).then(r => r.json())
    extensions.value = res.data || []
  } catch {
    ElMessage.error('加载扩展列表失败')
  } finally {
    loading.value = false
  }
}

const toggle = async (name, enabled) => {
  try {
    await fetch(`${API_HOST}/api/extensions/${name}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    }).then(r => r.json())
    ElMessage.success(enabled ? '已启用' : '已禁用')
    await fetchData()
  } catch {
    ElMessage.error('操作失败')
  }
}

const remove = async (name) => {
  try {
    await ElMessageBox.confirm(`确定删除扩展「${name}」？`, '提示', { type: 'warning' })
    await fetch(`${API_HOST}/api/extensions/${name}`, { method: 'DELETE' }).then(r => r.json())
    ElMessage.success('已删除')
    await fetchData()
  } catch {}
}

const create = async () => {
  if (!form.value.name.trim()) return ElMessage.warning('请输入名称')
  creating.value = true
  try {
    const res = await fetch(`${API_HOST}/api/extensions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    }).then(r => r.json())
    if (res.success === false) {
      ElMessage.error(res.message || '创建失败')
    } else {
      ElMessage.success('创建成功')
      showCreate.value = false
      form.value = { name: '', description: '', system_prompt: '', mode: 'all' }
      await fetchData()
    }
  } catch {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

const openEdit = (row) => {
  editForm.value = {
    name: row.name,
    description: row.description || '',
    system_prompt: row.systemPrompt || row.system_prompt || '',
    mode: row.mode || 'all',
  }
  showEdit.value = true
}

const saveEdit = async () => {
  saving.value = true
  try {
    const res = await fetch(`${API_HOST}/api/extensions/${editForm.value.name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: editForm.value.description,
        system_prompt: editForm.value.system_prompt,
        mode: editForm.value.mode,
      }),
    }).then(r => r.json())
    if (res.code === 404) {
      ElMessage.error('扩展不存在')
    } else {
      ElMessage.success('已保存')
      showEdit.value = false
      await fetchData()
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const reload = async () => {
  reloading.value = true
  try {
    await fetch(`${API_HOST}/api/extensions/reload`, { method: 'POST' }).then(r => r.json())
    ElMessage.success('扩展已重新加载')
    await fetchData()
  } catch {
    ElMessage.error('重载失败')
  } finally {
    reloading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

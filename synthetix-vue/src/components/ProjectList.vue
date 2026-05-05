<template>
  <div class="project-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目管理</span>
          <div class="header-actions">
            <el-upload
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleImport"
              accept=".json"
            >
              <el-button size="small">导入项目</el-button>
            </el-upload>
            <el-button type="primary" size="small" @click="showCreateDialog = true">新建项目</el-button>
          </div>
        </div>
      </template>

      <el-table :data="projects" v-loading="loading" style="width: 100%;">
        <el-table-column prop="name" label="项目名称" min-width="160">
          <template #default="{ row }">
            <span class="clickable-text" @click="openProject(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模式" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'workflow' ? 'primary' : 'warning'" size="small">
              {{ row.mode === 'workflow' ? '工作流' : '对话式' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="时长" width="80" align="center">
          <template #default="{ row }">
            {{ formatDuration(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.updatedAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openProject(row)">打开</el-button>
            <el-button size="small" text @click="exportProject(row)">导出</el-button>
            <el-button size="small" text type="danger" @click="deleteProject(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadProjects"
          @current-change="loadProjects"
        />
      </div>
    </el-card>

    <!-- 新建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建项目" width="420px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="createForm.name" placeholder="输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="可选描述" />
        </el-form-item>
        <el-form-item label="剪辑模式" required>
          <el-radio-group v-model="createForm.mode">
            <el-radio value="workflow">工作流剪辑</el-radio>
            <el-radio value="conversation">对话式剪辑</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '@/api/modules'
import { formatTime, formatDuration, getStatusType, getStatusText } from '@/utils/formatUtils'

const router = useRouter()

const projects = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  mode: 'workflow'
})

const loadProjects = async () => {
  loading.value = true
  try {
    const data = await projectApi.list({ page: page.value, page_size: pageSize.value })
    projects.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error('获取项目列表失败')
  } finally {
    loading.value = false
  }
}

const createProject = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  creating.value = true
  try {
    const data = await projectApi.create({
      name: createForm.value.name,
      description: createForm.value.description,
      mode: createForm.value.mode
    })
    showCreateDialog.value = false
    ElMessage.success('项目创建成功')
    openProject(data)
  } catch (error) {
    // error handled in api
  } finally {
    creating.value = false
  }
}

const openProject = (row) => {
  router.push({ path: '/editor', query: { projectId: row.id || row.projectId } })
}

const exportProject = async (row) => {
  try {
    const data = await projectApi.exportProject(row.id || row.projectId)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${row.name || 'project'}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const deleteProject = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除项目 "${row.name}"？`, '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await projectApi.remove(row.id || row.projectId)
    ElMessage.success('已删除')
    await loadProjects()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleImport = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    await projectApi.importProject(formData)
    ElMessage.success('导入成功')
    await loadProjects()
  } catch (error) {
    ElMessage.error('导入失败')
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.project-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.clickable-text {
  color: #409eff;
  cursor: pointer;
}

.clickable-text:hover {
  text-decoration: underline;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>

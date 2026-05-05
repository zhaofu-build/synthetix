<template>
  <div class="cookie-manager">
    <el-alert v-if="cookieExists" type="success" :closable="false" show-icon>
      <template #title>Cookie 文件已配置（{{ lineCount }} 行）</template>
    </el-alert>
    <el-alert v-else type="warning" :closable="false" show-icon>
      <template #title>未配置 Cookie，部分视频网站（抖音、B站等）下载可能失败</template>
    </el-alert>

    <div class="cookie-section">
      <div class="section-header">
        <span class="section-title">支持站点</span>
      </div>
      <div class="site-tags">
        <el-tag v-for="site in sites" :key="site.domain" :type="hasDomain(site.domain) ? 'success' : 'info'" size="small">
          {{ site.name }}
        </el-tag>
      </div>
    </div>

    <div class="cookie-section">
      <div class="section-header">
        <span class="section-title">Cookie 内容</span>
        <div class="section-actions">
          <el-upload :show-file-list="false" accept=".txt" :before-upload="handleFileUpload">
            <el-button text size="small"><el-icon><Upload /></el-icon> 上传 cookies.txt</el-button>
          </el-upload>
          <el-button v-if="cookieExists" text size="small" type="danger" @click="handleDelete">
            <el-icon><Delete /></el-icon> 删除
          </el-button>
        </div>
      </div>
      <el-input v-model="content" type="textarea" :rows="10" placeholder="粘贴 Netscape 格式的 Cookie 内容，或上传 cookies.txt 文件" />
      <div class="cookie-footer">
        <el-button type="primary" size="small" :loading="saving" @click="handleSave">保存</el-button>
        <span class="cookie-hint">
          使用浏览器插件（如 "Get cookies.txt LOCALLY"）在目标网站导出 Cookie
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Delete } from '@element-plus/icons-vue'
import { systemApi } from '@/api/modules/system'

const content = ref('')
const cookieExists = ref(false)
const saving = ref(false)

const sites = [
  { name: '抖音', domain: 'douyin.com' },
  { name: 'B站', domain: 'bilibili.com' },
  { name: 'YouTube', domain: 'youtube.com' },
  { name: 'Twitter/X', domain: 'twitter.com' },
  { name: 'Instagram', domain: 'instagram.com' },
]

const lineCount = computed(() => content.value.split('\n').filter(l => l.trim() && !l.startsWith('#')).length)

const hasDomain = (domain) => content.value.toLowerCase().includes(domain)

const loadCookies = async () => {
  try {
    const res = await systemApi.getCookies()
    cookieExists.value = res.exists
    content.value = res.content || ''
  } catch {
    cookieExists.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await systemApi.saveCookies(content.value)
    cookieExists.value = !!content.value.trim()
    ElMessage.success('Cookie 已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async () => {
  await ElMessageBox.confirm('确定删除 Cookie 文件？删除后部分网站下载可能失败。', '确认删除')
  try {
    await systemApi.deleteCookies()
    content.value = ''
    cookieExists.value = false
    ElMessage.success('Cookie 已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

const handleFileUpload = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    content.value = e.target.result
    handleSave()
  }
  reader.readAsText(file)
  return false
}

onMounted(loadCookies)
</script>

<style scoped>
.cookie-manager { display: flex; flex-direction: column; gap: 12px; }
.cookie-section { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; padding: 12px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.section-title { font-weight: 600; font-size: 13px; }
.section-actions { display: flex; gap: 4px; }
.site-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.cookie-footer { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.cookie-hint { font-size: 11px; color: var(--el-text-color-placeholder); }
</style>

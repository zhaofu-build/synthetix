<template>
  <el-dialog v-model="bgmManagerVisible" title="BGM 管理" width="600px" @close="emit('close')">
    <div style="display: flex; justify-content: flex-end; margin-bottom: 12px; gap: 8px;">
      <el-upload
        action="#"
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleBgmUpload"
      >
        <el-button type="primary" size="small">上传BGM</el-button>
      </el-upload>
      <el-button size="small" @click="aiGenerateBgm" :loading="bgmGenerating">AI 生成BGM</el-button>
    </div>
    <el-table :data="bgmList" size="small" v-loading="bgmLoading">
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column label="试听">
        <template #default="{ row }">
          <audio v-if="row.webPath" :src="assetUrl(row.webPath)" controls style="height: 28px; width: 100%;" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="selectBgmFromList(row)">选用</el-button>
          <el-button size="small" text type="danger" @click="deleteBgm(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { assetUrl, projectApi } from '@/api/modules'

const props = defineProps({
  visible: Boolean,
  creative: { type: String, default: '' },
  style: { type: String, default: '' },
  targetDuration: { type: Number, default: 30 }
})

const emit = defineEmits(['close', 'selected'])

const bgmList = ref([])
const bgmLoading = ref(false)
const bgmManagerVisible = ref(false)
const bgmGenerating = ref(false)

watch(() => props.visible, (val) => {
  if (val) {
    bgmManagerVisible.value = true
    loadBgmList()
  }
})

const loadBgmList = async () => {
  bgmLoading.value = true
  try {
    const data = await projectApi.listBgm()
    bgmList.value = data?.items || data || []
  } catch (error) {
    console.error('获取BGM列表失败:', error)
    bgmList.value = []
  } finally {
    bgmLoading.value = false
  }
}

const selectBgmFromList = (row) => {
  emit('selected', { id: row.id, webPath: row.webPath, name: row.name })
  bgmManagerVisible.value = false
  ElMessage.success(`已选用: ${row.name}`)
}

const handleBgmUpload = async (file) => {
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/ogg']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式')
    return
  }
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    formData.append('name', file.name.replace(/\.[^.]+$/, ''))
    await projectApi.uploadBgm(formData)
    ElMessage.success('BGM上传成功')
    await loadBgmList()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const deleteBgm = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该BGM？', '提示', { type: 'warning' })
    await projectApi.deleteBgm(id)
    ElMessage.success('已删除')
    await loadBgmList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const aiGenerateBgm = async () => {
  if (!props.creative) {
    ElMessage.warning('请先输入文案描述')
    return
  }
  bgmGenerating.value = true
  try {
    const data = await projectApi.aiGenerateBgm({
      description: props.creative,
      style: props.style,
      duration: props.targetDuration
    })
    if (data) {
      emit('selected', { id: data.id, webPath: data.webPath, name: data.name })
      ElMessage.success('BGM生成成功')
      await loadBgmList()
    }
  } catch (error) {
    ElMessage.error(error.message || 'AI生成BGM失败')
  } finally {
    bgmGenerating.value = false
  }
}
</script>

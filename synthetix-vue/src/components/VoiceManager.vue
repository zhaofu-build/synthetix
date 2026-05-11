<template>
  <el-dialog v-model="voiceManagerVisible" title="音色管理" width="700px" @close="emit('close')">
    <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
      <el-button type="primary" size="small" @click="openAddVoiceDialog">添加音色</el-button>
    </div>
    <el-table :data="voiceList" size="small" v-loading="voiceLoading">
      <el-table-column prop="audioName" label="名称" width="140" />
      <el-table-column prop="promptText" label="参考文本" show-overflow-tooltip />
      <el-table-column label="参考音频" width="120">
        <template #default="{ row }">
          <audio v-if="row.webPath" :src="assetUrl(row.webPath)" controls style="height: 28px; width: 100px;" />
          <span v-else style="color: #909399; font-size: 12px;">无</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130">
        <template #default="{ row }">
          <el-button size="small" text @click="openEditVoiceDialog(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="deleteVoice(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>

  <el-dialog v-model="voiceFormVisible" :title="voiceFormIsEdit ? '编辑音色' : '添加音色'" width="480px">
    <el-form :model="voiceForm" label-width="90px">
      <el-form-item label="音色名称" required>
        <el-input v-model="voiceForm.audio_name" placeholder="输入音色名称" />
      </el-form-item>
      <el-form-item label="参考音频">
        <div v-if="voiceFormIsEdit && voiceFormExistAudio && !voiceFormAudioName" style="margin-bottom: 6px;">
          <audio :src="voiceFormExistAudio" controls style="height: 32px; width: 100%;" />
        </div>
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="handleVoiceAudioUpload"
        >
          <el-button size="small">{{ voiceFormIsEdit ? '替换音频' : '选择音频' }}</el-button>
        </el-upload>
        <div v-if="voiceFormAudioName" style="margin-top: 4px; font-size: 12px; color: #67c23a;">
          已选择: {{ voiceFormAudioName }}
        </div>
      </el-form-item>
      <el-form-item label="参考文本" required>
        <el-input v-model="voiceForm.prompt_text" type="textarea" :rows="3" placeholder="参考音频对应的文本" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="voiceFormVisible = false">取消</el-button>
      <el-button type="primary" :loading="voiceSaving" @click="saveVoiceForm">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { assetUrl, audioApi } from '@/api/modules'

const props = defineProps({
  visible: Boolean
})

const emit = defineEmits(['close', 'updated'])

const voiceManagerVisible = ref(false)
const voiceFormVisible = ref(false)
const voiceFormIsEdit = ref(false)
const voiceFormAudioFile = ref(null)
const voiceFormAudioName = ref('')
const voiceFormExistAudio = ref('')
const voiceSaving = ref(false)
const voiceLoading = ref(false)
const voiceList = ref([])
const voiceForm = ref({
  id: null,
  audio_name: '',
  prompt_text: ''
})

watch(() => props.visible, (val) => {
  if (val) {
    voiceManagerVisible.value = true
    loadVoiceList()
  }
})

const loadVoiceList = async () => {
  voiceLoading.value = true
  try {
    const data = await audioApi.getSourceAudio({ page_size: 100 })
    voiceList.value = data?.items || []
  } catch (error) {
    ElMessage.error('获取音色列表失败')
  } finally {
    voiceLoading.value = false
  }
}

const openAddVoiceDialog = () => {
  voiceFormIsEdit.value = false
  voiceFormAudioFile.value = null
  voiceFormAudioName.value = ''
  voiceFormExistAudio.value = ''
  voiceForm.value = {
    id: null,
    audio_name: '',
    prompt_text: ''
  }
  voiceFormVisible.value = true
}

const openEditVoiceDialog = (row) => {
  voiceFormIsEdit.value = true
  voiceFormAudioFile.value = null
  voiceFormAudioName.value = ''
  voiceFormExistAudio.value = row.webPath ? assetUrl(row.webPath) : ''
  voiceForm.value = {
    id: row.id,
    audio_name: row.audioName || '',
    prompt_text: row.promptText || ''
  }
  voiceFormVisible.value = true
}

const handleVoiceAudioUpload = (file) => {
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/flac']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式，请上传 MP3/WAV/FLAC')
    return
  }
  voiceFormAudioFile.value = file.raw
  voiceFormAudioName.value = file.name
}

const saveVoiceForm = async () => {
  const form = voiceForm.value
  if (!form.audio_name.trim()) {
    ElMessage.warning('请输入音色名称')
    return
  }
  if (!form.prompt_text.trim()) {
    ElMessage.warning('请输入参考文本')
    return
  }

  voiceSaving.value = true
  try {
    if (voiceFormIsEdit.value) {
      await audioApi.updateAudio(form.id, {
        audio_name: form.audio_name,
        prompt_text: form.prompt_text
      })
      ElMessage.success('音色更新成功')
    } else {
      if (!voiceFormAudioFile.value) {
        ElMessage.warning('请选择参考音频文件')
        voiceSaving.value = false
        return
      }
      const ext = voiceFormAudioName.value.split('.').pop()
      const formData = new FormData()
      formData.append('file', voiceFormAudioFile.value)
      formData.append('audio_name', form.audio_name)
      formData.append('prompt_text', form.prompt_text)
      formData.append('output_format', ext)
      await audioApi.saveTimbre(formData)
      ElMessage.success('音色添加成功')
    }
    voiceFormVisible.value = false
    await loadVoiceList()
    emit('updated')
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  } finally {
    voiceSaving.value = false
  }
}

const deleteVoice = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该音色？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await audioApi.deleteSourceAudio(id)
    ElMessage.success('已删除')
    await loadVoiceList()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}
</script>

<template>
  <div style="margin-top: 16px;">
    <el-button type="primary" @click="handleRender" :loading="rendering" style="width: 100%;">
      应用并渲染
    </el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { projectApi } from '@/api/modules'

const props = defineProps({
  projectId: { type: [Number, String], default: null },
  ttsLocalPath: { type: String, default: '' },
  selectedBgm: { type: [Number, String], default: null },
  bgmVolume: { type: Number, default: 0.3 },
  totalDuration: { type: Number, default: 0 }
})

const emit = defineEmits(['rendered'])

const rendering = ref(false)

const handleRender = async () => {
  rendering.value = true
  try {
    await projectApi.applyPlan(props.projectId)

    const audioConfig = {}
    if (props.ttsLocalPath) {
      audioConfig.tts_path = props.ttsLocalPath
    }
    if (props.selectedBgm) {
      audioConfig.bgm_id = props.selectedBgm
      audioConfig.bgm_volume = props.bgmVolume
    }

    const renderData = await projectApi.render(props.projectId, audioConfig)
    const result = {
      duration: renderData.duration || props.totalDuration,
      webPath: renderData.webPath
    }
    emit('rendered', result)
    ElMessage.success('渲染完成')
  } catch (error) {
    ElMessage.error(`渲染失败: ${error.message}`)
  } finally {
    rendering.value = false
  }
}
</script>

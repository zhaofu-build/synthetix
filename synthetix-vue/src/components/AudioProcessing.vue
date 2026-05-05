<template>
  <div class="audio-processing">
    <!-- 素材处理 -->
    <el-collapse v-model="activePanels" class="processing-section">
      <el-collapse-item title="素材处理" name="material">
        <el-card shadow="never">
          <el-row :gutter="20">

            <el-col :span="15">
                  <el-upload
                      action="#"
                      drag
                      :show-file-list="false"
                      :auto-upload="false"
                      :on-change="handleSourceAudioUpload"
                      :disabled="uploadAudio"
                      class="full-width-upload"
                      accept=".mp3,.wav,.flac">
                    <template #default>
                      <p class="drop-subtext">上传歌曲</p>
                      <div class="drop-overlay" :class="{ 'has-audio': audioPath }">
                        <div v-if="!audioPath" class="upload-guide">
                          <el-icon :size="60">
                            <Upload/>
                          </el-icon>
                          <p class="drop-text">点击或拖放音频文件到这里</p>
                        </div>
                        <audio
                            v-if="audioPath"
                            :src="audioWebPath"
                            controls
                            class="audio-preview"/>
                        <div v-if="audioPath" class="replace-overlay">
                        </div>
                        <p v-if="uploadAudio" class="upload-status">上传中...</p>
                      </div>
                    </template>
                  </el-upload>

            </el-col>

            <el-col :span="9">

                  <el-upload
                      action="#"
                      drag
                      :show-file-list="false"
                      :auto-upload="false"
                      :on-change="handleYourSourceAudioUpload"
                      :disabled="uploadAudio"
                  >
                    <template #default>
                      <div class="drop-overlay" :class="{ 'has-audio': sourceAudioPath }">
                        <p class="drop-subtext">你的声音</p>
                        <div v-if="!sourceAudioPath" class="upload-guide">
                          <el-icon :size="60">
                            <Upload/>
                          </el-icon>
                          <p class="drop-text">点击或拖放音频文件到这里</p>
                        </div>
                        <audio
                            v-if="sourceAudioPath"
                            :src="sourceAudioWebPath"
                            controls
                            class="audio-preview"/>
                        <div v-if="sourceAudioPath" class="replace-overlay">
                        </div>
                      </div>
                    </template>
                  </el-upload>

            </el-col>

          </el-row>
        </el-card>
      </el-collapse-item>
    </el-collapse>

    <!-- 分离结果 -->
    <el-collapse v-model="activePanels" class="result-section">
      <el-collapse-item title="分离结果" name="result">
        <el-row :gutter="20">
          <el-col :span="12">

            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <el-icon>
                    <Headset/>
                  </el-icon>
                  <span>人声歌声</span>
                </div>
              </template>
              <el-upload
                  action="#"
                  drag
                  :show-file-list="false"
                  :auto-upload="false"
                  :on-change="handleSourceAudioUpload"
                  class="full-width-upload"
                  accept=".mp3,.wav,.flac">
                <template #default>
                  <div class="drop-overlay" :class="{ 'has-audio': vocalUrl }">
                    <div v-if="!vocalUrl" class="upload-guide">
                      <el-icon :size="30">
                        <Upload/>
                      </el-icon>
                      <p class="drop-text">点击或拖放音频文件到这里</p>
                    </div>
                    <audio
                        v-if="vocalUrl"
                        :src="vocalWebUrl"
                        controls
                        class="audio-preview"/>
                    <div v-if="vocalUrl" class="replace-overlay">
                    </div>
                  </div>
                </template>
              </el-upload>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <el-icon>
                    <VideoPause/>
                  </el-icon>
                  <span>伴奏</span>
                </div>
              </template>
              <el-upload
                  action="#"
                  drag
                  :show-file-list="false"
                  :auto-upload="false"
                  :on-change="handleSourceAudioUpload"
                  class="full-width-upload"
                  accept=".mp3,.wav,.flac">
                <template #default>
                  <div class="drop-overlay" :class="{ 'has-audio': accompanimentUrl }">
                    <div v-if="!accompanimentUrl" class="upload-guide">
                      <el-icon :size="30">
                        <Upload/>
                      </el-icon>
                      <p class="drop-text">点击或拖放音频文件到这里</p>
                    </div>
                    <audio
                        v-if="accompanimentUrl"
                        :src="accompanimentWebUrl"
                        controls
                        class="audio-preview"/>
                    <div v-if="accompanimentUrl" class="replace-overlay">
                    </div>
                  </div>
                </template>
              </el-upload>

            </el-card>
          </el-col>
        </el-row>

        <el-row :span="8">
                    <el-button
                        type="success"
                        size="large"
                        :loading="separating"
                        @click="handleSeparate"
                    >
                      <el-icon>
                        <MagicStick/>
                      </el-icon>
                      分离音频和伴奏
                    </el-button>
          <el-button
              type="warning"
              size="large"
              @click="handleMerge"
          >
            <el-icon>
              <Connection/>
            </el-icon>
            歌曲转换
          </el-button>
        </el-row>
      </el-collapse-item>
    </el-collapse>

  </div>
</template>

<script setup>
import {ref} from 'vue'
import {ElIcon, ElMessage} from 'element-plus'
import API from "@/components/config/api.js";
import {Upload, Headset, Connection, VideoPause, MagicStick} from "@element-plus/icons-vue";


// 响应式状态
const activePanels = ref(['material', 'result', 'merge'])
const audioPath = ref(null)
const audioWebPath = ref(null)
const uploadAudio = ref(false)
const sourceAudioPath = ref(null)
const sourceAudioWebPath = ref(null)
const merging = ref(false)
const separating = ref(false)
const vocalUrl = ref(null)
const vocalWebUrl = ref(null)
const accompanimentUrl = ref(null)
const accompanimentWebUrl = ref(null)

// 处理源音频上传
const handleYourSourceAudioUpload = async (file) => {
  // 加强文件类型验证
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/flac']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式')
    return false
  }
  try {
    uploadAudio.value = true
    const formData = new FormData()
    formData.append('file_stream', file.raw)
    const response = await fetch(API.upload_video, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('上传失败')

    const result = await response.json()
    // 后端返回格式: {success: true, data: {webPath, localPath, ...}, ...}
    const data = result.data || {}
    sourceAudioWebPath.value = `${API.HOST}/${data.webPath}`
    sourceAudioPath.value = data.localPath
    ElMessage.success('文件上传成功')
  } catch (error) {
    ElMessage.error(error.message)
    return false
  } finally {
    uploadAudio.value = false
  }
  return false // 阻止默认上传
}


// 处理源音频上传
const handleSourceAudioUpload = async (file) => {
  // 加强文件类型验证
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/flac']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式')
    return false
  }
  try {
    uploadAudio.value = true
    const formData = new FormData()
    formData.append('file_stream', file.raw)
    const response = await fetch(API.upload_all_file_stream, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('上传失败')

    const result = await response.json()
    // 后端返回格式: {success: true, data: {webPath, localPath, ...}, ...}
    const data = result.data || {}
    audioWebPath.value = `${API.HOST}/${data.webPath}`
    audioPath.value = data.localPath
    ElMessage.success('文件上传成功')
  } catch (error) {
    ElMessage.error(error.message)
    return false
  } finally {
    uploadAudio.value = false
  }
  return false // 阻止默认上传
}

// 移除源音频
const removeSourceAudio = () => {
  audioWebPath.value = null
  audioPath.value = null
  vocalUrl.value = null
  accompanimentUrl.value = null
}

// 音频分离
const handleSeparate = async () => {
  if (!audioPath.value) {
    ElMessage.error('请先上传原素材')
    return
  }
  try {
    separating.value = true
    const params = {
      audio_path: audioPath.value,
    }
    const response = await fetch(API.separate_audio, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params)
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {vocalWebUrl, vocalUrl, accompanimentWebUrl, accompanimentUrl}, ...}
    const data = result.data || {}
    vocalWebUrl.value = `${API.HOST}/${data.vocalWebUrl}`
    vocalUrl.value = data.vocalUrl
    accompanimentWebUrl.value = `${API.HOST}/${data.accompanimentWebUrl}`
    accompanimentUrl.value = data.accompanimentUrl
    ElMessage.success('分离成功')
  } catch (error) {
    ElMessage.error(`分离失败: ${error.message}`)
  } finally {
    separating.value = false
  }
}

// 歌曲转换
const handleMerge = async () => {

  if (!audioPath.value) {
    ElMessage.error('请先上传你的声音')
    return
  }
  // 歌曲转换
  try {
    merging.value = true
    const params = {
      audio_path: audioPath.value,
    }
    const response = await fetch(API.separate_audio, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params)
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {vocalWebUrl, vocalUrl, accompanimentWebUrl, accompanimentUrl}, ...}
    const data = result.data || {}
    vocalWebUrl.value = `${API.HOST}/${data.vocalWebUrl}`
    vocalUrl.value = data.vocalUrl
    accompanimentWebUrl.value = `${API.HOST}/${data.accompanimentWebUrl}`
    accompanimentUrl.value = data.accompanimentUrl
    ElMessage.success('歌曲转换成功')
  } catch (error) {
    ElMessage.error(`转换失败: ${error.message}`)
  } finally {
    merging.value = false
  }
}
</script>
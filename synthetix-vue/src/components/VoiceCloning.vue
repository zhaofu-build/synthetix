<template>
  <div class="voice-clone-container">
    <!-- 音频处理面板 -->
    <el-collapse v-model="activePanels" class="processing-section">
      <div class="audio-panels">
        <!-- 源音频上传面板 -->
        <el-card class="audio-panel source-audio">
          <div class="panel-header">
            <el-icon class="panel-icon">
              <Upload/>
            </el-icon>
            <h3>参考音频</h3>
          </div>
          <el-upload
              drag
              :show-file-list="false"
              :auto-upload="false"
              @change="handleSourceAudioUpload"
          >
            <template #default>
              <div class="upload-content">
                <transition name="el-fade-in">
                  <div v-if="!sourceAudioPath" class="upload-empty">
                    <el-icon class="upload-icon">
                      <Upload/>
                    </el-icon>
                    <p class="upload-text">参考音频:拖放音频文件或点击上传</p>
                    <p class="upload-subtext">支持 MP3/WAV/FLAC 格式</p>
                  </div>
                </transition>

                <div v-if="sourceAudioPath" class="audio-preview">
                  <audio :src="sourceAudioWebPath" controls class="audio-element"/>
                  <el-button
                      circle
                      class="remove-button"
                      @click="sourceAudioPath = null; sourceAudioBase64 = null;">
                    <el-icon>
                      <Close/>
                    </el-icon>
                  </el-button>
                </div>
              </div>
            </template>
          </el-upload>
          <!-- 文本输入区域 -->
          <div class="text-inputs">
            <el-form-item label="参考文本" class="enhanced-input">
              <el-input
                  v-model="sourceText"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入参考音频的文本内容"
                  resize="none"
                  clearable
                  :maxlength="200"
                  show-word-limit
              />
            </el-form-item>

            <el-form-item label="生成文本" class="enhanced-input">
              <el-input
                  v-model="text"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入需要生成语音的文本"
                  resize="none"
                  clearable
                  :maxlength="500"
                  show-word-limit
              />
            </el-form-item>
          </div>
        </el-card>
        <el-card >
          <template #header>
            <div class="card-header">
              <span>音色管理</span>
            </div>
          </template>

          <el-table :data="audioList">
            <el-table-column>
              <template #default="{ row }">
                  <span class="clickable-text" @click="handlePreview(row.web_path, row.prompt_text)">
                  {{ row.audio_name }}
                  </span>
              </template>
            </el-table-column>
            <el-table-column width="100">
              <template #default="{ row }">
                <el-button
                    type="danger"
                    size="small"
                    @click="deleteMaterial(row.id)"
                >删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

        </el-card>
      </div>
    </el-collapse>

    <!-- 修改：添加控制面板和生成结果面板的容器 -->
    <div class="control-result-container">
      <!-- 参数控制区域 -->
      <el-card class="param-controls">
        <el-form-item label="随机种子" class="slider-item">
          <el-input-number
              v-model="seed"
              :min="0"
              :max="100000"
              controls-position="right"/>
        </el-form-item>
        <el-form-item :label="`语速`" class="slider-item">
          <el-slider
              v-model="speed"
              :min="0.5"
              :max="2"
              :step="0.05"
              show-input
              input-size="small"/>
        </el-form-item>
        <el-form-item label="Top P" class="slider-item">
          <el-slider
              v-model="top_p"
              :min="0"
              :max="1"
              :step="0.01"
              show-input/>
        </el-form-item>
        <el-form-item label="Temperature" class="slider-item">
          <el-slider
              v-model="temperature"
              :min="0"
              :max="1"
              :step="0.01"
              show-input/>
        </el-form-item>
        <el-form-item label="重复惩罚" class="slider-item">
          <el-slider
              v-model="repetition_penalty"
              :min="1"
              :max="2"
              :step="0.1"
              show-input></el-slider>
        </el-form-item>
        <!-- 操作按钮 -->
        <div class="action-area">
          <el-button
              type="primary"
              size="large"
              :loading="saveing"
              @click="saveTimbre"
              class="magic-button"
          >
            <template #icon>
              <el-icon>
                <MagicStick/>
              </el-icon>
            </template>
            保存音色
          </el-button>

          <el-button
              type="primary"
              size="large"
              :loading="generating"
              @click="handleClone"
              class="magic-button"
          >
            <template #icon>
              <el-icon>
                <MagicStick/>
              </el-icon>
            </template>
            开始语音克隆
          </el-button>
        </div>
      </el-card>

      <!-- 生成音频面板 -->
      <el-card class="audio-panel generated-audio">
        <div class="panel-header">
          <el-icon class="panel-icon">
            <MagicStick/>
          </el-icon>
          <h3>生成结果</h3>
        </div>

        <div class="result-content">
          <template v-if="finalWebUrl">
            <audio :src="finalWebUrl + '?t=' + audioTimestamp" controls class="audio-element"/>
          </template>
          <div v-else class="empty-result">
            <el-icon class="result-icon">
              <Headset/>
            </el-icon>
            <p class="result-text">等待生成语音内容</p>
            <p class="result-subtext">克隆结果将在此处显示</p>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import {ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import API from "@/components/config/api.js"
import {Upload, Close, MagicStick, Download, Headset} from '@element-plus/icons-vue'
import axios from 'axios'

const audioList = ref([])
// 音频相关状态
const activePanels = ref(['material', 'result', 'merge'])
const sourceAudioPath = ref(null)
const sourceAudioWebPath = ref(null)
const sourceAudioBase64 = ref(null) // 新增：存储音频的Base64
const finalWebUrl = ref(null)
const audioTimestamp = ref(Date.now())
const generating = ref(false)
const saveing = ref(false)
// 文本内容
const sourceText = ref('')
const text = ref('')

// 控制参数
const seed = ref(Math.floor(Math.random() * 100000) + 1) // 新增随机种子参数
const speed = ref(1)   // 对应后端的speed_factor
const top_p = ref(0.85)
const temperature = ref(0.8)
const repetition_penalty = ref(1.1) // 新增重复惩罚因子

// 获取已存在音色素材
const refreshAudioList = async () => {
  // GET /api/audios
  const {data} = await axios.get(API.get_source_audio)
  // 后端返回格式: {success: true, data: {items: [...], total: 0, ...}, ...}
  audioList.value = data.data?.items || []
}

// 删除本地素材
const deleteMaterial = async (id) => {
  // DELETE /api/audios/{id}
  await axios.delete(`${API.del_source_audio}/${id}`)
  refreshAudioList()
}

// 点击文件名事件
const handlePreview = async (web_path, prompt_text) => {
  sourceAudioWebPath.value = `${API.HOST}/${web_path}`
  sourceText.value = prompt_text
  sourceAudioPath.value = web_path
  console.log(prompt_text)
  console.log(sourceAudioWebPath.value)
  try {
    // 新增：获取音频base64数据
    const response = await fetch(sourceAudioWebPath.value)
    if (!response.ok) throw new Error('音频获取失败')
    const blob = await response.blob()

    // 转换blob为base64
    const reader = new FileReader()
    reader.readAsDataURL(blob)
    reader.onload = () => {
      sourceAudioBase64.value = reader.result.split(',')[1]
    }
  } catch (error) {
    ElMessage.error(`音频加载失败: ${error.message}`)
    sourceAudioBase64.value = null
  }
}
const handleSourceAudioUpload = async (file) => {
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/flac']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式')
    return false
  }

  try {
    // 新增：读取文件为Base64
    const reader = new FileReader()
    reader.onload = (e) => {
      // 只保留base64数据部分（去掉data URI前缀）
      sourceAudioBase64.value = e.target.result.split(',')[1]
    }
    reader.readAsDataURL(file.raw)

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

    sourceAudioWebPath.value = `${API.HOST}/${data.webPath}`
    sourceAudioPath.value = data.localPath
    ElMessage.success('文件上传成功')
  } catch (error) {
    ElMessage.error(error.message)
  }
}

// 修改函数名为handleClone，符合新接口语义
const handleClone = async () => {
  // if (!sourceAudioBase64.value) {
  //   ElMessage.error('请先上传参考音频')
  //   return
  // }
  // if (!text.value) {
  //   ElMessage.error('请输入生成文本')
  //   return
  // }

  try {
    generating.value = true
    audioTimestamp.value = Date.now()

    // 请求参数
    const params = {
      text: text.value,
      seed: seed.value,
      speed_factor: speed.value,
      top_p: top_p.value,
      temperature: temperature.value,
      repetition_penalty: repetition_penalty.value,
      references_audio: sourceAudioBase64.value,
      references_text: sourceText.value,
      audio_source_id:-1
    }

    const response = await fetch(API.fish_voice, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params)
    })

    // 新接口返回文件路径
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.message || '生成失败')
    }
    const result = await response.json()
    // 后端返回格式: {success: true, data: {webPath, ...}, ...}
    const data = result.data || {}
    finalWebUrl.value = `${API.HOST}/${data.webPath}`
    // const filename = await response.text() // 获取文件名
    // finalWebUrl.value = `${API.HOST}/${filename}` // 合成完整URL
    ElMessage.success('语音生成成功')
  } catch (error) {
    ElMessage.error(`生成失败: ${error.message}`)
  } finally {
    generating.value = false
  }
}

const saveTimbre = async () => {
  if (!sourceAudioPath.value) {
    ElMessage.error('请先上传参考音频')
    return
  }
  if (!sourceText.value) {
    ElMessage.error('请输入参考文本')
    return
  }

  try {
    const { value: audioName } = await ElMessageBox.prompt(
        '请输入音色名称',
        '保存音色',
        {
          confirmButtonText: '保存',
          cancelButtonText: '取消',
          inputPlaceholder: '自定义音色名称',
          inputValidator: (value) => {
            if (!value || value.trim() === '') {
              return '音色名称不能为空';
            }
            return true;
          }
        }
    );
    if (!audioName) return; // 用户点击取消


    const formData = new FormData();
    const audioFile = await fetch(sourceAudioWebPath.value)
        .then(res => res.blob())
        .then(blob => new File([blob], sourceAudioPath.value.split('/').pop()));

    formData.append('file', audioFile);
    formData.append('audio_name', audioName);
    formData.append('prompt_text', sourceText.value);
    formData.append('seed', seed.value);
    formData.append('speed', speed.value);
    formData.append('top_p', top_p.value);
    formData.append('temperature', temperature.value);
    formData.append('repetition_penalty', repetition_penalty.value);
    formData.append('output_format', audioFile.name.split('.')[1]); // 自动检测格式

    saveing.value = true;

    // 3. 使用FormData提交所有参数
    const response = await fetch(API.save_timbre, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) throw new Error('保存失败');
    ElMessage.success('音色保存成功');
    refreshAudioList();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(`保存失败: ${error.message || error}`);
    }
  } finally {
    saveing.value = false
  }
  refreshAudioList()
}

// 初始化加载素材
refreshAudioList()
</script>
<style scoped src="@/styles/components/voice-cloning.css"></style>
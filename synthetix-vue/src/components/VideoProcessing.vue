<template>
  <div class="video-processing">
    <el-row :gutter="20">
      <!-- 左侧预览区 -->
      <el-col :span="12">
        <div
            class="preview-wrapper"
            @dragover.prevent="dragover=true"
            @dragleave="dragover=false"
            @drop="handleDrop"
            @click="handleVideoClick"
            :class="{ 'dragover': dragover }"
            :style="{ cursor: !videoPath ? 'pointer' : 'default' }">
          <!-- 自定义拖放提示层 -->
          <div v-if="!videoPath" class="drop-overlay">
            <el-icon :size="60">
              <Upload/>
            </el-icon>
            <p class="drop-text">点击或拖放视频上传</p>
          </div>
          <!-- 视频预览 -->
          <video v-if="videoPath" :src="videoWebPath" controls class="video-preview"/>
          <!-- 隐藏的上传组件 -->
          <el-upload
              ref="uploader"
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleVideoUpload"
              :disabled="uploadVideo"
              style="display: none">
          </el-upload>
        </div>
      </el-col>

      <!-- 右侧配置面板 -->
      <el-col :span="12">
        <el-tabs type="border-card">
          <el-tab-pane label="下载">
            <el-form label-position="top">
              <el-form-item label="视频URL">
                <el-input
                    v-model="videoUrl"
                    type="textarea"
                    :rows="2"
                    placeholder="请输入视频URL，支持上千网站视频下载"/>
              </el-form-item>
              <el-button
                  type="primary"
                  @click="handleDownload"
                  :loading="downloading">视频下载
              </el-button>
              <el-alert
                  v-if="downloadStatus"
                  :title="downloadStatus"
                  type="info"
                  class="mt-10"
                  show-icon/>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="基础">
            <el-form label-position="top">
              <!-- 处理参数 -->
              <el-form-item label="输出格式">
                <el-select
                    v-model="form.output_format"
                    placeholder="选择输出格式">
                  <el-option
                      v-for="fmt in ['mp4','avi','mov','mkv','webm']"
                      :key="fmt"
                      :value="fmt"/>
                </el-select>
              </el-form-item>
              <el-form-item label="剪切范围 (HH:MM:SS)">
                <div class="time-range">
                  <el-input v-model="form.start_time" placeholder="开始时间"/>
                  <el-input v-model="form.end_time" placeholder="结束时间"/>
                </div>
              </el-form-item>
              <el-form-item label="视频调整">
                <div class="slider-group">
                  <div class="slider-item">
                    <span>播放速度 ({{ form.speed }}x)</span>
                    <el-slider
                        v-model="form.speed"
                        :min="0"
                        :max="2"
                        :step="0.1"/>
                  </div>
                  <div class="slider-item">
                    <span>音量 ({{ (form.volume * 100).toFixed(0) }}%)</span>
                    <el-slider
                        v-model="form.volume"
                        :min="0"
                        :max="2"
                        :step="0.1"/>
                  </div>
                </div>
              </el-form-item>
              <el-button
                  type="primary"
                  @click="handleProcess"
                  :loading="uploadVideo">
                <el-icon>
                  <MagicStick/>
                </el-icon>
                开始处理
              </el-button>
            </el-form>

          </el-tab-pane>
          <el-tab-pane label="字幕">
            <el-row :gutter="20">
              <!-- 左侧配置区域 -->
              <el-col :span="14">
                <el-card shadow="hover">
                  <!-- 配置表单 -->
                  <el-form label-position="top">
                    <el-row :gutter="20">
                      <el-col :span="12">
                        <el-form-item label="输出格式">
                          <el-select v-model="config.outputFormat">
                            <el-option
                                v-for="fmt in outputFormats"
                                :key="fmt"
                                :label="fmt"
                                :value="fmt"/>
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-collapse v-show="config.isTranslate">
                        <el-row :gutter="20">
                          <el-col :span="8">
                            <el-form-item label="翻译引擎">
                              <el-select v-model="config.translator">
                                <el-option
                                    v-for="engine in translatorEngines"
                                    :key="engine"
                                    :label="engine"
                                    :value="engine"/>
                              </el-select>
                            </el-form-item>
                          </el-col>
                          <el-col :span="8">
                            <el-form-item label="目标语言">
                              <el-select v-model="config.targetLanguage">
                                <el-option
                                    v-for="lang in languageOptions"
                                    :key="lang.value"
                                    :label="lang.label"
                                    :value="lang.value"/>
                              </el-select>
                            </el-form-item>
                          </el-col>
                          <el-col :span="8">
                            <el-form-item>
                              <el-checkbox v-model="config.doubleSubtitle">双语对照</el-checkbox>
                            </el-form-item>
                          </el-col>
                        </el-row>
                      </el-collapse>
                    </el-row>
                    <!-- 高级设置 -->
                    <el-collapse>
                      <el-row :gutter="20">
                        <el-col :span="12">
                          <!-- 翻译设置 -->
                          <el-form-item class="mt-20">
                            <el-checkbox v-model="config.isTranslate">启用翻译</el-checkbox>
                          </el-form-item>
                        </el-col>
                        <el-col :span="12">
                          <!-- 生成按钮 -->
                          <el-button
                              type="primary"
                              class="mt-20"
                              @click="handleTranscribe">
                            生成字幕文件
                          </el-button>
                        </el-col>
                      </el-row>
                    </el-collapse>

                    <!-- 字幕合成设置 -->

                    <el-row :gutter="20">
                      <el-col :span="12">
                        <el-form-item label="字幕类型">
                          <el-checkbox v-model="config.isSoft">软字幕</el-checkbox>
                        </el-form-item>
                        <el-form-item label="字体大小">
                          <el-input-number
                              v-model="config.fontsize"
                              :min="12"
                              :max="36"
                              controls-position="right"/>
                        </el-form-item>
                      </el-col>
                      <el-col :span="12">
                        <el-form-item label="字体：">
                          <el-input v-model="config.fontname" style="width: 240px" placeholder="Please input"/>
                        </el-form-item>
                        <el-form-item label="字体颜色：">
                          <el-input v-model="config.fontcolor" style="width: 240px" placeholder="Please input"/>
                        </el-form-item>
                        <el-form-item label="底部边距：">
                          <el-input v-model="config.subtitle_bottom" style="width: 240px" placeholder="Please input"/>
                        </el-form-item>
                      </el-col>
                    </el-row>
                    <el-row :span="4">
                      <el-button
                          type="success"
                          @click="handleAddSubtitle"
                          :disabled="!subtitleContent">
                        合成字幕到视频
                      </el-button>
                    </el-row>
                  </el-form>
                </el-card>
              </el-col>
              <!-- 右侧预览区域 -->
              <el-col :span="10">
                <el-card shadow="hover">
                  <template #header>
                    <div class="preview-header">
                      <span>字幕预览</span>
                      <el-upload
                          action="#"
                          :show-file-list="false"
                          :before-upload="handleSubtitleUpload">
                        <el-button type="primary" size="small">
                          上传字幕
                        </el-button>
                      </el-upload>
                      <el-button
                          type="primary"
                          size="small"
                          @click="handleSaveSubtitle"
                          :disabled="!subtitleContent">
                        保存字幕
                      </el-button>
                    </div>
                  </template>
                  <el-input
                      v-model="subtitleContent"
                      type="textarea"
                      :rows="20"
                      resize="none"
                      placeholder="生成或上传的字幕内容将显示在此处"/>
                </el-card>
              </el-col>
            </el-row>
          </el-tab-pane>
          <el-tab-pane label="音频">
            <el-upload
                action="#"
                drag
                :show-file-list="false"
                :auto-upload="false"
                :on-change="handleAudioUpload"
                :disabled="uploadAudio"
                class="full-width-upload"
                accept=".mp3,.wav,.flac">
              <template #default>
                <div class="drop-overlay" :class="{ 'has-audio': audioPath }">
                  <div v-if="!audioPath">
                    <el-icon :size="30">
                      <Upload/>
                    </el-icon>
                    <p class="drop-text">点击或拖放音频上传</p>
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
            <el-button
                type="primary"
                @click="handleExtractAudio"
                class="mt-10">提取音频
            </el-button>
            <el-button
                class="mt-10"
                type="warning"
                @click="handleMergeAudioVideo"
                :disabled="!audioWebPath">
              音视频合并（覆盖原声）
            </el-button>
          </el-tab-pane>
          <el-tab-pane label="图片">
            <el-input
                v-model="extractTime"
                placeholder="提取时间 (HH:MM:SS)"
                class="mt-10"
                style="width: 200px">
              <template #append>
                <el-button
                    @click="handleExtractFrame"
                    :disabled="!isValidTime">提取图片
                </el-button>
              </template>
            </el-input>
            <!-- 图片预览 -->
            <div class="image-preview mt-10" v-if="extractedImage">
              <el-image
                  :src="extractedImage"
                  fit="contain"
                  style="max-height: 200px"
                  :preview-src-list="[extractedImage]">
                <template #error>
                  <div>图片加载失败</div>
                </template>
              </el-image>
            </div>
          </el-tab-pane>
          <el-tab-pane label="压缩" >
            <div class="settings-container">
              <!-- 文件夹地址输入 -->
              <el-form-item label="压缩文件夹" prop="folderPath">
                <el-input
                    v-model="folderPath"
                    placeholder="请输入文件夹路径"
                    clearable/>
              </el-form-item>
              <el-form-item label="备份文件夹" prop="backupDir">
                <el-input
                    v-model="backupDir"
                    placeholder="压缩之后源文件会转移到此文件夹内"
                    clearable/>
              </el-form-item>

              <!-- CRF滑块 -->
              <el-form-item label="CRF值 (0-24)" prop="crf">
                <div class="slider-item">
                  <el-slider
                      v-model="crf"
                      :min="0"
                      :max="24"
                      :step="1"
                      show-input/>
                </div>
              </el-form-item>

              <!-- 最大比特率滑块 -->
              <el-form-item label="最大比特率 (K)" prop="maxBitrate">
                <div class="slider-item">
                  <el-slider
                      v-model="maxBitrate"
                      :min="1000"
                      :max="20000"
                      :step="100"
                      show-input/>
                </div>
              </el-form-item>
              <el-form-item >
                <el-tooltip content="转码并去除视频中不必须部分减少体积" placement="top">
                  <el-icon :size="18" >
                    <QuestionFilled />
                  </el-icon>
                </el-tooltip>
              <el-button
                  type="primary"
                  @click="startCompression"
                  :loading="is_compression"
                  class="mt-10">开始压缩
              </el-button>
              </el-form-item>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import {ref, computed} from 'vue'
import API from './config/api'
import {ElMessage, ElIcon} from 'element-plus'
import {Upload, MagicStick,QuestionFilled } from '@element-plus/icons-vue'
import axios from "axios";


// 响应式数据
const dragover = ref(false)
const uploadVideo = ref(false)
const videoPath = ref(null) // 存储后端返回的文件路径
const videoWebPath = ref(null) // 预览URL

const form = ref({
  output_format: 'mp4',
  start_time: '00:00:00',
  end_time: '',
  speed: 1,
  volume: 1,
})

// 下载视频相关状态
const videoUrl = ref('')
const downloading = ref(false)
const downloadStatus = ref('')

// 音频相关状态
const audioWebPath = ref(null)
const audioPath = ref(null)
const uploadAudio = ref(false)

// 图片相关状态
const extractTime = ref('00:00:00')
const extractedImage = ref(null)

// 字幕相关
const subtitleFile = ref(null)
const subtitleContent = ref('')
const outputFormats = ['srt', 'txt']
const translatorEngines = ['google', 'baidu', 'deepl']
const languageOptions = [
  {value: 'zh', label: '中文'},
  {value: 'en', label: '英文'},
  {value: 'ja', label: '日语'},
  {value: 'fr', label: '法语'},
  {value: 'ko', label: '韩语'},
  {value: 'de', label: '德语'},
  {value: 'ru', label: '俄语'},
  {value: 'ar', label: '阿拉伯语'},
  {value: 'es', label: '西班牙语'},
  {value: 'vi', label: '越南语'},
  {value: 'pt', label: '葡萄牙语'},
  {value: 'id', label: '印度尼西亚语'},
]

const config = ref({
  outputFormat: 'srt',
  language: 'auto',
  isTranslate: false,
  translator: 'google',
  targetLanguage: 'zh',
  doubleSubtitle: false,
  isSoft: false,
  fontname: '楷体',
  fontsize: 16,
  fontcolor: '&Hffffff',
  subtitle_bottom: 20
})

const handleVideoClick = () => {
  if (!videoPath.value && !uploadVideo.value) {
    document.querySelector('.preview-wrapper input[type=file]').click()
  }
}

// 视频下载
const handleDownload = async () => {
  try {
    downloading.value = true
    const response = await fetch(API.download_video, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_url: videoUrl.value,
      })
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {filename, web_path, local_path, duration}, ...}
    const data = result.data || {}
    videoPath.value = data.localPath || ''
    videoWebPath.value = `${API.HOST}/${data.webPath}` // 拼接静态资源地址
    // 响应式赋值
    form.value = {
      ...form.value,
      end_time: data.duration || '00:00:00',
    }
    downloadStatus.value = '下载成功'
  } catch (error) {
    downloadStatus.value = '下载失败: ' + error.message
  } finally {
    downloading.value = false
  }
}

// 视频上传
const handleVideoUpload = async (uploadFile) => {
  // 统一获取原生文件对象
  const file = uploadFile.raw || uploadFile;

  // 安全校验
  if (!file || !file.type) {
    ElMessage.error('无效的文件对象');
    return false;
  }

  if (!file.type.startsWith('video/')) {
    ElMessage.error('请选择有效的视频文件')
    return false
  }
  try {
    uploadVideo.value = true
    const formData = new FormData()
    formData.append('file_stream', file)
    const response = await fetch(API.upload_video, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('上传失败')
    const result = await response.json()
    // 后端已自动转换为 camelCase: {webPath, localPath, duration}
    const data = result.data || {}
    videoPath.value = data.localPath
    videoWebPath.value = `${API.HOST}/${data.webPath}`
    // 响应式赋值
    form.value = {
      ...form.value,
      end_time: data.duration || '00:00:00',
    }
    ElMessage.success('文件上传成功')
  } catch (error) {
    ElMessage.error(error.message)
    return false
  } finally {
    uploadVideo.value = false
  }
  return false // 阻止默认上传
}

// 处理拖放上传
const handleDrop = async (e) => {
  e.preventDefault()
  dragover.value = false
  const file = e.dataTransfer.files[0]
  if (file) await handleVideoUpload(file)
}

// 视频处理
const handleProcess = async () => {
  if (!videoPath.value) {
    ElMessage.error('请先上传视频文件')
    return
  }
  try {
    uploadVideo.value = true
    const params = {
      input_path: videoPath.value,
      output_format: form.value.output_format,
      speed: form.value.speed,
      volume: form.value.volume
    }
    // 添加时间参数
    if (form.value.start_time) params.start_time = form.value.start_time
    if (form.value.end_time) params.end_time = form.value.end_time
    const response = await fetch(API.process_video, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params)
    })
    if (!response.ok) throw new Error('处理失败')
    const result = await response.json()
    // 后端返回格式: {success: true, data: {filename, web_path, local_path, duration}, ...}
    const data = result.data || {}
    videoWebPath.value = `${API.HOST}/${data.webPath}`
    videoPath.value = data.localPath
    // 响应式赋值
    form.value = {
      ...form.value,
      end_time: data.duration || '00:00:00',
    }
    ElMessage.success('视频处理完成')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    uploadVideo.value = false
  }
}

// 时间格式验证
const isValidTime = computed(() => {
  return /^([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/.test(extractTime.value)
})

// 音频提取
const handleExtractAudio = async () => {
  try {
    const response = await fetch(API.get_audio, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_url: videoPath.value,
      })
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {filename, web_path, local_path, duration}, ...}
    const data = result.data || {}
    audioPath.value = data.localPath
    audioWebPath.value = `${API.HOST}/${data.webPath}` // 拼接静态资源地址
    ElMessage.success('音频提取成功')
  } catch (error) {
    ElMessage.success('音频提取失败' + error.message)
  }
}

// 音频上传处理
const handleAudioUpload = async (file) => {
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
    // 后端返回格式: {success: true, data: {filename, web_path, local_path}, ...}
    const data = result.data || {}
    audioPath.value = data.localPath
    audioWebPath.value = `${API.HOST}/${data.webPath}`
    ElMessage.success('音频上传成功')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    uploadAudio.value = false
  }
  return false
}

// 音视频合并
const handleMergeAudioVideo = async () => {
  if (!audioWebPath.value) return

  try {
    const response = await fetch(API.add_audio_to_video, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_path: videoPath.value,
        audio_path: audioPath.value
      })
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {web_path, local_path, duration}, ...}
    const data = result.data || {}
    videoPath.value = data.localPath
    videoWebPath.value = `${API.HOST}/${data.webPath}` // 拼接静态资源地址
    // 调用合并接口
    ElMessage.success('音视频合并成功')
  } catch (error) {
    ElMessage.error('合并失败: ' + error.message)
  }
}

// 图片提取
const handleExtractFrame = async () => {
  if (!isValidTime.value) return
  if (!videoPath.value) {
    ElMessage.error('请先上传视频文件')
    return
  }
  extractedImage.value = null
  try {
    const response = await fetch(API.extract_frame, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_input: videoPath.value,
        time_ss: extractTime.value
      })
    })
    const result = await response.json()
    // 后端返回格式: {success: true, data: {web_path, ...}, ...}
    const data = result.data || {}
    extractedImage.value = `${API.HOST}/${data.webPath}`
    ElMessage.success('图片提取成功')
  } catch (error) {
    ElMessage.error('提取失败: ' + error.message)
  }
}

// 执行转录
const handleTranscribe = async () => {
  if (!videoPath.value) {
    ElMessage.error('请先上传音视频文件')
    return
  }
  try {
    const response = await fetch(API.transcribe, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        input_path: videoPath.value,
        output_format: config.value.outputFormat,
        is_translate: config.value.isTranslate,
        subtitle_double: config.value.doubleSubtitle,
        translator_engine: config.value.translator,
        subtitle_language: config.value.targetLanguage
      })
    })
    // 新增：解析JSON响应体
    const result = await response.json() // ✅ 正确解析数据
    const data = result.data || {}
    subtitleContent.value = data.subtitleContent || data.subtitle_content || ''
    ElMessage.success('字幕生成成功')
  } catch (error) {
    ElMessage.error(`生成失败: ${error.message}`)
  }
}

// 合成字幕到视频
const handleAddSubtitle = async () => {
  if (!videoPath.value || !subtitleContent.value) {
    ElMessage.error('需要音视频文件和字幕内容')
    return
  }

  try {
    const response = await fetch(API.video_add_subtitle, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        video_input: videoPath.value,
        subtitle_content: subtitleContent.value,
        is_soft: config.value.isSoft,
        fontname: config.value.fontname,
        fontsize: config.value.fontsize,
        fontcolor: config.value.fontcolor,
        subtitle_bottom: config.value.subtitle_bottom,
      })
    })
    // 新增：解析JSON响应体
    const result = await response.json() // ✅ 正确解析数据
    // 后端返回格式: {success: true, data: {filename, web_path, local_path, duration}, ...}
    const data = result.data || {}
    videoWebPath.value = `${API.HOST}/${data.webPath}`
    videoPath.value = data.localPath
    // 响应式赋值
    form.value = {
      ...form.value,
      end_time: data.duration || '00:00:00',
    }
    ElMessage.success('字幕合成成功')
  } catch (error) {
    ElMessage.error(`合成失败: ${error.message}`)
  }
}

// 处理字幕文件上传
const handleSubtitleUpload = (file) => {
  // if (!['text/plain', 'application/x-subrip'].includes(file.type)) {
  //   ElMessage.error('仅支持SRT/TXT格式字幕')
  //   return false
  // }
  const reader = new FileReader()
  reader.onload = (e) => {
    subtitleContent.value = e.target.result
  }
  // 添加错误处理
  reader.onerror = (e) => {
    console.error('文件读取失败:', e.target.error)
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  subtitleFile.value = file
  return false
}

// 保存字幕文件
const handleSaveSubtitle = async () => {
  try {
    // 1. 检查是否有字幕内容
    if (!subtitleContent.value?.trim()) {
      ElMessage.warning('请先上传或输入字幕内容')
      return
    }
    // 2. 创建文件Blob
    const blob = new Blob([subtitleContent.value], {
      type: subtitleFile.value?.type || 'application/x-subrip' // 默认SRT类型
    })
    // 3. 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = subtitleFile.value?.name || 'subtitle.srt' // 保留原文件名或默认
    // 4. 触发下载
    document.body.appendChild(a)
    a.click()
    // 5. 清理资源
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    ElMessage.success('字幕文件下载成功')
  } catch (error) {
    ElMessage.error(`下载失败: ${error.message}`)
    console.error('下载错误:', error)
  }
}

// 压缩
const folderPath = ref('');
const backupDir = ref('');
const crf = ref(20);  // 默认值20
const maxBitrate = ref(8000);  // 默认值8000K
const is_compression = ref(false);
const startCompression = async () => {
  try {
    is_compression.value = true
    const response = await fetch(API.start_compression, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        input_dir: folderPath.value,
        backup_dir: backupDir.value,
        crf: crf.value,
        max_bitrate: maxBitrate.value,
      })
    })
    const data = await response.json()
  } catch (error) {
    ElMessage.error(`异常: ${error.message}`)
  } finally {
    is_compression.value = false
  }
}
</script>

<style scoped src="@/styles/components/video-processing.css"></style>
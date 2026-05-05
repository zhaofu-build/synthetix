<template>
  <div class="ai-clip-container">
    <!-- 新建项目命名对话框 -->
    <el-dialog
      v-model="showNamingDialog"
      title="新建对话式项目"
      width="420px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-form @submit.prevent="confirmCreateProject">
        <el-form-item label="项目名称" required>
          <el-input
            ref="namingInputRef"
            v-model="namingInput"
            placeholder="请输入项目名称"
            maxlength="50"
            show-word-limit
            :status="namingError ? 'error' : ''"
            @input="namingError = ''"
          />
          <div v-if="namingError" style="color: #f56c6c; font-size: 12px; margin-top: 4px;">{{ namingError }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelCreate">取消</el-button>
        <el-button type="primary" @click="confirmCreateProject" :loading="namingLoading" :disabled="!namingInput.trim()">
          确定创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 修改项目名对话框 -->
    <el-dialog v-model="renameDialogVisible" title="修改项目名称" width="400px">
      <el-input
        v-model="renameInput"
        placeholder="请输入新的项目名称"
        maxlength="50"
        show-word-limit
        :status="renameError ? 'error' : ''"
        @input="renameError = ''"
      />
      <div v-if="renameError" style="color: #f56c6c; font-size: 12px; margin-top: 4px;">{{ renameError }}</div>
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename" :loading="renameLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 项目头部 -->
    <div class="project-header">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 项目列表
      </el-button>
      <div class="project-name-wrap">
        <span class="project-name-text">{{ projectName }}</span>
        <el-button size="small" text @click="openRenameDialog">
          <el-icon><Edit /></el-icon> 修改项目名
        </el-button>
        <el-tag size="small" type="warning">对话式</el-tag>
      </div>
    </div>

    <el-row :gutter="20" class="full-height">
      <!-- 左侧对话区 -->
      <el-col :span="8" class="chat-panel">
        <el-card class="chat-card">
          <template #header>
            <div class="card-header">
              <span>AI 剪辑助手</span>
              <el-button type="danger" size="small" @click="clearChat">清空</el-button>
            </div>
          </template>

          <!-- 对话消息 -->
          <div class="messages-container" ref="messagesRef">
            <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
              <div class="message-avatar">
                <el-avatar v-if="msg.role === 'user'" :size="32">U</el-avatar>
                <el-avatar v-else :size="32" type="primary">AI</el-avatar>
              </div>
              <div class="message-content">
                <div class="message-text" v-html="formatMessage(msg.content)"></div>
                <!-- 操作按钮 -->
                <div v-if="msg.action" class="message-actions">
                  <el-button
                    type="primary"
                    size="small"
                    @click="confirmAction(msg.action)"
                    :loading="executing"
                  >
                    确认执行
                  </el-button>
                  <el-button
                    size="small"
                    @click="cancelAction"
                  >
                    取消
                  </el-button>
                </div>
                <!-- 素材选择 -->
                <div v-if="msg.suggestions && msg.status === 'collecting'" class="suggestions">
                  <div
                    v-for="(item, i) in msg.suggestions"
                    :key="i"
                    class="suggestion-item"
                    @click="selectSuggestion(item)"
                  >
                    {{ item.name || item }}
                  </div>
                </div>
              </div>
            </div>
            <div v-if="loading" class="message assistant">
              <div class="message-avatar">
                <el-avatar :size="32" type="primary">AI</el-avatar>
              </div>
              <div class="message-content">
                <div class="message-text loading-text">
                  <span v-for="i in 3" :key="i" class="dot"></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="input-area">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              placeholder="描述你想要的视频效果，例如：帮我剪辑一个30秒的短视频..."
              @keydown.enter.ctrl="sendMessage"
              :disabled="loading"
            />
            <div class="input-actions">
              <el-select v-model="currentVideoId" placeholder="当前视频" size="small" clearable style="width: 150px">
                <el-option
                  v-for="video in recentVideos"
                  :key="video.id"
                  :label="video.name"
                  :value="video.id"
                />
              </el-select>
              <el-button type="primary" @click="sendMessage" :loading="loading">
                发送
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧预览区 -->
      <el-col :span="16" class="preview-panel">
        <el-card class="preview-card">
          <template #header>
            <div class="card-header">
              <span>视频预览</span>
              <div class="header-actions">
                <el-upload
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="handleVideoUpload"
                  accept="video/*"
                >
                  <el-button type="primary" size="small">上传视频</el-button>
                </el-upload>
              </div>
            </div>
          </template>

          <div class="video-container">
            <video
              v-if="videoWebPath"
              :src="videoWebPath"
              controls
              class="video-preview"
            />
            <div v-else class="video-placeholder">
              <el-icon :size="60"><VideoPlay /></el-icon>
              <p>上传或生成视频后在此预览</p>
            </div>
          </div>

          <!-- 执行结果 -->
          <div v-if="lastResult" class="result-section">
            <el-divider>执行结果</el-divider>
            <div class="result-content">
              <el-tag v-if="lastResult.success" type="success">成功</el-tag>
              <el-tag v-else type="danger">失败</el-tag>
              <span class="result-message">{{ lastResult.message }}</span>
              <el-button
                v-if="lastResult.output_path || lastResult.web_path"
                type="primary"
                size="small"
                @click="playResult(lastResult.output_path || lastResult.web_path)"
              >
                播放结果
              </el-button>
            </div>
          </div>

          <!-- 快捷操作 -->
          <div class="quick-actions">
            <el-divider>快捷操作</el-divider>
            <el-space wrap>
              <el-button size="small" @click="quickAction('帮我查看素材库')">查看素材</el-button>
              <el-button size="small" @click="quickAction('帮我下载一些海边风景素材')">下载素材</el-button>
              <el-button size="small" @click="quickAction('帮我把当前视频前30秒剪出来')">剪切视频</el-button>
              <el-button size="small" @click="quickAction('帮我把当前视频调整为2倍速')">调整速度</el-button>
              <el-button size="small" @click="quickAction('帮我分析当前视频')">分析视频</el-button>
            </el-space>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { VideoPlay, ArrowLeft, Edit } from '@element-plus/icons-vue'
import { videoApi, assetUrl, API_HOST } from '@/api/modules'
import { projectApi } from '@/api/modules'
import { renderMarkdown } from '@/utils/sanitize'

const route = useRoute()
const router = useRouter()

// 项目状态
const projectId = ref(null)
const projectName = ref('未命名项目')

// 命名对话框
const showNamingDialog = ref(false)
const namingInput = ref('')
const namingError = ref('')
const namingLoading = ref(false)
const namingInputRef = ref(null)

// 修改项目名
const renameDialogVisible = ref(false)
const renameInput = ref('')
const renameError = ref('')
const renameLoading = ref(false)

// 对话状态
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const executing = ref(false)
const messagesRef = ref(null)
const sessionId = ref(null)
const currentVideoId = ref(null)

// 视频状态
const videoPath = ref('')
const videoWebPath = ref('')
const duration = ref('')
const recentVideos = ref([])
const lastResult = ref(null)

// 项目导航
const goBack = () => {
  router.push('/editor')
}

// 取消创建
const cancelCreate = () => {
  router.push('/editor')
}

// 确认创建项目
const confirmCreateProject = async () => {
  const name = namingInput.value.trim()
  if (!name) {
    namingError.value = '请输入项目名称'
    return
  }
  namingLoading.value = true
  namingError.value = ''
  try {
    const data = await projectApi.create({
      name,
      mode: 'conversation'
    })
    projectId.value = data.id
    projectName.value = data.name
    showNamingDialog.value = false
    router.replace({ path: '/ai-clip', query: { projectId: data.id } })
  } catch (error) {
    if (error?.message?.includes('已存在') || error?.message?.includes('DuplicateName')) {
      namingError.value = '该名称已被使用，请换一个'
    } else {
      namingError.value = error.message || '创建失败'
    }
  } finally {
    namingLoading.value = false
  }
}

// 修改项目名
const openRenameDialog = () => {
  renameInput.value = projectName.value
  renameError.value = ''
  renameDialogVisible.value = true
}

const confirmRename = async () => {
  const name = renameInput.value.trim()
  if (!name) {
    renameError.value = '项目名称不能为空'
    return
  }
  if (name === projectName.value) {
    renameDialogVisible.value = false
    return
  }
  renameLoading.value = true
  try {
    await projectApi.update(projectId.value, { name })
    projectName.value = name
    renameDialogVisible.value = false
    ElMessage.success('项目名称已更新')
  } catch (error) {
    if (error?.message?.includes('已存在') || error?.message?.includes('DuplicateName')) {
      renameError.value = '该名称已被其他项目使用，请换一个'
    } else {
      renameError.value = error.message || '修改失败'
    }
  } finally {
    renameLoading.value = false
  }
}

// 保存对话历史到项目
const saveChatHistory = () => {
  if (!projectId.value) return
  const history = messages.value.map(m => ({
    role: m.role,
    content: m.content
  }))
  projectApi.update(projectId.value, { chat_history: history }).catch(() => {})
}

// 加载项目
const loadProject = async (id) => {
  try {
    const data = await projectApi.getFull(id)
    projectId.value = data.id
    projectName.value = data.name || '未命名项目'
    // 恢复对话历史
    if (data.chatHistory && data.chatHistory.length > 0) {
      messages.value = data.chatHistory.map(m => ({
        role: m.role,
        content: m.content
      }))
    }
    // 恢复输出视频
    if (data.outputPath) {
      videoWebPath.value = assetUrl(data.outputPath)
    }
  } catch (error) {
    ElMessage.error('加载项目失败')
  }
}

// 发送消息
const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const body = {
      session_id: sessionId.value,
      message: text,
      context: {
        current_video_id: currentVideoId.value
      }
    }
    if (projectId.value) {
      body.project_id = projectId.value
    }

    const response = await fetch(`${API_HOST}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const result = await response.json()
    if (!result.success) throw new Error(result.message || '请求失败')

    const data = result.data
    sessionId.value = data.sessionId || data.session_id

    // 添加 AI 响应
    const aiMessage = {
      role: 'assistant',
      content: data.reply,
      status: data.status,
      action: data.action,
      suggestions: data.suggestions
    }
    messages.value.push(aiMessage)

    // 如果有执行结果
    if (data.result) {
      lastResult.value = data.result
      if (data.result.success && data.result.web_path) {
        videoWebPath.value = assetUrl(data.result.web_path)
      }
    }

    // 保存对话历史
    saveChatHistory()

  } catch (error) {
    ElMessage.error(`发送失败: ${error.message}`)
    messages.value.pop()
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 确认执行
const confirmAction = async (action) => {
  executing.value = true
  try {
    const body = {
      session_id: sessionId.value,
      message: '确认'
    }
    if (projectId.value) {
      body.project_id = projectId.value
    }

    const response = await fetch(`${API_HOST}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    const result = await response.json()
    if (!result.success) throw new Error(result.message || '执行失败')

    const data = result.data

    messages.value.push({
      role: 'assistant',
      content: data.reply
    })

    if (data.result) {
      lastResult.value = data.result
      if (data.result.success && (data.result.web_path || data.result.output_path)) {
        const path = data.result.web_path || data.result.output_path
        videoWebPath.value = path.startsWith('http') ? path : assetUrl(path)
        ElMessage.success('执行成功')
      }
    }

    saveChatHistory()

  } catch (error) {
    ElMessage.error(`执行失败: ${error.message}`)
  } finally {
    executing.value = false
    scrollToBottom()
  }
}

// 取消操作
const cancelAction = async () => {
  try {
    const response = await fetch(`${API_HOST}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        message: '取消'
      })
    })

    const result = await response.json()
    messages.value.push({
      role: 'assistant',
      content: result.data?.reply || '操作已取消'
    })
    saveChatHistory()
  } catch (error) {
    ElMessage.error('取消失败')
  }
  scrollToBottom()
}

// 选择建议
const selectSuggestion = (item) => {
  const text = typeof item === 'string' ? item : item.name
  inputText.value = text
  sendMessage()
}

// 快捷操作
const quickAction = (text) => {
  inputText.value = text
  sendMessage()
}

// 清空对话
const clearChat = () => {
  messages.value = []
  sessionId.value = null
  lastResult.value = null
  saveChatHistory()
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 格式化消息
const formatMessage = (content) => {
  if (!content) return ''
  return renderMarkdown(content)
}

// 上传视频
const handleVideoUpload = async (file) => {
  try {
    const data = await videoApi.upload(file.raw)
    videoPath.value = data.localPath
    videoWebPath.value = assetUrl(data.webPath)
    duration.value = data.duration || '00:00:00'
    currentVideoId.value = data.id
    ElMessage.success('视频上传成功')

    if (!recentVideos.value.find(v => v.id === data.id)) {
      recentVideos.value.unshift({
        id: data.id,
        name: data.filename || file.name
      })
      if (recentVideos.value.length > 10) {
        recentVideos.value.pop()
      }
    }
  } catch (error) {
    ElMessage.error(`上传失败: ${error.message}`)
  }
}

// 播放结果
const playResult = (path) => {
  if (path.startsWith('http')) {
    videoWebPath.value = path
  } else {
    videoWebPath.value = assetUrl(path)
  }
}

// 加载最近视频
const loadRecentVideos = async () => {
  try {
    const response = await fetch(`${API_HOST}/api/videos?page=1&page_size=10`)
    const result = await response.json()
    if (result.success && result.data?.items) {
      recentVideos.value = result.data.items.map(v => ({
        id: v.id,
        name: v.videoName || v.name
      }))
    }
  } catch (error) {
    console.error('加载视频列表失败:', error)
  }
}

// 初始化
onMounted(async () => {
  loadRecentVideos()

  const pid = route.query.projectId
  if (pid) {
    await loadProject(parseInt(pid))
  } else {
    showNamingDialog.value = true
    await nextTick()
    if (namingInputRef.value) {
      namingInputRef.value.focus()
    }
  }
})
</script>

<style scoped>
.ai-clip-container {
  height: calc(100vh - 100px);
  padding: 20px;
}

.project-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: var(--el-bg-color-overlay, #1d1e1f);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter, #4c4d4f);
}

.project-name-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.project-name-text {
  font-size: 16px;
  font-weight: 500;
}

.full-height {
  height: calc(100% - 60px);
}

.chat-panel, .preview-panel {
  height: 100%;
}

.chat-card, .preview-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 15px;
  min-height: 200px;
  max-height: calc(100vh - 410px);
}

.message {
  display: flex;
  margin-bottom: 12px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  margin: 0 8px;
}

.message-content {
  max-width: 80%;
}

.message-text {
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.message.user .message-text {
  background: #409eff;
  color: white;
}

.message.assistant .message-text {
  background: white;
  color: #333;
  border: 1px solid #e4e7ed;
}

.message-actions {
  margin-top: 10px;
  display: flex;
  gap: 10px;
}

.suggestions {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggestion-item {
  padding: 6px 12px;
  background: #ecf5ff;
  border: 1px solid #409eff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: #409eff;
  transition: all 0.2s;
}

.suggestion-item:hover {
  background: #409eff;
  color: white;
}

.loading-text {
  display: flex;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  border-top: 1px solid #e4e7ed;
  padding-top: 15px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.video-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  min-height: 300px;
}

.video-preview {
  max-width: 100%;
  max-height: 100%;
}

.video-placeholder {
  text-align: center;
  color: #909399;
}

.video-placeholder p {
  margin-top: 15px;
}

.result-section {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #e4e7ed;
}

.result-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.result-message {
  flex: 1;
}

.quick-actions {
  margin-top: 20px;
}
</style>

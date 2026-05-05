<template>
  <div class="llm-chat-container">
    <el-card class="chat-card">
      <template #header>
        <div class="card-header">
          <span>LLM 对话</span>
          <el-button type="danger" size="small" @click="clearMessages">清空对话</el-button>
        </div>
      </template>

      <!-- 对话消息区域 -->
      <div class="messages-container" ref="messagesRef">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
          <div class="message-avatar">
            <el-avatar v-if="msg.role === 'user'" :size="32">U</el-avatar>
            <el-avatar v-else :size="32" type="primary">AI</el-avatar>
          </div>
          <div class="message-content">
            <div class="message-text" v-html="formatMessage(msg.content)"></div>
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

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="3"
          placeholder="输入消息..."
          @keydown.enter.ctrl="sendMessage"
          :disabled="loading"
        />
        <div class="input-actions">
          <div class="options">
            <el-select v-model="model" placeholder="选择模型" size="small" clearable style="width: 150px">
              <el-option label="默认模型" value="" />
              <el-option label="deepseek-chat" value="deepseek-chat" />
              <el-option label="qwen-turbo" value="qwen-turbo" />
              <el-option label="gpt-4" value="gpt-4" />
            </el-select>
            <el-slider v-model="temperature" :min="0" :max="1" :step="0.1" style="width: 100px; margin-left: 10px" />
            <span class="temp-label">温度: {{ temperature }}</span>
          </div>
          <el-button type="primary" @click="sendMessage" :loading="loading">
            发送 (Ctrl+Enter)
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '@/utils/sanitize'
import { API_HOST } from '@/api/modules'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref(null)
const model = ref('')
const temperature = ref(0.7)

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
    // 构建请求
    const requestMessages = messages.value.map(m => ({
      role: m.role,
      content: m.content
    }))

    const response = await fetch(`${API_HOST}/api/nexus/llm/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: requestMessages,
        model: model.value || undefined,
        generation: {
          temperature: temperature.value,
          max_tokens: 2048
        }
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    // 添加 AI 消息占位
    messages.value.push({ role: 'assistant', content: '' })
    const aiIndex = messages.value.length - 1

    // 处理 SSE 流
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const json = JSON.parse(data)
            if (json.text) {
              messages.value[aiIndex].content += json.text
              scrollToBottom()
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (error) {
    console.error('发送消息失败:', error)
    ElMessage.error(`发送失败: ${error.message}`)
    // 移除失败的消息
    messages.value.pop()
  } finally {
    loading.value = false
  }
}

// 清空对话
const clearMessages = () => {
  messages.value = []
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 格式化消息（Markdown 渲染）
const formatMessage = (content) => {
  if (!content) return ''
  return renderMarkdown(content)
}
</script>

<style scoped>
.llm-chat-container {
  height: 100%;
  padding: 20px;
}

.chat-card {
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
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 20px;
  min-height: 300px;
  max-height: calc(100vh - 350px);
}

.message {
  display: flex;
  margin-bottom: 16px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  margin: 0 10px;
}

.message-content {
  max-width: 70%;
}

.message-text {
  padding: 10px 15px;
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

.loading-text {
  display: flex;
  align-items: center;
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

.options {
  display: flex;
  align-items: center;
}

.temp-label {
  font-size: 12px;
  color: #909399;
  margin-left: 5px;
}
</style>

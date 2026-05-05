import { defineStore } from 'pinia'
import { projectApi, videoApi, audioApi } from '@/api/modules'
import { API_HOST } from '@/api/modules'
import { ElMessage } from 'element-plus'
import { storage } from '@/utils/storage'
import { APP_CONSTANTS } from '@/constants'

const PANEL_KEY = APP_CONSTANTS.STORAGE_KEYS.PANEL_STATE

function loadPanelState() {
  return storage.get(PANEL_KEY, {})
}

function savePanelState(state) {
  storage.set(PANEL_KEY, {
    workspaceCollapsed: state.workspaceCollapsed,
    rightPanelCollapsed: state.rightPanelCollapsed,
    panelRatios: state.panelRatios,
  })
}

export const useProjectStore = defineStore('project', {
  state: () => ({
    projectId: null,
    project: {
      name: '',
      description: '',
      mode: 'workflow',
      status: 'draft',
      duration: 0,
      materialIds: [],
      creative: '',
      targetDuration: 30,
      style: '动感',
      speakerId: null,
      ttsPath: null,
      bgmId: null,
      bgmVolume: 0.3,
      currentStep: 0,
      chatHistory: [],
      planData: null,
      timelineData: null,
      outputPath: null,
      outputVideos: [],
    },
    // 关联数据
    materials: [],
    speaker: null,
    bgm: null,
    // 保存状态
    saving: false,
    _saveTimers: {},

    // ==================== 统一编辑器状态 ====================
    // 聊天
    sessionId: null,
    messages: [],
    chatLoading: false,
    chatExecuting: false,
    pendingConfirmation: null, // { toolName, params, aiIdx }
    _activeSseController: null, // AbortController for active SSE stream
    // 对话模式
    chatMode: 'free', // 'free' | 'plan' | 'research'
    planOperations: [], // [{id, type, tool, params, description, risk, status}]
    planSummary: '',
    planLoading: false,
    planExecutionState: 'idle', // 'idle' | 'generating' | 'confirming' | 'executing' | 'done'
    // 面板 UI
    activeTab: 'materials',
    chatCollapsed: false,
    workspaceCollapsed: false,
    rightPanelCollapsed: false,
    panelRatios: null, // [left, center, right] 百分比，null 表示默认
    // 素材库
    materialLibrary: [],
    materialLoading: false,
    // 音频
    bgmList: [],
    voiceList: [],
    audioLoading: false,
    // 方案
    planLoading: false,
    // 预览
    previewVideoPath: null,
    // 渲染
    rendering: false,
    // 未保存标记
    hasUnsavedChanges: false,
    // 版本快照
    versionSnapshots: [],
  }),

  getters: {
    isLoaded: (state) => state.projectId !== null,
    isWorkflow: (state) => state.project.mode === 'workflow',
    isConversation: (state) => state.project.mode === 'conversation',
  },

  actions: {
    // ==================== 项目管理 ====================

    async createProject({ name, description = '', mode = 'workflow' }) {
      try {
        const data = await projectApi.create({ name, description, mode })
        this.projectId = data.id
        this.project = { ...this._defaultProject(), ...data }
        this.materials = []
        this.speaker = null
        this.bgm = null
        return data
      } catch (error) {
        ElMessage.error('创建项目失败: ' + error.message)
        throw error
      }
    },

    async loadProject(projectId) {
      try {
        const data = await projectApi.getFull(projectId)
        this.projectId = data.id
        this.project = { ...this._defaultProject(), ...data }
        this.materials = data.materials || []
        this.speaker = data.speaker || null
        this.bgm = data.bgm || null
        // 恢复聊天历史
        if (data.chatHistory && data.chatHistory.length) {
          this.messages = Array.isArray(data.chatHistory) ? data.chatHistory : []
        }
        // 恢复 sessionId（localStorage 持久化）
        const storedSid = localStorage.getItem(`session_${projectId}`)
        if (storedSid) this.sessionId = storedSid
        // 恢复面板状态
        const saved = loadPanelState()
        if (saved.workspaceCollapsed !== undefined) this.workspaceCollapsed = saved.workspaceCollapsed
        if (saved.rightPanelCollapsed !== undefined) this.rightPanelCollapsed = saved.rightPanelCollapsed
        if (saved.panelRatios) this.panelRatios = saved.panelRatios
        return data
      } catch (error) {
        ElMessage.error('加载项目失败: ' + error.message)
        throw error
      }
    },

    async saveField(field, value) {
      if (!this.projectId) return
      this.hasUnsavedChanges = true
      if (this._saveTimers[field]) clearTimeout(this._saveTimers[field])
      this._saveTimers[field] = setTimeout(async () => {
        try {
          this.saving = true
          await projectApi.update(this.projectId, { [field]: value })
          this.hasUnsavedChanges = false
        } catch (error) {
          console.error(`保存 ${field} 失败:`, error)
          ElMessage.error(`保存${field}失败: ${error.message}`)
        } finally {
          this.saving = false
        }
      }, 300)
    },

    async saveFields(fields) {
      if (!this.projectId) return
      try {
        this.saving = true
        const data = await projectApi.update(this.projectId, fields)
        if (data) Object.assign(this.project, data)
        this.hasUnsavedChanges = false
      } catch (error) {
        console.error('保存失败:', error)
        ElMessage.error(`保存失败: ${error.message}`)
      } finally {
        this.saving = false
      }
    },

    async exportProject() {
      if (!this.projectId) return
      try {
        const data = await projectApi.exportProject(this.projectId)
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `project_${this.projectId}.json`
        a.click()
        URL.revokeObjectURL(url)
        ElMessage.success('导出成功')
      } catch (error) {
        ElMessage.error('导出失败: ' + error.message)
      }
    },

    async saveProject() {
      if (!this.projectId) return
      try {
        this.saving = true
        const data = await projectApi.update(this.projectId, this.project)
        if (data) Object.assign(this.project, data)
        this.hasUnsavedChanges = false
        ElMessage.success('保存成功')
      } catch (error) {
        ElMessage.error('保存失败: ' + error.message)
      } finally {
        this.saving = false
      }
    },

    clearProject() {
      this.resetProject()
    },

    resetProject() {
      this.projectId = null
      this.project = this._defaultProject()
      this.materials = []
      this.speaker = null
      this.bgm = null
      this.saving = false
      this.sessionId = null
      this.messages = []
      this.activeTab = 'materials'
      this.chatCollapsed = false
    },

    _defaultProject() {
      return {
        name: '', description: '', mode: 'workflow', status: 'draft',
        duration: 0, materialIds: [], creative: '', targetDuration: 30,
        style: '动感', speakerId: null, ttsPath: null, bgmId: null,
        bgmVolume: 0.3, currentStep: 0, chatHistory: [],
        planData: null, timelineData: null, outputPath: null, outputVideos: [],
      }
    },

    // ==================== 聊天（Agent 对话） ====================

    async processChatMessage(input) {
      this.messages.push({ role: 'user', content: input })
      this.chatLoading = true

      try {
        const body = {
          session_id: this.sessionId || undefined,
          message: input,
          context: {
            current_video_id: this.project.currentVideoId || null,
            project_id: this.projectId || null,
          },
        }
        if (this.projectId) body.project_id = this.projectId

        const response = await fetch(`${API_HOST}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const res = await response.json()
        if (!res.success) throw new Error(res.message || '请求失败')

        const data = res.data
        this.sessionId = data.sessionId || data.session_id || this.sessionId
        if (this.projectId && this.sessionId) {
          localStorage.setItem(`session_${this.projectId}`, this.sessionId)
        }

        const aiMsg = {
          role: 'assistant',
          content: data.reply,
          status: data.status,
          action: data.action,
          suggestions: data.suggestions,
          missingSlots: data.missingSlots,
        }
        this.messages.push(aiMsg)

        // 如果有执行结果，触发面板刷新
        if (data.result) {
          this._handleToolResult(data.result)
        }

        // 保存聊天历史
        this._saveChatHistory()
      } catch (error) {
        this.messages.push({ role: 'assistant', content: `处理失败: ${error.message}`, status: 'error' })
      } finally {
        this.chatLoading = false
      }
    },

    async processChatMessageStream(input, attachments = []) {
      // 如果有正在进行的 SSE 流，先取消
      if (this._activeSseController) {
        this._activeSseController.abort()
        this._activeSseController = null
      }

      this.messages.push({ role: 'user', content: input, attachments: attachments.length ? attachments : undefined })
      this.chatLoading = true

      // 占位 AI 消息
      this.messages.push({ role: 'assistant', content: '', status: 'streaming', toolCalls: [] })
      const aiIdx = this.messages.length - 1

      try {
        const body = {
          session_id: this.sessionId || undefined,
          message: input,
          context: {
            current_video_id: this.project.currentVideoId || null,
            project_id: this.projectId || null,
            attachments: attachments.length ? attachments : undefined,
          },
        }
        if (this.projectId) body.project_id = this.projectId

        const controller = new AbortController()
        this._activeSseController = controller

        const response = await fetch(`${API_HOST}/api/agent/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let lastToolResult = null

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6)
            if (data === '[DONE]') continue

            try {
              const event = JSON.parse(data)

              switch (event.type) {
                case 'session':
                  this.sessionId = event.session_id
                  if (this.projectId && event.session_id) {
                    localStorage.setItem(`session_${this.projectId}`, event.session_id)
                  }
                  break
                case 'thinking':
                  this.messages[aiIdx].content = `思考中... (第${event.iteration}轮)`
                  break
                case 'tool_start': {
                  const isDestructive = event.permission === 'destructive'
                  // 追加工具调用卡片
                  if (!this.messages[aiIdx].toolCalls) this.messages[aiIdx].toolCalls = []
                  this.messages[aiIdx].toolCalls.push({
                    tool: event.tool,
                    params: event.params,
                    status: 'running',
                    permission: event.permission,
                  })
                  if (isDestructive) {
                    this.messages[aiIdx].status = 'confirming'
                    this.messages[aiIdx].action = { toolName: event.tool, params: event.params }
                    this.pendingConfirmation = { toolName: event.tool, params: event.params, aiIdx }
                  }
                  lastToolResult = null
                  break
                }
                case 'tool_progress': {
                  const calls = this.messages[aiIdx].toolCalls
                  if (calls && calls.length) {
                    const lastCall = [...calls].reverse().find(c => c.tool === event.tool && c.status === 'running')
                    if (lastCall) {
                      lastCall.progress = {
                        percent: event.percent || '',
                        speed: event.speed || '',
                        eta: event.eta || '',
                        total: event.total || '',
                      }
                    }
                  }
                  break
                }
                case 'tool_result': {
                  // 更新最后一个同工具名的卡片状态
                  const calls = this.messages[aiIdx].toolCalls
                  if (calls && calls.length) {
                    const lastCall = [...calls].reverse().find(c => c.tool === event.tool && c.status === 'running')
                    if (lastCall) {
                      lastCall.status = event.success ? 'success' : 'error'
                      if (event.media_info) lastCall.mediaInfo = event.media_info
                      if (event.preview) lastCall.result = event.preview
                    }
                  }
                  lastToolResult = { tool: event.tool, success: event.success }
                  break
                }
                case 'reply':
                  // 追加而非替换，实现流式打字效果
                  if (this.messages[aiIdx].status === 'streaming' || this.messages[aiIdx].status === 'replying') {
                    this.messages[aiIdx].content += event.content
                    this.messages[aiIdx].status = 'replying'
                  } else {
                    this.messages[aiIdx].content = event.content
                  }
                  break
                case 'done':
                  this.messages[aiIdx].status = event.status
                  if (lastToolResult) {
                    this._handleToolResult(lastToolResult)
                  }
                  break
                case 'error':
                  this.messages[aiIdx].content = `处理失败: ${event.message}`
                  this.messages[aiIdx].status = 'error'
                  break
              }
            } catch (e) {
              // 忽略 SSE 解析错误
            }
          }
        }

        this._saveChatHistory()
      } catch (error) {
        if (error.name === 'AbortError') {
          // SSE 被主动取消（新对话或确认操作），不显示错误
        } else {
          this.messages[aiIdx].content = `连接失败: ${error.message}`
          this.messages[aiIdx].status = 'error'
        }
      } finally {
        this._activeSseController = null
        this.chatLoading = false
      }
    },

    stopChat() {
      if (this._activeSseController) {
        this._activeSseController.abort()
        this._activeSseController = null
      }
      // 将最后一条 streaming 消息标记为已停止
      const last = this.messages[this.messages.length - 1]
      if (last && last.role === 'assistant' && last.status === 'streaming') {
        last.status = 'stopped'
        if (!last.content) last.content = ''
      }
      this.chatLoading = false
      this._saveChatHistory()
    },

    async confirmAction() {
      // 先取消正在进行的 SSE 流，避免双执行
      if (this._activeSseController) {
        this._activeSseController.abort()
        this._activeSseController = null
      }

      this.chatExecuting = true
      const pending = this.pendingConfirmation
      if (pending) {
        // 从确认状态恢复为流式状态
        this.messages[pending.aiIdx].status = 'streaming'
        this.messages[pending.aiIdx].content = `正在执行: ${pending.toolName}...`
        this.messages[pending.aiIdx].action = null
        this.pendingConfirmation = null
      }
      try {
        const body = {
          session_id: this.sessionId || undefined,
          message: '确认执行',
          context: { project_id: this.projectId || null },
        }
        if (this.projectId) body.project_id = this.projectId

        const response = await fetch(`${API_HOST}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const res = await response.json()
        if (!res.success) throw new Error(res.message || '执行失败')

        const data = res.data
        this.sessionId = data.sessionId || data.session_id || this.sessionId
        if (this.projectId && this.sessionId) {
          localStorage.setItem(`session_${this.projectId}`, this.sessionId)
        }

        this.messages.push({ role: 'assistant', content: data.reply, status: data.status })

        if (data.result) {
          this._handleToolResult(data.result)
        }
        this._saveChatHistory()
      } catch (error) {
        this.messages.push({ role: 'assistant', content: `执行失败: ${error.message}`, status: 'error' })
      } finally {
        this.chatExecuting = false
      }
    },

    async cancelAction() {
      const pending = this.pendingConfirmation
      if (pending) {
        this.messages[pending.aiIdx].status = 'streaming'
        this.messages[pending.aiIdx].action = null
        this.pendingConfirmation = null
      }
      try {
        const body = {
          session_id: this.sessionId || undefined,
          message: '取消执行',
          context: { project_id: this.projectId || null },
        }
        const response = await fetch(`${API_HOST}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const res = await response.json()
        const data = res.data
        this.messages.push({ role: 'assistant', content: data?.reply || '操作已取消' })
        this._saveChatHistory()
      } catch (error) {
        ElMessage.error('取消失败')
      }
    },

    /** 根据工具执行结果自动刷新对应面板 */
    _handleToolResult(result) {
      if (!result) return
      const tool = result.tool || ''
      const outputPath = result.output_path || result.web_path

      // 更新预览
      if (outputPath) {
        this.previewVideoPath = outputPath
      }

      // 素材类工具 → 刷新素材库
      const materialTools = ['list_videos', 'search_material', 'download_video', 'random_video', 'delete_material',
        'cut_video', 'merge_videos', 'smart_clip', 'add_subtitle', 'change_speed', 'compress_video']
      if (materialTools.includes(tool)) {
        this.refreshMaterials()
        this.activeTab = 'materials'
      }

      // 智能剪辑 → 刷新方案
      if (tool === 'smart_clip') {
        this.activeTab = 'plan'
      }

      // 音频类工具 → 切到音频 tab
      const audioTools = ['generate_tts', 'generate_music', 'add_audio', 'extract_audio', 'mix_audio_to_video', 'separate_vocal', 'add_echo', 'denoise_audio', 'normalize_audio']
      if (audioTools.includes(tool)) {
        if (result.output_path) this.project.ttsPath = result.output_path
        this.activeTab = 'audio'
      }

      // 视频分析类 → 切到预览
      const analysisTools = ['analyze_video', 'analyze_video_vl', 'transcribe_video', 'get_video_detail']
      if (analysisTools.includes(tool)) {
        this.activeTab = 'materials'
      }
    },

    _saveChatHistory() {
      if (this.projectId) {
        // 深拷贝确保 reactive proxy 被正确序列化为 plain JSON
        const plain = JSON.parse(JSON.stringify(this.messages.slice(-50)))
        this.saveField('chat_history', plain)
        // 持久化 sessionId 到 localStorage
        if (this.sessionId) {
          localStorage.setItem(`session_${this.projectId}`, this.sessionId)
        }
      }
    },

    // ==================== 素材管理 ====================

    async refreshMaterials() {
      this.materialLoading = true
      try {
        const [data, full] = await Promise.all([
          videoApi.getSourceVideos({ page: 1, page_size: 50 }),
          this.projectId ? projectApi.getFull(this.projectId) : Promise.resolve(null),
        ])
        this.materialLibrary = data.items || data || []
        if (full) {
          this.materials = full.materials || []
        }
      } catch (error) {
        console.error('加载素材列表失败:', error)
        ElMessage.error(`加载素材失败: ${error.message}`)
      } finally {
        this.materialLoading = false
      }
    },

    async addMaterialToProject(materialId) {
      if (!this.projectId) return
      const ids = [...(this.project.materialIds || [])]
      if (!ids.includes(materialId)) {
        ids.push(materialId)
        this.project.materialIds = ids
        // 立即保存并刷新关联素材
        await projectApi.update(this.projectId, { material_ids: ids })
        const full = await projectApi.getFull(this.projectId)
        this.materials = full.materials || []
      }
    },

    async removeMaterialFromProject(materialId) {
      if (!this.projectId) return
      const ids = (this.project.materialIds || []).filter(id => id !== materialId)
      this.project.materialIds = ids
      this.materials = this.materials.filter(m => m.id !== materialId)
      await projectApi.update(this.projectId, { material_ids: ids })
    },

    // ==================== BGM 管理 ====================

    async refreshBgmList() {
      try {
        const data = await projectApi.listBgm()
        this.bgmList = data.items || data || []
      } catch (error) {
        console.error('加载 BGM 列表失败:', error)
      }
    },

    // ==================== 音色管理 ====================

    async refreshVoiceList() {
      this.audioLoading = true
      try {
        const data = await audioApi.getSourceAudio({ page: 1, page_size: 50 })
        this.voiceList = data.items || data || []
      } catch (error) {
        console.error('加载音色列表失败:', error)
      } finally {
        this.audioLoading = false
      }
    },

    // ==================== 方案与渲染 ====================

    async generatePlan({ creative, targetDuration, style }) {
      if (!this.projectId) return
      this.planLoading = true
      try {
        const data = await projectApi.generatePlan(this.projectId, {
          creative, target_duration: targetDuration, style,
        })
        this.project.planData = data
        this.activeTab = 'plan'
        return data
      } catch (error) {
        ElMessage.error('生成方案失败: ' + error.message)
      } finally {
        this.planLoading = false
      }
    },

    async applyAndRender({ ttsPath, bgmId, bgmVolume }) {
      if (!this.projectId) return
      this.rendering = true
      try {
        await projectApi.applyPlan(this.projectId)
        const data = await projectApi.render(this.projectId, {
          tts_path: ttsPath, bgm_id: bgmId, bgm_volume: bgmVolume,
        })
        this.project.outputPath = data.output_path || data.web_path
        if (data.output_videos) {
          this.project.outputVideos = data.output_videos
        } else {
          // 兼容旧后端：把单个 output 追加到列表
          const existing = this.project.outputVideos || []
          const exists = existing.some(v => v.path === this.project.outputPath)
          if (!exists && this.project.outputPath) {
            existing.push({ path: this.project.outputPath, created_at: new Date().toISOString() })
            this.project.outputVideos = existing
          }
        }
        this.previewVideoPath = this.project.outputPath
        this.activeTab = 'preview'
        ElMessage.success('渲染完成')
        return data
      } catch (error) {
        ElMessage.error('渲染失败: ' + error.message)
      } finally {
        this.rendering = false
      }
    },

    setActiveTab(tab) {
      this.activeTab = tab
    },

    toggleChat() {
      this.chatCollapsed = !this.chatCollapsed
    },
    toggleWorkspace() {
      this.workspaceCollapsed = !this.workspaceCollapsed
      savePanelState(this)
    },
    toggleRightPanel() {
      this.rightPanelCollapsed = !this.rightPanelCollapsed
      savePanelState(this)
    },

    // ==================== 方案模式 ====================

    setChatMode(mode) {
      this.chatMode = mode
      if (mode !== 'plan') {
        this.planOperations = []
        this.planSummary = ''
        this.planExecutionState = 'idle'
      }
    },

    async generatePlan(message) {
      this.planLoading = true
      this.planExecutionState = 'generating'
      this.planOperations = []
      try {
        const response = await fetch(`${API_HOST}/api/agent/plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message,
            project_id: this.projectId,
            session_id: this.sessionId,
          }),
        })
        const result = await response.json()
        if (result.code === 200 && result.data) {
          const planData = result.data
          this.planSummary = planData.summary || ''
          const ops = (planData.operations || []).map((op, i) => ({
            ...op,
            id: op.id || `op_${i}`,
            status: 'pending',
            selected: true,
          }))
          this.planOperations = ops
          this.planExecutionState = ops.length ? 'confirming' : 'idle'
          return planData
        } else {
          ElMessage.error(result.message || '方案生成失败')
          this.planExecutionState = 'idle'
        }
      } catch (error) {
        ElMessage.error('方案生成失败: ' + error.message)
        this.planExecutionState = 'idle'
      } finally {
        this.planLoading = false
      }
    },

    toggleOperation(opId) {
      const op = this.planOperations.find(o => o.id === opId)
      if (op) op.selected = !op.selected
    },

    selectAllOperations() {
      this.planOperations.forEach(o => { o.selected = true })
    },

    deselectAllOperations() {
      this.planOperations.forEach(o => { o.selected = false })
    },

    async executeSelectedOperations() {
      const selected = this.planOperations.filter(o => o.selected && o.status === 'pending')
      if (!selected.length) return

      this.planExecutionState = 'executing'
      for (const op of selected) {
        op.status = 'executing'
        try {
          const response = await fetch(`${API_HOST}/api/agent/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool: op.tool, params: op.params }),
          })
          const result = await response.json()
          op.status = result.code === 200 ? 'done' : 'error'
          op.result = result.data
          // 处理工具结果（复用现有逻辑）
          if (result.code === 200) {
            this._handleToolResult(op.tool, result.data)
          }
        } catch (error) {
          op.status = 'error'
          op.error = error.message
        }
      }
      this.planExecutionState = 'done'
    },

    // ==================== 版本快照 ====================

    async createSnapshot(label = '') {
      if (!this.projectId) return
      const snapshot = {
        id: Date.now(),
        label,
        timestamp: new Date().toISOString(),
        projectData: JSON.parse(JSON.stringify(this.project)),
        materials: JSON.parse(JSON.stringify(this.materials)),
        materialCount: this.materials.length,
      }
      try {
        const res = await fetch(`${API_HOST}/api/projects/${this.projectId}/plan/snapshot`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label, data: snapshot }),
        })
        const result = await res.json()
        if (result.code === 200) {
          this.versionSnapshots.unshift(snapshot)
          ElMessage.success('快照已保存')
        }
      } catch (e) {
        this.versionSnapshots.unshift(snapshot)
      }
    },

    async loadSnapshots() {
      if (!this.projectId) return
      try {
        const res = await fetch(`${API_HOST}/api/projects/${this.projectId}/plan/snapshots`).then(r => r.json())
        if (res.code === 200 && res.data?.snapshots) {
          this.versionSnapshots = res.data.snapshots
        }
      } catch (e) {}
    },

    async restoreSnapshot(snapshotId) {
      const snap = this.versionSnapshots.find(s => s.id === snapshotId)
      if (!snap) return
      Object.assign(this.project, JSON.parse(JSON.stringify(snap.projectData)))
      this.materials = JSON.parse(JSON.stringify(snap.materials))
      await this.saveProject()
      ElMessage.success('已恢复到快照版本')
    },
  },
})

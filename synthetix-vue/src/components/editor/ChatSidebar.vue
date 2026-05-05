<template>
  <div class="chat-sidebar">
    <div class="chat-header">
      <span class="chat-title">{{ t('editor.aiTitle') }}</span>
      <el-input v-if="showSearch" v-model="searchKeyword" placeholder="搜索消息..." size="small"
                class="search-input" clearable @blur="!searchKeyword && (showSearch = false)" />
      <el-button v-else text size="small" @click="showSearch = true" title="搜索"><el-icon><Search /></el-icon></el-button>
      <el-button text size="small" @click="exportChat" title="导出"><el-icon><Download /></el-icon></el-button>
      <el-button text size="small" @click="clearChat">{{ t('editor.clearChat') }}</el-button>
    </div>

    <!-- 对话模式切换 -->
    <div class="chat-mode-tabs">
      <div v-for="m in chatModes" :key="m.value" class="mode-tab" :class="{ active: store.chatMode === m.value }"
           @click="store.setChatMode(m.value)" :title="m.desc">
        <el-icon :size="14"><component :is="m.icon" /></el-icon>
        <span>{{ m.label }}</span>
      </div>
    </div>

    <!-- 方案模式操作面板 -->
    <div v-if="store.chatMode === 'plan' && store.planOperations.length" class="plan-panel">
      <div v-if="store.planSummary" class="plan-summary">{{ store.planSummary }}</div>
      <div class="plan-actions-bar">
        <el-button size="small" @click="store.selectAllOperations()">全选</el-button>
        <el-button size="small" @click="store.deselectAllOperations()">取消全选</el-button>
        <el-button size="small" type="primary"
                   :loading="store.planExecutionState === 'executing'"
                   :disabled="!selectedOps.length || store.planExecutionState === 'executing'"
                   @click="store.executeSelectedOperations()">
          执行选中 ({{ selectedOps.length }}/{{ store.planOperations.length }})
        </el-button>
      </div>
      <div class="plan-operations">
        <PlanOperationCard v-for="op in store.planOperations" :key="op.id"
                           :operation="op" :selected="op.selected"
                           @toggle="store.toggleOperation(op.id)" />
      </div>
    </div>

    <div class="chat-messages" ref="messagesRef">
      <div v-for="(msg, i) in filteredMessages" :key="i"
           class="chat-message" :class="msg.role">
        <div class="message-bubble" @mouseenter="hoverMsg = i" @mouseleave="hoverMsg = -1"
             @contextmenu.prevent="onMsgContext($event, msg, i)">
          <!-- 时间戳 -->
          <div class="msg-meta">
            <span class="msg-time">{{ relativeTime(msg.timestamp) }}</span>
          </div>
          <!-- 工具调用卡片 -->
          <div v-if="msg.toolCalls && msg.toolCalls.length" class="tool-cards">
            <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="tool-card" :class="tc.status">
              <div class="tool-card-header">
                <span class="tool-icon">
                  <el-icon v-if="tc.status === 'running'" class="is-loading"><Loading /></el-icon>
                  <el-icon v-else-if="tc.status === 'success'" class="tool-success"><CircleCheck /></el-icon>
                  <el-icon v-else class="tool-error"><CircleClose /></el-icon>
                </span>
                <span class="tool-name">{{ tc.tool }}</span>
                <el-tag v-if="tc.permission" size="small" :type="tc.permission === 'destructive' ? 'danger' : 'info'"
                        class="tool-perm">{{ tc.permission }}</el-tag>
                <span v-if="tc.duration" class="tool-duration">{{ tc.duration }}ms</span>
                <span v-if="tc.tokens" class="tool-tokens">~{{ tc.tokens }}tok</span>
              </div>
              <div v-if="tc.params && Object.keys(tc.params).length" class="tool-params">
                <span v-for="(val, key) in tc.params" :key="key" class="tool-param-item">
                  <span class="tool-param-key">{{ formatParamKey(String(key)) }}</span>: {{ val }}
                </span>
              </div>
              <div v-if="tc.result" class="tool-result-summary">
                <el-button text size="small" @click="tc._expanded = !tc._expanded">
                  {{ tc._expanded ? '收起结果' : '查看结果' }}
                </el-button>
                <pre v-if="tc._expanded" class="tool-result-json">{{ formatToolResult(tc.result) }}</pre>
              </div>
              <FfmpegPreview v-if="tc.ffmpegCmd" :command="tc.ffmpegCmd.split(' ')" />
              <TempAssetCard v-if="tc.mediaInfo && tc.status === 'success'" :media-info="tc.mediaInfo" @preview="openPreview" @refresh="refreshMaterials" />
              <div v-if="tc.status === 'error'" class="tool-retry">
                <el-button v-if="isCookieError(tc)" text size="small" type="warning" @click="openCookieManager">
                  <el-icon><Present /></el-icon> 配置Cookie
                </el-button>
              </div>
              <!-- 下载进度条 -->
              <div v-if="tc.progress && tc.status === 'running'" class="tool-progress">
                <el-progress :percentage="parseFloat(tc.progress.percent) || 0" :stroke-width="6"
                             :show-text="false" class="tool-progress-bar" />
                <span class="tool-progress-text">
                  {{ tc.progress.percent }}{{ tc.progress.speed ? ` · ${tc.progress.speed}` : '' }}{{ tc.progress.eta ? ` · 剩余 ${tc.progress.eta}` : '' }}
                </span>
              </div>
            </div>
          </div>
          <div v-html="formatMessage(msg.content)" class="msg-content" :class="{ streaming: msg.status === 'streaming' || msg.status === 'replying' }"></div>
          <div v-if="msg.status === 'stopped'" class="msg-stopped">已停止生成</div>
          <!-- 用户上传的附件内联展示 -->
          <div v-if="msg.attachments && msg.attachments.length" class="msg-attachments">
            <template v-for="(att, ai) in msg.attachments" :key="ai">
              <img v-if="att.type === 'image'" :src="att.webPath" class="msg-att-image" @click="openPreview(att.webPath, 'image')" />
              <video v-else-if="att.type === 'video'" :src="att.webPath" class="msg-att-video" controls />
              <audio v-else-if="att.type === 'audio'" :src="att.webPath" class="msg-att-audio" controls />
              <div v-else class="msg-att-file"><el-icon :size="14"><Document /></el-icon> {{ att.name }}</div>
            </template>
          </div>
          <!-- 确认面板 -->
          <div v-if="msg.status === 'confirming' && msg.action" class="confirm-panel">
            <div class="confirm-info">
              <el-tag type="danger" size="small">{{ t('editor.confirmRequired') }}</el-tag>
              <span class="confirm-tool">{{ msg.action.toolName }}</span>
            </div>
            <div v-if="msg.action.params && Object.keys(msg.action.params).length" class="confirm-params-table">
              <div v-for="(val, key) in msg.action.params" :key="key" class="param-row">
                <span class="param-key">{{ formatParamKey(String(key)) }}</span>
                <span class="param-val" :class="{ 'param-highlight': isHighlightParam(String(key)) }">{{ val }}</span>
              </div>
            </div>
            <div class="action-buttons">
              <el-button type="danger" size="small" :loading="store.chatExecuting" @click="store.confirmAction()">{{ t('editor.confirmExecute') }}</el-button>
              <el-button size="small" @click="store.cancelAction()">{{ t('common.cancel') }}</el-button>
            </div>
          </div>
          <!-- 消息操作按钮（始终占位，hover 时显示） -->
          <div class="msg-bottom-actions" :class="{ 'actions-visible': hoverMsg === i }">
            <el-button text size="small" @click="copyMsg(msg)" title="复制">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
            <el-button v-if="msg.role === 'assistant'" text size="small" @click="retryMsg(msg)" title="重新推理">
              <el-icon><RefreshRight /></el-icon>
            </el-button>
            <el-button v-if="msg.role === 'assistant'" text size="small" @click="deleteMsg(i)" title="删除">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <!-- 建议 -->
          <div v-if="msg.suggestions && msg.suggestions.length" class="suggestions">
            <el-tag v-for="s in msg.suggestions" :key="s" size="small" class="suggestion-tag"
                    @click="store.processChatMessageStream(s)">{{ s }}</el-tag>
          </div>
        </div>
      </div>
      <div v-if="store.chatLoading" class="chat-loading">
        <span class="typing-dots"><span>.</span><span>.</span><span>.</span></span> {{ t('editor.thinking') }}
      </div>
    </div>

    <!-- 快捷指令面板 -->
    <div class="cmd-panel">
      <div class="cmd-header" @click="showCmdPanel = !showCmdPanel">
        <span class="cmd-title">快捷指令</span>
        <el-icon :size="12"><ArrowUp v-if="showCmdPanel" /><ArrowDown v-else /></el-icon>
      </div>
      <div v-if="showCmdPanel" class="cmd-body">
        <div class="cmd-categories">
          <span v-for="cat in cmdCategories" :key="cat.key"
                class="cmd-cat" :class="{ active: activeCmdCat === cat.key }"
                @click="activeCmdCat = cat.key">{{ cat.icon }} {{ cat.label }}</span>
        </div>
        <div class="cmd-items">
          <el-tag v-for="cmd in activeCmds" :key="cmd.text" size="small"
                  class="cmd-tag" @click="useCmd(cmd.text)">{{ cmd.label }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="chat-input">
      <!-- 附件预览条 -->
      <div v-if="attachments.length" class="attachment-bar">
        <div v-for="(att, i) in attachments" :key="i" class="attachment-item">
          <img v-if="att.type === 'image'" :src="att.webPath" class="att-thumb" />
          <el-icon v-else-if="att.type === 'audio'" :size="18"><Headset /></el-icon>
          <el-icon v-else-if="att.type === 'video'" :size="18"><VideoCameraFilled /></el-icon>
          <el-icon v-else :size="18"><Document /></el-icon>
          <span class="att-name">{{ att.name }}</span>
          <el-icon class="att-remove" @click="attachments.splice(i, 1)"><Close /></el-icon>
        </div>
      </div>
      <div class="input-row">
        <el-button :icon="Paperclip" :disabled="store.chatLoading || uploading" :loading="uploading"
                   @click="$refs.fileInput.click()" circle size="small" title="上传素材" class="input-btn" />
        <input ref="fileInput" type="file" accept="image/*,video/*,audio/*" hidden @change="onFileSelect" />
        <el-input v-model="inputText" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }"
                  :placeholder="t('editor.inputPlaceholder')"
                  :disabled="store.chatLoading"
                  @keydown.enter.exact.prevent="sendMessage" class="input-field" />
        <el-button v-if="store.chatLoading" type="danger" :icon="CircleClose"
                   @click="store.stopChat()" circle size="small" class="input-btn stop-btn" />
        <el-button v-else type="primary" :icon="Promotion"
                   @click="sendMessage" circle size="small" class="input-btn send-btn" />
      </div>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div v-if="ctxMenu.visible.value" class="context-menu"
           :style="{ left: ctxMenu.position.value.x + 'px', top: ctxMenu.position.value.y + 'px' }">
        <div class="ctx-item" @click="copyMsg(ctxMenu.contextData.value?.msg)">
          <el-icon><CopyDocument /></el-icon> 复制内容
        </div>
        <div class="ctx-item" @click="deleteMsg(ctxMenu.contextData.value?.index)">
          <el-icon><Delete /></el-icon> 删除
        </div>
      </div>
    </Teleport>

    <!-- 临时素材预览弹窗 -->
    <el-dialog v-model="previewVisible" title="预览" width="640" top="6vh" destroy-on-close append-to-body>
      <video v-if="previewType === 'video'" :src="previewUrl" controls style="width: 100%; max-height: 70vh" />
      <audio v-else-if="previewType === 'audio'" :src="previewUrl" controls style="width: 100%" />
      <img v-else-if="previewType === 'image'" :src="previewUrl" style="width: 100%; max-height: 70vh; object-fit: contain" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { Loading, Promotion, CircleCheck, CircleClose, Search, CopyDocument, RefreshRight, Delete, ChatDotRound, Film, DataAnalysis, Download, Star, StarFilled, Paperclip, Close, VideoCameraFilled, Headset, Document, ArrowUp, ArrowDown, Present } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { renderMarkdown } from '@/utils/sanitize'
import { useContextMenu } from '@/utils/useContextMenu'
import PlanOperationCard from './PlanOperationCard.vue'
import FfmpegPreview from './FfmpegPreview.vue'
import TempAssetCard from './TempAssetCard.vue'
import { videoApi } from '../../api/modules/video'
import { assetUrl, API_HOST } from '../../utils/request'

const { t } = useI18n()
const store = useProjectStore()
const inputText = ref('')
const messagesRef = ref(null)
const hoverMsg = ref(-1)
const showSearch = ref(false)
const searchKeyword = ref('')
const showCmdPanel = ref(true)
const activeCmdCat = ref('common')
const attachments = ref([])
const uploading = ref(false)

// 对话模式
const chatModes = [
  { value: 'free', label: '对话', icon: ChatDotRound, desc: '自由对话模式' },
  { value: 'plan', label: '方案', icon: Film, desc: '生成可编辑的剪辑方案' },
  { value: 'research', label: '研究', icon: DataAnalysis, desc: '深度分析模式' },
]
const selectedOps = computed(() => store.planOperations.filter(o => o.selected))

// 临时素材预览
const previewVisible = ref(false)
const previewUrl = ref('')
const previewType = ref('video')
const openPreview = (url, type) => {
  previewUrl.value = url
  previewType.value = type || 'video'
  previewVisible.value = true
}

const refreshMaterials = () => {
  if (store.projectId) store.loadProject(store.projectId)
}

// 右键菜单
const ctxMenu = useContextMenu()
const onMsgContext = (e, msg, index) => {
  ctxMenu.open(e, { msg, index })
}
const deleteMsg = (index) => {
  ctxMenu.close()
  if (index == null || index < 0) return
  const msg = store.messages[index]
  if (!msg) return
  // assistant 消息：连同前一条 user 一起删除
  if (msg.role === 'assistant' && index > 0 && store.messages[index - 1].role === 'user') {
    store.messages.splice(index - 1, 2)
  } else {
    store.messages.splice(index, 1)
  }
  store._saveChatHistory()
}

// ========== 快捷指令 ==========
const cmdCategories = [
  { key: 'ai', label: 'AI', icon: '🤖' },
  { key: 'clip', label: '剪辑', icon: '✂️' },
  { key: 'audio', label: '音频', icon: '🎵' },
  { key: 'subtitle', label: '字幕', icon: '🔤' },
  { key: 'videoEffect', label: '视频特效', icon: '🎬' },
  { key: 'imageEffect', label: '图片特效', icon: '🖼️' },
  { key: 'material', label: '素材', icon: '📁' },
  { key: 'tool', label: '工具', icon: '🔧' },
]

const cmdData = {
  ai: [
    { label: '智能剪辑', text: '使用项目素材帮我智能剪辑一个30秒的短视频，风格动感' },
    { label: '生成配音', text: '帮我生成一段语音：' },
    { label: '生成BGM', text: '帮我生成一段背景音乐，风格是：' },
    { label: '推荐BGM', text: '根据我的视频风格推荐适合的背景音乐' },
    { label: '字幕提取', text: '帮我提取这个视频的字幕' },
    { label: '分离人声伴奏', text: '帮我分离视频中的人声和伴奏' },
    { label: 'AI视频分析', text: '帮我用AI深度分析视频内容，理解场景、人物和风格' },
    { label: 'AI图片分析', text: '帮我分析这张图片的内容' },
    { label: '分析字幕高光', text: '帮我分析视频字幕，找出高光片段和情感峰值' },
    { label: '场景检测', text: '帮我检测视频中的场景切换点' },
    { label: '智能提取关键帧', text: '帮我从视频中智能提取关键帧' },
    { label: '优化提示词', text: '帮我优化这个AI提示词：' },
    { label: '翻译文本', text: '帮我把以下内容翻译成：' },
    { label: '检测语言', text: '帮我检测这段文本是什么语言：' },
  ],
  clip: [
    { label: '剪切指定时段', text: '帮我剪切视频，从 00:00:05 到 00:00:30' },
    { label: '合并全部素材', text: '帮我把所有项目素材按顺序合并成一个视频' },
    { label: '按间隔分割', text: '帮我把视频按每30秒分割成多个片段' },
    { label: '调整速度', text: '帮我把视频速度调整为1.5倍' },
    { label: '慢动作', text: '帮我把视频做成慢动作效果' },
    { label: '慢动作插帧', text: '帮我把视频做成慢动作插帧效果' },
    { label: '倒放视频', text: '帮我把视频倒放' },
    { label: '视频防抖', text: '帮我对视频进行防抖稳定处理' },
    { label: '压缩视频', text: '帮我压缩视频文件大小' },
    { label: '格式转换', text: '帮我把视频转换为MP4格式' },
    { label: '转GIF动图', text: '帮我把视频片段转换为GIF动图' },
    { label: '图片转视频', text: '帮我把图片转为视频，使用缩放效果' },
  ],
  audio: [
    { label: '提取音频', text: '帮我提取视频的音频轨道' },
    { label: '添加背景音乐', text: '帮我把背景音乐添加到视频中' },
    { label: '添加配音', text: '帮我把配音添加到视频中' },
    { label: '混合音频', text: '帮我把配音和BGM同时混入视频' },
    { label: '音频标准化', text: '帮我把音频音量标准化' },
    { label: '音频淡入淡出', text: '帮我把音频添加淡入淡出效果' },
    { label: '音频降噪', text: '帮我对音频进行降噪处理' },
    { label: '添加回声', text: '帮我把音频添加回声/混响效果' },
    { label: '音频变调', text: '帮我把音频升调2个半音' },
    { label: '音频均衡器', text: '帮我调节音频均衡器' },
    { label: '音频倒放', text: '帮我把音频倒放' },
  ],
  subtitle: [
    { label: '添加字幕', text: '帮我把字幕文件添加到视频中' },
    { label: '翻译字幕', text: '帮我把字幕翻译成英语' },
    { label: 'SRT转ASS', text: '帮我把SRT字幕转换为ASS格式' },
    { label: '叠加文字', text: '帮我在视频上叠加文字：' },
  ],
  videoEffect: [
    { label: '调整亮度对比度', text: '帮我调整视频的亮度和对比度' },
    { label: '调整饱和度', text: '帮我调整视频的饱和度' },
    { label: '色彩调整', text: '帮我调整视频的色彩风格' },
    { label: '模糊效果', text: '帮我给视频添加模糊效果' },
    { label: '锐化', text: '帮我对视频进行锐化处理' },
    { label: '旋转90度', text: '帮我把视频顺时针旋转90度' },
    { label: '水平翻转', text: '帮我把视频水平翻转' },
    { label: '垂直翻转', text: '帮我把视频垂直翻转' },
    { label: '裁剪画面', text: '帮我裁剪视频画面区域' },
    { label: '淡入淡出', text: '帮我给视频添加淡入淡出效果' },
    { label: '画中画', text: '帮我做一个画中画效果，把第二个视频叠加到主视频上' },
    { label: '添加水印', text: '帮我给视频添加图片水印' },
  ],
  imageEffect: [
    { label: '缩放图片', text: '帮我把图片缩放到800x600' },
    { label: '裁剪图片', text: '帮我把图片裁剪到800x600，从中心开始' },
    { label: '旋转图片', text: '帮我把图片旋转90度' },
    { label: '翻转图片', text: '帮我把图片水平翻转' },
    { label: '调整亮度', text: '帮我把图片调亮一点' },
    { label: '调整对比度', text: '帮我增加图片的对比度' },
    { label: '调整饱和度', text: '帮我提高图片饱和度' },
    { label: '模糊图片', text: '帮我给图片加模糊效果' },
    { label: '锐化图片', text: '帮我锐化图片让它更清晰' },
    { label: '格式转换', text: '帮我把图片转换为JPG格式' },
    { label: '压缩图片', text: '帮我压缩图片减小文件大小' },
    { label: '添加文字', text: '帮我在图片上添加文字：' },
  ],
  material: [
    { label: '查看素材库', text: '列出我当前项目的所有素材' },
    { label: '搜索本地素材', text: '帮我在本地搜索素材：' },
    { label: '在线搜索视频', text: '帮我在线搜索视频素材，关键词：' },
    { label: '下载视频', text: '帮我下载视频，URL是：' },
    { label: '随机素材', text: '帮我随机选一个素材' },
    { label: '设置封面', text: '帮我把视频当前画面设为封面' },
    { label: '更新描述', text: '帮我更新素材的描述和标签' },
    { label: '删除素材', text: '帮我删除素材：' },
    { label: '批量压缩', text: '帮我批量压缩素材目录下的所有视频' },
    { label: '搜索文件', text: '帮我在素材目录搜索文件：' },
    { label: '查看视频详情', text: '帮我查看视频的详细信息（分辨率、帧率、编码等）' },
    { label: '提取指定帧', text: '帮我提取视频第5秒的截图' },
  ],
  tool: [
    { label: '获取系统信息', text: '查看系统信息（GPU、磁盘等）' },
    { label: '打开文件夹', text: '帮我在文件管理器中打开素材目录' },
    { label: '时间格式转换', text: '帮我把 90 秒转换为 HH:MM:SS 格式' },
    { label: '查看任务进度', text: '帮我查看后台任务的执行进度' },
    { label: '浏览器打开', text: '帮我在浏览器中打开：' },
    { label: '浏览器截图', text: '帮我截取网页截图：' },
    { label: '知识库搜索', text: '帮我在知识库中搜索：' },
  ],
}

const activeCmds = computed(() => cmdData[activeCmdCat.value] || [])
const useCmd = (text) => { inputText.value = text }

// 搜索过滤
const filteredMessages = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return store.messages
  return store.messages.filter(m => (m.content || '').toLowerCase().includes(kw))
})

const sendMessage = () => {
  const text = inputText.value.trim()
  if ((!text && !attachments.value.length) || store.chatLoading) return
  inputText.value = ''
  const atts = [...attachments.value]
  attachments.value = []

  // 方案模式使用 plan API
  if (store.chatMode === 'plan') {
    store.generatePlan(text)
    return
  }

  // 深度研究模式或自由对话
  store.processChatMessageStream(text, atts)
}

const onFileSelect = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''

  // 判断文件类型
  let type = 'file'
  if (file.type.startsWith('image/')) type = 'image'
  else if (file.type.startsWith('video/')) type = 'video'
  else if (file.type.startsWith('audio/')) type = 'audio'

  uploading.value = true
  try {
    const res = await videoApi.uploadFile(file, store.projectId, store.sessionId)
    attachments.value.push({
      name: file.name,
      type,
      localPath: res.localPath,
      webPath: assetUrl(res.webPath),
      tempFileId: res.tempFileId,
      videoId: res.videoId,
      fileType: res.fileType,
    })
  } catch (err) {
    ElMessage.error('上传失败: ' + (err.message || '未知错误'))
  } finally {
    uploading.value = false
  }
}

const clearChat = async () => {
  // 删除该项目的所有后端会话（防止恢复出已删除的历史）
  if (store.projectId) {
    try {
      await fetch(`${API_HOST}/api/agent/sessions/project/${store.projectId}`, { method: 'DELETE' })
    } catch (e) { /* ignore */ }
  }
  store.messages = []
  store.sessionId = null
  if (store.projectId) {
    localStorage.removeItem(`session_${store.projectId}`)
    await store.saveField('chat_history', [])
  }
}

const formatMessage = (content) => {
  if (!content) return ''
  // 过滤工具执行记录（仅用于 LLM 上下文，不显示给用户）
  const display = content.replace(/\n\n\[工具执行记录\]\n[\s\S]*$/, '')
  return renderMarkdown(display)
}

const relativeTime = (ts) => {
  if (!ts) return ''
  const diff = Date.now() - ts
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

const copyMsg = (msg) => {
  navigator.clipboard.writeText(msg.content || '')
}

const retryMsg = (msg) => {
  // 找到这条 AI 回复之前的用户消息，删除这对对话，用原内容重新推理
  const idx = store.messages.indexOf(msg)
  if (idx > 0) {
    const userMsg = store.messages[idx - 1]
    if (userMsg.role === 'user') {
      const content = userMsg.content
      const attachments = userMsg.attachments || []
      store.messages.splice(idx - 1)
      store.processChatMessageStream(content, attachments)
    }
  }
}

const toggleFavorite = (msg) => {
  msg.favorite = !msg.favorite
}

const exportChat = () => {
  const lines = store.messages
    .filter(m => m.role === 'user' || m.role === 'assistant')
    .map(m => `## ${m.role === 'user' ? '用户' : 'AI'}\n\n${m.content || ''}`)
    .join('\n\n---\n\n')
  const blob = new Blob([`# 对话导出\n\n${lines}`], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chat_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

const paramKeyLabels = {
  video_id: '视频ID', start_time: '开始时间', end_time: '结束时间',
  output_path: '输出路径', text: '文本', duration: '时长',
  speed: '速度', volume: '音量', format: '格式', quality: '质量',
}
const highlightKeys = new Set(['video_id', 'start_time', 'end_time', 'output_path'])
const formatParamKey = (key) => paramKeyLabels[key] || key
const isHighlightParam = (key) => highlightKeys.has(key)

const formatToolResult = (result) => {
  try {
    return typeof result === 'string' ? result : JSON.stringify(result, null, 2)
  } catch { return String(result) }
}


const cookieErrorKeywords = ['cookie', 'Cookie', 'cookies.txt', '登录', 'Fresh cookies']
const isCookieError = (tc) => {
  if (tc.tool !== 'download_video') return false
  return cookieErrorKeywords.some(kw =>
    (tc.result?.error || tc.result?.preview || '').includes(kw)
  )
}

const openCookieManager = () => {
  window.dispatchEvent(new CustomEvent('open-dialog', { detail: 'cookieManager' }))
}

watch(() => store.messages.length, async () => {
  await nextTick()
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
})
</script>

<style scoped>
.chat-sidebar {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  overflow: hidden;
}
/* 模式切换标签 */
.chat-mode-tabs {
  display: flex;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  padding: 0 12px;
}
.mode-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.mode-tab:hover { color: var(--el-color-primary); }
.mode-tab.active {
  color: var(--el-color-primary);
  border-bottom-color: var(--el-color-primary);
  font-weight: 500;
}
/* 方案面板 */
.plan-panel {
  border-bottom: 1px solid var(--el-border-color-lighter);
  max-height: 300px;
  overflow-y: auto;
  padding: 8px 12px;
}
.plan-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
  padding: 6px 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.plan-actions-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.plan-operations {
  display: flex;
  flex-direction: column;
}
.chat-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 4px;
}
.chat-title { flex: 1; font-weight: 600; font-size: 14px; }
.search-input { width: 120px; }

.chat-messages { flex: 1; overflow-y: auto; padding: 12px; }
.chat-message { margin-bottom: 12px; }
.chat-message.user { text-align: right; }
.chat-message.user .message-bubble {
  background: var(--el-color-primary);
  color: white;
  display: inline-block;
  text-align: left;
  border-radius: 12px 12px 4px 12px;
  padding: 8px 12px;
  max-width: 90%;
}
.chat-message.assistant .message-bubble {
  background: var(--el-fill-color-light);
  border-radius: 12px 12px 12px 4px;
  padding: 8px 12px;
  max-width: 95%;
  font-size: 13px;
  line-height: 1.6;
}

/* 消息元信息 */
.msg-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.msg-time { font-size: 10px; color: var(--el-text-color-placeholder); }
.msg-bottom-actions {
  display: flex;
  gap: 2px;
  margin-top: 4px;
  justify-content: flex-start;
  height: 24px;
  visibility: hidden;
  opacity: 0;
  transition: opacity 0.15s;
}
.msg-bottom-actions.actions-visible {
  visibility: visible;
  opacity: 0.6;
}
.msg-bottom-actions.actions-visible:hover { opacity: 1; }

.action-buttons { margin-top: 8px; display: flex; gap: 8px; }
.confirm-panel {
  margin-top: 8px; padding: 8px;
  background: var(--el-color-danger-light-9);
  border-radius: 6px;
  border: 1px solid var(--el-color-danger-light-7);
}
.confirm-info { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.confirm-tool { font-weight: 600; font-size: 13px; }
.confirm-params-table { margin-bottom: 8px; font-size: 12px; display: flex; flex-direction: column; gap: 4px; }
.param-row { display: flex; gap: 8px; align-items: baseline; }
.param-key { color: var(--el-text-color-secondary); min-width: 70px; flex-shrink: 0; font-size: 11px; }
.param-val { color: var(--el-text-color-primary); font-family: monospace; font-size: 12px; word-break: break-all; }
.param-highlight { color: var(--el-color-danger); font-weight: 600; }

/* 工具卡片 */
.tool-cards { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.tool-card {
  background: var(--el-fill-color-lighter);
  border-radius: 6px; padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
  font-size: 12px; transition: border-color 0.2s;
}
.tool-card.running { border-color: var(--el-color-primary-light-5); }
.tool-card.success { border-color: var(--el-color-success-light-5); }
.tool-card.error { border-color: var(--el-color-danger-light-5); }
.tool-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.tool-icon { display: flex; align-items: center; font-size: 14px; }
.tool-success { color: var(--el-color-success); }
.tool-error { color: var(--el-color-danger); }
.tool-name { font-weight: 600; color: var(--el-text-color-primary); }
.tool-perm { margin-left: auto; font-size: 10px; }
.tool-duration { font-size: 10px; color: var(--el-text-color-placeholder); font-family: monospace; margin-left: 4px; }
.tool-tokens { font-size: 10px; color: var(--el-text-color-placeholder); font-family: monospace; margin-left: 2px; }
.tool-result-summary { margin-top: 4px; }
.tool-result-json { font-size: 10px; background: var(--el-fill-color-lighter); padding: 6px; border-radius: 4px; max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin: 4px 0 0; }
.tool-ffmpeg-preview { margin-top: 2px; }
.ffmpeg-cmd { display: block; font-size: 10px; background: var(--el-fill-color-lighter); padding: 4px 6px; border-radius: 4px; white-space: pre-wrap; word-break: break-all; margin: 4px 0 0; color: var(--el-color-success); }
.tool-retry { margin-top: 2px; }
.tool-progress { margin-top: 4px; }
.tool-progress-bar { flex: 1; }
.tool-progress-text { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; display: block; }
.tool-params { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--el-text-color-secondary); }
.tool-param-item { font-family: monospace; font-size: 11px; }
.tool-param-key { color: var(--el-text-color-regular); font-weight: 500; }

/* 流式光标 */
.msg-content.streaming::after {
  content: '▊'; animation: blink 1s step-end infinite;
  color: var(--el-color-primary); margin-left: 2px;
}
.msg-stopped {
  margin-top: 6px; font-size: 12px; color: var(--el-text-color-placeholder);
  border-top: 1px dashed var(--el-border-color-lighter); padding-top: 6px;
}
@keyframes blink { 50% { opacity: 0; } }

/* 消息内联附件 */
.msg-attachments { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.msg-att-image { max-width: 200px; max-height: 160px; border-radius: 6px; cursor: pointer; object-fit: cover; }
.msg-att-video { max-width: 280px; max-height: 180px; border-radius: 6px; }
.msg-att-audio { width: 220px; }
.msg-att-file { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--el-text-color-secondary); padding: 4px 8px; background: var(--el-fill-color-light); border-radius: 4px; }

/* 打字指示器 */
.typing-dots span { animation: dotBounce 1.4s infinite ease-in-out both; }
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes dotBounce {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

.suggestions { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }
.suggestion-tag { cursor: pointer; }
.suggestion-tag:hover { opacity: 0.8; }
.chat-loading { text-align: center; color: var(--el-text-color-secondary); font-size: 13px; padding: 8px; }

/* 快捷指令面板 */
.cmd-panel {
  border-top: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}
.cmd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  transition: color 0.15s;
}
.cmd-header:hover { color: var(--el-color-primary); }
.cmd-title { font-weight: 500; }
.cmd-body {
  padding: 0 12px 6px;
}
.cmd-categories {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.cmd-cat {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  cursor: pointer;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  transition: all 0.15s;
  white-space: nowrap;
}
.cmd-cat:hover { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.cmd-cat.active { background: var(--el-color-primary); color: #fff; }
.cmd-items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 80px;
  overflow-y: auto;
}
.cmd-tag { cursor: pointer; transition: all 0.15s; }
.cmd-tag:hover { opacity: 0.75; }

/* 输入区 */
.chat-input {
  display: flex; flex-direction: column; gap: 4px;
  padding: 8px 12px; border-top: 1px solid var(--el-border-color-lighter);
}
.input-row { display: flex; align-items: flex-end; gap: 6px; }
.input-btn { flex-shrink: 0; }
.input-field { flex: 1; min-width: 0; }
.input-field :deep(.el-textarea__inner) { resize: none; padding: 6px 10px; }
.send-btn { flex-shrink: 0; }
.stop-btn { flex-shrink: 0; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .6; } }

/* 附件预览条 */
.attachment-bar {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0;
}
.attachment-item {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px; background: var(--el-fill-color-light);
  border-radius: 4px; font-size: 12px; max-width: 180px;
}
.att-thumb { width: 28px; height: 28px; object-fit: cover; border-radius: 3px; flex-shrink: 0; }
.att-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.att-remove { cursor: pointer; color: var(--el-text-color-secondary); flex-shrink: 0; }
.att-remove:hover { color: var(--el-color-danger); }

/* 右键菜单 */
.context-menu {
  position: fixed;
  z-index: 9999;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 4px 0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 140px;
}
.ctx-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.ctx-item:hover { background: var(--el-fill-color-light); }

/* 动效过渡 */
.chat-message {
  transition: opacity 0.2s, transform 0.2s;
}
.suggestion-tag {
  transition: all 0.2s;
}

/* 代码块样式 */
:deep(.code-block) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  font-family: 'Consolas', 'Monaco', monospace;
}
:deep(.inline-code) {
  background: var(--el-fill-color);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
}

/* 代码块包装器 */
:deep(.code-block-wrapper) {
  position: relative;
  margin: 4px 0;
}
:deep(.code-copy-btn) {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.7);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}
:deep(.code-block-wrapper:hover .code-copy-btn) {
  opacity: 1;
}
:deep(.code-copy-btn:hover) {
  background: rgba(255,255,255,0.2);
  color: #fff;
}
</style>

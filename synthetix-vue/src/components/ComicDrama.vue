<template>
  <div class="comic-drama">
    <!-- 系列管理视图（未加载项目时显示） -->
    <div v-if="!projectId" class="series-view">
      <div class="series-header">
        <h3>漫剧系列</h3>
        <el-button type="primary" size="small" @click="showCreateSeriesDialog = true">新建系列</el-button>
      </div>

      <!-- 独立项目创建 -->
      <el-card v-if="!showSeriesList" class="series-empty">
        <div class="empty-hint">
          <p>创建系列来管理多集漫剧，或创建独立项目</p>
          <div style="display: flex; gap: 12px; justify-content: center; margin-top: 16px;">
            <el-button @click="loadSeriesList">查看系列列表</el-button>
            <el-button type="primary" @click="showNamingDialog = true">创建独立项目</el-button>
          </div>
        </div>
      </el-card>

      <!-- 系列列表 -->
      <div v-if="showSeriesList" class="series-list">
        <el-card v-for="s in seriesList" :key="s.id" class="series-card" @click="openSeries(s)">
          <div class="series-card-header">
            <span class="series-name">{{ s.name }}</span>
            <div style="display: flex; gap: 8px; align-items: center;">
              <el-tag size="small" type="info">{{ s.episodeCount || 0 }} 集</el-tag>
              <el-tag size="small">{{ s.style || '动漫' }}</el-tag>
              <el-button size="small" text type="danger" @click.stop="deleteSeries(s.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <p v-if="s.description" class="series-desc">{{ s.description }}</p>
        </el-card>
        <div v-if="seriesList.length === 0" class="empty-hint">暂无系列，点击上方按钮创建</div>
      </div>
    </div>

    <!-- 系列详情/集数管理弹窗 -->
    <el-dialog v-model="showSeriesDetail" :title="currentSeries?.name || '系列详情'" width="700px" @close="showSeriesDetail = false">
      <div v-if="currentSeries" class="series-detail">
        <div class="series-info-bar">
          <span>画风: <strong>{{ currentSeries.style }}</strong></span>
          <span>类型: <strong>{{ currentSeries.genre || '未设置' }}</strong></span>
          <span>角色: <strong>{{ (currentSeries.characters || []).length }}</strong></span>
          <el-button size="small" @click="editSeriesCharacters">编辑角色库</el-button>
        </div>
        <el-divider />
        <div class="series-episodes-header">
          <h4>集数列表</h4>
          <el-button type="primary" size="small" @click="createEpisode">新建集数</el-button>
        </div>
        <div class="episode-list">
          <div v-for="ep in seriesEpisodes" :key="ep.id" class="episode-item" @click="openEpisode(ep)">
            <div class="episode-info">
              <span class="episode-num">第{{ ep.episodeNumber }}集</span>
              <span class="episode-name">{{ ep.name }}</span>
              <el-tag size="small" :type="getStatusType(ep.status)">{{ getStatusText(ep.status) }}</el-tag>
            </div>
            <el-button size="small" text type="danger" @click.stop="deleteEpisode(ep.id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <div v-if="seriesEpisodes.length === 0" class="empty-hint">暂无集数</div>
        </div>
      </div>
    </el-dialog>

    <!-- 系列角色编辑弹窗 -->
    <el-dialog v-model="showSeriesCharDialog" title="全局角色库" width="500px">
      <div v-for="(char, idx) in seriesCharacters" :key="idx" class="character-item">
        <div class="character-header">
          <span>角色 {{ idx + 1 }}</span>
          <el-button size="small" text type="danger" @click="seriesCharacters.splice(idx, 1)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <el-form label-position="top" size="small">
          <el-form-item label="名称"><el-input v-model="char.name" /></el-form-item>
          <el-form-item label="外貌"><el-input v-model="char.appearance" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="性格"><el-input v-model="char.personality" /></el-form-item>
        </el-form>
      </div>
      <el-button size="small" @click="seriesCharacters.push({ name: '', appearance: '', personality: '' })">添加角色</el-button>
      <template #footer>
        <el-button @click="showSeriesCharDialog = false">取消</el-button>
        <el-button type="primary" @click="saveSeriesCharacters" :loading="saving">保存并同步</el-button>
      </template>
    </el-dialog>

    <!-- 新建系列弹窗 -->
    <el-dialog v-model="showCreateSeriesDialog" title="新建漫剧系列" width="450px">
      <el-form label-position="top">
        <el-form-item label="系列名称" required>
          <el-input v-model="newSeriesForm.name" placeholder="输入系列名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newSeriesForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="画风">
          <el-select v-model="newSeriesForm.style" style="width: 100%;">
            <el-option label="动漫" value="动漫" />
            <el-option label="写实" value="写实" />
            <el-option label="水墨" value="水墨" />
            <el-option label="像素" value="像素" />
            <el-option label="美漫" value="美漫" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newSeriesForm.genre" style="width: 100%;">
            <el-option label="剧情" value="drama" />
            <el-option label="喜剧" value="comedy" />
            <el-option label="动作" value="action" />
            <el-option label="恋爱" value="romance" />
            <el-option label="悬疑" value="mystery" />
            <el-option label="奇幻" value="fantasy" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateSeriesDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmCreateSeries" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- 项目编辑视图（加载项目后显示） -->
    <template v-if="projectId">
      <!-- 系列信息栏（属于系列时显示） -->
      <div v-if="project.seriesId" class="series-bar">
        <div class="series-bar-left">
          <el-button text @click="backToSeriesList"><el-icon><ArrowLeft /></el-icon> 返回系列</el-button>
          <span class="series-bar-divider">|</span>
          <span>第{{ project.episodeNumber }}集</span>
        </div>
        <div class="series-bar-right">
          <el-button size="small" text @click="switchToPrevEpisode" :disabled="!canSwitchPrev">上一集</el-button>
          <el-button size="small" text @click="switchToNextEpisode" :disabled="!canSwitchNext">下一集</el-button>
        </div>
      </div>

    <!-- 命名弹窗 -->
    <el-dialog
      v-model="showNamingDialog"
      title="新建漫剧项目"
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

    <!-- 步骤导航 -->
    <div class="step-nav">
      <div
        v-for="(step, idx) in steps"
        :key="idx"
        class="step-nav-item"
        :class="{ active: currentStep === idx, done: currentStep > idx }"
        @click="currentStep = idx"
      >
        <div class="step-circle">
          <el-icon v-if="currentStep > idx" :size="16"><Check /></el-icon>
          <span v-else>{{ idx + 1 }}</span>
        </div>
        <div class="step-text">
          <span class="step-title">{{ step.title }}</span>
          <span class="step-desc">{{ step.desc }}</span>
        </div>
      </div>
    </div>

    <!-- 主体内容 -->
    <el-row :gutter="16">
      <!-- 左侧：分镜预览 -->
      <el-col :span="16">
        <el-card class="preview-card">
          <template #header>
            <div class="card-header">
              <span>{{ currentStep === 5 ? '最终视频' : '分镜预览' }}</span>
              <span v-if="totalDuration > 0" style="color: #909399; font-size: 13px;">
                总时长: {{ formatDuration(totalDuration) }}
              </span>
            </div>
          </template>

          <!-- 最终视频预览 -->
          <div v-if="currentStep === 5 && latestOutputVideo" class="video-container">
            <video :src="latestOutputVideo" controls class="video-player" />
          </div>

          <!-- 分镜网格 -->
          <div v-else class="storyboard-grid">
            <div
              v-for="(panel, idx) in panels"
              :key="idx"
              class="panel-card"
              :class="{ active: selectedPanelIndex === idx }"
              @click="selectedPanelIndex = idx"
            >
              <div class="panel-image">
                <img v-if="panel.generatedImagePath" :src="assetUrl(panel.generatedImagePath)" />
                <div v-else class="panel-placeholder">
                  <el-icon :size="28"><Picture /></el-icon>
                  <span>{{ (panel.sceneDescription || '').slice(0, 30) }}{{ (panel.sceneDescription || '').length > 30 ? '...' : '' }}</span>
                </div>
              </div>
              <div class="panel-info">
                <span class="panel-seq">#{{ idx + 1 }}</span>
                <span class="panel-dur">{{ panel.duration || 3 }}s</span>
                <el-icon v-if="panel.generatedImagePath" style="color: #67C23A;"><Check /></el-icon>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：编辑面板 -->
      <el-col :span="8">

        <!-- Step 0: 脚本 -->
        <el-card v-show="currentStep === 0" class="edit-card">
          <template #header><span>脚本生成</span></template>
          <el-form label-position="top">
            <el-form-item label="故事设定">
              <el-input v-model="scriptInput" type="textarea" :rows="4" placeholder="描述你的漫剧故事..." />
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="genre" style="width: 100%;">
                <el-option label="剧情" value="drama" />
                <el-option label="喜剧" value="comedy" />
                <el-option label="动作" value="action" />
                <el-option label="恋爱" value="romance" />
                <el-option label="悬疑" value="mystery" />
                <el-option label="奇幻" value="fantasy" />
              </el-select>
            </el-form-item>
            <el-form-item label="时长/分镜数">
              <div style="display: flex; gap: 8px; align-items: center; width: 100%;">
                <el-radio-group v-model="scriptSizeMode" size="small" style="flex-shrink: 0;">
                  <el-radio-button value="duration">按时长</el-radio-button>
                  <el-radio-button value="panels">按分镜数</el-radio-button>
                </el-radio-group>
                <el-input-number
                  v-if="scriptSizeMode === 'duration'"
                  v-model="targetDuration"
                  :min="10"
                  :max="600"
                  :step="10"
                  style="flex: 1;"
                >
                  <template #suffix>秒</template>
                </el-input-number>
                <el-input-number
                  v-else
                  v-model="numPanels"
                  :min="3"
                  :max="50"
                  style="flex: 1;"
                />
              </div>
            </el-form-item>
            <el-form-item label="画风">
              <el-select v-model="project.style" style="width: 100%;">
                <el-option label="动漫" value="动漫" />
                <el-option label="写实" value="写实" />
                <el-option label="水墨" value="水墨" />
                <el-option label="像素" value="像素" />
                <el-option label="美漫" value="美漫" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="generateScript" :loading="scriptGenerating" style="width: 100%;">
            {{ project.scriptData ? '重新生成脚本' : '生成脚本' }}
          </el-button>

          <!-- 已生成脚本概览 -->
          <div v-if="project.scriptData" class="script-overview">
            <h4>{{ project.scriptData.title || '未命名' }}</h4>
            <p class="synopsis">{{ project.scriptData.synopsis }}</p>
            <div class="script-stats">
              <span>分镜: {{ panels.length }}</span>
              <span>角色: {{ characters.length }}</span>
              <span>总时长: {{ formatDuration(totalDuration) }}</span>
            </div>
          </div>
        </el-card>

        <!-- Step 1: 角色 -->
        <el-card v-show="currentStep === 1" class="edit-card">
          <template #header>
            <div class="card-header">
              <span>角色设计</span>
              <el-button size="small" @click="addCharacter">添加角色</el-button>
            </div>
          </template>
          <div v-for="(char, idx) in characters" :key="idx" class="character-item">
            <div class="character-header">
              <span>角色 {{ idx + 1 }}</span>
              <el-button size="small" text type="danger" @click="removeCharacter(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-form label-position="top" size="small">
              <el-form-item label="名称">
                <el-input v-model="char.name" placeholder="角色名" />
              </el-form-item>
              <el-form-item label="外貌描述">
                <el-input v-model="char.appearance" type="textarea" :rows="2" placeholder="发色、发型、眼色、服装..." />
              </el-form-item>
              <el-form-item label="性格">
                <el-input v-model="char.personality" placeholder="性格特点" />
              </el-form-item>
              <el-form-item label="音色描述">
                <el-input v-model="char.voiceDescription" placeholder="如：清亮少女音" />
              </el-form-item>
              <el-form-item label="参考图">
                <div class="char-ref-image-area">
                  <img v-if="char.referenceImage" :src="assetUrl(char.referenceImage)" class="char-ref-thumb" />
                  <div v-else class="char-ref-placeholder">无参考图</div>
                  <div class="char-ref-actions">
                    <el-upload
                      :auto-upload="false"
                      :show-file-list="false"
                      accept="image/*"
                      @change="(f) => uploadCharRefImage(idx, f)"
                    >
                      <el-button size="small">上传图片</el-button>
                    </el-upload>
                    <el-button size="small" @click="generateCharRefImage(idx)" :loading="char._refLoading">
                      AI 生成
                    </el-button>
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </div>
          <el-button v-if="characters.length > 0" type="primary" @click="saveCharacters" :loading="saving" style="width: 100%; margin-top: 12px;">
            保存角色
          </el-button>
        </el-card>

        <!-- Step 2: 分镜 -->
        <el-card v-show="currentStep === 2" class="edit-card">
          <template #header>
            <div class="card-header">
              <span>分镜编辑</span>
              <el-button size="small" @click="addPanel">添加分镜</el-button>
            </div>
          </template>
          <div class="panel-edit-list">
            <div v-for="(panel, idx) in panels" :key="idx" class="panel-edit-item">
              <div class="panel-edit-header">
                <span>分镜 #{{ idx + 1 }}</span>
                <div class="panel-edit-actions">
                  <el-button size="small" text @click="generateImage(idx)" :loading="panel._imageLoading">
                    生成图片
                  </el-button>
                  <el-button v-if="panel.generatedImagePath" size="small" text @click="generateVideo(idx)" :loading="panel._videoLoading">
                    {{ panel.generatedVideoPath ? '重新生成视频' : '生成视频' }}
                  </el-button>
                  <el-button size="small" text type="danger" @click="removePanel(idx)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
              <el-input
                v-model="panel.sceneDescription"
                type="textarea"
                :rows="2"
                placeholder="场景描述（用于AI图片生成）"
                size="small"
              />
              <el-row :gutter="8" style="margin-top: 8px;">
                <el-col :span="8">
                  <el-input-number v-model="panel.duration" :min="1" :max="30" :step="0.5" size="small" style="width: 100%;" />
                </el-col>
                <el-col :span="8">
                  <el-select v-model="panel.transition" size="small" style="width: 100%;">
                    <el-option label="Cut" value="cut" />
                    <el-option label="Fade" value="fade" />
                    <el-option label="Dissolve" value="dissolve" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <el-select v-model="panel.emotion" size="small" style="width: 100%;">
                    <el-option label="中性" value="neutral" />
                    <el-option label="开心" value="happy" />
                    <el-option label="悲伤" value="sad" />
                    <el-option label="紧张" value="tense" />
                    <el-option label="浪漫" value="romantic" />
                  </el-select>
                </el-col>
              </el-row>
              <div v-if="panel.generatedVideoPath" class="panel-video-preview">
                <video :src="assetUrl(panel.generatedVideoPath)" controls style="width: 100%; max-height: 120px;" />
              </div>
            </div>
          </div>
          <el-button type="primary" @click="savePanels" :loading="saving" style="width: 100%; margin-top: 12px;">
            保存分镜
          </el-button>
        </el-card>

        <!-- Step 3: 音频 -->
        <el-card v-show="currentStep === 3" class="edit-card">
          <template #header><span>语音合成</span></template>
          <div class="panel-audio-list">
            <div v-for="(panel, idx) in panelsWithDialogue" :key="idx" class="panel-audio-item">
              <h5>分镜 #{{ panel._index + 1 }}</h5>
              <div v-for="(dlg, dIdx) in panel.dialogues" :key="dIdx" class="dialogue-item">
                <div class="dialogue-header">
                  <el-tag size="small" type="info">{{ dlg.characterId || '旁白' }}</el-tag>
                  <el-button size="small" text @click="generateAudio(panel._index, dlg.text)">
                    生成语音
                  </el-button>
                </div>
                <p class="dialogue-text">{{ dlg.text }}</p>
                <audio v-if="getAudioPath(panel._index, dIdx)" :src="assetUrl(getAudioPath(panel._index, dIdx))" controls style="width: 100%;" />
              </div>
            </div>
            <div v-if="panelsWithDialogue.length === 0" class="empty-hint">
              没有对白可生成，请先在脚本中添加对白
            </div>
          </div>
        </el-card>

        <!-- Step 4: BGM -->
        <el-card v-show="currentStep === 4" class="edit-card">
          <template #header><span>BGM 设置</span></template>
          <el-form label-position="top">
            <el-form-item label="BGM 文件">
              <el-select v-model="bgmConfig.path" placeholder="选择 BGM" style="width: 100%;" clearable>
                <el-option v-for="b in bgmList" :key="b.id" :label="b.name" :value="b.webPath" />
              </el-select>
            </el-form-item>
            <el-form-item label="音量">
              <el-slider v-model="bgmConfig.volume" :min="0" :max="1" :step="0.05" :format-tooltip="v => `${Math.round(v * 100)}%`" />
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="saveBgmConfig" :loading="saving" style="width: 100%;">
            保存 BGM 配置
          </el-button>
          <audio v-if="bgmConfig.path" :src="assetUrl(bgmConfig.path)" controls style="width: 100%; margin-top: 12px;" />
        </el-card>

        <!-- Step 5: 合成 -->
        <el-card v-show="currentStep === 5" class="edit-card">
          <template #header><span>合成视频</span></template>
          <div class="compose-summary">
            <p>分镜数: <strong>{{ panels.length }}</strong></p>
            <p>总时长: <strong>{{ formatDuration(totalDuration) }}</strong></p>
            <p>有图片: <strong>{{ panels.filter(p => p.generatedImagePath).length }}/{{ panels.length }}</strong></p>
            <p>BGM: <strong>{{ bgmConfig.path ? '已选择' : '未选择' }}</strong></p>
          </div>
          <el-button type="primary" @click="composeVideo" :loading="composing" style="width: 100%;" size="large">
            合成漫剧视频
          </el-button>
        </el-card>

      </el-col>
    </el-row>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="showRenameDialog" title="重命名项目" width="400px">
      <el-input v-model="renameInput" maxlength="50" show-word-limit />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit, Check, Delete, Picture, ArrowLeft } from '@element-plus/icons-vue'
import { comicDramaApi, comicSeriesApi, projectApi, assetUrl } from '@/api/modules'
import { getStatusType, getStatusText, formatDuration } from '@/utils/formatUtils'

const route = useRoute()
const router = useRouter()

// ==================== 步骤定义 ====================
const steps = [
  { title: '脚本', desc: 'AI 生成' },
  { title: '角色', desc: '设计' },
  { title: '分镜', desc: '画面' },
  { title: '音频', desc: '配音' },
  { title: 'BGM', desc: '配乐' },
  { title: '合成', desc: '导出' },
]

// ==================== 状态 ====================
const currentStep = ref(0)
const projectId = ref(null)
const project = reactive({
  name: '',
  status: 'draft',
  style: '动漫',
  scriptData: null,
  currentStep: 0,
  outputVideos: [],
})
const characters = ref([])
const panels = ref([])
const bgmConfig = reactive({ path: '', volume: 0.3 })
const bgmList = ref([])
const selectedPanelIndex = ref(-1)

// 脚本输入
const scriptInput = ref('')
const genre = ref('drama')
const numPanels = ref(10)
const targetDuration = ref(60)
const scriptSizeMode = ref('duration')
const scriptGenerating = ref(false)

// 加载状态
const saving = ref(false)
const composing = ref(false)

// 命名弹窗
const showNamingDialog = ref(false)
const namingInput = ref('')
const namingError = ref('')
const namingLoading = ref(false)
const namingInputRef = ref(null)

// 重命名弹窗
const showRenameDialog = ref(false)
const renameInput = ref('')

// 系列管理
const showSeriesList = ref(false)
const seriesList = ref([])
const showSeriesDetail = ref(false)
const currentSeries = ref(null)
const seriesEpisodes = ref([])
const showCreateSeriesDialog = ref(false)
const newSeriesForm = reactive({ name: '', description: '', style: '动漫', genre: 'drama' })
const showSeriesCharDialog = ref(false)
const seriesCharacters = ref([])

// ==================== 计算属性 ====================
const totalDuration = computed(() => {
  return panels.value.reduce((sum, p) => sum + (p.duration || 3), 0)
})

const latestOutputVideo = computed(() => {
  const vids = project.outputVideos || []
  if (vids.length === 0) return null
  const latest = vids[vids.length - 1]
  return assetUrl(latest.path)
})

const panelsWithDialogue = computed(() => {
  return panels.value
    .map((p, i) => ({ ...p, _index: i }))
    .filter(p => p.dialogues && p.dialogues.length > 0)
})

const canSwitchPrev = computed(() => {
  if (!project.seriesId || !currentSeries.value) return false
  return (project.episodeNumber || 1) > 1
})

const canSwitchNext = computed(() => {
  if (!project.seriesId || !currentSeries.value) return false
  return seriesEpisodes.value.some(ep => ep.episodeNumber > (project.episodeNumber || 1))
})

// ==================== 初始化 ====================
onMounted(async () => {
  const pid = route.query.projectId
  if (pid) {
    await loadProject(pid)
  }
  // 无项目时不自动弹窗，显示系列管理视图
  loadBgmList()
})

// ==================== 项目操作 ====================
async function loadProject(pid) {
  try {
    const res = await comicDramaApi.get(pid)
    const data = res
    projectId.value = data.id
    Object.assign(project, data)
    if (data.characters) characters.value = data.characters
    if (data.panels) panels.value = data.panels.map(p => ({ ...p, _imageLoading: false }))
    if (data.bgmConfig) Object.assign(bgmConfig, data.bgmConfig)
    if (data.scriptData) project.scriptData = data.scriptData
    if (data.currentStep !== undefined) currentStep.value = data.currentStep
    showNamingDialog.value = false

    // 恢复脚本输入
    if (data.scriptData) {
      scriptInput.value = data.scriptData.synopsis || ''
    }

    // 如果属于系列，加载系列集数列表
    if (data.seriesId) {
      try {
        const sRes = await comicSeriesApi.get(data.seriesId)
        currentSeries.value = sRes
        seriesEpisodes.value = sRes.episodes || []
      } catch { /* ignore */ }
    }
  } catch (e) {
    ElMessage.error('加载项目失败')
  }
}

async function confirmCreateProject() {
  if (!namingInput.value.trim()) return
  namingError.value = ''
  namingLoading.value = true
  try {
    const res = await comicDramaApi.create({
      name: namingInput.value.trim(),
      genre: genre.value,
    })
    projectId.value = res.id
    await loadProject(res.id)
    router.replace({ path: '/comic-drama', query: { projectId: res.id } })
  } catch (e) {
    namingError.value = e.response?.data?.message || '创建失败'
  } finally {
    namingLoading.value = false
  }
}

function cancelCreate() {
  router.push('/editor')
}

function openRenameDialog() {
  renameInput.value = project.name
  showRenameDialog.value = true
}

async function confirmRename() {
  if (!renameInput.value.trim()) return
  try {
    await comicDramaApi.update(projectId.value, { name: renameInput.value.trim() })
    project.name = renameInput.value.trim()
    showRenameDialog.value = false
    ElMessage.success('重命名成功')
  } catch (e) {
    ElMessage.error('重命名失败')
  }
}

// ==================== Debounce 自动保存 ====================
const _saveTimers = {}
function debounceSave(field, value, delay = 300) {
  if (!projectId.value) return
  if (_saveTimers[field]) clearTimeout(_saveTimers[field])
  _saveTimers[field] = setTimeout(async () => {
    try {
      await comicDramaApi.update(projectId.value, { [field]: value })
    } catch { /* auto save silently fails */ }
  }, delay)
}

// 步骤变化自动保存
watch(currentStep, (val) => debounceSave('current_step', val))

// ==================== 脚本生成 ====================
async function generateScript() {
  if (!scriptInput.value.trim()) {
    ElMessage.warning('请输入故事设定')
    return
  }
  scriptGenerating.value = true
  try {
    const res = await comicDramaApi.generateScript(projectId.value, {
      description: scriptInput.value.trim(),
      genre: genre.value,
      num_panels: scriptSizeMode.value === 'panels' ? numPanels.value : undefined,
      target_duration: scriptSizeMode.value === 'duration' ? targetDuration.value : undefined,
      characters: characters.value.length > 0 ? characters.value : undefined,
    })
    const data = res
    Object.assign(project, data)
    if (data.characters) characters.value = data.characters
    if (data.panels) panels.value = data.panels.map(p => ({ ...p, _imageLoading: false }))
    if (data.scriptData) project.scriptData = data.scriptData
    currentStep.value = 1
    ElMessage.success(`脚本生成成功，共 ${panels.value.length} 个分镜`)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '脚本生成失败')
  } finally {
    scriptGenerating.value = false
  }
}

// ==================== 角色管理 ====================
function addCharacter() {
  characters.value.push({ name: '', appearance: '', personality: '', voiceDescription: '' })
}

function removeCharacter(idx) {
  characters.value.splice(idx, 1)
}

async function saveCharacters() {
  saving.value = true
  try {
    await comicDramaApi.updateCharacters(projectId.value, characters.value)
    ElMessage.success('角色已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function uploadCharRefImage(charIdx, uploadFile) {
  if (!uploadFile?.raw) return
  const formData = new FormData()
  formData.append('file', uploadFile.raw)
  try {
    await comicDramaApi.uploadCharRefImage(projectId.value, charIdx, formData)
    await loadProject(projectId.value)
    ElMessage.success('参考图上传成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '上传失败')
  }
}

async function generateCharRefImage(charIdx) {
  characters.value[charIdx]._refLoading = true
  try {
    const res = await comicDramaApi.generateCharRefImage(projectId.value, charIdx)
    if (res.stub) {
      ElMessage.info('图片生成服务尚未就绪')
      return
    }
    await loadProject(projectId.value)
    ElMessage.success('参考图生成完成')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '生成失败')
  } finally {
    if (characters.value[charIdx]) characters.value[charIdx]._refLoading = false
  }
}

// ==================== 分镜管理 ====================
function addPanel() {
  panels.value.push({
    sequence: panels.value.length,
    sceneDescription: '',
    duration: 3.0,
    transition: 'cut',
    emotion: 'neutral',
    dialogues: [],
    generatedImagePath: null,
    generatedAudioPaths: [],
    _imageLoading: false,
  })
}

function removePanel(idx) {
  panels.value.splice(idx, 1)
  // 重新编号
  panels.value.forEach((p, i) => { p.sequence = i })
}

async function savePanels() {
  saving.value = true
  try {
    const cleanPanels = panels.value.map(({ _imageLoading, ...rest }) => rest)
    await comicDramaApi.updatePanels(projectId.value, cleanPanels)
    ElMessage.success('分镜已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function generateImage(idx) {
  panels.value[idx]._imageLoading = true
  try {
    const res = await comicDramaApi.generatePanelImage(projectId.value, {
      panel_index: idx,
      scene_description: panels.value[idx].sceneDescription,
    })
    if (res.stub) {
      ElMessage.info('图片生成服务尚未就绪，敬请期待')
      return
    }
    await loadProject(projectId.value)
    ElMessage.success(`分镜 ${idx + 1} 图片生成完成`)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '图片生成失败')
  } finally {
    panels.value[idx]._imageLoading = false
  }
}

async function generateVideo(idx) {
  if (!panels.value[idx]._videoLoading) panels.value[idx]._videoLoading = true
  try {
    await comicDramaApi.generatePanelVideo(projectId.value, {
      panel_index: idx,
      duration: panels.value[idx].duration || 3,
    })
    await loadProject(projectId.value)
    ElMessage.success(`分镜 ${idx + 1} 视频生成完成`)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '视频生成失败')
  } finally {
    if (panels.value[idx]) panels.value[idx]._videoLoading = false
  }
}

// ==================== 音频 ====================
async function generateAudio(panelIdx, text) {
  if (!text) {
    ElMessage.warning('没有可用的文本')
    return
  }
  try {
    await comicDramaApi.generatePanelAudio(projectId.value, {
      panel_index: panelIdx,
      text: text,
    })
    await loadProject(projectId.value)
    ElMessage.success('语音生成完成')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '语音生成失败')
  }
}

function getAudioPath(panelIdx, dialogueIdx) {
  const panel = panels.value[panelIdx]
  if (!panel || !panel.generatedAudioPaths) return null
  return panel.generatedAudioPaths[dialogueIdx] || null
}

// ==================== BGM ====================
async function loadBgmList() {
  try {
    const res = await projectApi.listBgm()
    bgmList.value = res.items || []
  } catch { /* ignore */ }
}

async function saveBgmConfig() {
  saving.value = true
  try {
    await comicDramaApi.updateBgmConfig(projectId.value, { ...bgmConfig })
    ElMessage.success('BGM 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// ==================== 合成 ====================
async function composeVideo() {
  const readyPanels = panels.value.filter(p => p.generatedImagePath)
  if (readyPanels.length === 0) {
    ElMessage.warning('请先生成至少一个分镜的画面图片')
    return
  }
  composing.value = true
  try {
    const res = await comicDramaApi.compose(projectId.value)
    await loadProject(projectId.value)
    currentStep.value = 5
    ElMessage.success('漫剧视频合成完成！')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '合成失败')
  } finally {
    composing.value = false
  }
}

// ==================== 系列管理 ====================
async function loadSeriesList() {
  try {
    const res = await comicSeriesApi.list()
    seriesList.value = (res.items || [])
    showSeriesList.value = true
  } catch (e) {
    ElMessage.error('加载系列列表失败')
  }
}

async function confirmCreateSeries() {
  if (!newSeriesForm.name.trim()) {
    ElMessage.warning('请输入系列名称')
    return
  }
  saving.value = true
  try {
    await comicSeriesApi.create({ ...newSeriesForm })
    showCreateSeriesDialog.value = false
    newSeriesForm.name = ''
    newSeriesForm.description = ''
    await loadSeriesList()
    ElMessage.success('系列创建成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '创建失败')
  } finally {
    saving.value = false
  }
}

async function deleteSeries(id) {
  try {
    await comicSeriesApi.remove(id)
    seriesList.value = seriesList.value.filter(s => s.id !== id)
    ElMessage.success('系列已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function openSeries(s) {
  try {
    const res = await comicSeriesApi.get(s.id)
    currentSeries.value = res
    seriesEpisodes.value = res.episodes || []
    showSeriesDetail.value = true
  } catch (e) {
    ElMessage.error('加载系列详情失败')
  }
}

async function createEpisode() {
  if (!currentSeries.value) return
  saving.value = true
  try {
    const res = await comicSeriesApi.createEpisode(currentSeries.value.id, {})
    seriesEpisodes.value.push(res)
    ElMessage.success('集数创建成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '创建失败')
  } finally {
    saving.value = false
  }
}

async function deleteEpisode(epId) {
  try {
    await comicDramaApi.remove(epId)
    seriesEpisodes.value = seriesEpisodes.value.filter(ep => ep.id !== epId)
    ElMessage.success('集数已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function openEpisode(ep) {
  showSeriesDetail.value = false
  await loadProject(ep.id)
  router.replace({ path: '/comic-drama', query: { projectId: ep.id } })
}

async function editSeriesCharacters() {
  if (!currentSeries.value) return
  seriesCharacters.value = JSON.parse(JSON.stringify(currentSeries.value.characters || []))
  showSeriesCharDialog.value = true
}

async function saveSeriesCharacters() {
  if (!currentSeries.value) return
  saving.value = true
  try {
    await comicSeriesApi.update(currentSeries.value.id, { characters: seriesCharacters.value })
    await comicSeriesApi.syncCharacters(currentSeries.value.id)
    currentSeries.value.characters = JSON.parse(JSON.stringify(seriesCharacters.value))
    showSeriesCharDialog.value = false
    ElMessage.success('角色已保存并同步到所有集数')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function backToSeriesList() {
  projectId.value = null
  panels.value = []
  characters.value = []
  project.scriptData = null
  router.replace({ path: '/comic-drama' })
  loadSeriesList()
}

async function switchToPrevEpisode() {
  const prevEp = seriesEpisodes.value.find(ep => ep.episodeNumber === (project.episodeNumber || 1) - 1)
  if (prevEp) await openEpisode(prevEp)
}

async function switchToNextEpisode() {
  const nextEp = seriesEpisodes.value.find(ep => ep.episodeNumber === (project.episodeNumber || 1) + 1)
  if (nextEp) await openEpisode(nextEp)
}
</script>

<style scoped>
.comic-drama {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 步骤导航 */
.step-nav {
  display: flex;
  gap: 0;
  background: var(--el-bg-color);
  border-radius: 10px;
  padding: 6px 0;
  overflow-x: auto;
}
.step-nav-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.2s;
  border-right: 1px solid var(--el-border-color-lighter);
}
.step-nav-item:last-child { border-right: none; }
.step-nav-item:hover { background: var(--el-fill-color-light); }
.step-nav-item.active { background: var(--el-color-primary-light-9); }
.step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.step-nav-item.active .step-circle { background: var(--el-color-primary); color: #fff; }
.step-nav-item.done .step-circle { background: var(--el-color-success); color: #fff; }
.step-text { display: flex; flex-direction: column; }
.step-title { font-size: 14px; font-weight: 500; }
.step-desc { font-size: 12px; color: var(--el-text-color-secondary); }

/* 预览卡 */
.preview-card { flex: 1; overflow: hidden; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.video-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 360px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.video-player { width: 100%; max-height: 450px; }

/* 分镜网格 */
.storyboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
  max-height: 520px;
  overflow-y: auto;
  padding: 4px;
}
.panel-card {
  border: 2px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.2s;
}
.panel-card:hover { border-color: var(--el-color-primary-light-5); }
.panel-card.active { border-color: var(--el-color-primary); }
.panel-image {
  height: 140px;
  background: var(--el-fill-color-lighter);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.panel-image img { width: 100%; height: 100%; object-fit: cover; }
.panel-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  padding: 8px;
  text-align: center;
}
.panel-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  font-size: 12px;
}
.panel-seq { font-weight: 600; }
.panel-dur { color: var(--el-text-color-secondary); }

/* 编辑面板 */
.edit-card { max-height: calc(100vh - 260px); overflow-y: auto; }

/* 角色 */
.character-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.character-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
}
.char-ref-image-area {
  display: flex; gap: 12px; align-items: flex-start;
}
.char-ref-thumb {
  width: 80px; height: 80px; object-fit: cover; border-radius: 6px; border: 1px solid var(--el-border-color-lighter);
}
.char-ref-placeholder {
  width: 80px; height: 80px; display: flex; align-items: center; justify-content: center;
  background: var(--el-fill-color-lighter); border-radius: 6px; font-size: 12px; color: var(--el-text-color-placeholder);
}
.char-ref-actions { display: flex; flex-direction: column; gap: 6px; }

/* 分镜编辑 */
.panel-edit-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.panel-edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 13px;
}
.panel-edit-actions { display: flex; gap: 4px; flex-wrap: wrap; }
.panel-video-preview { margin-top: 8px; border-radius: 6px; overflow: hidden; background: #000; }

/* 音频 */
.panel-audio-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.panel-audio-item h5 { margin: 0 0 8px 0; font-size: 13px; }
.dialogue-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.dialogue-item:last-child { border-bottom: none; }
.dialogue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.dialogue-text { font-size: 13px; color: var(--el-text-color-regular); margin: 4px 0; }

/* 合成摘要 */
.compose-summary p { margin: 6px 0; font-size: 14px; }
.empty-hint { color: var(--el-text-color-placeholder); text-align: center; padding: 20px; }

/* 脚本概览 */
.script-overview {
  margin-top: 16px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.script-overview h4 { margin: 0 0 8px 0; }
.synopsis { color: var(--el-text-color-secondary); font-size: 13px; margin: 0 0 8px 0; }
.script-stats { display: flex; gap: 16px; font-size: 12px; color: var(--el-text-color-secondary); }

/* 系列管理 */
.series-view { flex: 1; display: flex; flex-direction: column; gap: 16px; }
.series-header { display: flex; justify-content: space-between; align-items: center; }
.series-header h3 { margin: 0; }
.series-list { display: flex; flex-direction: column; gap: 12px; }
.series-card { cursor: pointer; transition: border-color 0.2s; }
.series-card:hover { border-color: var(--el-color-primary); }
.series-card-header { display: flex; justify-content: space-between; align-items: center; }
.series-name { font-weight: 600; font-size: 15px; }
.series-desc { color: var(--el-text-color-secondary); font-size: 13px; margin: 8px 0 0 0; }
.series-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; background: var(--el-bg-color); border-radius: 8px;
}
.series-bar-left, .series-bar-right { display: flex; align-items: center; gap: 8px; }
.series-bar-divider { color: var(--el-border-color); }
.series-detail { max-height: 60vh; overflow-y: auto; }
.series-info-bar { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.series-episodes-header { display: flex; justify-content: space-between; align-items: center; }
.series-episodes-header h4 { margin: 0; }
.episode-list { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.episode-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px; cursor: pointer; transition: border-color 0.2s;
}
.episode-item:hover { border-color: var(--el-color-primary); }
.episode-info { display: flex; gap: 8px; align-items: center; }
.episode-num { font-weight: 600; font-size: 13px; }
.episode-name { font-size: 13px; }
</style>

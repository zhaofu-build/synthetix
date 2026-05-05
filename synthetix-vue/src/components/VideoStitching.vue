<template>
  <div class="video-stitching">
    <!-- 新建项目命名对话框 -->
    <el-dialog
      v-model="showNamingDialog"
      title="新建工作流项目"
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

    <!-- 主内容区 -->
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
        <el-tag v-if="project.status" :type="getStatusType(project.status)" size="small">
          {{ getStatusText(project.status) }}
        </el-tag>
      </div>
    </div>

    <!-- 可点击的步骤导航 -->
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

    <el-row :gutter="20">
      <!-- 左侧：视频预览 -->
      <el-col :span="16">
        <el-card class="preview-card">
          <template #header>
            <div class="card-header">
              <span>视频预览</span>
              <el-tag v-if="project.status" :type="getStatusType(project.status)">
                {{ getStatusText(project.status) }}
              </el-tag>
            </div>
          </template>

          <div class="video-container">
            <video
              v-if="previewVideo"
              :src="previewVideo"
              controls
              class="video-player"
            />
            <div v-else class="video-placeholder">
              <el-icon :size="60"><VideoPlay /></el-icon>
              <p>预览视频</p>
            </div>
          </div>

          <!-- 时间线 -->
          <div v-if="currentPlan && currentPlan.clips && currentPlan.clips.length > 0" class="timeline-preview">
            <div class="timeline-header">
              <span>时间线预览</span>
              <span class="duration">总时长: {{ formatDuration(currentPlan.totalDuration) }}</span>
            </div>
            <div class="timeline-track">
              <div
                v-for="(clip, idx) in currentPlan.clips"
                :key="idx"
                class="timeline-clip"
                :style="getClipStyle(clip, idx)"
                @click="previewClip(clip)"
              >
                <span class="clip-name">{{ clip.materialName || `片段${idx + 1}` }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 剪辑方案 -->
        <el-card v-if="currentPlan && currentPlan.clips && currentPlan.clips.length > 0" class="plan-card">
          <template #header>
            <div class="card-header">
              <span>剪辑方案</span>
              <el-button type="primary" size="small" @click="regeneratePlan" :loading="generating">
                重新规划
              </el-button>
            </div>
          </template>

          <el-table :data="currentPlan.clips" size="small">
            <el-table-column prop="materialName" label="素材" width="150">
              <template #default="{ row }">
                <span class="clickable-text" @click="previewMaterial(row.materialId)">
                  {{ row.materialName }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="startTime" label="开始" width="80" />
            <el-table-column prop="endTime" label="结束" width="80" />
            <el-table-column prop="purpose" label="用途" />
            <el-table-column label="操作" width="100">
              <template #default="{ row, $index }">
                <el-button size="small" text @click="editClip($index)">编辑</el-button>
                <el-button size="small" text type="danger" @click="removeClip($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：各步骤面板 -->
      <el-col :span="8">
        <!-- 面板 1：素材 -->
        <el-card v-show="currentStep === 0" class="material-card">
          <template #header>
            <div class="card-header">
              <span>使用素材</span>
              <el-button type="primary" size="small" @click="openMaterialDialog">素材库</el-button>
            </div>
          </template>

          <el-table :data="selectedMaterials" height="400" size="small">
            <el-table-column prop="videoName" label="文件名">
              <template #default="{ row }">
                <span class="clickable-text" @click="previewMaterial(row.id)">
                  {{ row.videoName }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="durationHms" label="时长" width="70" />
            <el-table-column width="60">
              <template #default="{ row, $index }">
                <el-button size="small" text type="danger" @click="removeMaterial($index)">
                  移出
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 面板 2：方案配置 -->
        <el-card v-show="currentStep === 1" class="config-card">
          <template #header>
            <span>配置剪辑方案</span>
          </template>

          <el-form label-width="80px">
            <el-form-item label="文案">
              <el-input
                v-model="creative"
                type="textarea"
                :rows="4"
                placeholder="描述你想要的视频效果..."
              />
            </el-form-item>
            <el-form-item label="目标时长">
              <el-input-number v-model="targetDuration" :min="10" :max="300" :step="5" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="风格">
              <el-select v-model="style" placeholder="选择风格">
                <el-option label="动感" value="动感" />
                <el-option label="舒缓" value="舒缓" />
                <el-option label="电影感" value="电影感" />
                <el-option label="纪录片" value="纪录片" />
              </el-select>
            </el-form-item>
          </el-form>

          <div class="step-actions">
            <el-button type="primary" @click="generatePlan" :loading="generating">
              生成剪辑方案
            </el-button>
          </div>
        </el-card>

        <!-- 面板 3：文案语音 + BGM + 渲染 -->

        <!-- 文案语音卡片 -->
        <el-card v-show="currentStep === 2" class="tts-card">
          <template #header>
            <span>文案语音</span>
          </template>

          <el-form label-width="80px" size="small">
            <el-form-item label="文案">
              <el-input v-model="creative" type="textarea" :rows="3" placeholder="输入文案内容..." />
            </el-form-item>
            <el-form-item label="音色">
              <div style="display: flex; gap: 8px; width: 100%;">
                <el-select v-model="selectedSpeaker" placeholder="选择配音音色" clearable style="flex: 1;">
                  <el-option
                    v-for="item in audioOptions"
                    :key="item.id"
                    :label="item.label"
                    :value="item.id"
                  />
                </el-select>
                <el-button size="default" @click="openVoiceManager">管理</el-button>
              </div>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                @click="generateTtsAudio"
                :loading="ttsGenerating"
                :disabled="!creative || !selectedSpeaker"
              >
                生成文案音频
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 生成的音频试听 -->
          <div v-if="ttsAudioUrl" class="tts-preview">
            <audio :src="ttsAudioUrl" controls style="width: 100%; height: 36px;" />
          </div>
        </el-card>

        <!-- BGM 配置卡片 -->
        <el-card v-show="currentStep === 2" class="bgm-card" style="margin-top: 16px;">
          <template #header>
            <span>BGM 配置</span>
          </template>

          <div class="bgm-row">
            <el-select v-model="selectedBgm" placeholder="从曲库选择BGM" clearable style="flex: 1;">
              <el-option
                v-for="item in bgmList"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
            <el-button type="primary" @click="aiSelectBgm" :loading="bgmSelecting">
              AI 选曲
            </el-button>
          </div>

          <div v-if="selectedBgmUrl" class="bgm-preview">
            <audio :src="selectedBgmUrl" controls style="width: 100%; height: 36px;" />
            <div class="bgm-volume">
              <span class="volume-label">音量</span>
              <el-slider v-model="bgmVolume" :min="0" :max="1" :step="0.05" style="flex: 1;" />
              <span class="volume-value">{{ Math.round(bgmVolume * 100) }}%</span>
            </div>
          </div>

          <div class="bgm-actions">
            <el-button @click="openBgmManager">管理曲库</el-button>
          </div>
        </el-card>

        <!-- 渲染按钮 -->
        <div v-show="currentStep === 2" style="margin-top: 16px;">
          <el-button type="primary" @click="applyAndRender" :loading="rendering" style="width: 100%;">
            应用并渲染
          </el-button>
        </div>

        <!-- 面板 4：导出 -->
        <el-card v-show="currentStep === 3" class="export-card">
          <template #header>
            <span>导出完成</span>
          </template>

          <div class="export-result">
            <el-result
              icon="success"
              title="视频渲染完成"
              :sub-title="`总时长: ${formatDuration(project.duration)}`"
            >
              <template #extra>
                <el-button type="primary" @click="downloadVideo">下载视频</el-button>
                <el-button @click="resetProject">新建项目</el-button>
              </template>
            </el-result>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 素材库对话框 -->
    <el-dialog v-model="materialDialogVisible" title="素材库" width="80%">
      <el-card>
        <template #header>
          <div class="card-header">
            <el-button type="primary" size="small" @click="openKeywordDialog" :loading="getSourceing">
              AI 获取素材
            </el-button>
            <el-upload
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleVideoUpload"
            >
              <el-button type="primary" size="small">上传素材</el-button>
            </el-upload>
          </div>
        </template>

        <el-table :data="materialLibrary" height="500">
          <el-table-column prop="videoName" label="文件名">
            <template #default="{ row }">
              <span class="clickable-text" @click="previewMaterial(row.id)">
                {{ row.videoName }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="durationHms" label="时长" width="80" />
          <el-table-column prop="description" label="描述">
            <template #default="{ row }">
              <div class="description-cell">
                <span>{{ row.description || '暂无描述' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column width="180">
            <template #default="{ row }">
              <el-button size="small" @click="addToSelection(row)">使用</el-button>
              <el-button size="small" @click="analyzeMaterial(row.id)" :loading="row.analyzing">
                AI分析
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-dialog>

    <!-- 关键词输入对话框 -->
    <el-dialog v-model="keywordDialogVisible" title="AI 获取素材" width="400px">
      <el-input v-model="keywordInput" placeholder="输入素材关键词" clearable />
      <template #footer>
        <el-button @click="keywordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmKeywordDialog">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑片段对话框 -->
    <el-dialog v-model="editClipDialogVisible" title="编辑片段" width="400px">
      <el-form v-if="editingClip" label-width="80px">
        <el-form-item label="素材">
          <el-input :value="editingClip.materialName" disabled />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-input v-model="editingClip.startTime" placeholder="00:00:00" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-input v-model="editingClip.endTime" placeholder="00:00:10" />
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="editingClip.purpose" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editClipDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveClipEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 音色管理对话框 -->
    <el-dialog v-model="voiceManagerVisible" title="音色管理" width="700px">
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

    <!-- 添加/编辑音色对话框 -->
    <el-dialog v-model="voiceFormVisible" :title="voiceFormIsEdit ? '编辑音色' : '添加音色'" width="480px">
      <el-form :model="voiceForm" label-width="90px">
        <el-form-item label="音色名称" required>
          <el-input v-model="voiceForm.audio_name" placeholder="输入音色名称" />
        </el-form-item>
        <el-form-item label="参考音频">
          <!-- 编辑时回显已有音频 -->
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

    <!-- BGM 管理对话框 -->
    <el-dialog v-model="bgmManagerVisible" title="BGM 管理" width="600px">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 12px; gap: 8px;">
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="handleBgmUpload"
        >
          <el-button type="primary" size="small">上传BGM</el-button>
        </el-upload>
        <el-button size="small" @click="aiGenerateBgm" :loading="bgmGenerating">AI 生成BGM</el-button>
      </div>
      <el-table :data="bgmList" size="small" v-loading="bgmLoading">
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column label="试听">
          <template #default="{ row }">
            <audio v-if="row.webPath" :src="assetUrl(row.webPath)" controls style="height: 28px; width: 100%;" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="selectBgmFromList(row)">选用</el-button>
            <el-button size="small" text type="danger" @click="deleteBgm(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 修改项目名对话框 -->
    <el-dialog v-model="renameDialogVisible" title="修改项目名称" width="400px">
      <el-input
        ref="renameInputRef"
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
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, Check, ArrowLeft, Edit } from '@element-plus/icons-vue'
import API from './config/api'
import { assetUrl, API_HOST } from '@/api/modules'
import { projectApi } from '@/api/modules'
import { useProjectStore } from '@/store/modules/project'
import { formatDuration, getStatusType, getStatusText } from '@/utils/formatUtils'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

// 步骤定义
const steps = [
  { title: '准备素材', desc: '选择或上传' },
  { title: '配置方案', desc: 'AI 生成' },
  { title: 'BGM与渲染', desc: '确认输出' },
  { title: '导出视频', desc: '下载' }
]

// 流程状态
const currentStep = ref(0)
const projectId = ref(null)
const project = ref({ status: 'draft', duration: 0 })
const projectName = ref('未命名项目')

// 素材
const selectedMaterials = ref([])
const materialLibrary = ref([])
const materialDialogVisible = ref(false)
const keywordDialogVisible = ref(false)
const keywordInput = ref('')
const getSourceing = ref(false)

// 配置
const creative = ref('')
const targetDuration = ref(30)
const style = ref('动感')
const selectedSpeaker = ref(null)
const audioOptions = ref([])

// 方案
const currentPlan = ref({ clips: [], transitions: [], audio: {}, totalDuration: 0 })
const generating = ref(false)
const rendering = ref(false)

// TTS 文案语音
const ttsAudioUrl = ref('')
const ttsLocalPath = ref('')
const ttsGenerating = ref(false)

// 预览
const previewVideo = ref('')

// 编辑
const editClipDialogVisible = ref(false)
const editingClip = ref(null)
const editingIndex = ref(-1)

// ==================== 素材管理 ====================

const openMaterialDialog = async () => {
  materialDialogVisible.value = true
  await refreshMaterials(0)
}

const openKeywordDialog = () => {
  keywordInput.value = creative.value || ''
  keywordDialogVisible.value = true
}

const confirmKeywordDialog = async () => {
  if (!keywordInput.value.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  keywordDialogVisible.value = false
  await llmGetSource(keywordInput.value)
}

const addToSelection = (material) => {
  if (!selectedMaterials.value.find(m => m.id === material.id)) {
    selectedMaterials.value.push(material)
    ElMessage.success('已添加到使用列表')
  }
}

const removeMaterial = (index) => {
  selectedMaterials.value.splice(index, 1)
}

const refreshMaterials = async (videoType) => {
  try {
    const response = await fetch(`${API.get_source_videos}?video_type=${videoType}`)
    const result = await response.json()
    const items = result.data?.items || []
    items.forEach(item => {
      if (!materialLibrary.value.find(m => m.id === item.id)) {
        item.analyzing = false
      }
    })
    materialLibrary.value = items
  } catch (error) {
    ElMessage.error('获取素材失败')
  }
}

const handleVideoUpload = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file_stream', file.raw)
    const response = await fetch(API.upload_source_videos_stream, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('上传失败')
    await refreshMaterials(0)
    ElMessage.success('上传成功')
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const llmGetSource = async (keyword) => {
  try {
    getSourceing.value = true
    await fetch(API.llm_get_source, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ creative: keyword })
    })
    await refreshMaterials(0)
    ElMessage.success('素材获取成功')
  } catch (error) {
    ElMessage.error('获取失败')
  } finally {
    getSourceing.value = false
  }
}

const analyzeMaterial = async (id) => {
  const item = materialLibrary.value.find(m => m.id === id)
  if (!item) return
  item.analyzing = true
  try {
    const response = await fetch(`${API.get_description}/${id}/description`)
    const result = await response.json()
    if (result.data?.description) {
      item.description = result.data.description
    }
    ElMessage.success('分析完成')
  } catch (error) {
    ElMessage.error('分析失败')
  } finally {
    item.analyzing = false
  }
}

const previewMaterial = (id) => {
  const item = materialLibrary.value.find(m => m.id === id) ||
               selectedMaterials.value.find(m => m.id === id)
  if (item) {
    previewVideo.value = assetUrl(item.webPath)
  }
}

// ==================== 方案生成 ====================

const generatePlan = async () => {
  if (!creative.value) {
    ElMessage.warning('请输入文案描述')
    return
  }
  if (selectedMaterials.value.length === 0) {
    ElMessage.warning('请先选择素材')
    return
  }

  generating.value = true
  try {
    if (!projectId.value) {
      const createRes = await fetch(`${API_HOST}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: creative.value.slice(0, 20),
          description: creative.value
        })
      })
      const createData = await createRes.json()
      if (createData.success) {
        projectId.value = createData.data.id
        project.value = createData.data
      }
    }

    const response = await fetch(`${API_HOST}/api/projects/${projectId.value}/plan/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        description: creative.value,
        duration: targetDuration.value,
        style: style.value
      })
    })
    const result = await response.json()
    if (result.success) {
      currentPlan.value = result.data
      currentStep.value = 2
      ElMessage.success('方案生成成功')
    } else {
      throw new Error(result.message || '生成失败')
    }
  } catch (error) {
    ElMessage.error(`生成失败: ${error.message}`)
  } finally {
    generating.value = false
  }
}

const regeneratePlan = async () => {
  currentStep.value = 1
}

// ==================== 文案语音 ====================

const generateTtsAudio = async () => {
  if (!creative.value || !selectedSpeaker.value) {
    ElMessage.warning('请输入文案并选择音色')
    return
  }
  ttsGenerating.value = true
  try {
    const response = await fetch(`${API_HOST}/api/projects/generate-tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: creative.value,
        speaker_id: selectedSpeaker.value
      })
    })
    const result = await response.json()
    if (result.success) {
      ttsAudioUrl.value = assetUrl(result.data.webPath)
      ttsLocalPath.value = result.data.localPath
      ElMessage.success('文案音频生成成功')
    } else {
      throw new Error(result.message || '生成失败')
    }
  } catch (error) {
    ElMessage.error(`文案音频生成失败: ${error.message}`)
  } finally {
    ttsGenerating.value = false
  }
}

// ==================== 片段编辑 ====================

const editClip = (index) => {
  editingIndex.value = index
  editingClip.value = { ...currentPlan.value.clips[index] }
  editClipDialogVisible.value = true
}

const saveClipEdit = () => {
  if (editingIndex.value >= 0 && editingClip.value) {
    currentPlan.value.clips[editingIndex.value] = editingClip.value
    editClipDialogVisible.value = false
    ElMessage.success('已保存')
  }
}

const removeClip = (index) => {
  currentPlan.value.clips.splice(index, 1)
  ElMessage.success('已删除')
}

const previewClip = (clip) => {
  previewMaterial(clip.materialId)
}

// ==================== 渲染导出 ====================

const applyAndRender = async () => {
  rendering.value = true
  try {
    const applyRes = await fetch(`${API_HOST}/api/projects/${projectId.value}/plan/apply`, {
      method: 'POST'
    })
    const applyData = await applyRes.json()
    if (!applyData.success) {
      throw new Error(applyData.message || '应用失败')
    }

    // 携带音频配置（有则合成，无则跳过）
    const audioConfig = {}
    if (ttsLocalPath.value) {
      audioConfig.tts_path = ttsLocalPath.value
    }
    if (selectedBgm.value) {
      audioConfig.bgm_id = selectedBgm.value
      audioConfig.bgm_volume = bgmVolume.value
    }

    const renderRes = await fetch(`${API_HOST}/api/projects/${projectId.value}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(audioConfig)
    })
    const renderData = await renderRes.json()
    if (renderData.success) {
      project.value.status = 'completed'
      project.value.duration = renderData.data.duration || currentPlan.value.totalDuration
      previewVideo.value = assetUrl(renderData.data.webPath)
      currentStep.value = 3
      ElMessage.success('渲染完成')
    } else {
      throw new Error(renderData.message || '渲染失败')
    }
  } catch (error) {
    ElMessage.error(`渲染失败: ${error.message}`)
  } finally {
    rendering.value = false
  }
}

const downloadVideo = () => {
  if (previewVideo.value) {
    window.open(previewVideo.value, '_blank')
  }
}

const resetProject = () => {
  router.push('/editor')
}

// ==================== 工具函数 ====================

const getClipStyle = (clip, index) => {
  const totalWidth = 100
  const totalDuration = currentPlan.value.totalDuration || 1
  const clipDuration = parseFloat(clip.endTime?.split(':').reduce((acc, t) => acc * 60 + parseFloat(t), 0) || 5)
  const width = (clipDuration / totalDuration) * totalWidth
  return {
    width: `${Math.max(width, 5)}%`,
    backgroundColor: `hsl(${index * 60}, 70%, 60%)`
  }
}

// ==================== 音色管理 ====================

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

const openVoiceManager = async () => {
  voiceManagerVisible.value = true
  await loadVoiceList()
}

const loadVoiceList = async () => {
  voiceLoading.value = true
  try {
    const response = await fetch(`${API.get_source_audio}?page_size=100`)
    const result = await response.json()
    voiceList.value = result.data?.items || []
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
      const params = new URLSearchParams()
      params.append('audio_name', form.audio_name)
      params.append('prompt_text', form.prompt_text)
      const response = await fetch(`${API.del_source_audio}/${form.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
      })
      const result = await response.json()
      if (!result.success) throw new Error(result.message || '更新失败')
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
      const response = await fetch(API.save_timbre, {
        method: 'POST',
        body: formData
      })
      if (!response.ok) throw new Error('添加失败')
      ElMessage.success('音色添加成功')
    }
    voiceFormVisible.value = false
    await loadVoiceList()
    await refreshAudioList()
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
    const response = await fetch(`${API.del_source_audio}/${id}`, { method: 'DELETE' })
    const result = await response.json()
    if (!result.success) throw new Error(result.message || '删除失败')
    ElMessage.success('已删除')
    await loadVoiceList()
    await refreshAudioList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// ==================== BGM 管理 ====================

const bgmList = ref([])
const bgmLoading = ref(false)
const bgmManagerVisible = ref(false)
const selectedBgm = ref(null)
const selectedBgmUrl = ref('')
const bgmVolume = ref(0.3)
const bgmSelecting = ref(false)
const bgmGenerating = ref(false)

const loadBgmList = async () => {
  bgmLoading.value = true
  try {
    const response = await fetch(`${API_HOST}/api/projects/bgm`)
    const result = await response.json()
    bgmList.value = result.data?.items || result.data || []
  } catch (error) {
    console.error('获取BGM列表失败:', error)
    bgmList.value = []
  } finally {
    bgmLoading.value = false
  }
}

const openBgmManager = async () => {
  bgmManagerVisible.value = true
  await loadBgmList()
}

const selectBgmFromList = (row) => {
  selectedBgm.value = row.id
  selectedBgmUrl.value = assetUrl(row.webPath)
  bgmManagerVisible.value = false
  ElMessage.success(`已选用: ${row.name}`)
}

const handleBgmUpload = async (file) => {
  const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/ogg']
  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('不支持的音频格式')
    return
  }
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    formData.append('name', file.name.replace(/\.[^.]+$/, ''))
    const response = await fetch(`${API_HOST}/api/projects/bgm`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('上传失败')
    ElMessage.success('BGM上传成功')
    await loadBgmList()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const deleteBgm = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该BGM？', '提示', { type: 'warning' })
    await fetch(`${API_HOST}/api/projects/bgm/${id}`, { method: 'DELETE' })
    ElMessage.success('已删除')
    await loadBgmList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const aiSelectBgm = async () => {
  if (!creative.value) {
    ElMessage.warning('请先输入文案描述')
    return
  }
  bgmSelecting.value = true
  try {
    const response = await fetch(`${API_HOST}/api/projects/bgm/ai-select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: creative.value, style: style.value })
    })
    const result = await response.json()
    if (result.success && result.data) {
      selectedBgm.value = result.data.id
      selectedBgmUrl.value = assetUrl(result.data.webPath)
      ElMessage.success(`AI推荐: ${result.data.name}`)
    } else {
      ElMessage.info('暂无合适的BGM，请手动上传或AI生成')
    }
  } catch (error) {
    ElMessage.error('AI选曲失败')
  } finally {
    bgmSelecting.value = false
  }
}

const aiGenerateBgm = async () => {
  if (!creative.value) {
    ElMessage.warning('请先输入文案描述')
    return
  }
  bgmGenerating.value = true
  try {
    const response = await fetch(`${API_HOST}/api/projects/bgm/ai-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: creative.value, style: style.value, duration: targetDuration.value })
    })
    const result = await response.json()
    if (result.success && result.data) {
      selectedBgm.value = result.data.id
      selectedBgmUrl.value = assetUrl(result.data.webPath)
      ElMessage.success('BGM生成成功')
      await loadBgmList()
    } else {
      throw new Error(result.message || '生成失败')
    }
  } catch (error) {
    ElMessage.error(error.message || 'AI生成BGM失败')
  } finally {
    bgmGenerating.value = false
  }
}

// 加载音色列表
const refreshAudioList = async () => {
  try {
    const response = await fetch(API.get_source_audio)
    const result = await response.json()
    const items = result.data?.items || []
    audioOptions.value = items.map(item => ({
      id: item.id,
      label: item.audioName
    }))
  } catch (error) {
    console.error('获取音色失败:', error)
  }
}

// ==================== 项目加载与自动保存 ====================

const goBack = () => {
  router.push('/editor')
}

// ---- 新建项目命名 ----
const showNamingDialog = ref(false)
const namingInput = ref('')
const namingError = ref('')
const namingLoading = ref(false)
const namingInputRef = ref(null)
const projectReady = ref(false) // 项目是否已就绪

// ---- 修改项目名 ----
const renameDialogVisible = ref(false)
const renameInput = ref('')
const renameError = ref('')
const renameLoading = ref(false)

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

const cancelCreate = () => {
  router.push('/editor')
}

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
      mode: 'workflow'
    })
    projectId.value = data.id
    projectName.value = data.name
    projectReady.value = true
    showNamingDialog.value = false
    router.replace({ path: '/video-stitching', query: { projectId: data.id } })
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

const loadProjectData = async (id) => {
  try {
    const data = await projectApi.getFull(id)
    projectId.value = data.id
    projectName.value = data.name || '未命名项目'
    projectReady.value = true
    project.value = { status: data.status || 'draft', duration: data.duration || 0 }
    currentStep.value = data.currentStep ?? 0
    creative.value = data.creative || ''
    targetDuration.value = data.targetDuration ?? 30
    style.value = data.style || '动感'
    selectedSpeaker.value = data.speakerId ?? null
    selectedBgm.value = data.bgmId ?? null
    bgmVolume.value = data.bgmVolume ?? 0.3
    ttsLocalPath.value = data.ttsPath || ''
    if (data.ttsPath) {
      ttsAudioUrl.value = assetUrl(data.ttsPath)
    }
    if (data.bgm) {
      selectedBgmUrl.value = assetUrl(data.bgm.webPath)
    }
    if (data.planData) {
      currentPlan.value = data.planData
    }
    if (data.outputPath) {
      previewVideo.value = assetUrl(data.outputPath)
    }
    // 加载关联素材
    if (data.materials && data.materials.length > 0) {
      selectedMaterials.value = data.materials.map(m => ({
        id: m.id,
        videoName: m.videoName,
        webPath: m.webPath,
        durationHms: m.durationHms,
        duration: m.duration,
        description: m.description
      }))
    }
  } catch (error) {
    ElMessage.error('加载项目失败')
  }
}

const ensureProject = async () => {
  if (projectId.value) return
  // 新项目：弹出命名对话框
  showNamingDialog.value = true
  await nextTick()
  if (namingInputRef.value) {
    namingInputRef.value.focus()
  }
}

// 防抖保存（每个字段独立 timer）
const _saveTimers = {}
const debounceSave = (field, value) => {
  if (!projectId.value) return
  if (_saveTimers[field]) clearTimeout(_saveTimers[field])
  _saveTimers[field] = setTimeout(() => {
    projectApi.update(projectId.value, { [field]: value }).catch(() => {})
  }, 300)
}

// 监听变化自动保存
watch(selectedMaterials, (val) => {
  debounceSave('material_ids', val.map(m => m.id))
}, { deep: true })

watch(creative, (val) => debounceSave('creative', val))
watch(targetDuration, (val) => debounceSave('target_duration', val))
watch(style, (val) => debounceSave('style', val))
watch(selectedSpeaker, (val) => debounceSave('speaker_id', val))
watch(ttsLocalPath, (val) => debounceSave('tts_path', val))
watch(selectedBgm, (val) => debounceSave('bgm_id', val))
watch(bgmVolume, (val) => debounceSave('bgm_volume', val))
watch(currentStep, (val) => debounceSave('current_step', val))

onMounted(async () => {
  refreshMaterials(1)
  refreshAudioList()

  // 从URL加载已有项目
  const pid = route.query.projectId
  if (pid) {
    await loadProjectData(parseInt(pid))
    // loadProjectData 会设置 projectReady = true
  } else {
    // 新项目：弹出命名对话框，用户必须先命名
    showNamingDialog.value = true
    await nextTick()
    if (namingInputRef.value) {
      namingInputRef.value.focus()
    }
  }
})
</script>

<style scoped src="@/styles/components/video-stitching.css"></style>

<style scoped>
.video-stitching {
  padding: 20px;
}

/* 项目头部 */
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

.project-name-input {
  width: 200px;
}

.project-name-input :deep(.el-input__inner) {
  font-size: 16px;
  font-weight: 500;
}

.save-indicator {
  font-size: 12px;
  color: #909399;
}

/* 步骤导航条 */
.step-nav {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  background: var(--el-bg-color-overlay, #1d1e1f);
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid var(--el-border-color-lighter, #4c4d4f);
}

.step-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 6px;
  transition: background 0.2s;
}

.step-nav-item:hover {
  background: var(--el-fill-color-light, #262727);
}

.step-nav-item.active {
  background: var(--el-color-primary-dark-2, #337ecc);
}

.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  background: var(--el-fill-color, #303133);
  color: var(--el-text-color-secondary, #a8abb2);
  transition: all 0.2s;
}

.step-nav-item.active .step-circle {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.step-nav-item.done .step-circle {
  background: var(--el-color-success, #67c23a);
  color: #fff;
}

.step-text {
  display: flex;
  flex-direction: column;
}

.step-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary, #e5eaf3);
}

.step-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary, #a8abb2);
}

.step-nav-item.active .step-title {
  color: #fff;
}

.step-nav-item.active .step-desc {
  color: rgba(255, 255, 255, 0.7);
}

/* 分隔线 */
.step-nav-item + .step-nav-item {
  padding-left: 20px;
  position: relative;
}

.step-nav-item + .step-nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 1px;
  height: 24px;
  transform: translateY(-50%);
  background: var(--el-border-color, #4c4d4f);
}

.step-nav-item.active + .step-nav-item::before,
.step-nav-item + .step-nav-item.active::before {
  background: transparent;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-card, .plan-card, .material-card, .config-card, .render-card, .export-card {
  margin-bottom: 20px;
}

.video-container {
  width: 100%;
  position: relative;
  padding-top: 56.25%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video-player {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.timeline-preview {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid var(--el-border-color-lighter, #e4e7ed);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.duration {
  color: #909399;
}

.timeline-track {
  display: flex;
  height: 40px;
  background: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
}

.timeline-clip {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.timeline-clip:hover {
  opacity: 0.8;
}

.clip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 5px;
}

.step-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.clickable-text {
  color: #409eff;
  cursor: pointer;
}

.clickable-text:hover {
  text-decoration: underline;
}

.unit {
  margin-left: 5px;
  color: #909399;
}

/* BGM */
.bgm-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.bgm-preview {
  margin-top: 16px;
  padding: 12px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 8px;
}

.bgm-volume {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.volume-label {
  font-size: 13px;
  white-space: nowrap;
}

.volume-value {
  font-size: 12px;
  color: #909399;
  min-width: 36px;
  text-align: right;
}

.bgm-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.tts-preview {
  margin-top: 12px;
  padding: 10px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 8px;
}
</style>

<template>
  <div class="video-analysis">
    <!-- 素材选择 -->
    <div class="section">
      <h4>选择视频素材</h4>
      <el-select v-model="form.videoId" placeholder="选择视频" filterable style="width: 100%">
        <el-option v-for="v in videos" :key="v.id" :label="`${v.id}: ${v.name || v.fileName}`" :value="v.id" />
      </el-select>
    </div>

    <!-- 分析类型 -->
    <div class="section">
      <h4>选择分析类型</h4>
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 视频分析 -->
        <el-tab-pane label="视频分析" name="analyze">
          <p class="hint">AI 分析视频内容，返回场景、对象、动作等信息</p>
        </el-tab-pane>

        <!-- 转录分析 -->
        <el-tab-pane label="转录分析" name="analyze_transcript">
          <el-form label-width="80px">
            <el-form-item label="分析维度">
              <el-select v-model="form.transcriptMode" style="width: 100%">
                <el-option label="高光片段" value="highlights" />
                <el-option label="主题边界" value="topics" />
                <el-option label="情感峰值" value="emotion" />
                <el-option label="综合分析" value="all" />
              </el-select>
            </el-form-item>
          </el-form>
          <p class="hint">基于字幕/转录文本分析内容，比 VL 快 10 倍</p>
        </el-tab-pane>

        <!-- 质量检测 -->
        <el-tab-pane label="质量检测" name="quality_check">
          <el-form label-width="80px">
            <el-form-item label="检测项">
              <el-checkbox-group v-model="form.checkItems">
                <el-checkbox value="black_frame">黑屏</el-checkbox>
                <el-checkbox value="silence">静音</el-checkbox>
                <el-checkbox value="jump_cut">跳切</el-checkbox>
                <el-checkbox value="duration">时长合规</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 静音检测 -->
        <el-tab-pane label="静音检测" name="detect_silence">
          <el-form label-width="80px">
            <el-form-item label="静音阈值">
              <el-input-number v-model="form.silenceThreshold" :min="-80" :max="0" :step="5" />
              <span class="unit">dB</span>
            </el-form-item>
            <el-form-item label="最短时长">
              <el-input-number v-model="form.silenceMinDuration" :min="0.1" :max="60" :step="0.5" />
              <span class="unit">秒</span>
            </el-form-item>
          </el-form>
          <p class="hint">检测视频中的静音段，返回静音开始/结束时间</p>
        </el-tab-pane>

        <!-- 场景切换 -->
        <el-tab-pane label="场景切换" name="detect_scene">
          <p class="hint">检测视频中的场景切换点，返回切换时间列表</p>
        </el-tab-pane>

        <!-- 说话人分离 -->
        <el-tab-pane label="说话人分离" name="diarize">
          <el-form label-width="80px">
            <el-form-item label="说话人数">
              <el-input-number v-model="form.numSpeakers" :min="0" :max="10" />
              <span class="unit">（0 = 自动检测）</span>
            </el-form-item>
          </el-form>
          <p class="hint">分离不同说话人，返回每段的说话人 ID 和时间范围</p>
        </el-tab-pane>

        <!-- 元数据生成 -->
        <el-tab-pane label="元数据生成" name="metadata">
          <p class="hint">AI 生成标题、标签、描述、推荐封面帧等平台发布元数据</p>
        </el-tab-pane>

        <!-- 关键帧提取 -->
        <el-tab-pane label="关键帧提取" name="keyframes">
          <el-form label-width="80px">
            <el-form-item label="提取模式">
              <el-select v-model="form.keyframeMode" style="width: 100%">
                <el-option label="固定间隔" value="interval" />
                <el-option label="场景切换" value="scene" />
                <el-option label="智能混合" value="smart" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="form.keyframeMode === 'interval'" label="间隔">
              <el-input-number v-model="form.keyframeInterval" :min="1" :max="60" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="最大帧数">
              <el-input-number v-model="form.maxKeyframes" :min="1" :max="100" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 执行 -->
    <div class="section" style="text-align: center; margin-top: 16px">
      <el-button type="primary" :loading="loading" :disabled="!form.videoId" @click="execute">
        {{ loading ? '分析中...' : '开始分析' }}
      </el-button>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="section result-section">
      <el-alert :title="result.success !== false ? '分析完成' : '分析失败'" :type="result.success !== false ? 'success' : 'error'" show-icon :closable="false" />
      <div v-if="result.success !== false" class="result-detail">
        <pre class="result-json">{{ formatResult(result) }}</pre>
        <el-button size="small" style="margin-top: 8px" @click="copyResult">复制结果</el-button>
      </div>
      <div v-if="result.success === false && result.error" class="result-detail">
        <p style="color: #f56c6c">{{ result.error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { post, get } from '@/utils/request'
import { API_HOST } from '@/utils/request'

const videos = ref([])
const loading = ref(false)
const result = ref(null)
const activeTab = ref('analyze')

const form = reactive({
  videoId: null,
  transcriptMode: 'all',
  checkItems: ['black_frame', 'silence', 'jump_cut', 'duration'],
  silenceThreshold: -30,
  silenceMinDuration: 1.0,
  numSpeakers: 0,
  keyframeMode: 'smart',
  keyframeInterval: 5,
  maxKeyframes: 30,
})

const tabToolMap = {
  analyze: 'analyze_video',
  analyze_transcript: 'analyze_transcript',
  quality_check: 'quality_check',
  detect_silence: 'detect_silence',
  detect_scene: 'detect_scene_change',
  diarize: 'diarize_speakers',
  metadata: 'generate_metadata',
  keyframes: 'extract_keyframes',
}

function getParams() {
  const base = { video_id: form.videoId }
  switch (activeTab.value) {
    case 'analyze_transcript': return { ...base, mode: form.transcriptMode }
    case 'quality_check': return { ...base, checks: form.checkItems }
    case 'detect_silence': return { ...base, threshold: form.silenceThreshold, min_duration: form.silenceMinDuration }
    case 'diarize': return { ...base, num_speakers: form.numSpeakers }
    case 'keyframes': return { ...base, mode: form.keyframeMode, interval: form.keyframeInterval, max_frames: form.maxKeyframes }
    default: return base
  }
}

function formatResult(data) {
  if (typeof data === 'string') return data
  try { return JSON.stringify(data, null, 2) } catch { return String(data) }
}

async function execute() {
  if (!form.videoId) { ElMessage.warning('请先选择视频'); return }
  loading.value = true
  result.value = null
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, {
      tool: tabToolMap[activeTab.value],
      params: getParams(),
    })
    result.value = data
    ElMessage.success('分析完成')
  } catch (e) {
    result.value = { success: false, error: e.message }
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function copyResult() {
  navigator.clipboard.writeText(formatResult(result.value))
  ElMessage.success('已复制')
}

onMounted(async () => {
  try {
    const data = await get(`${API_HOST}/api/videos`, { page: 1, page_size: 200 })
    videos.value = data.items || data || []
  } catch { videos.value = [] }
})
</script>

<style scoped>
.video-analysis { padding: 8px 0; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; color: #606266; }
.unit { margin-left: 8px; color: #909399; font-size: 12px; }
.hint { color: #909399; font-size: 12px; margin: 8px 0 0; }
.result-section { margin-top: 12px; }
.result-detail { margin-top: 8px; }
.result-json {
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

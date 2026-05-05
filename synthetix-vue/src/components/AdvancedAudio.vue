<template>
  <div class="advanced-audio">
    <!-- 素材选择 -->
    <div class="section">
      <h4>选择音频素材</h4>
      <el-select v-model="form.videoId" placeholder="选择含音频的视频或音频素材" filterable style="width: 100%">
        <el-option v-for="v in videos" :key="v.id" :label="`${v.id}: ${v.name || v.fileName}`" :value="v.id" />
      </el-select>
    </div>

    <!-- 音频效果 -->
    <div class="section">
      <h4>选择处理类型</h4>
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 标准化 -->
        <el-tab-pane label="标准化" name="normalize">
          <el-form label-width="80px">
            <el-form-item label="目标响度">
              <el-input-number v-model="form.targetLoudness" :min="-30" :max="0" :step="1" />
              <span class="unit">LUFS</span>
            </el-form-item>
          </el-form>
          <p class="hint">统一音量到目标响度，适合多段素材拼接前处理</p>
        </el-tab-pane>

        <!-- 均衡器 -->
        <el-tab-pane label="均衡器" name="equalize">
          <el-form label-width="80px">
            <el-form-item label="低频增益">
              <el-slider v-model="form.lowGain" :min="-12" :max="12" :step="1" show-input />
            </el-form-item>
            <el-form-item label="中频增益">
              <el-slider v-model="form.midGain" :min="-12" :max="12" :step="1" show-input />
            </el-form-item>
            <el-form-item label="高频增益">
              <el-slider v-model="form.highGain" :min="-12" :max="12" :step="1" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 淡入淡出 -->
        <el-tab-pane label="淡入淡出" name="fade">
          <el-form label-width="80px">
            <el-form-item label="淡入时长">
              <el-input-number v-model="form.audioFadeIn" :min="0" :max="30" :step="0.5" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="淡出时长">
              <el-input-number v-model="form.audioFadeOut" :min="0" :max="30" :step="0.5" />
              <span class="unit">秒</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 回声/混响 -->
        <el-tab-pane label="回声混响" name="echo">
          <el-form label-width="80px">
            <el-form-item label="回声强度">
              <el-slider v-model="form.echoGain" :min="0" :max="1" :step="0.05" show-input />
            </el-form-item>
            <el-form-item label="延迟时间">
              <el-input-number v-model="form.echoDelay" :min="10" :max="1000" :step="10" />
              <span class="unit">ms</span>
            </el-form-item>
            <el-form-item label="衰减系数">
              <el-slider v-model="form.echoDecay" :min="0" :max="1" :step="0.05" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 降噪 -->
        <el-tab-pane label="降噪" name="denoise">
          <el-form label-width="80px">
            <el-form-item label="降噪强度">
              <el-slider v-model="form.denoiseStrength" :min="1" :max="50" :step="1" show-input />
            </el-form-item>
          </el-form>
          <p class="hint">自动降低背景噪音，强度越高降噪越激进</p>
        </el-tab-pane>

        <!-- 变调 -->
        <el-tab-pane label="变调" name="pitch">
          <el-form label-width="80px">
            <el-form-item label="音高变化">
              <el-slider v-model="form.pitchSemitones" :min="-12" :max="12" :step="1" show-input />
              <span class="unit">半音</span>
            </el-form-item>
          </el-form>
          <p class="hint">改变音高而不改变速度，正值升高，负值降低</p>
        </el-tab-pane>

        <!-- 倒放 -->
        <el-tab-pane label="倒放" name="reverse">
          <p class="hint">将音频倒序播放（仅反转音频，画面不变）</p>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 执行 -->
    <div class="section" style="text-align: center; margin-top: 16px">
      <el-button type="primary" :loading="loading" :disabled="!form.videoId" @click="execute">
        {{ loading ? '处理中...' : '应用' }}
      </el-button>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="section result-section">
      <el-alert :title="result.success !== false ? '处理成功' : '处理失败'" :type="result.success !== false ? 'success' : 'error'" show-icon :closable="false" />
      <div v-if="result.success !== false && result.output_path" class="result-detail">
        <p>输出文件: {{ result.output_path }}</p>
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
const activeTab = ref('normalize')

const form = reactive({
  videoId: null,
  targetLoudness: -16,
  lowGain: 0,
  midGain: 0,
  highGain: 0,
  audioFadeIn: 2,
  audioFadeOut: 2,
  echoGain: 0.5,
  echoDelay: 100,
  echoDecay: 0.5,
  denoiseStrength: 10,
  pitchSemitones: 0,
})

const tabToolMap = {
  normalize: 'normalize_audio',
  equalize: 'equalize_audio',
  fade: 'fade_audio',
  echo: 'add_echo',
  denoise: 'denoise_audio',
  pitch: 'pitch_shift',
  reverse: 'reverse_audio',
}

function getParams() {
  const base = { video_id: form.videoId }
  switch (activeTab.value) {
    case 'normalize': return { ...base, target_loudness: form.targetLoudness }
    case 'equalize': return { ...base, low_gain: form.lowGain, mid_gain: form.midGain, high_gain: form.highGain }
    case 'fade': return { ...base, fade_in: form.audioFadeIn, fade_out: form.audioFadeOut }
    case 'echo': return { ...base, gain: form.echoGain, delay: form.echoDelay, decay: form.echoDecay }
    case 'denoise': return { ...base, strength: form.denoiseStrength }
    case 'pitch': return { ...base, semitones: form.pitchSemitones }
    case 'reverse': return base
    default: return base
  }
}

async function execute() {
  if (!form.videoId) { ElMessage.warning('请先选择素材'); return }
  loading.value = true
  result.value = null
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, {
      tool: tabToolMap[activeTab.value],
      params: getParams(),
    })
    result.value = data
    ElMessage.success('处理完成')
  } catch (e) {
    result.value = { success: false, error: e.message }
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const data = await get(`${API_HOST}/api/videos`, { page: 1, page_size: 200 })
    videos.value = data.items || data || []
  } catch { videos.value = [] }
})
</script>

<style scoped>
.advanced-audio { padding: 8px 0; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; color: #606266; }
.unit { margin-left: 8px; color: #909399; font-size: 12px; }
.hint { color: #909399; font-size: 12px; margin: 8px 0 0; }
.result-section { margin-top: 12px; }
.result-detail { margin-top: 8px; font-size: 13px; }
</style>

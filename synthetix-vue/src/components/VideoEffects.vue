<template>
  <div class="video-effects">
    <!-- 素材选择 -->
    <div class="section">
      <h4>选择视频素材</h4>
      <el-select v-model="form.videoId" placeholder="选择视频" filterable style="width: 100%" @change="onVideoChange">
        <el-option v-for="v in videos" :key="v.id" :label="`${v.id}: ${v.name || v.fileName}`" :value="v.id" />
      </el-select>
      <div v-if="selectedVideo" class="video-info">
        <span>{{ selectedVideo.fileName }}</span>
        <span v-if="selectedVideo.duration">({{ selectedVideo.duration }}s)</span>
      </div>
    </div>

    <!-- 效果类型选择 -->
    <div class="section">
      <h4>选择效果</h4>
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 亮度/对比度/饱和度 -->
        <el-tab-pane label="亮度对比度" name="brightness">
          <el-form label-width="80px">
            <el-form-item label="亮度">
              <el-slider v-model="form.brightness" :min="-1" :max="1" :step="0.1" show-input />
            </el-form-item>
            <el-form-item label="对比度">
              <el-slider v-model="form.contrast" :min="0.1" :max="10" :step="0.1" show-input />
            </el-form-item>
            <el-form-item label="饱和度">
              <el-slider v-model="form.saturation" :min="0" :max="3" :step="0.1" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 模糊/锐化 -->
        <el-tab-pane label="模糊锐化" name="blur_sharpen">
          <el-radio-group v-model="form.effectSubType" style="margin-bottom: 12px">
            <el-radio-button value="blur">模糊</el-radio-button>
            <el-radio-button value="sharpen">锐化</el-radio-button>
          </el-radio-group>
          <template v-if="form.effectSubType === 'blur'">
            <el-form label-width="80px">
              <el-form-item label="模糊强度">
                <el-slider v-model="form.sigma" :min="0.1" :max="20" :step="0.5" show-input />
              </el-form-item>
            </el-form>
          </template>
          <template v-else>
            <el-form label-width="80px">
              <el-form-item label="锐化强度">
                <el-slider v-model="form.sharpenAmount" :min="0" :max="5" :step="0.5" show-input />
              </el-form-item>
            </el-form>
          </template>
        </el-tab-pane>

        <!-- 旋转/翻转 -->
        <el-tab-pane label="旋转翻转" name="rotate_flip">
          <el-radio-group v-model="form.effectSubType" style="margin-bottom: 12px">
            <el-radio-button value="rotate">旋转</el-radio-button>
            <el-radio-button value="flip">翻转</el-radio-button>
          </el-radio-group>
          <template v-if="form.effectSubType === 'rotate'">
            <el-radio-group v-model="form.angle">
              <el-radio-button :value="90">90°</el-radio-button>
              <el-radio-button :value="180">180°</el-radio-button>
              <el-radio-button :value="270">270°</el-radio-button>
            </el-radio-group>
          </template>
          <template v-else>
            <el-radio-group v-model="form.flipDirection">
              <el-radio-button value="horizontal">水平翻转</el-radio-button>
              <el-radio-button value="vertical">垂直翻转</el-radio-button>
            </el-radio-group>
          </template>
        </el-tab-pane>

        <!-- 裁剪 -->
        <el-tab-pane label="裁剪" name="crop">
          <el-form label-width="80px">
            <el-form-item label="宽度">
              <el-input-number v-model="form.cropW" :min="1" />
            </el-form-item>
            <el-form-item label="高度">
              <el-input-number v-model="form.cropH" :min="1" />
            </el-form-item>
            <el-form-item label="X 偏移">
              <el-input-number v-model="form.cropX" :min="0" />
            </el-form-item>
            <el-form-item label="Y 偏移">
              <el-input-number v-model="form.cropY" :min="0" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 淡入淡出 -->
        <el-tab-pane label="淡入淡出" name="fade">
          <el-form label-width="80px">
            <el-form-item label="淡入时长">
              <el-input-number v-model="form.fadeIn" :min="0" :max="30" :step="0.5" /> 秒
            </el-form-item>
            <el-form-item label="淡出时长">
              <el-input-number v-model="form.fadeOut" :min="0" :max="30" :step="0.5" /> 秒
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 色彩调整 -->
        <el-tab-pane label="色彩调整" name="color">
          <el-form label-width="80px">
            <el-form-item label="色相">
              <el-slider v-model="form.hue" :min="0" :max="360" :step="1" show-input />
            </el-form-item>
            <el-form-item label="亮度">
              <el-slider v-model="form.colorBrightness" :min="-10" :max="10" :step="0.5" show-input />
            </el-form-item>
            <el-form-item label="对比度">
              <el-slider v-model="form.colorContrast" :min="-1000" :max="1000" :step="10" show-input />
            </el-form-item>
            <el-form-item label="饱和度">
              <el-slider v-model="form.colorSaturation" :min="-1000" :max="1000" :step="10" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 文字叠加 -->
        <el-tab-pane label="文字叠加" name="text_overlay">
          <el-form label-width="80px">
            <el-form-item label="文字内容">
              <el-input v-model="form.text" placeholder="输入叠加文字" />
            </el-form-item>
            <el-form-item label="字体大小">
              <el-input-number v-model="form.fontSize" :min="10" :max="200" />
            </el-form-item>
            <el-form-item label="字体颜色">
              <el-color-picker v-model="form.fontColor" />
            </el-form-item>
            <el-form-item label="X 位置">
              <el-input-number v-model="form.textX" :min="0" />
            </el-form-item>
            <el-form-item label="Y 位置">
              <el-input-number v-model="form.textY" :min="0" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 水印 -->
        <el-tab-pane label="水印" name="watermark">
          <el-form label-width="80px">
            <el-form-item label="水印图片">
              <el-upload :auto-upload="false" :limit="1" accept="image/*" :on-change="onWatermarkChange">
                <el-button>选择图片</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item label="位置">
              <el-select v-model="form.watermarkPosition">
                <el-option label="左上" value="top-left" />
                <el-option label="右上" value="top-right" />
                <el-option label="左下" value="bottom-left" />
                <el-option label="右下" value="bottom-right" />
                <el-option label="居中" value="center" />
              </el-select>
            </el-form-item>
            <el-form-item label="透明度">
              <el-slider v-model="form.watermarkOpacity" :min="0" :max="1" :step="0.05" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 特殊效果 -->
        <el-tab-pane label="特殊效果" name="special">
          <el-radio-group v-model="form.effectSubType" style="margin-bottom: 12px">
            <el-radio-button value="reverse">视频倒放</el-radio-button>
            <el-radio-button value="stabilize">视频防抖</el-radio-button>
            <el-radio-button value="slowmo">慢动作</el-radio-button>
            <el-radio-button value="pip">画中画</el-radio-button>
          </el-radio-group>
          <template v-if="form.effectSubType === 'slowmo'">
            <el-form label-width="80px">
              <el-form-item label="慢放倍数">
                <el-slider v-model="form.slowmoFactor" :min="0.1" :max="0.9" :step="0.1" show-input />
              </el-form-item>
            </el-form>
          </template>
          <template v-if="form.effectSubType === 'pip'">
            <el-form label-width="80px">
              <el-form-item label="叠加视频">
                <el-select v-model="form.pipVideoId" placeholder="选择叠加视频" filterable>
                  <el-option v-for="v in videos" :key="v.id" :label="`${v.id}: ${v.name || v.fileName}`" :value="v.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="位置">
                <el-select v-model="form.pipPosition">
                  <el-option label="左上" value="top-left" />
                  <el-option label="右上" value="top-right" />
                  <el-option label="左下" value="bottom-left" />
                  <el-option label="右下" value="bottom-right" />
                </el-select>
              </el-form-item>
              <el-form-item label="小窗比例">
                <el-slider v-model="form.pipScale" :min="0.1" :max="0.5" :step="0.05" show-input />
              </el-form-item>
            </el-form>
          </template>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 执行按钮 -->
    <div class="section" style="text-align: center; margin-top: 16px">
      <el-button type="primary" :loading="loading" :disabled="!form.videoId" @click="execute">
        {{ loading ? '处理中...' : '应用效果' }}
      </el-button>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="section result-section">
      <el-alert :title="result.success ? '处理成功' : '处理失败'" :type="result.success ? 'success' : 'error'" show-icon :closable="false" />
      <div v-if="result.success && result.output_path" class="result-detail">
        <p>输出文件: {{ result.output_path }}</p>
        <el-button type="primary" size="small" @click="openFolder">打开所在文件夹</el-button>
      </div>
      <div v-if="!result.success && result.error" class="result-detail">
        <p style="color: #f56c6c">{{ result.error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { post, get } from '@/utils/request'
import { API_HOST } from '@/utils/request'

const videos = ref([])
const loading = ref(false)
const result = ref(null)
const activeTab = ref('brightness')

const selectedVideo = computed(() => videos.value.find(v => v.id === form.videoId))

const form = reactive({
  videoId: null,
  // brightness
  brightness: 0,
  contrast: 1.0,
  saturation: 1.0,
  // blur/sharpen
  effectSubType: 'blur',
  sigma: 2.0,
  sharpenAmount: 1.5,
  // rotate/flip
  angle: 90,
  flipDirection: 'horizontal',
  // crop
  cropW: 1920,
  cropH: 1080,
  cropX: 0,
  cropY: 0,
  // fade
  fadeIn: 2.0,
  fadeOut: 2.0,
  // color
  hue: 0,
  colorBrightness: 0,
  colorContrast: 0,
  colorSaturation: 0,
  // text overlay
  text: '',
  fontSize: 48,
  fontColor: '#ffffff',
  textX: 50,
  textY: 50,
  // watermark
  watermarkFile: null,
  watermarkPosition: 'bottom-right',
  watermarkOpacity: 0.8,
  // special
  slowmoFactor: 0.5,
  pipVideoId: null,
  pipPosition: 'bottom-right',
  pipScale: 0.25,
})

const toolMap = {
  brightness: 'adjust_brightness',
  blur_sharpen: '', // dynamic
  rotate_flip: '', // dynamic
  crop: 'crop_video',
  fade: 'fade_video',
  color: 'color_adjust',
  text_overlay: 'add_text_overlay',
  watermark: 'add_watermark',
  special: '', // dynamic
}

function getToolName() {
  if (activeTab.value === 'blur_sharpen') {
    return form.effectSubType === 'blur' ? 'blur_video' : 'sharpen_video'
  }
  if (activeTab.value === 'rotate_flip') {
    return form.effectSubType === 'rotate' ? 'rotate_video' : 'flip_video'
  }
  if (activeTab.value === 'special') {
    const map = { reverse: 'reverse_video', stabilize: 'stabilize_video', slowmo: 'slow_motion', pip: 'picture_in_picture' }
    return map[form.effectSubType]
  }
  return toolMap[activeTab.value]
}

function getParams() {
  const base = { video_id: form.videoId }
  switch (activeTab.value) {
    case 'brightness':
      return { ...base, brightness: form.brightness, contrast: form.contrast, saturation: form.saturation }
    case 'blur_sharpen':
      return form.effectSubType === 'blur'
        ? { ...base, sigma: form.sigma }
        : { ...base, amount: form.sharpenAmount }
    case 'rotate_flip':
      return form.effectSubType === 'rotate'
        ? { ...base, angle: form.angle }
        : { ...base, direction: form.flipDirection }
    case 'crop':
      return { ...base, width: form.cropW, height: form.cropH, x: form.cropX, y: form.cropY }
    case 'fade':
      return { ...base, fade_in: form.fadeIn, fade_out: form.fadeOut }
    case 'color':
      return { ...base, hue: form.hue, brightness: form.colorBrightness, contrast: form.colorContrast, saturation: form.colorSaturation }
    case 'text_overlay':
      return { ...base, text: form.text, font_size: form.fontSize, font_color: form.fontColor.replace('#', '0x'), x: form.textX, y: form.textY }
    case 'watermark':
      return { ...base, watermark_path: form.watermarkFile, position: form.watermarkPosition, opacity: form.watermarkOpacity }
    case 'special':
      if (form.effectSubType === 'slowmo') return { ...base, speed_factor: form.slowmoFactor }
      if (form.effectSubType === 'pip') return { ...base, overlay_video_id: form.pipVideoId, position: form.pipPosition, scale: form.pipScale }
      return base
    default:
      return base
  }
}

async function execute() {
  if (!form.videoId) { ElMessage.warning('请先选择视频'); return }
  const tool = getToolName()
  const params = getParams()
  loading.value = true
  result.value = null
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, { tool, params })
    result.value = data
    if (data.success !== false) ElMessage.success('处理完成')
    else ElMessage.error(data.error || '处理失败')
  } catch (e) {
    result.value = { success: false, error: e.message }
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function onVideoChange() {
  result.value = null
}

function onWatermarkChange(file) {
  form.watermarkFile = file.raw?.path || file.name
}

function openFolder() {
  // best-effort: no dedicated API, ignore silently
}

onMounted(async () => {
  try {
    const data = await get(`${API_HOST}/api/videos`, { page: 1, page_size: 200 })
    videos.value = data.items || data || []
  } catch { videos.value = [] }
})
</script>

<style scoped>
.video-effects { padding: 8px 0; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; color: #606266; }
.video-info { margin-top: 4px; font-size: 12px; color: #909399; }
.result-section { margin-top: 12px; }
.result-detail { margin-top: 8px; font-size: 13px; }
</style>

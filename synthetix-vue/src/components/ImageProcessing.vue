<template>
  <div class="image-processing">
    <!-- 图片上传/选择 -->
    <div class="section">
      <h4>选择图片</h4>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept="image/*"
        :on-change="onImageChange"
        drag
      >
        <el-icon style="font-size: 32px; color: #c0c4cc"><UploadFilled /></el-icon>
        <div>拖拽或点击上传图片</div>
      </el-upload>
      <div v-if="imagePreview" class="preview-box">
        <img :src="imagePreview" style="max-width: 200px; max-height: 120px" />
      </div>
    </div>

    <!-- 处理类型 -->
    <div class="section">
      <h4>选择操作</h4>
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 缩放 -->
        <el-tab-pane label="缩放" name="resize">
          <el-form label-width="80px">
            <el-form-item label="宽度">
              <el-input-number v-model="form.resizeW" :min="1" :max="10000" />
            </el-form-item>
            <el-form-item label="高度">
              <el-input-number v-model="form.resizeH" :min="1" :max="10000" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="form.keepAspect">保持宽高比</el-checkbox>
            </el-form-item>
          </el-form>
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

        <!-- 旋转/翻转 -->
        <el-tab-pane label="旋转翻转" name="rotate_flip">
          <el-radio-group v-model="form.rotateSubType" style="margin-bottom: 12px">
            <el-radio-button value="rotate">旋转</el-radio-button>
            <el-radio-button value="flip">翻转</el-radio-button>
          </el-radio-group>
          <template v-if="form.rotateSubType === 'rotate'">
            <el-radio-group v-model="form.angle">
              <el-radio-button :value="90">90°</el-radio-button>
              <el-radio-button :value="180">180°</el-radio-button>
              <el-radio-button :value="270">270°</el-radio-button>
            </el-radio-group>
          </template>
          <template v-else>
            <el-radio-group v-model="form.flipDir">
              <el-radio-button value="horizontal">水平翻转</el-radio-button>
              <el-radio-button value="vertical">垂直翻转</el-radio-button>
            </el-radio-group>
          </template>
        </el-tab-pane>

        <!-- 调整 -->
        <el-tab-pane label="亮度对比度" name="adjust">
          <el-form label-width="80px">
            <el-form-item label="亮度">
              <el-slider v-model="form.imgBrightness" :min="-100" :max="100" :step="5" show-input />
            </el-form-item>
            <el-form-item label="对比度">
              <el-slider v-model="form.imgContrast" :min="-100" :max="100" :step="5" show-input />
            </el-form-item>
            <el-form-item label="饱和度">
              <el-slider v-model="form.imgSaturation" :min="-100" :max="100" :step="5" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 模糊/锐化 -->
        <el-tab-pane label="模糊锐化" name="blur_sharpen">
          <el-radio-group v-model="form.blurSubType" style="margin-bottom: 12px">
            <el-radio-button value="blur">模糊</el-radio-button>
            <el-radio-button value="sharpen">锐化</el-radio-button>
          </el-radio-group>
          <el-form label-width="80px">
            <el-form-item :label="form.blurSubType === 'blur' ? '模糊强度' : '锐化强度'">
              <el-slider v-model="form.blurAmount" :min="0.1" :max="20" :step="0.5" show-input />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 格式转换 -->
        <el-tab-pane label="格式转换" name="convert">
          <el-form label-width="80px">
            <el-form-item label="目标格式">
              <el-radio-group v-model="form.outputFormat">
                <el-radio-button value="jpg">JPG</el-radio-button>
                <el-radio-button value="png">PNG</el-radio-button>
                <el-radio-button value="webp">WebP</el-radio-button>
                <el-radio-button value="bmp">BMP</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 压缩 -->
        <el-tab-pane label="压缩" name="compress">
          <el-form label-width="80px">
            <el-form-item label="质量">
              <el-slider v-model="form.quality" :min="1" :max="100" :step="1" show-input />
            </el-form-item>
          </el-form>
          <p class="hint">质量越低文件越小，1-100（仅对 JPEG/WebP 有效）</p>
        </el-tab-pane>

        <!-- 添加文字 -->
        <el-tab-pane label="添加文字" name="add_text">
          <el-form label-width="80px">
            <el-form-item label="文字内容">
              <el-input v-model="form.imgText" placeholder="输入文字" />
            </el-form-item>
            <el-form-item label="字体大小">
              <el-input-number v-model="form.imgTextSize" :min="10" :max="200" />
            </el-form-item>
            <el-form-item label="字体颜色">
              <el-color-picker v-model="form.imgTextColor" />
            </el-form-item>
            <el-form-item label="X 位置">
              <el-input-number v-model="form.imgTextX" :min="0" />
            </el-form-item>
            <el-form-item label="Y 位置">
              <el-input-number v-model="form.imgTextY" :min="0" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 执行 -->
    <div class="section" style="text-align: center; margin-top: 16px">
      <el-button type="primary" :loading="loading" :disabled="!uploadedFilePath" @click="execute">
        {{ loading ? '处理中...' : '执行' }}
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
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { post } from '@/utils/request'
import { API_HOST } from '@/utils/request'

const loading = ref(false)
const result = ref(null)
const activeTab = ref('resize')
const imagePreview = ref('')
const uploadedFilePath = ref('')
const uploadRef = ref()

const form = reactive({
  resizeW: 1920, resizeH: 1080, keepAspect: true,
  cropW: 800, cropH: 600, cropX: 0, cropY: 0,
  rotateSubType: 'rotate', angle: 90, flipDir: 'horizontal',
  imgBrightness: 0, imgContrast: 0, imgSaturation: 0,
  blurSubType: 'blur', blurAmount: 2,
  outputFormat: 'png',
  quality: 80,
  imgText: '', imgTextSize: 48, imgTextColor: '#ffffff', imgTextX: 50, imgTextY: 50,
})

async function onImageChange(file) {
  if (file.raw) {
    imagePreview.value = URL.createObjectURL(file.raw)
    // Upload to server
    const fd = new FormData()
    fd.append('file', file.raw)
    try {
      const data = await post(`${API_HOST}/api/tools/upload/file`, fd)
      uploadedFilePath.value = data.file_path || data.path || data.local_path || ''
    } catch {
      ElMessage.error('图片上传失败')
    }
  }
}

const tabToolMap = {
  resize: 'resize_image',
  crop: 'crop_image',
  rotate_flip: '', // dynamic
  adjust: 'adjust_image',
  blur_sharpen: '', // dynamic
  convert: 'convert_image',
  compress: 'compress_image',
  add_text: 'add_text_to_image',
}

function getToolName() {
  if (activeTab.value === 'rotate_flip') return form.rotateSubType === 'rotate' ? 'rotate_image' : 'flip_image'
  if (activeTab.value === 'blur_sharpen') return form.blurSubType === 'blur' ? 'blur_image' : 'sharpen_image'
  return tabToolMap[activeTab.value]
}

function getParams() {
  const base = { input_path: uploadedFilePath.value }
  switch (activeTab.value) {
    case 'resize': return { ...base, width: form.resizeW, height: form.resizeH, keep_aspect: form.keepAspect }
    case 'crop': return { ...base, width: form.cropW, height: form.cropH, x: form.cropX, y: form.cropY }
    case 'rotate_flip':
      return form.rotateSubType === 'rotate'
        ? { ...base, angle: form.angle }
        : { ...base, direction: form.flipDir }
    case 'adjust':
      return { ...base, brightness: form.imgBrightness, contrast: form.imgContrast, saturation: form.imgSaturation }
    case 'blur_sharpen':
      return form.blurSubType === 'blur'
        ? { ...base, sigma: form.blurAmount }
        : { ...base, amount: form.blurAmount }
    case 'convert': return { ...base, output_format: form.outputFormat }
    case 'compress': return { ...base, quality: form.quality }
    case 'add_text':
      return { ...base, text: form.imgText, font_size: form.imgTextSize, font_color: form.imgTextColor.replace('#', '0x'), x: form.imgTextX, y: form.imgTextY }
    default: return base
  }
}

async function execute() {
  if (!uploadedFilePath.value) { ElMessage.warning('请先上传图片'); return }
  loading.value = true
  result.value = null
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, {
      tool: getToolName(),
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
</script>

<style scoped>
.image-processing { padding: 8px 0; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; color: #606266; }
.preview-box { margin-top: 8px; text-align: center; }
.hint { color: #909399; font-size: 12px; margin: 8px 0 0; }
.result-section { margin-top: 12px; }
.result-detail { margin-top: 8px; font-size: 13px; }
</style>

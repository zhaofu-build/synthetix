<template>
  <div class="subtitle-style-editor">
    <div class="style-toolbar">
      <span class="toolbar-label">字幕样式</span>
      <el-select v-model="presetKey" size="small" placeholder="选择预设" style="width: 100px" @change="applyPreset">
        <el-option v-for="(p, k) in presets" :key="k" :label="p.name" :value="k" />
      </el-select>
    </div>

    <div class="style-form">
      <el-form size="small" label-width="60px">
        <el-form-item label="字体">
          <el-select v-model="style.fontFamily" style="width: 120px" filterable>
            <el-option v-for="f in fontOptions" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="大小">
          <el-slider v-model="style.fontSize" :min="12" :max="72" :step="1" style="width: 120px" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="style.color" size="small" />
        </el-form-item>
        <el-form-item label="粗体">
          <el-switch v-model="style.bold" />
        </el-form-item>
        <el-form-item label="描边">
          <el-color-picker v-model="style.strokeColor" size="small" />
          <el-slider v-model="style.strokeWidth" :min="0" :max="6" :step="0.5" style="width: 80px; margin-left: 8px" />
        </el-form-item>
        <el-form-item label="阴影">
          <el-slider v-model="style.shadow" :min="0" :max="4" :step="0.5" style="width: 100px" />
        </el-form-item>
        <el-form-item label="背景">
          <el-color-picker v-model="style.bgColor" size="small" show-alpha />
        </el-form-item>
        <el-form-item label="位置">
          <el-select v-model="style.position" style="width: 100px">
            <el-option label="底部居中" value="bottom" />
            <el-option label="顶部居中" value="top" />
            <el-option label="中间" value="center" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <!-- 预览 -->
    <div class="style-preview">
      <div class="preview-video">
        <div class="preview-subtitle" :style="previewStyle">示例字幕文本</div>
      </div>
    </div>

    <div class="style-actions">
      <el-button size="small" type="primary" @click="applyStyle">应用到所有</el-button>
      <el-button size="small" @click="saveAsPreset">存为预设</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useSubtitleStore } from '@/store/modules/subtitle'

const subtitleStore = useSubtitleStore()

const presetKey = ref('')
const style = reactive({
  fontFamily: 'Microsoft YaHei',
  fontSize: 28,
  color: '#FFFFFF',
  strokeColor: '#000000',
  strokeWidth: 2,
  shadow: 0,
  bold: false,
  bgColor: 'rgba(0,0,0,0.5)',
  position: 'bottom',
})

const presets = {
  classic: { name: '经典白字', fontFamily: 'Microsoft YaHei', fontSize: 28, color: '#FFFFFF', strokeColor: '#000000', strokeWidth: 2, shadow: 0, bold: false, bgColor: 'rgba(0,0,0,0.5)', position: 'bottom' },
  bold: { name: '粗体黄字', fontFamily: 'Microsoft YaHei', fontSize: 32, color: '#FFD700', strokeColor: '#000000', strokeWidth: 3, shadow: 0, bold: true, bgColor: 'rgba(0,0,0,0.6)', position: 'bottom' },
  minimal: { name: '极简无框', fontFamily: 'Arial', fontSize: 24, color: '#FFFFFF', strokeColor: '#000000', strokeWidth: 1, shadow: 0, bold: false, bgColor: 'transparent', position: 'bottom' },
  cartoon: { name: '卡通描边', fontFamily: 'Microsoft YaHei', fontSize: 30, color: '#FFFFFF', strokeColor: '#FF6B6B', strokeWidth: 4, shadow: 2, bold: true, bgColor: 'transparent', position: 'center' },
  shadow: { name: '阴影立体', fontFamily: 'SimHei', fontSize: 26, color: '#FFFFFF', strokeColor: '#000000', strokeWidth: 1, shadow: 3, bold: false, bgColor: 'transparent', position: 'bottom' },
}

const fontOptions = [
  'Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong',
  'STXinwei', 'STHupo', 'STKaiti', 'STZhongsong', 'STFangsong',
  'Arial', 'Helvetica', 'Georgia', 'Times New Roman', 'Consolas',
]

/** #RRGGBB → ASS &HBBGGRR */
function toAssColor(hex) {
  if (!hex || hex === 'transparent') return null
  const m = hex.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i)
  if (!m) return null
  return `&H${m[3]}${m[2]}${m[1]}`
}

/** rgba(r,g,b,a) → ASS &HBBGGRR (with alpha → semi-transparent bg) */
function rgbaToAssBg(rgba) {
  if (!rgba || rgba === 'transparent') return null
  const m = rgba.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
  if (!m) return toAssColor(rgba)
  const r = parseInt(m[1]).toString(16).padStart(2, '0')
  const g = parseInt(m[2]).toString(16).padStart(2, '0')
  const b = parseInt(m[3]).toString(16).padStart(2, '0')
  return `&H${b}${g}${r}`
}

const previewStyle = computed(() => ({
  fontFamily: style.fontFamily,
  fontSize: style.fontSize + 'px',
  color: style.color,
  fontWeight: style.bold ? 'bold' : 'normal',
  WebkitTextStroke: style.strokeWidth > 0 ? `${style.strokeWidth}px ${style.strokeColor}` : 'none',
  textShadow: [
    style.strokeWidth > 0 ? `${style.strokeColor} 1px 1px 2px` : '',
    style.shadow > 0 ? `2px 2px ${style.shadow * 2}px rgba(0,0,0,0.8)` : '',
  ].filter(Boolean).join(', ') || 'none',
  backgroundColor: style.bgColor,
  padding: style.bgColor !== 'transparent' ? '2px 12px' : '0',
  borderRadius: '4px',
  position: 'absolute',
  [style.position === 'bottom' ? 'bottom' : style.position === 'top' ? 'top' : 'top']: style.position === 'center' ? '50%' : '12px',
  transform: style.position === 'center' ? 'translateY(-50%)' : 'none',
}))

const applyPreset = (key) => {
  const p = presets[key]
  if (p) Object.assign(style, p)
}

const applyStyle = () => {
  const assColor = toAssColor(style.color)
  const assStroke = toAssColor(style.strokeColor)
  const assBg = rgbaToAssBg(style.bgColor)
  const positionMap = { bottom: 2, top: 8, center: 5 }
  subtitleStore.setStyle({
    ...style,
    fontName: style.fontFamily,
    assColor,
    assStroke,
    assBg,
    alignment: positionMap[style.position] || 2,
  })
  ElMessage.success('样式已应用')
}

const saveAsPreset = () => {
  const name = `自定义 ${Object.keys(presets).length + 1}`
  presets[`custom_${Date.now()}`] = { name, ...style }
  ElMessage.success('预设已保存')
}
</script>

<style scoped>
.subtitle-style-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}
.style-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-label { font-size: 12px; font-weight: 600; }
.style-form { max-height: 260px; overflow-y: auto; }
.style-preview {
  height: 80px;
  background: linear-gradient(135deg, #1a1a2e, #2d2d44);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.preview-video {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-subtitle {
  text-align: center;
  max-width: 80%;
  white-space: nowrap;
}
.style-actions {
  display: flex;
  gap: 6px;
}
</style>

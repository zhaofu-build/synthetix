<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- AI 服务 -->
      <el-tab-pane label="AI 服务" name="ai">
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">🌐</span>
            <span class="group-title">{{ t('settings.coreNexus') }}</span>
          </div>
          <div class="setting-row">
            <label class="setting-label">{{ t('settings.baseUrl') }}</label>
            <div class="setting-control url-row">
              <el-input
                  v-model="systemStore.config.core_nexus_base_url"
                  placeholder="http://127.0.0.1:9666"
                  clearable size="default" @change="onBaseUrlChange"/>
              <el-button type="success" size="default" :loading="testing" @click="testConnection">
                {{ t('settings.testConnection') }}
              </el-button>
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">{{ t('settings.coreNexusApiKey') }}</label>
            <div class="setting-control">
              <el-input v-model="systemStore.config.core_nexus_api_key"
                        type="password" show-password size="default"
                        placeholder="cn-xxxx..." />
            </div>
          </div>
        </div>
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">🤖</span>
            <span class="group-title">{{ t('settings.aiModel') }}</span>
          </div>
          <div class="model-grid">
            <div class="model-item" v-for="m in modelFields" :key="m.key">
              <label class="setting-label">{{ m.label }}</label>
              <el-select v-model="systemStore.config[m.key]" class="full-width" clearable size="default"
                         :placeholder="t('settings.defaultModel')">
                <el-option v-for="item in systemStore.models[m.type]" :key="item.name"
                           :label="item.name" :value="item.name">
                  <span>{{ item.name }}</span>
                  <span class="option-provider">{{ item.provider_name }}</span>
                </el-option>
              </el-select>
            </div>
          </div>
        </div>
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">🔍</span>
            <span class="group-title">联网搜索</span>
          </div>
          <div class="setting-row">
            <label class="setting-label">启用联网搜索</label>
            <div class="setting-control">
              <el-switch v-model="systemStore.config.web_search_enabled" />
              <span class="setting-hint">开启后 Agent 可通过 AI 服务搜索互联网实时信息（需服务端支持）</span>
            </div>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="视频 / 剪辑" name="video">
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">🎬</span>
            <span class="group-title">{{ t('settings.mediaSettings') }}</span>
          </div>
          <div class="setting-row">
            <label class="setting-label">{{ t('settings.videoSource') }}</label>
            <div class="setting-control">
              <el-select v-model="systemStore.config.video_type" class="full-width" size="default" placeholder="请选择视频源">
                <el-option v-for="item in videoSources" :key="item.value" :label="item.label" :value="item.value"/>
              </el-select>
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">{{ t('settings.apiKey') }}</label>
            <div class="setting-control">
              <el-input v-model="systemStore.config.video_api_keys" type="password" show-password size="default" placeholder="Pexels API Key"/>
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">Pixabay Key</label>
            <div class="setting-control">
              <el-input v-model="systemStore.config.pixabay_api_key" type="password" show-password size="default" placeholder="Pixabay API Key（可选）"/>
            </div>
          </div>
        </div>
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">✂️</span>
            <span class="group-title">剪辑偏好</span>
          </div>
          <div class="setting-row">
            <label class="setting-label">默认 CRF</label>
            <div class="setting-control">
              <el-slider v-model="ffmpegCrf" :min="18" :max="32" :step="1" show-input size="small" />
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">编码预设</label>
            <div class="setting-control">
              <el-select v-model="ffmpegPreset" size="default">
                <el-option v-for="p in presetOptions" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">GPU 加速</label>
            <div class="setting-control">
              <el-switch v-model="gpuAcceleration" />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 外观 -->
      <el-tab-pane label="外观" name="appearance">
        <div class="setting-group">
          <div class="group-header">
            <span class="group-icon">🎨</span>
            <span class="group-title">外观设置</span>
          </div>
          <div class="setting-row">
            <label class="setting-label">主题</label>
            <div class="setting-control">
              <el-radio-group v-model="selectedTheme" @change="switchTheme">
                <el-radio-button value="light">{{ t('settings.themeDefault') }}</el-radio-button>
                <el-radio-button value="dark">{{ t('settings.themeDark') }}</el-radio-button>
                <el-radio-button value="custom-dark">{{ t('settings.themeRipple') }}</el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <div class="setting-row">
            <label class="setting-label">语言</label>
            <div class="setting-control">
              <el-radio-group v-model="selectedLang" @change="switchLang">
                <el-radio-button value="zh-CN">中文</el-radio-button>
                <el-radio-button value="en-US">English</el-radio-button>
              </el-radio-group>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 底部保存栏 -->
    <div class="settings-footer">
      <span class="footer-hint">更改后点击保存生效</span>
      <el-button type="primary" size="default" @click="saveConfig" :loading="saving">
        {{ t('settings.saveSettings') }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import {useI18n} from 'vue-i18n'
import {useSystemStore} from '@/store/modules/system'
import {storeToRefs} from 'pinia'
import {systemApi} from '@/api'
import {THEME_LABELS} from '@/constants'
import { setLanguage, getCurrentLanguage } from '@/locales'

const { t } = useI18n()

const systemStore = useSystemStore()
const { theme: currentTheme } = storeToRefs(systemStore)

const modelFields = [
  { key: 'llm_model', type: 'LLM', label: computed(() => t('settings.llmModel')) },
  { key: 'tts_model', type: 'TTS', label: computed(() => t('settings.ttsModel')) },
  { key: 'asr_model', type: 'ASR', label: computed(() => t('settings.asrModel')) },
  { key: 'vl_model', type: 'VL', label: computed(() => t('settings.vlModel')) },
  { key: 'music_model', type: 'TEXT_TO_MUSIC', label: computed(() => t('settings.musicModel')) },
]

const videoSources = [
  {value: 'pexels', label: 'Pexels'},
  {value: 'pixabay', label: 'Pixabay'},
]

const saving = ref(false)
const testing = ref(false)
const activeTab = ref('ai')
const selectedTheme = ref(currentTheme.value || 'light')
const selectedLang = ref(getCurrentLanguage())

// FFmpeg settings
const ffmpegCrf = ref(23)
const ffmpegPreset = ref('medium')
const gpuAcceleration = ref(true)
const presetOptions = [
  { value: 'ultrafast', label: '极快 (低质量)' },
  { value: 'fast', label: '快速' },
  { value: 'medium', label: '中等 (默认)' },
  { value: 'slow', label: '慢速 (高质量)' },
]

const currentThemeLabel = computed(() => THEME_LABELS[currentTheme.value])
const currentLangLabel = computed(() => getCurrentLanguage() === 'zh-CN' ? '中文' : 'English')
const switchLang = (lang) => {
  setLanguage(lang)
  ElMessage.success(lang === 'zh-CN' ? '已切换为中文' : 'Switched to English')
}

onMounted(async () => {
  await systemStore.loadConfig()
  if (systemStore.config.core_nexus_base_url) {
    loadAllModels()
  }
})

const onBaseUrlChange = () => {
  if (systemStore.config.core_nexus_base_url) {
    loadAllModels()
  }
}

const loadAllModels = async () => {
  const types = ['LLM', 'TTS', 'ASR', 'VL', 'TEXT_TO_MUSIC']
  await Promise.all(types.map(type => systemStore.fetchModels(type)))
}

const testConnection = async () => {
  if (!systemStore.config.core_nexus_base_url) {
    ElMessage.warning(t('settings.baseUrl'))
    return
  }
  testing.value = true
  try {
    await systemApi.testConnection(systemStore.config.core_nexus_base_url)
    ElMessage.success(t('settings.connectionOk'))
    loadAllModels()
  } catch (error) {
    ElMessage.error(t('settings.connectionFailed'))
  } finally {
    testing.value = false
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    // Save FFmpeg preferences to config
    if (!systemStore.config.ffmpeg) systemStore.config.ffmpeg = {}
    systemStore.config.ffmpeg.default_crf = ffmpegCrf.value
    systemStore.config.ffmpeg.default_preset = ffmpegPreset.value
    systemStore.config.ffmpeg.gpu_acceleration = gpuAcceleration.value
    await systemStore.saveConfig()
    ElMessage.success(t('settings.configSaved'))
  } catch (error) {
    ElMessage.error(t('settings.saveFailed'))
  } finally {
    saving.value = false
  }
}

const switchTheme = (theme) => {
  const html = document.documentElement
  html.classList.remove('light', 'dark', 'custom-dark')
  document.body.classList.remove('light', 'dark', 'custom-dark')

  if (theme === 'custom-dark' || theme === 'ripple') {
    document.body.classList.add('dark')
    html.classList.add('dark')
  } else if (theme === 'dark') {
    html.classList.add('dark')
  } else {
    document.body.classList.add('light')
    html.classList.add('light')
  }
  systemStore.setTheme(theme)
}
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 72vh;
  overflow-y: auto;
  padding: 4px 8px 8px;
}

.settings-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.setting-group {
  background: var(--el-bg-color-page, #f5f7fa);
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 12px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.group-icon { font-size: 16px; }

.group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.setting-row:last-child { margin-bottom: 0; }

.setting-label {
  flex-shrink: 0;
  width: 90px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  text-align: right;
}

.setting-control {
  flex: 1;
  min-width: 0;
}

.url-row { display: flex; gap: 8px; }
.url-row .el-input { flex: 1; }

.model-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}

.model-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-item .setting-label {
  width: auto;
  text-align: left;
  font-size: 12px;
}

.option-provider {
  float: right;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.settings-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  margin-top: 8px;
}

.footer-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.full-width { width: 100%; }

.about-info { display: flex; flex-direction: column; gap: 8px; }
.about-row {
  display: flex; gap: 16px; font-size: 13px;
}
.about-label {
  width: 80px; flex-shrink: 0; color: var(--el-text-color-secondary); font-weight: 500;
}

@media (max-width: 600px) {
  .model-grid { grid-template-columns: 1fr; }
}
</style>

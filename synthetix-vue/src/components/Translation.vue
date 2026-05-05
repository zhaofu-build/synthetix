<template>
  <div class="translation-tool">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 文本翻译 -->
      <el-tab-pane label="文本翻译" name="translate">
        <el-form label-width="80px">
          <el-form-item label="源语言">
            <el-select v-model="form.sourceLang" style="width: 160px">
              <el-option label="自动检测" value="auto" />
              <el-option label="中文" value="zh" />
              <el-option label="英语" value="en" />
              <el-option label="日语" value="ja" />
              <el-option label="韩语" value="ko" />
              <el-option label="法语" value="fr" />
              <el-option label="德语" value="de" />
              <el-option label="西班牙语" value="es" />
              <el-option label="俄语" value="ru" />
              <el-option label="阿拉伯语" value="ar" />
              <el-option label="葡萄牙语" value="pt" />
              <el-option label="越南语" value="vi" />
              <el-option label="印尼语" value="id" />
            </el-select>
            <el-icon style="margin: 0 12px; font-size: 18px; color: #c0c4cc"><Right /></el-icon>
            <el-select v-model="form.targetLang" style="width: 160px">
              <el-option label="中文" value="zh" />
              <el-option label="英语" value="en" />
              <el-option label="日语" value="ja" />
              <el-option label="韩语" value="ko" />
              <el-option label="法语" value="fr" />
              <el-option label="德语" value="de" />
              <el-option label="西班牙语" value="es" />
              <el-option label="俄语" value="ru" />
              <el-option label="阿拉伯语" value="ar" />
              <el-option label="葡萄牙语" value="pt" />
              <el-option label="越南语" value="vi" />
              <el-option label="印尼语" value="id" />
            </el-select>
          </el-form-item>
          <el-form-item label="输入文本">
            <el-input v-model="form.text" type="textarea" :rows="6" placeholder="输入要翻译的文本" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="translate">
              {{ loading ? '翻译中...' : '翻译' }}
            </el-button>
            <el-button @click="swapLangs">交换语言</el-button>
          </el-form-item>
          <el-form-item v-if="translatedText" label="翻译结果">
            <el-input v-model="translatedText" type="textarea" :rows="6" readonly />
            <el-button size="small" style="margin-top: 8px" @click="copyResult">复制结果</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 语言检测 -->
      <el-tab-pane label="语言检测" name="detect">
        <el-form label-width="80px">
          <el-form-item label="输入文本">
            <el-input v-model="form.detectText" type="textarea" :rows="4" placeholder="输入要检测语言的文本" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="detectLoading" @click="detectLanguage">
              {{ detectLoading ? '检测中...' : '检测语言' }}
            </el-button>
          </el-form-item>
          <el-form-item v-if="detectedLang" label="检测结果">
            <el-tag type="success" size="large">{{ detectedLang }}</el-tag>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Right } from '@element-plus/icons-vue'
import { post } from '@/utils/request'
import { API_HOST } from '@/utils/request'

const activeTab = ref('translate')
const loading = ref(false)
const detectLoading = ref(false)
const translatedText = ref('')
const detectedLang = ref('')

const form = reactive({
  sourceLang: 'auto',
  targetLang: 'en',
  text: '',
  detectText: '',
})

async function translate() {
  if (!form.text.trim()) { ElMessage.warning('请输入文本'); return }
  loading.value = true
  translatedText.value = ''
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, {
      tool: 'translate_text',
      params: { text: form.text, source_lang: form.sourceLang, target_lang: form.targetLang },
    })
    translatedText.value = data.translated_text || data.text || data.result || JSON.stringify(data)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function detectLanguage() {
  if (!form.detectText.trim()) { ElMessage.warning('请输入文本'); return }
  detectLoading.value = true
  detectedLang.value = ''
  try {
    const data = await post(`${API_HOST}/api/agent/execute`, {
      tool: 'detect_language',
      params: { text: form.detectText },
    })
    detectedLang.value = data.language || data.lang || data.detected_language || JSON.stringify(data)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    detectLoading.value = false
  }
}

function swapLangs() {
  if (form.sourceLang === 'auto') { ElMessage.info('自动检测模式无法交换'); return }
  const tmp = form.sourceLang
  form.sourceLang = form.targetLang
  form.targetLang = tmp
  if (translatedText.value) {
    form.text = translatedText.value
    translatedText.value = ''
  }
}

function copyResult() {
  navigator.clipboard.writeText(translatedText.value)
  ElMessage.success('已复制')
}
</script>

<style scoped>
.translation-tool { padding: 8px 0; }
</style>

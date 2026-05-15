import { defineStore } from 'pinia'
import { systemApi } from '@/api'
import { storage } from '@/utils/storage'

export const useSystemStore = defineStore('system', {
  state: () => ({
    theme: storage.get('theme') || 'dark',
    config: {
      core_nexus_base_url: '',
      core_nexus_api_key: '',
      llm_model: '',
      tts_model: '',
      asr_model: '',
      multimodal_model: '',
      music_model: '',
      image_model: '',
      video_model: '',
      video_type: 'pexels',
      video_api_keys: '',
      pixabay_api_key: '',
      web_search_enabled: false,
    },
    models: {
      LLM: [],
      TTS: [],
      ASR: [],
      MULTIMODAL: [],
      TEXT_TO_MUSIC: [],
      TEXT_TO_IMAGE: [],
      VIDEO_GEN: [],
    }
  }),
  
  actions: {
    setTheme(theme) {
      // 移除所有主题类
      const html = document.documentElement
      const body = document.body
      html.classList.remove('light', 'dark', 'custom-dark')
      body.classList.remove('light', 'dark', 'custom-dark')
      
      // 根据主题类型添加相应的类
      // 波纹主题(custom-dark)需要应用dark类来激活ripple.css样式
      if (theme === 'custom-dark' || theme === 'ripple') {
        body.classList.add('dark')
        html.classList.add('dark')
      } else if (theme === 'dark') {
        html.classList.add('dark')
      } else {
        body.classList.add('light')
        html.classList.add('light')
      }
      
      this.theme = theme
      storage.set('theme', theme)
    },
    
    updateConfig(newConfig) {
      // 展平 core_nexus 嵌套配置到顶层（后端 to_camel 转换后 key 为 camelCase）
      const cn = newConfig.core_nexus || newConfig.coreNexus
      if (cn) {
        this.config.core_nexus_base_url = cn.base_url || cn.baseUrl || ''
        this.config.core_nexus_api_key = cn.api_key || cn.apiKey || ''
        this.config.llm_model = cn.llm_model || cn.llmModel || ''
        this.config.tts_model = cn.tts_model || cn.ttsModel || ''
        this.config.asr_model = cn.asr_model || cn.asrModel || ''
        this.config.multimodal_model = cn.multimodal_model || cn.multimodalModel || ''
        this.config.music_model = cn.music_model || cn.musicModel || ''
        this.config.image_model = cn.image_model || cn.imageModel || ''
        this.config.video_model = cn.video_model || cn.videoModel || ''
        delete newConfig.core_nexus
        delete newConfig.coreNexus
      }
      // 展平 web_search 嵌套配置
      const ws = newConfig.web_search || newConfig.webSearch
      if (ws) {
        this.config.web_search_enabled = ws.enabled ?? ws.isEnabled ?? false
        delete newConfig.web_search
        delete newConfig.webSearch
        delete newConfig.coreNexus
      }
      this.config = { ...this.config, ...newConfig }
    },

    async loadConfig() {
      try {
        const data = await systemApi.getConfig()
        this.updateConfig(data)
      } catch (error) {
        console.error('Failed to load config:', error)
      }
    },

    async saveConfig() {
      try {
        // 将扁平配置转为 dot-path 格式供后端 config_manager
        const configData = {
          'core_nexus.base_url': this.config.core_nexus_base_url,
          'core_nexus.api_key': this.config.core_nexus_api_key,
          'core_nexus.llm_model': this.config.llm_model,
          'core_nexus.tts_model': this.config.tts_model,
          'core_nexus.asr_model': this.config.asr_model,
          'core_nexus.multimodal_model': this.config.multimodal_model,
          'core_nexus.music_model': this.config.music_model,
          'core_nexus.image_model': this.config.image_model,
          'core_nexus.video_model': this.config.video_model,
          video_type: this.config.video_type,
          video_api_keys: this.config.video_api_keys,
          pixabay_api_key: this.config.pixabay_api_key,
          'web_search.enabled': this.config.web_search_enabled,
        }
        await systemApi.saveConfig(configData)
      } catch (error) {
        console.error('Failed to save config:', error)
        throw error
      }
    },

    async fetchModels(taskType) {
      try {
        const res = await systemApi.getModels(taskType, this.config.core_nexus_base_url)
        const list = res?.models || res || []
        if (taskType) {
          this.models[taskType] = list
        } else {
          if (Array.isArray(list)) {
            list.forEach(item => {
              const type = item.task_type
              if (type && this.models[type] !== undefined) {
                this.models[type].push(item)
              }
            })
          }
        }
      } catch (error) {
        console.error('Failed to fetch models:', error)
      }
    },
    
    // 初始化系统设置
    initialize() {
      // 从本地存储加载配置
      this.loadConfig()
      
      // 应用主题
      this.setTheme(this.theme)
    }
  }
})
// 应用常量定义
export const APP_CONSTANTS = {
  // 主题相关
  THEMES: {
    LIGHT: 'light',
    DARK: 'dark',
    RIPPLE: 'custom-dark' // 或 'ripple'
  },
  
  // API 相关
  API_STATUS: {
    SUCCESS: 200,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    SERVER_ERROR: 500
  },
  
  // 存储键名
  STORAGE_KEYS: {
    THEME: 'theme',
    TOKEN: 'token',
    USER_INFO: 'user_info',
    CONFIG: 'app_config',
    PANEL_STATE: 'synthetix_panel_state',
  },
  
  // 路由相关
  ROUTE_NAMES: {
    VIDEO_STITCHING: 'VideoStitching',
    VIDEO_AI_STITCHING: 'VideoAIStitching',
    VOICE_CLONING: 'VoiceCloning',
    COMFY_UI_AUDIO: 'ComfyUIAudio',
    AUDIO_PROCESSING: 'AudioProcessing',
    VIDEO_PROCESSING: 'VideoProcessing',
    SYSTEM_SETTING: 'SystemSetting'
  },
  
  // 默认配置
  DEFAULT_CONFIG: {
    LLM_MODEL: 'g4f',
    VIDEO_TYPE: 'pexels'
  }
}

// 主题标签
export const THEME_LABELS = {
  'light': '默认',
  'dark': '暗黑',
  'custom-dark': '波纹'
}
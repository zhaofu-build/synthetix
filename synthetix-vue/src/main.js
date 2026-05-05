import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/theme-chalk/index.css'
import App from './App.vue'
import router from './router'
import store from './store'
import { useSystemStore } from './store/modules/system' // 修改为使用系统设置存储
import { setupErrorHandler } from './utils/errorHandler'
import { setupDirectives } from './directives'
import { storage } from './utils/storage'
import i18n from './locales'

// 1. 根据用户设置添加主题类
const savedTheme = storage.get('theme', 'dark') // 默认为dark而不是ripple

// 根据主题类型添加相应的类 - 与 store 中的逻辑保持一致
const html = document.documentElement
const body = document.body
html.classList.remove('light', 'dark', 'custom-dark')
body.classList.remove('light', 'dark', 'custom-dark')

// 波纹主题(custom-dark)需要应用dark类来激活ripple.css样式
if (savedTheme === 'custom-dark' || savedTheme === 'ripple') {
  body.classList.add('dark')
  html.classList.add('dark')
} else if (savedTheme === 'dark') {
  html.classList.add('dark')
} else {
  body.classList.add('light')
  html.classList.add('light')
}

// 2. 按顺序引入样式
import '@/styles/ripple.css' // 自定义波纹(覆盖官方)
import '@/styles/markdown.css' // Markdown 富文本样式
import 'element-plus/theme-chalk/dark/css-vars.css' // 官方暗黑
import '@/styles/dark.css'

const app = createApp(App)

// 设置全局错误处理
setupErrorHandler(app)

// 注册自定义指令
setupDirectives(app)

app.use(ElementPlus)
app.use(store)
app.use(router)
app.use(i18n)

// 初始化系统设置状态
const systemStore = useSystemStore()
systemStore.initialize()

// 开发环境启用性能监控
if (import.meta.env.DEV) {
  import('./utils/performance').then(({ default: performance }) => {
    performance.start('app-init')
    console.log('Performance monitoring enabled')
  })

  // 打印环境信息
  import('./utils/env').then(({ printEnvironmentInfo }) => {
    printEnvironmentInfo()
  })
}

app.mount('#app')
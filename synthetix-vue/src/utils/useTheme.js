import { ref, watch } from 'vue'

const STORAGE_KEY = 'synthetix_theme'

const theme = ref(localStorage.getItem(STORAGE_KEY) || 'dark')

// 模块加载时立即应用主题，避免首次渲染白屏闪烁
function applyTheme(val) {
  localStorage.setItem(STORAGE_KEY, val)
  document.documentElement.setAttribute('data-theme', val)
  if (val === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}
applyTheme(theme.value)

export function useTheme() {
  const toggleTheme = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  watch(theme, (val) => {
    applyTheme(val)
  })

  return { theme, toggleTheme }
}

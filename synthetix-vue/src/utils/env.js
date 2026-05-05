// 环境信息工具
export function printEnvironmentInfo() {
  console.group('🔧 Environment Info')
  console.log('Environment:', import.meta.env.MODE)
  console.log('Development:', import.meta.env.DEV)
  console.log('Production:', import.meta.env.PROD)
  console.log('Base URL:', import.meta.env.BASE_URL)
  console.log('Node Version:', import.meta.env.VITE_NODE_VERSION || 'N/A')
  console.log('Vue Version:', import.meta.env.VITE_VUE_VERSION || 'N/A')
  console.groupEnd()
}

// 导出环境信息
export const environment = {
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
  mode: import.meta.env.MODE,
  baseUrl: import.meta.env.BASE_URL
}
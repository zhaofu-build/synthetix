import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  server: {
    port: 9528,  // ← ZF tool
    open: true,   // 启动自动打开浏览器（可选）
    host: '0.0.0.0', // 允许局域网访问（可选）
    allowedHosts: [
      '757e73c5.r20.cpolar.top', // 显式添加
      '.cpolar.top' // 通配符匹配
    ],
    proxy: {
      // 将 /api 请求代理到后端，解决 Vite dev server 下相对路径 API 调用问题
      '/api': {
        target: 'http://127.0.0.1:9527',
        changeOrigin: true,
      },
    },
  },
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: process.env.NODE_ENV !== 'production',
    rollupOptions: {
      external: [
        '@tauri-apps/api/event',
        '@tauri-apps/plugin-updater',
        '@tauri-apps/plugin-process',
      ],
      output: {
        manualChunks: {
          'element-plus': ['element-plus'],
          'vue-router': ['vue-router'],
          'pinia': ['pinia'],
          'axios': ['axios']
        }
      }
    }
  }
})

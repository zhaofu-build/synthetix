import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_HOST } from '@/api/modules'

export const usePublishStore = defineStore('publish', {
  state: () => ({
    platforms: {},
    selectedPlatform: 'douyin',
    exporting: false,
    exportHistory: [],
  }),

  actions: {
    async fetchPlatforms() {
      try {
        const res = await fetch(`${API_HOST}/api/platform-presets`).then(r => r.json())
        if (res.code === 200) this.platforms = res.data
      } catch (e) {
        console.error('获取平台预设失败:', e)
      }
    },

    async exportForPlatform(projectId) {
      if (!projectId || !this.selectedPlatform) return
      this.exporting = true
      try {
        const preset = this.platforms[this.selectedPlatform]
        const res = await fetch(`${API_HOST}/api/projects/${projectId}/render`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            platform: this.selectedPlatform,
            width: preset.width,
            height: preset.height,
            bitrate: preset.bitrate,
            fps: preset.fps,
          }),
        }).then(r => r.json())
        if (res.code === 200) {
          this.exportHistory.unshift({
            id: Date.now(),
            platform: this.selectedPlatform,
            name: preset.name,
            time: new Date().toISOString(),
            status: 'processing',
          })
          return true
        }
        return false
      } catch (e) {
        console.error('导出失败:', e)
        return false
      } finally {
        this.exporting = false
      }
    },
  },
})

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { publishApi, projectApi } from '@/api/modules'

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
        const data = await publishApi.getPlatforms()
        this.platforms = data
      } catch (e) {
        console.error('获取平台预设失败:', e)
      }
    },

    async exportForPlatform(projectId) {
      if (!projectId || !this.selectedPlatform) return
      this.exporting = true
      try {
        const preset = this.platforms[this.selectedPlatform]
        await projectApi.render(projectId, {
          platform: this.selectedPlatform,
          width: preset.width,
          height: preset.height,
          bitrate: preset.bitrate,
          fps: preset.fps,
        })
        this.exportHistory.unshift({
          id: Date.now(),
          platform: this.selectedPlatform,
          name: preset.name,
          time: new Date().toISOString(),
          status: 'processing',
        })
        return true
      } catch (e) {
        console.error('导出失败:', e)
        return false
      } finally {
        this.exporting = false
      }
    },
  },
})

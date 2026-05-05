import { defineStore } from 'pinia'
import { ref } from 'vue'
import { qualityApi } from '@/api/modules'

export const useQualityStore = defineStore('quality', {
  state: () => ({
    reports: {},
    checking: false,
  }),

  actions: {
    async runCheck(projectId, videoPath, clips, targetDuration) {
      this.checking = true
      try {
        const data = await qualityApi.check(videoPath, clips, targetDuration)
        if (data) {
          this.reports[projectId] = data
          return data
        }
        return null
      } catch (e) {
        console.error('质量检测失败:', e)
        return null
      } finally {
        this.checking = false
      }
    },

    getReport(projectId) {
      return this.reports[projectId] || null
    },
  },
})

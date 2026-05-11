import { defineStore } from 'pinia'
import { timelineApi } from '@/api/modules'

export const useTimelineStore = defineStore('timeline', {
  state: () => ({
    tracks: [
      { id: 'v1', type: 'video', name: '视频', clips: [], muted: false, locked: false },
      { id: 'a1', type: 'audio', name: '音频 1', clips: [], muted: false, locked: false },
      { id: 'a2', type: 'audio', name: '音频 2', clips: [], muted: false, locked: false },
      { id: 's1', type: 'subtitle', name: '字幕', clips: [], muted: false, locked: false },
      { id: 'm1', type: 'marker', name: '标记', clips: [], muted: false, locked: false },
    ],
    duration: 0,
    zoom: 1.0,       // 1.0 = 1 pixel per second
    scrollX: 0,
    playheadPosition: 0,
    snapEnabled: true,
    selectedClipId: null,
    // AI 建议覆盖
    suggestedClips: [],
  }),

  getters: {
    totalWidth: (state) => Math.max(state.duration, 60) * state.zoom,
    playheadPercent: (state) => state.duration > 0 ? (state.playheadPosition / state.duration) * 100 : 0,
    videoTrack: (state) => state.tracks.find(t => t.type === 'video'),
    audioTracks: (state) => state.tracks.filter(t => t.type === 'audio'),
    subtitleTrack: (state) => state.tracks.find(t => t.type === 'subtitle'),
    markerTrack: (state) => state.tracks.find(t => t.type === 'marker'),
  },

  actions: {
    loadFromTimelineData(data) {
      if (!data) return
      // 从后端 timeline_data JSON 加载
      const trackTypes = ['video_track', 'audio_track', 'subtitle_track']
      const typeMap = { video_track: 'video', audio_track: 'audio', subtitle_track: 'subtitle' }

      for (const key of trackTypes) {
        const trackData = data[key]
        if (!trackData) continue
        const type = typeMap[key]
        const track = this.tracks.find(t => t.type === type)
        if (track && trackData.clips) {
          track.clips = trackData.clips.map(c => ({
            id: c.id,
            materialId: c.material_id,
            materialName: c.material_name,
            start: c.start,
            end: c.end,
            trimStart: c.trim_start || 0,
            trimEnd: c.trim_end || 0,
            speed: c.speed || 1,
            volume: c.volume || 1,
            marginBefore: c.margin_before || 0,
            marginAfter: c.margin_after || 0,
          }))
        }
      }

      // 从剪辑方案加载到视频轨道
      this._updateDuration()
    },

    loadFromPlanData(planData) {
      if (!planData || !planData.clips) return
      const videoTrack = this.tracks.find(t => t.id === 'v1')
      if (!videoTrack) return

      let currentTime = 0
      videoTrack.clips = planData.clips.map((clip, i) => {
        const startSec = parseTimeToSeconds(clip.start_time)
        const endSec = parseTimeToSeconds(clip.end_time)
        const clipStart = currentTime
        const clipEnd = clipStart + (endSec - startSec)
        currentTime = clipEnd
        return {
          id: `plan_${i}`,
          materialId: clip.material_id,
          materialName: clip.material_name || clip.purpose || `片段 ${i + 1}`,
          start: clipStart,
          end: clipEnd,
          trimStart: startSec,
          trimEnd: endSec,
          speed: 1,
          volume: 1,
          marginBefore: 0,
          marginAfter: 0,
          purpose: clip.purpose,
        }
      })
      this._updateDuration()
    },

    _updateDuration() {
      let maxEnd = 0
      for (const track of this.tracks) {
        for (const clip of track.clips) {
          maxEnd = Math.max(maxEnd, clip.end)
        }
      }
      this.duration = maxEnd
    },

    setZoom(zoom) {
      this.zoom = Math.max(0.1, Math.min(100, zoom))
    },

    zoomIn() { this.setZoom(this.zoom * 1.3) },
    zoomOut() { this.setZoom(this.zoom / 1.3) },

    setScrollX(x) {
      this.scrollX = Math.max(0, x)
    },

    setPlayheadPosition(position) {
      this.playheadPosition = Math.max(0, Math.min(this.duration, position))
    },

    selectClip(clipId) {
      this.selectedClipId = clipId
    },

    deselectClip() {
      this.selectedClipId = null
    },

    // 添加 AI 建议的片段（显示为虚线）
    addSuggestedClip(trackType, clip) {
      this.suggestedClips.push({ ...clip, trackType })
    },

    clearSuggestedClips() {
      this.suggestedClips = []
    },

    // 保存到后端
    async save(projectId) {
      if (!projectId) return
      try {
        const timelineData = {
          video_track: this.tracks.find(t => t.id === 'v1')?.toJSON() || null,
          audio_track: this.tracks.find(t => t.id === 'a1')?.toJSON() || null,
          subtitle_track: this.tracks.find(t => t.id === 's1')?.toJSON() || null,
        }
        await timelineApi.save(projectId, { timeline_data: timelineData })
      } catch (error) {
        console.error('保存时间线失败:', error)
      }
    },

    reset() {
      this.tracks.forEach(t => { t.clips = [] })
      this.duration = 0
      this.zoom = 1.0
      this.scrollX = 0
      this.playheadPosition = 0
      this.selectedClipId = null
      this.suggestedClips = []
    },
  },
})

// 工具函数
function parseTimeToSeconds(timeStr) {
  if (typeof timeStr === 'number') return timeStr
  if (!timeStr) return 0
  const parts = String(timeStr).split(':')
  if (parts.length === 3) {
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2])
  }
  if (parts.length === 2) {
    return parseInt(parts[0]) * 60 + parseFloat(parts[1])
  }
  return parseFloat(timeStr) || 0
}

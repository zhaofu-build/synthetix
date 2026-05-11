import { defineStore } from 'pinia'
import { subtitleApi } from '@/api/modules'

export const useSubtitleStore = defineStore('subtitle', {
  state: () => ({
    entries: [],       // [{id, startTime, endTime, text, speakerId, style}]
    speakers: [],      // [{id, name, color}]
    subtitleStyle: {
      fontName: '楷体',
      fontSize: 16,
      fontColor: '#ffffff',
      outlineColor: '#000000',
      outlineWidth: 2,
      bold: false,
      shadow: 0,
      position: 'bottom',
      alignment: 2,
      bgOpacity: 0,
      assBg: null,
    },
    stylePresets: [
      { name: '抖音风格', fontName: '黑体', fontSize: 20, fontColor: '#ffffff', outlineColor: '#000000', outlineWidth: 2, bold: true, shadow: 0, position: 'bottom' },
      { name: 'B站风格', fontName: '微软雅黑', fontSize: 14, fontColor: '#ffff00', outlineColor: '#000000', outlineWidth: 1, bold: false, shadow: 1, position: 'bottom' },
      { name: '极简', fontName: '微软雅黑', fontSize: 12, fontColor: '#ffffff', outlineColor: '#000000', outlineWidth: 0, bold: false, shadow: 0, position: 'bottom' },
    ],
    searchQuery: '',
    filterSpeakerId: null,
  }),

  getters: {
    filteredEntries: (state) => {
      let entries = state.entries
      if (state.filterSpeakerId) {
        entries = entries.filter(e => e.speakerId === state.filterSpeakerId)
      }
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase()
        entries = entries.filter(e => e.text.toLowerCase().includes(q))
      }
      return entries
    },
    speakerColorMap: (state) => {
      const colors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#00D1B2', '#9B59B6', '#3498DB']
      const map = {}
      state.speakers.forEach((s, i) => { map[s.id] = s.color || colors[i % colors.length] })
      return map
    },
  },

  actions: {
    loadFromSrt(srtText) {
      if (!srtText) return
      const blocks = srtText.trim().split(/\n\n+/)
      this.entries = []
      let speakerIdx = 0
      const speakerMap = {}

      for (const block of blocks) {
        const lines = block.trim().split('\n')
        if (lines.length < 3) continue
        const timeLine = lines[1]
        const match = timeLine.match(/(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})/)
        if (!match) continue
        const startTime = srtTimeToSeconds(match[1])
        const endTime = srtTimeToSeconds(match[2])
        const text = lines.slice(2).join('\n').trim()

        // 简单的说话人检测（如果有的话）
        const spkMatch = text.match(/^\[说话人(\d+)\]/)
        let speakerId = null
        if (spkMatch) {
          speakerId = `spk${spkMatch[1]}`
          if (!speakerMap[speakerId]) {
            speakerMap[speakerId] = { id: speakerId, name: `说话人 ${Object.keys(speakerMap).length + 1}`, color: null }
          }
        }

        this.entries.push({
          id: `sub_${this.entries.length}`,
          startTime,
          endTime,
          text: text.replace(/^\[说话人\d+\]\s*/, ''),
          speakerId,
        })
      }

      // 更新说话人列表
      this.speakers = Object.values(speakerMap)
    },

    updateEntry(id, updates) {
      const entry = this.entries.find(e => e.id === id)
      if (entry) Object.assign(entry, updates)
    },

    deleteEntry(id) {
      this.entries = this.entries.filter(e => e.id !== id)
    },

    setStyle(styleObj) {
      Object.assign(this.subtitleStyle, styleObj)
    },

    mergeEntries(ids) {
      if (ids.length < 2) return
      const toMerge = this.entries.filter(e => ids.includes(e.id))
      if (!toMerge.length) return
      const merged = {
        id: toMerge[0].id,
        startTime: Math.min(...toMerge.map(e => e.startTime)),
        endTime: Math.max(...toMerge.map(e => e.endTime)),
        text: toMerge.map(e => e.text).join(' '),
        speakerId: toMerge[0].speakerId,
      }
      this.entries = this.entries.filter(e => !ids.includes(e.id) || e.id === merged.id)
      const idx = this.entries.findIndex(e => e.id === merged.id)
      if (idx >= 0) this.entries[idx] = merged
    },

    setFilterSpeaker(speakerId) {
      this.filterSpeakerId = speakerId
    },

    setSearch(query) {
      this.searchQuery = query
    },

    updateSpeakerName(speakerId, name) {
      const spk = this.speakers.find(s => s.id === speakerId)
      if (spk) spk.name = name
    },

    async saveToProject(projectId) {
      if (!projectId) return
      try {
        await subtitleApi.save(projectId, {
          entries: this.entries,
          speakers: this.speakers,
          style: this.subtitleStyle,
        })
      } catch (error) {
        console.error('保存字幕失败:', error)
      }
    },

    async loadFromProject(projectId) {
      if (!projectId) return
      try {
        const data = await subtitleApi.load(projectId)
        if (data) {
          if (data.entries) this.entries = data.entries
          if (data.speakers) this.speakers = data.speakers
          if (data.style) Object.assign(this.subtitleStyle, data.style)
        }
      } catch (error) {
        // 404 is OK - no saved subtitles yet
      }
    },

    reset() {
      this.entries = []
      this.speakers = []
      this.searchQuery = ''
      this.filterSpeakerId = null
    },
  },
})

function srtTimeToSeconds(timeStr) {
  const [hms, ms] = timeStr.replace(',', '.').split('.')
  const [h, m, s] = hms.split(':').map(Number)
  return h * 3600 + m * 60 + s + (ms ? parseInt(ms) / 1000 : 0)
}

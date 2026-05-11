<template>
  <div class="subtitle-panel">
    <!-- 工具栏 -->
    <div class="subtitle-toolbar">
      <el-input v-model="subtitleStore.searchQuery" placeholder="搜索字幕..." size="small" clearable style="width: 160px" />
      <el-select v-model="subtitleStore.filterSpeakerId" placeholder="全部说话人" size="small" clearable style="width: 120px">
        <el-option v-for="spk in subtitleStore.speakers" :key="spk.id" :label="spk.name" :value="spk.id" />
      </el-select>
      <el-button size="small" @click="loadFromTranscription" :loading="loading">导入 ASR</el-button>
      <el-button size="small" @click="showStyleEditor = !showStyleEditor" title="字幕样式">
        <el-icon><Setting /></el-icon>
      </el-button>
    </div>

    <!-- 说话人面板 -->
    <div v-if="subtitleStore.speakers.length" class="speakers-bar">
      <SpeakerTag v-for="spk in subtitleStore.speakers" :key="spk.id"
                  :name="spk.name" :color="getSpeakerColor(spk.id)" :count="getSpeakerCount(spk.id)"
                  @rename="subtitleStore.updateSpeakerName(spk.id, $event)"
                  @click="subtitleStore.filterSpeakerId = spk.id" />
    </div>

    <!-- 字幕样式编辑器 -->
    <Transition name="panel-expand">
      <SubtitleStyleEditor v-if="showStyleEditor" :style-data="subtitleStore.currentStyle"
                           @update:style-data="subtitleStore.setStyle($event)" />
    </Transition>

    <!-- 字幕列表 -->
    <div class="subtitle-list" ref="listRef" @scroll="onListScroll">
      <div :style="{ height: totalListHeight + 'px', position: 'relative' }">
        <div v-for="entry in visibleEntries" :key="entry.id"
             class="subtitle-entry" :class="{ active: activeEntryId === entry.id }"
             :style="{ transform: `translateY(${entry._top}px)` }"
             @click="onEntryClick(entry)">
          <div class="entry-time">
            <span class="time-start">{{ formatSeconds(entry.startTime) }}</span>
            <span class="time-arrow">→</span>
            <span class="time-end">{{ formatSeconds(entry.endTime) }}</span>
          </div>
          <SpeakerTag v-if="entry.speakerId" :name="getSpeakerName(entry.speakerId)"
                      :color="getSpeakerColor(entry.speakerId)" :compact="true" />
          <div v-if="editingId === entry.id" class="entry-edit">
            <el-input v-model="editText" type="textarea" :rows="2" size="small" />
            <div class="edit-actions">
              <el-button size="small" type="primary" @click="saveEdit(entry)">保存</el-button>
              <el-button size="small" @click="editingId = null">取消</el-button>
            </div>
          </div>
          <div v-else class="entry-text" @dblclick="startEdit(entry.id)">
            {{ entry.text }}
          </div>
          <div class="entry-actions">
            <el-button text size="small" @click.stop="subtitleStore.deleteEntry(entry.id)" title="删除">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
      <div v-if="!subtitleStore.filteredEntries.length" class="empty-tip">
        {{ subtitleStore.entries.length ? '没有匹配的字幕' : '暂无字幕，点击"导入 ASR"从视频转录' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Delete, Setting } from '@element-plus/icons-vue'
import { useSubtitleStore } from '@/store/modules/subtitle'
import { useTimelineStore } from '@/store/modules/timeline'
import { useProjectStore } from '@/store/modules/project'
import { agentApi } from '@/api/modules'
import SpeakerTag from './SpeakerTag.vue'
import SubtitleStyleEditor from './SubtitleStyleEditor.vue'

const subtitleStore = useSubtitleStore()
const timelineStore = useTimelineStore()
const projectStore = useProjectStore()

const loading = ref(false)
const activeEntryId = ref(null)
const editingId = ref(null)
const editText = ref('')
const showStyleEditor = ref(false)

// Virtual scroll
const listRef = ref(null)
const ITEM_HEIGHT = 56
const BUFFER = 5
const scrollTop = ref(0)

const allEntries = computed(() => subtitleStore.filteredEntries)
const totalListHeight = computed(() => allEntries.value.length * ITEM_HEIGHT)

const visibleEntries = computed(() => {
  const list = allEntries.value
  if (list.length <= 50) {
    return list.map((e, i) => ({ ...e, _top: i * ITEM_HEIGHT }))
  }
  const containerH = listRef.value?.clientHeight || 400
  const start = Math.max(0, Math.floor(scrollTop.value / ITEM_HEIGHT) - BUFFER)
  const end = Math.min(list.length, Math.ceil((scrollTop.value + containerH) / ITEM_HEIGHT) + BUFFER)
  const slice = list.slice(start, end)
  return slice.map((e, i) => ({ ...e, _top: (start + i) * ITEM_HEIGHT }))
})

const onListScroll = () => {
  if (listRef.value) scrollTop.value = listRef.value.scrollTop
}

const formatSeconds = (sec) => {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const getSpeakerColor = (id) => subtitleStore.speakerColorMap[id] || '#909399'
const getSpeakerName = (id) => subtitleStore.speakers.find(s => s.id === id)?.name || id
const getSpeakerCount = (id) => subtitleStore.entries.filter(e => e.speakerId === id).length

const onEntryClick = (entry) => {
  activeEntryId.value = entry.id
  timelineStore.setPlayheadPosition(entry.startTime)
}

const startEdit = (id) => {
  const entry = subtitleStore.entries.find(e => e.id === id)
  if (entry) {
    editingId.value = id
    editText.value = entry.text
  }
}

const saveEdit = (entry) => {
  subtitleStore.updateEntry(entry.id, { text: editText.value })
  editingId.value = null
}

const loadFromTranscription = async () => {
  if (!projectStore.projectId) return
  loading.value = true
  try {
    // 获取项目素材
    const materials = projectStore.materials
    if (!materials.length) {
      return
    }
    // 对第一个素材进行 ASR
    const video = materials[0]
    const result = await agentApi.execute({ tool: 'transcribe_video', params: { video_id: video.id } })
    if (result?.success) {
      subtitleStore.loadFromSrt(result.subtitle)
    }
  } catch (error) {
    console.error('导入 ASR 失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.subtitle-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.subtitle-toolbar {
  display: flex;
  gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.speakers-bar {
  display: flex;
  gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  flex-wrap: wrap;
}
.speaker-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid;
  font-size: 11px;
}
.speaker-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.speaker-name {
  border: none;
  background: none;
  font-size: 11px;
  width: 60px;
  outline: none;
  color: inherit;
}
.speaker-stats { color: var(--el-text-color-placeholder); font-size: 10px; }
.subtitle-list {
  flex: 1;
  overflow-y: auto;
  position: relative;
}
.subtitle-entry {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  cursor: pointer;
  transition: background 0.15s;
  position: absolute;
  left: 0;
  right: 0;
  height: 56px;
  box-sizing: border-box;
}
.subtitle-entry:hover { background: var(--el-fill-color-lighter); }
.subtitle-entry.active { background: var(--el-color-primary-light-9); }
.entry-time {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-family: monospace;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.time-arrow { color: var(--el-text-color-placeholder); }
.entry-speaker {
  font-size: 10px;
  color: #fff;
  padding: 0 6px;
  border-radius: 8px;
  flex-shrink: 0;
}
.entry-text {
  flex: 1;
  font-size: 13px;
  min-width: 0;
  word-break: break-all;
}
.entry-edit { width: 100%; }
.edit-actions { display: flex; gap: 4px; margin-top: 4px; }
.entry-actions { flex-shrink: 0; opacity: 0; }
.subtitle-entry:hover .entry-actions { opacity: 1; }
.empty-tip {
  padding: 20px;
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
</style>

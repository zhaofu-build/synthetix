<template>
  <div class="clip-plan-panel">
    <!-- 配置表单（可折叠） -->
    <div class="config-section" :class="{ collapsed: configCollapsed }">
      <div class="config-toggle" @click="configCollapsed = !configCollapsed">
        <span class="config-toggle-title">剪辑方案配置</span>
        <el-icon class="config-toggle-arrow"><ArrowRight /></el-icon>
      </div>
      <div v-show="!configCollapsed" class="config-body">
        <el-form label-position="top" size="small">
          <el-form-item label="创意描述">
            <el-input v-model="creative" type="textarea" :rows="3"
                      placeholder="描述你想要的视频效果..." />
          </el-form-item>
          <div class="config-row">
            <el-form-item label="目标时长(秒)">
              <el-input-number v-model="targetDuration" :min="10" :max="300" :step="5" />
            </el-form-item>
            <el-form-item label="风格">
              <el-select v-model="style">
                <el-option label="动感" value="动感" />
                <el-option label="舒缓" value="舒缓" />
                <el-option label="电影感" value="电影感" />
                <el-option label="纪录片" value="纪录片" />
              </el-select>
            </el-form-item>
          </div>
          <el-button type="primary" size="small" :loading="store.planLoading" @click="handleGenerate" style="width:100%">
            <el-icon><MagicStick /></el-icon> 生成方案
          </el-button>
          <el-button size="small" @click="showTemplateSelector = true" style="width:100%">
            <el-icon><Grid /></el-icon> 选择模板
          </el-button>
        </el-form>
      </div>
    </div>

    <!-- 方案结果 -->
    <el-skeleton v-if="store.planLoading" :rows="6" animated />
    <div v-else-if="plan && plan.clips && plan.clips.length" class="plan-section">
      <!-- 方案头部 -->
      <div class="plan-header">
        <span>剪辑方案 ({{ plan.clips.length }} 片段，{{ plan.totalDuration || targetDuration }}s)</span>
        <div class="plan-header-actions">
          <el-button text size="small" @click="configCollapsed = false">修改配置</el-button>
          <el-button text size="small" @click="handleRegenerate">重新生成</el-button>
        </div>
      </div>

      <!-- 片段快捷操作 -->
      <div class="clip-toolbar">
        <el-button text size="small" @click="undo" :disabled="!undoStack.length">
          <el-icon><RefreshLeft /></el-icon> 撤销
        </el-button>
        <el-button text size="small" @click="redo" :disabled="!redoStack.length">
          <el-icon><RefreshRight /></el-icon> 重做
        </el-button>
        <span class="toolbar-sep">|</span>
        <el-button text size="small" @click="selectAllClips">全选</el-button>
        <el-button text size="small" @click="invertSelection">反选</el-button>
        <el-button text size="small" type="danger" @click="deleteSelected" :disabled="!selectedClips.length">
          删除选中({{ selectedClips.length }})
        </el-button>
        <el-button text size="small" @click="mergeSelected" :disabled="selectedClips.length < 2">
          合并选中
        </el-button>
      </div>

      <!-- 增强时间轴 -->
      <div class="timeline-visual">
        <div class="timeline-ruler">
          <span v-for="tick in rulerTicks" :key="tick" class="ruler-tick"
                :style="{ left: tick.pct + '%' }">{{ tick.label }}</span>
        </div>
        <div class="timeline-tracks">
          <div class="timeline-bar">
            <div v-for="(clip, i) in plan.clips" :key="i" class="timeline-clip"
                 :style="clipStyle(clip, i)"
                 :class="{ active: hoveredClip === i }"
                 @mouseenter="hoveredClip = i"
                 @mouseleave="hoveredClip = -1"
                 @click="editClip(clip, i)">
              <span class="clip-label">{{ clip.purpose || `片段${i + 1}` }}</span>
              <span class="clip-time">{{ formatTime(clip.start_time) }} - {{ formatTime(clip.end_time) }}</span>
            </div>
          </div>
        </div>
        <div class="timeline-legend">
          <span v-for="(clip, i) in plan.clips" :key="i" class="legend-item"
                :class="{ active: hoveredClip === i }"
                @mouseenter="hoveredClip = i" @mouseleave="hoveredClip = -1">
            <span class="legend-dot" :style="{ background: clipColor(i) }"></span>
            #{{ i + 1 }}
          </span>
        </div>
      </div>

      <!-- 片段列表（支持拖拽排序） -->
      <div class="clips-list">
        <TransitionGroup name="list">
        <div v-for="(clip, i) in plan.clips" :key="i"
             class="clip-item" :class="{ active: hoveredClip === i, dragging: dragIdx === i, 'drag-over': dragOverIdx === i }"
             draggable="true"
             @mouseenter="hoveredClip = i" @mouseleave="hoveredClip = -1"
             @dragstart="onDragStart($event, i)" @dragover.prevent="onDragOver($event, i)"
             @dragend="onDragEnd($event)" @drop="onDrop($event, i)">
          <div class="clip-color-bar" :style="{ background: clipColor(i) }"></div>
          <div class="clip-thumb" :style="thumbStyle(clip)">
            <span class="clip-thumb-time">{{ clipDuration(clip) }}s</span>
          </div>
          <div class="clip-info">
            <div class="clip-name">{{ clip.material_name || clip.purpose || `片段 ${i + 1}` }}</div>
            <div class="clip-meta">
              <span>{{ formatTime(clip.start_time) }} → {{ formatTime(clip.end_time) }}</span>
              <span class="clip-duration">{{ clipDuration(clip) }}s</span>
            </div>
          </div>
          <div class="clip-purpose">{{ clip.purpose }}</div>
          <div class="clip-actions">
            <el-button text size="small" @click="editClip(clip, i)">编辑</el-button>
            <el-button text size="small" type="danger" @click="removeClip(i)">删除</el-button>
          </div>
        </div>
        </TransitionGroup>
      </div>
    </div>

    <!-- 空状态 -->
    <el-empty v-else-if="!store.planLoading" description="暂无剪辑方案，请配置后点击生成" />

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑片段" width="360">
      <el-form label-width="60px" size="small">
        <el-form-item label="开始"><el-input v-model="editingClip.start_time" /></el-form-item>
        <el-form-item label="结束"><el-input v-model="editingClip.end_time" /></el-form-item>
        <el-form-item label="用途"><el-input v-model="editingClip.purpose" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveClipEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模板选择器 -->
    <PlanTemplateSelector v-if="showTemplateSelector" @apply="applyTemplate" @close="showTemplateSelector = false" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { MagicStick, ArrowRight, RefreshLeft, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { parseSeconds, clipColor } from '@/utils/formatUtils'
import ClipCard from './ClipCard.vue'
import PlanTemplateSelector from './PlanTemplateSelector.vue'
import { useDragReorder } from '@/composables/useDragReorder'

const store = useProjectStore()

const creative = ref('')
const targetDuration = ref(30)
const style = ref('动感')
const editDialogVisible = ref(false)
const editingClip = ref({})
const editingIndex = ref(-1)
const showTemplateSelector = ref(false)
const versionHistory = ref([])
const currentVersionIndex = ref(-1)
const hoveredClip = ref(-1)
const configCollapsed = ref(false)

const { dragIndex: dragIdx, dropIndex: dragOverIdx, onDragStart, onDragOver, onDragEnd, onDrop } = useDragReorder({
  onReorder: (from, to) => {
    const clips = plan.value.clips
    const [moved] = clips.splice(from, 1)
    clips.splice(to, 0, moved)
    store.saveField('plan_data', plan.value)
  },
})
const selectedClips = ref([])

const undoStack = ref([])
const redoStack = ref([])

const pushUndo = () => {
  if (plan.value?.clips) {
    undoStack.value.push(JSON.parse(JSON.stringify(plan.value.clips)))
    redoStack.value = []
    if (undoStack.value.length > 30) undoStack.value.shift()
  }
}
const undo = () => {
  if (!undoStack.value.length) return
  redoStack.value.push(JSON.parse(JSON.stringify(plan.value.clips)))
  plan.value.clips = undoStack.value.pop()
  store.saveField('plan_data', plan.value)
}
const redo = () => {
  if (!redoStack.value.length) return
  undoStack.value.push(JSON.parse(JSON.stringify(plan.value.clips)))
  plan.value.clips = redoStack.value.pop()
  store.saveField('plan_data', plan.value)
}
const selectAllClips = () => { selectedClips.value = plan.value.clips.map((_, i) => i) }
const invertSelection = () => {
  const all = plan.value.clips.map((_, i) => i)
  selectedClips.value = all.filter(i => !selectedClips.value.includes(i))
}
const deleteSelected = () => {
  if (!selectedClips.value.length) return
  pushUndo()
  plan.value.clips = plan.value.clips.filter((_, i) => !selectedClips.value.includes(i))
  store.saveField('plan_data', plan.value)
  selectedClips.value = []
}
const mergeSelected = () => {
  if (selectedClips.value.length < 2) return
  pushUndo()
  const sorted = [...selectedClips.value].sort((a, b) => a - b)
  const first = plan.value.clips[sorted[0]]
  const last = plan.value.clips[sorted[sorted.length - 1]]
  first.end_time = last.end_time
  first.purpose = first.purpose || last.purpose
  plan.value.clips = plan.value.clips.filter((_, i) => !sorted.includes(i) || i === sorted[0])
  store.saveField('plan_data', plan.value)
  selectedClips.value = []
}

// 模板应用
const applyTemplate = (tpl) => {
  creative.value = tpl.creative
  targetDuration.value = tpl.duration
  style.value = tpl.style
}

// 版本快照
const saveVersion = () => {
  if (!plan.value?.clips) return
  const snapshot = {
    timestamp: Date.now(),
    clips: JSON.parse(JSON.stringify(plan.value.clips)),
  }
  versionHistory.value.push(snapshot)
  if (versionHistory.value.length > 20) versionHistory.value.shift()
  currentVersionIndex.value = versionHistory.value.length - 1
  ElMessage.success('已保存版本快照')
}

const restoreVersion = (idx) => {
  const snapshot = versionHistory.value[idx]
  if (!snapshot) return
  pushUndo()
  plan.value.clips = JSON.parse(JSON.stringify(snapshot.clips))
  store.saveField('plan_data', plan.value)
  currentVersionIndex.value = idx
}

const plan = computed(() => store.project.planData || null)

const totalDuration = computed(() => plan.value?.totalDuration || targetDuration.value || 30)

const rulerTicks = computed(() => {
  const total = totalDuration.value
  const step = total <= 30 ? 5 : total <= 60 ? 10 : total <= 120 ? 15 : 30
  const ticks = []
  for (let t = 0; t <= total; t += step) {
    ticks.push({ pct: (t / total) * 100, label: `${t}s` })
  }
  return ticks
})

const handleGenerate = async () => {
  if (!creative.value.trim()) {
    ElMessage.warning('请输入创意描述')
    return
  }
  configCollapsed.value = true
  await store.generatePlan({
    creative: creative.value,
    targetDuration: targetDuration.value,
    style: style.value,
  })
}

const handleRegenerate = async () => {
  if (store.project.planData) {
    try {
      await ElMessageBox.confirm('重新生成将覆盖当前方案，是否继续？', '提示', {
        confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
      })
    } catch { return }
  }
  configCollapsed.value = false
  store.project.planData = null
}

const editClip = (clip, index) => {
  editingClip.value = { ...clip }
  editingIndex.value = index
  editDialogVisible.value = true
}

const saveClipEdit = () => {
  if (plan.value && plan.value.clips && editingIndex.value >= 0) {
    pushUndo()
    plan.value.clips[editingIndex.value] = { ...editingClip.value }
    store.saveField('plan_data', plan.value)
  }
  editDialogVisible.value = false
}

const removeClip = (index) => {
  if (plan.value && plan.value.clips) {
    pushUndo()
    plan.value.clips.splice(index, 1)
    store.saveField('plan_data', plan.value)
  }
}

const clipDuration = (clip) => {
  const s = parseSeconds(clip.start_time)
  const e = parseSeconds(clip.end_time)
  return (e - s).toFixed(1)
}

const clipStyle = (clip, i) => {
  const total = totalDuration.value
  const s = parseSeconds(clip.start_time)
  const e = parseSeconds(clip.end_time)
  const left = (s / total) * 100
  const width = Math.max(2, ((e - s) / total) * 100)
  return {
    left: left + '%',
    width: width + '%',
    background: clipColor(i),
  }
}

const formatTime = (t) => t || '00:00:00'

const thumbStyle = (clip) => {
  // Use material thumbnail if available, otherwise colored placeholder
  if (clip.thumbnail) {
    return { backgroundImage: `url(${clip.thumbnail})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  }
  const idx = plan.value?.clips?.indexOf(clip) ?? 0
  return { background: clipColor(idx) + '33' }
}
</script>

<style scoped>
.clip-plan-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 配置折叠 */
.config-section {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}
.config-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  transition: background 0.15s;
}
.config-toggle:hover { background: var(--el-fill-color-light); }
.config-toggle-arrow {
  transition: transform 0.2s;
  font-size: 12px;
}
.config-section:not(.collapsed) .config-toggle-arrow {
  transform: rotate(90deg);
}
.config-body { padding: 0 12px 12px; }
.config-row { display: flex; gap: 16px; }
.config-row .el-form-item { flex: 1; }

/* 方案区 */
.plan-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 13px;
  padding: 0 4px;
}
.plan-header-actions { display: flex; gap: 4px; }

/* 增强时间轴 */
.timeline-visual {
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 8px;
}
.timeline-ruler {
  position: relative;
  height: 16px;
  margin-bottom: 4px;
}
.ruler-tick {
  position: absolute;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  transform: translateX(-50%);
  top: 0;
}
.timeline-tracks { position: relative; }
.timeline-bar {
  position: relative;
  height: 36px;
  border-radius: 4px;
  background: var(--el-fill-color);
  overflow: hidden;
}
.timeline-clip {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 0 4px;
  transition: filter 0.15s, box-shadow 0.15s;
  overflow: hidden;
  min-width: 24px;
}
.timeline-clip:hover, .timeline-clip.active {
  filter: brightness(1.15);
  box-shadow: 0 0 0 2px rgba(255,255,255,0.5);
  z-index: 2;
}
.clip-label {
  font-size: 10px;
  color: #fff;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
.clip-time {
  font-size: 9px;
  color: rgba(255,255,255,0.8);
  white-space: nowrap;
}
.timeline-legend {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: color 0.15s;
}
.legend-item.active { color: var(--el-text-color-primary); font-weight: 600; }
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* 片段列表 */
.clips-list { display: flex; flex-direction: column; gap: 4px; }
.clip-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.clip-item:hover, .clip-item.active {
  background: var(--el-fill-color-light);
  border-color: var(--el-border-color-lighter);
}
.clip-item[draggable="true"] { cursor: grab; }
.clip-item.dragging { opacity: 0.4; }
.clip-item.drag-over { border-top: 2px solid var(--el-color-primary); }
.clip-color-bar {
  width: 4px;
  height: 28px;
  border-radius: 2px;
  flex-shrink: 0;
}
.clip-thumb {
  width: 36px;
  height: 20px;
  border-radius: 3px;
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
}
.clip-thumb-time {
  font-size: 8px;
  color: #fff;
  background: rgba(0,0,0,0.5);
  padding: 0 2px;
  border-radius: 1px;
  line-height: 1.4;
}
.clip-info { flex-shrink: 0; min-width: 100px; }
.clip-name { font-size: 12px; font-weight: 600; }
.clip-meta { font-size: 11px; color: var(--el-text-color-secondary); display: flex; gap: 8px; }
.clip-duration { color: var(--el-color-primary); font-weight: 500; }
.clip-purpose {
  flex: 1;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.clip-actions { display: flex; gap: 2px; flex-shrink: 0; }
.clip-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  font-size: 12px;
}
.toolbar-sep {
  color: var(--el-border-color);
  margin: 0 2px;
}
</style>

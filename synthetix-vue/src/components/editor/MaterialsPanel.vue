<template>
  <div class="materials-panel"
       @dragover.prevent="dragOver = true"
       @dragleave="dragOver = false"
       @drop.prevent="handleDrop">
    <!-- 拖拽遮罩 -->
    <div v-if="dragOver" class="drop-overlay">
      <el-icon size="32"><Upload /></el-icon>
      <span>拖拽素材文件到此处上传</span>
    </div>

    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <div class="toolbar-left">
        <el-input v-model="searchKeyword" placeholder="搜索素材..." size="small" clearable
                  prefix-icon="Search" class="search-input" />
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="list"><el-icon><List /></el-icon></el-radio-button>
          <el-radio-button value="grid"><el-icon><Grid /></el-icon></el-radio-button>
        </el-radio-group>
      </div>
      <div class="toolbar-right">
        <el-button size="small" @click="store.refreshMaterials()" :loading="store.materialLoading">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="primary" size="small" @click="showManager = true">
          <el-icon><FolderOpened /></el-icon> 素材管理
        </el-button>
      </div>
    </div>

    <!-- 筛选标签 -->
    <div class="filter-bar">
      <el-tag v-for="f in filterOptions" :key="f.value" size="small"
              :type="activeFilter === f.value ? '' : 'info'"
              :effect="activeFilter === f.value ? 'dark' : 'plain'"
              class="filter-tag" @click="activeFilter = f.value">
        {{ f.label }}
      </el-tag>
      <el-select v-model="activeTagFilter" placeholder="标签筛选" size="small" clearable filterable allow-create
                 class="tag-filter-select" :disabled="!allTags.length">
        <el-option v-for="t in allTags" :key="t" :label="t" :value="t" />
      </el-select>
    </div>

    <!-- 批量操作栏 -->
    <div v-if="selectedIds.length" class="batch-bar">
      <span class="batch-info">已选 {{ selectedIds.length }} 项</span>
      <el-button size="small" @click="batchAddToProject">添加到项目</el-button>
      <el-button size="small" type="danger" @click="batchRemove">批量移出</el-button>
      <el-button text size="small" @click="selectedIds = []">取消选择</el-button>
    </div>

    <!-- 上传进度条 -->
    <div v-if="uploadProgress !== null" class="upload-progress">
      <el-progress :percentage="uploadProgress" :stroke-width="4" :show-text="true" />
      <el-button text size="small" @click="cancelUpload">取消</el-button>
    </div>

    <!-- 骨架屏 -->
    <el-skeleton v-if="store.materialLoading && !projectMaterials.length" :rows="4" animated />

    <!-- 列表视图 -->
    <el-table v-else-if="viewMode === 'list' && filteredMaterials.length" :data="filteredMaterials"
              stripe size="small" style="width: 100%"
              @selection-change="onSelectionChange">
      <el-table-column type="selection" width="36" />
      <el-table-column label="素材" min-width="120">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:4px">
            <el-icon v-if="analyzingId === row.id" class="is-loading" size="14"><Loading /></el-icon>
            <el-icon v-else-if="hasAnalysis(row)" size="14" color="var(--el-color-success)"><CircleCheck /></el-icon>
            <el-icon v-else-if="getFileIcon(row) === 'headset'" size="14" color="var(--el-color-primary)"><Headset /></el-icon>
            <el-icon v-else-if="getFileIcon(row) === 'picture'" size="14" color="var(--el-color-primary)"><Picture /></el-icon>
            <el-icon v-else-if="getFileIcon(row) === 'document'" size="14" color="var(--el-text-color-secondary)"><Document /></el-icon>
            <el-icon v-else size="14" color="var(--el-text-color-placeholder)"><VideoPlay /></el-icon>
            <span class="material-name" @click="previewMaterial(row)">{{ row.videoName || row.video_name || row.name }}</span>
            <el-tag v-if="row.isTemp" size="small" type="warning">临时</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="时长" width="65">
        <template #default="{ row }">{{ row.durationHms || row.duration_hms || '-' }}</template>
      </el-table-column>
      <el-table-column label="描述" min-width="100">
        <template #default="{ row }">
          <el-tooltip placement="top" :disabled="!row.description">
            <template #content>
              <div class="desc-tooltip" v-if="isSegmentJson(row.description)">
                <div v-for="(seg, i) in parseSegments(row.description)" :key="i" class="seg-item">
                  <span class="seg-time">{{ seg.start }}s-{{ seg.end }}s</span>
                  <span class="seg-desc">{{ seg.desc }}</span>
                </div>
                <div v-if="parseField(row.description, 'transcription')" class="seg-item" style="margin-top:4px;border-top:1px solid var(--el-border-color-lighter);padding-top:4px">
                  <span class="seg-time">字幕</span>
                  <span class="seg-desc">{{ parseField(row.description, 'transcription') }}</span>
                </div>
                <div v-if="parseField(row.description, 'asr_status')" class="seg-item" style="color:var(--el-text-color-secondary);font-size:11px">
                  ASR: {{ parseField(row.description, 'asr_status') }}
                </div>
              </div>
              <span v-else>{{ row.description }}</span>
            </template>
            <span class="text-ellipsis desc-clickable" @click="openEditDesc(row)">{{ formatDescBrief(row.description) }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="标签" width="120">
        <template #default="{ row }">
          <div class="cell-tags">
            <el-tag v-for="t in parseTags(row.tags)" :key="t" size="small" type="info" class="cell-tag">{{ t }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="" width="100" fixed="right">
        <template #default="{ row }">
          <span class="action-link" @click="openEditMaterial(row)">编辑</span>
          <el-divider direction="vertical" />
          <span class="action-link danger" @click="removeFromProject(row)">移出</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 网格视图（虚拟滚动） -->
    <div v-else-if="viewMode === 'grid' && filteredMaterials.length"
         ref="gridContainerEl" class="materials-grid-virtual" @scroll="onGridScroll">
      <div class="virtual-spacer" :style="{ height: gridTotalHeight + 'px', position: 'relative' }">
        <div v-for="item in gridVisibleItems" :key="item.data.id" class="mat-card"
             :style="{ position: 'absolute', top: item.top + 'px', left: item.left, width: item.width }"
             @click="detailMaterial = item.data">
          <div class="mat-thumb" :class="getThumbClass(item.data)">
            <img v-if="getFileType(item.data) === 'image' && (item.data.webPath || item.data.web_path)"
                 :src="assetUrl(item.data.webPath || item.data.web_path)" class="mat-thumb-img" />
            <el-icon v-else size="24" class="mat-thumb-icon">
              <Headset v-if="getFileType(item.data) === 'audio'" />
              <Picture v-else-if="getFileType(item.data) === 'image'" />
              <Document v-else-if="getFileType(item.data) === 'document'" />
              <VideoPlay v-else />
            </el-icon>
            <span v-if="item.data.durationHms || item.data.duration_hms" class="mat-duration">
              {{ item.data.durationHms || item.data.duration_hms }}
            </span>
            <span v-if="analyzingId === item.data.id" class="mat-badge analyzing">分析中</span>
            <span v-else-if="hasAnalysis(item.data)" class="mat-badge analyzed">已分析</span>
          </div>
          <div class="mat-card-info">
            <div class="mat-card-name">{{ item.data.videoName || item.data.video_name || item.data.name }}</div>
            <div v-if="parseTags(item.data.tags).length" class="mat-card-tags">
              <el-tag v-for="t in parseTags(item.data.tags).slice(0, 3)" :key="t" size="small" type="info">{{ t }}</el-tag>
            </div>
          </div>
          <div class="mat-card-actions" @click.stop>
            <el-button text size="small" @click="openEditMaterial(item.data)">编辑</el-button>
            <el-button text size="small" type="danger" @click="removeFromProject(item.data)">移出</el-button>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-else-if="!store.materialLoading" description="暂无素材，点击素材管理添加" :image-size="60" />

    <!-- 素材管理弹窗 -->
    <el-dialog v-model="showManager" title="素材管理" width="750" top="4vh" destroy-on-close>
      <el-tabs v-model="managerTab">
        <el-tab-pane label="本地素材" name="local">
          <div class="manager-toolbar">
            <el-button type="primary" size="small" @click="triggerUpload">
              <el-icon><Upload /></el-icon> 上传素材
            </el-button>
            <el-button size="small" @click="store.refreshMaterials()" :loading="store.materialLoading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-divider direction="vertical" />
            <el-tag v-for="f in filterOptions" :key="f.value" size="small"
                    :type="managerTypeFilter === f.value ? '' : 'info'"
                    :effect="managerTypeFilter === f.value ? 'dark' : 'plain'"
                    style="cursor:pointer;margin-right:4px" @click="managerTypeFilter = f.value">
              {{ f.label }}
            </el-tag>
            <template v-if="managerTags.length">
              <el-divider direction="vertical" />
              <el-tag v-for="t in managerTags" :key="t" size="small"
                      :type="managerTagFilter === t ? 'warning' : 'info'"
                      :effect="managerTagFilter === t ? 'dark' : 'plain'"
                      style="cursor:pointer;margin-right:4px" @click="managerTagFilter = managerTagFilter === t ? '' : t">
                {{ t }}
              </el-tag>
            </template>
          </div>
      <el-table :data="managerFilteredMaterials" stripe size="small" v-loading="store.materialLoading"
                max-height="calc(80vh - 200px)" style="width: 100%">
        <el-table-column label="素材" min-width="100">
          <template #default="{ row }">
            <div style="display:flex;align-items:center;gap:4px">
              <el-icon v-if="getFileIcon(row) === 'headset'" size="14" color="var(--el-color-primary)"><Headset /></el-icon>
              <el-icon v-else-if="getFileIcon(row) === 'picture'" size="14" color="var(--el-color-primary)"><Picture /></el-icon>
              <el-icon v-else-if="getFileIcon(row) === 'document'" size="14" color="var(--el-text-color-secondary)"><Document /></el-icon>
              <el-icon v-else size="14" color="var(--el-text-color-placeholder)"><VideoPlay /></el-icon>
              <span class="material-name" @click="previewMaterial(row)">{{ row.videoName || row.video_name || row.name }}</span>
              <el-tag v-if="row.isTemp" size="small" type="warning">临时</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="55">
          <template #default="{ row }">
            <span style="font-size:12px;color:var(--el-text-color-secondary)">{{ { video: '视频', audio: '音频', image: '图片', document: '文档' }[getFileType(row)] || '视频' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="60">
          <template #default="{ row }">{{ row.durationHms || row.duration_hms || '-' }}</template>
        </el-table-column>
        <el-table-column label="描述" min-width="140">
          <template #default="{ row }">
            <el-tooltip placement="top" :disabled="!row.description">
              <template #content>
                <div class="desc-tooltip" v-if="isSegmentJson(row.description)">
                  <div v-for="(seg, i) in parseSegments(row.description)" :key="i" class="seg-item">
                    <span class="seg-time">{{ seg.start }}s-{{ seg.end }}s</span>
                    <span class="seg-desc">{{ seg.desc }}</span>
                  </div>
                  <div v-if="parseField(row.description, 'transcription')" class="seg-item" style="margin-top:4px;border-top:1px solid var(--el-border-color-lighter);padding-top:4px">
                    <span class="seg-time">字幕</span>
                    <span class="seg-desc">{{ parseField(row.description, 'transcription') }}</span>
                  </div>
                  <div v-if="parseField(row.description, 'asr_status')" class="seg-item" style="color:var(--el-text-color-secondary);font-size:11px">
                    ASR: {{ parseField(row.description, 'asr_status') }}
                  </div>
                </div>
                <span v-else>{{ row.description }}</span>
              </template>
              <span class="text-ellipsis desc-clickable" @click="openEditDesc(row)">{{ formatDescBrief(row.description) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="标签" width="120">
          <template #default="{ row }">
            <div class="cell-tags">
              <el-tag v-for="t in parseTags(row.tags)" :key="t" size="small" type="info" class="cell-tag">{{ t }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <span class="action-link" @click="openEditMaterial(row)">编辑</span>
              <el-divider direction="vertical" />
              <span v-if="!isInProject(row.id)" class="action-link" @click="addToProject(row)">使用</span>
              <span v-else class="action-disabled">已使用</span>
              <el-divider direction="vertical" />
              <span class="action-link" :class="{ disabled: analyzingId === row.id }" @click="aiAnalyze(row)">
                {{ analyzingId === row.id ? (analyzeStep || '预处理中') : 'AI预处理' }}
              </span>
              <el-divider direction="vertical" />
              <span class="action-link danger" @click="deleteMaterial(row)">删除</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
        </el-tab-pane>
        <el-tab-pane label="在线搜索" name="online">
          <div class="online-search">
            <div class="online-search-bar">
              <el-select v-model="onlineSource" size="small" style="width:100px;flex-shrink:0">
                <el-option label="全部" value="all" />
                <el-option label="Pexels" value="pexels" />
                <el-option label="Pixabay" value="pixabay" />
              </el-select>
              <el-input v-model="onlineQuery" placeholder="搜索关键词..." size="small" clearable @keyup.enter="searchOnline" />
              <el-button type="primary" size="small" :loading="onlineLoading" @click="searchOnline">搜索</el-button>
            </div>
            <div v-if="onlineResults.length" class="online-grid">
              <div v-for="item in onlineResults" :key="item.id" class="online-card" @click="previewOnline(item)">
                <img v-if="item.image" :src="item.image" class="online-thumb" alt="" />
                <video v-else :src="item.videoUrl" muted loop class="online-thumb"
                       @mouseenter="$event.target.play()" @mouseleave="$event.target.pause()" />
                <div class="online-play-icon"><el-icon :size="24"><VideoPlay /></el-icon></div>
                <span class="online-provider">{{ item.provider }}</span>
                <div class="online-info" @click.stop>
                  <span class="online-duration">{{ item.duration }}s</span>
                  <el-button size="small" type="primary" @click="downloadOnline(item)" :loading="item.downloading">添加</el-button>
                </div>
              </div>
            </div>
            <el-empty v-else-if="!onlineLoading" description="搜索在线素材" :image-size="40" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="URL 下载" name="download">
          <div class="url-download-tab">
            <el-input v-model="downloadUrl" placeholder="粘贴素材链接，支持视频/音频/图片" size="small" clearable @keyup.enter="downloadVideo" />
            <el-button type="primary" size="small" :loading="downloading" @click="downloadVideo" style="margin-top: 10px">
              <el-icon><Download /></el-icon> 下载
            </el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 编辑素材弹窗 -->
    <el-dialog v-model="showEditMaterial" title="编辑素材" width="500" append-to-body destroy-on-close>
      <el-form label-position="top" size="small">
        <el-form-item label="素材名称">
          <el-input v-model="editName" placeholder="输入素材名称" />
        </el-form-item>
        <el-form-item label="标签">
          <div class="tag-editor">
            <el-tag v-for="t in editTags" :key="t" closable size="small" @close="editTags = editTags.filter(x => x !== t)">{{ t }}</el-tag>
            <el-input v-if="showTagInput" ref="tagInputRef" v-model="tagInputVal" size="small" style="width:100px"
                      @keyup.enter="addTag" @blur="addTag" />
            <el-button v-else size="small" @click="showTagInput = true; tagInputVal = ''">+ 标签</el-button>
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editDescText" type="textarea" :rows="8" placeholder="输入素材描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditMaterial = false">取消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveMaterialEdit">保存</el-button>
      </template>
    </el-dialog>

    <input ref="uploadInput" type="file" accept="video/*,audio/*,image/*,.srt,.ass,.vtt,.txt,.json" multiple style="display:none" @change="handleUpload" />

    <!-- 素材详情侧边栏 -->
    <Transition name="slide">
      <div v-if="detailMaterial" class="detail-sidebar">
        <div class="detail-header">
          <span class="detail-title">素材详情</span>
          <el-button text size="small" @click="detailMaterial = null"><el-icon><Close /></el-icon></el-button>
        </div>
        <div class="detail-body">
          <div class="detail-thumb" @click="previewMaterial(detailMaterial)">
            <img v-if="getFileType(detailMaterial) === 'image' && (detailMaterial.webPath || detailMaterial.web_path)"
                 :src="assetUrl(detailMaterial.webPath || detailMaterial.web_path)" style="width:100%;height:100%;object-fit:contain;border-radius:6px" />
            <el-icon v-else size="36">
              <Headset v-if="getFileType(detailMaterial) === 'audio'" />
              <Picture v-else-if="getFileType(detailMaterial) === 'image'" />
              <Document v-else-if="getFileType(detailMaterial) === 'document'" />
              <VideoPlay v-else />
            </el-icon>
          </div>
          <div class="detail-field">
            <label>名称</label>
            <span>{{ detailMaterial.videoName || detailMaterial.video_name || detailMaterial.name }}</span>
          </div>
          <div class="detail-field">
            <label>时长</label>
            <span>{{ detailMaterial.durationHms || detailMaterial.duration_hms || '-' }}</span>
          </div>
          <div class="detail-field">
            <label>描述</label>
            <span class="detail-desc">{{ detailMaterial.description || '暂无描述' }}</span>
          </div>
          <div class="detail-actions">
            <el-button size="small" @click="openEditMaterial(detailMaterial)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeFromProject(detailMaterial); detailMaterial = null">移出项目</el-button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 在线预览弹窗 -->
    <el-dialog v-model="showOnlinePreview" title="素材预览" width="640" append-to-body destroy-on-close>
      <div v-if="previewItem" class="online-preview">
        <video :src="previewItem.previewUrl || previewItem.videoUrl" controls autoplay class="online-preview-video" />
        <div class="online-preview-info">
          <span>时长: {{ previewItem.duration }}s</span>
          <el-button type="primary" @click="downloadOnline(previewItem)" :loading="previewItem.downloading">下载到素材库</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'
import { Upload, Download, Refresh, VideoPlay, List, Grid, Close, CircleCheck, Warning, Loading, Headset, Picture, Document } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { videoApi, aiApi } from '@/api/modules'
import { assetUrl, API_HOST } from '@/api/modules'

const store = useProjectStore()
const openMaterialPreview = inject('openMaterialPreview', () => {})

const showManager = ref(false)
const managerTab = ref('local')
const onlineQuery = ref('')
const onlineResults = ref([])
const onlineLoading = ref(false)
const onlineSource = ref('all')
const showOnlinePreview = ref(false)
const previewItem = ref(null)

const previewOnline = (item) => {
  previewItem.value = item
  showOnlinePreview.value = true
}

const searchOnline = async () => {
  if (!onlineQuery.value) return
  onlineLoading.value = true
  try {
    const resp = await fetch(`${API_HOST}/api/videos/search-online?query=${encodeURIComponent(onlineQuery.value)}&source=${onlineSource.value}`)
    const result = await resp.json()
    if (result.success && result.data?.videos) {
      onlineResults.value = result.data.videos.map(v => ({
        id: v.url,
        videoUrl: v.url,
        previewUrl: v.preview_url || v.url,
        duration: v.duration || 0,
        image: v.image || '',
        search_term: v.search_term || '',
      }))
    } else {
      onlineResults.value = []
      if (result.message) ElMessage.warning(result.message)
    }
  } catch (e) {
    console.error('在线搜索失败:', e)
    ElMessage.error('搜索失败，请检查网络')
  } finally {
    onlineLoading.value = false
  }
}

const downloadOnline = async (item) => {
  item.downloading = true
  try {
    const tags = item.search_term || onlineQuery.value || ''
    const resp = await fetch(`${API_HOST}/api/videos/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_url: item.videoUrl, tags }),
    })
    const result = await resp.json()
    if (result.success) {
      ElMessage.success('素材已下载')
      store.refreshMaterials()
    } else {
      ElMessage.error(result.message || '下载失败')
    }
  } catch (e) {
    ElMessage.error('下载失败')
  } finally {
    item.downloading = false
  }
}
const showEditMaterial = ref(false)
const downloadUrl = ref('')
const downloading = ref(false)
const analyzingId = ref(null)
const uploadInput = ref(null)
const editName = ref('')
const editDescText = ref('')
const editTags = ref([])
const showTagInput = ref(false)
const tagInputVal = ref('')
const activeTagFilter = ref('')
const managerTagFilter = ref('')
const managerTypeFilter = ref('all')

const managerTags = computed(() => {
  const tagSet = new Set()
  for (const m of store.materialLibrary) {
    for (const t of parseTags(m.tags)) tagSet.add(t)
  }
  return [...tagSet].sort()
})

const managerFilteredMaterials = computed(() => {
  let list = store.materialLibrary
  if (managerTypeFilter.value !== 'all') {
    list = list.filter(m => getFileType(m) === managerTypeFilter.value)
  }
  if (managerTagFilter.value) {
    list = list.filter(m => parseTags(m.tags).includes(managerTagFilter.value))
  }
  return list
})
const editingMaterial = ref(null)
const savingEdit = ref(false)
const searchKeyword = ref('')
const viewMode = ref('list')
const dragOver = ref(false)
const uploadProgress = ref(null)
const activeFilter = ref('all')
const selectedIds = ref([])
const detailMaterial = ref(null)
let uploadCtrl = null

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
  { label: '图片', value: 'image' },
  { label: '文档', value: 'document' },
]

const hasAnalysis = (mat) => {
  const desc = mat.description || ''
  if (!desc || desc === '-') return false
  try { return !!JSON.parse(desc)?.segments?.length } catch { return desc.length > 10 }
}

const projectMaterials = computed(() => store.materials || [])

const parseDuration = (m) => {
  const hms = m.durationHms || m.duration_hms || ''
  if (!hms) return m.duration || 0
  const parts = hms.split(':').map(Number)
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return parts[0] || 0
}

const filteredMaterials = computed(() => {
  let list = projectMaterials.value
  const filter = activeFilter.value
  if (filter !== 'all') list = list.filter(m => getFileType(m) === filter)
  const kw = searchKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(m => {
      const name = (m.videoName || m.video_name || m.name || '').toLowerCase()
      const desc = (m.description || '').toLowerCase()
      return name.includes(kw) || desc.includes(kw)
    })
  }
  if (activeTagFilter.value) {
    list = list.filter(m => parseTags(m.tags).includes(activeTagFilter.value))
  }
  return list
})

const onSelectionChange = (rows) => {
  selectedIds.value = rows.map(r => r.id)
}

const batchAddToProject = async () => {
  for (const id of selectedIds.value) {
    await store.addMaterialToProject(id)
  }
  ElMessage.success(`已添加 ${selectedIds.value.length} 个素材到项目`)
  selectedIds.value = []
}

const batchRemove = async () => {
  try {
    await ElMessageBox.confirm(`确定移出 ${selectedIds.value.length} 个素材？`, '提示', { type: 'warning' })
  } catch { return }
  for (const id of selectedIds.value) {
    await store.removeMaterialFromProject(id)
  }
  ElMessage.success('已批量移出')
  selectedIds.value = []
}

const isSegmentJson = (text) => {
  if (!text) return false
  try { return JSON.parse(text) && Array.isArray(JSON.parse(text).segments) } catch { return false }
}
const parseSegments = (text) => { try { return JSON.parse(text).segments || [] } catch { return [] } }
const parseField = (text, field) => { try { return JSON.parse(text)[field] || '' } catch { return '' } }
const parseTags = (tags) => { if (!tags) return []; return String(tags).split(',').map(t => t.trim()).filter(Boolean) }
const getFileType = (row) => row.fileType || row.file_type || 'video'
const getFileIcon = (row) => {
  const ft = getFileType(row)
  if (ft === 'audio') return 'headset'
  if (ft === 'image') return 'picture'
  if (ft === 'document') return 'document'
  return 'video'
}
const getThumbClass = (row) => `thumb-${getFileType(row)}`

const allTags = computed(() => {
  const tagSet = new Set()
  for (const m of store.materialLibrary) {
    for (const t of parseTags(m.tags)) tagSet.add(t)
  }
  for (const m of (store.materials || [])) {
    for (const t of parseTags(m.tags)) tagSet.add(t)
  }
  return [...tagSet].sort()
})
const formatDescBrief = (text) => {
  if (!text) return '-'
  if (isSegmentJson(text)) return parseSegments(text).map(s => `${s.start}s-${s.end}s ${s.desc}`).join('；')
  return text
}
const openEditDesc = (row) => { openEditMaterial(row) }

const openEditMaterial = (row) => {
  editingMaterial.value = row
  editName.value = row.videoName || row.video_name || row.name || ''
  const raw = row.description || ''
  editDescText.value = isSegmentJson(raw) ? JSON.stringify(JSON.parse(raw), null, 2) : raw
  editTags.value = parseTags(row.tags)
  showTagInput.value = false
  tagInputVal.value = ''
  showEditMaterial.value = true
}

const addTag = () => {
  const val = tagInputVal.value.trim()
  if (val && !editTags.value.includes(val)) {
    editTags.value.push(val)
  }
  tagInputVal.value = ''
  showTagInput.value = false
}

const saveMaterialEdit = async () => {
  if (!editingMaterial.value) return
  savingEdit.value = true
  let descToSave = editDescText.value
  try { descToSave = JSON.stringify(JSON.parse(descToSave)) } catch {}
  const tagsStr = editTags.value.join(',')
  try {
    await videoApi.updateVideoSource(editingMaterial.value.id, {
      video_name: editName.value.trim(),
      description: descToSave,
      tags: tagsStr || null,
    })
    editingMaterial.value.videoName = editName.value.trim()
    editingMaterial.value.video_name = editName.value.trim()
    editingMaterial.value.description = descToSave
    editingMaterial.value.tags = tagsStr || null
    showEditMaterial.value = false
    ElMessage.success('素材已更新')
  } catch (error) { ElMessage.error('更新失败') }
  finally { savingEdit.value = false }
}

const isInProject = (id) => (store.project.materialIds || []).includes(id)
const addToProject = async (row) => { await store.addMaterialToProject(row.id); ElMessage.success('已添加到项目') }
const removeFromProject = async (row) => { await store.removeMaterialFromProject(row.id); ElMessage.success('已从项目移出') }

const saveToLibrary = async (row) => {
  try {
    await videoApi.saveToLibrary(row.id)
    ElMessage.success('已存入素材库')
    store.refreshMaterials()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.message || '未知错误'))
  }
}

const deleteTempMaterial = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该临时素材？', '提示', { type: 'warning' })
    await videoApi.deleteTempMaterial(row.id)
    ElMessage.success('已删除')
    store.refreshMaterials()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败: ' + (e.message || '未知错误'))
  }
}

const previewMaterial = (row) => {
  const path = row.webPath || row.web_path || row.localPath || row.local_path
  const fileType = row.fileType || row.file_type || 'video'
  if (path) openMaterialPreview(assetUrl(path), fileType)
}
const triggerUpload = () => { uploadInput.value?.click() }

const handleUpload = async (e) => {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  await uploadFiles(files)
  e.target.value = ''
}

const handleDrop = async (e) => {
  dragOver.value = false
  const allowed = ['video/', 'audio/', 'image/']
  const files = Array.from(e.dataTransfer.files).filter(f => allowed.some(t => f.type.startsWith(t)))
  if (!files.length) { ElMessage.warning('请拖入素材文件（视频/音频/图片）'); return }
  await uploadFiles(files)
}

const uploadFiles = async (files) => {
  for (const file of files) {
    uploadCtrl = new AbortController()
    uploadProgress.value = 0
    try {
      const res = await videoApi.uploadFile(file)
      if (res.videoId && store.projectId) {
        await store.addMaterialToProject(res.videoId)
      }
      ElMessage.success(`${file.name} 上传成功`)
    } catch (error) {
      if (error.name !== 'CanceledError') ElMessage.error('上传失败: ' + error.message)
    }
  }
  uploadProgress.value = null
  uploadCtrl = null
  store.refreshMaterials()
}

const cancelUpload = () => {
  uploadCtrl?.abort()
  uploadProgress.value = null
}

const downloadVideo = async () => {
  const url = downloadUrl.value.trim()
  if (!url) { ElMessage.warning('请输入素材链接'); return }
  downloading.value = true
  try {
    await videoApi.downloadVideo({ url })
    ElMessage.success('下载完成')
    downloadUrl.value = ''
    managerTab.value = 'local'
    store.refreshMaterials()
  } catch (error) { ElMessage.error('下载失败: ' + error.message) }
  finally { downloading.value = false }
}

const analyzeStep = ref('')
const aiAnalyze = async (row) => {
  analyzingId.value = row.id
  analyzeStep.value = '画面分析中'
  try {
    const data = await videoApi.getVideoDescription(row.id)
    if (data.description) {
      row.description = data.description
      ElMessage.success('预处理完成（画面分析 + 字幕提取）')
    } else {
      ElMessage.warning('未获取到描述')
    }
  } catch (error) {
    ElMessage.error('分析失败: ' + (error.response?.data?.message || error.message))
  } finally {
    analyzingId.value = null
    analyzeStep.value = ''
  }
}

const deleteMaterial = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除这个素材？', '提示', { type: 'warning' })
    await videoApi.deleteSourceVideos(row.id)
    ElMessage.success('删除成功')
    store.refreshMaterials()
  } catch {}
}

// --- 虚拟网格（大量素材性能优化） ---
const gridContainerEl = ref(null)
const gridScrollTop = ref(0)
const gridContainerHeight = ref(600)
const CARD_W = 112
const CARD_H = 120
const GRID_GAP = 8
const GRID_BUF = 3

const gridCols = computed(() => {
  const w = gridContainerEl.value?.clientWidth || 350
  return Math.max(1, Math.floor((w + GRID_GAP) / (CARD_W + GRID_GAP)))
})

const gridTotalHeight = computed(() => {
  const rows = Math.ceil(filteredMaterials.value.length / gridCols.value)
  return rows * (CARD_H + GRID_GAP) + GRID_GAP
})

const gridVisibleItems = computed(() => {
  const cols = gridCols.value
  const rowH = CARD_H + GRID_GAP
  const firstRow = Math.max(0, Math.floor(gridScrollTop.value / rowH) - GRID_BUF)
  const lastRow = Math.ceil((gridScrollTop.value + gridContainerHeight.value) / rowH) + GRID_BUF
  const items = []
  for (let r = firstRow; r <= lastRow; r++) {
    for (let c = 0; c < cols; c++) {
      const idx = r * cols + c
      if (idx >= filteredMaterials.value.length) break
      items.push({
        data: filteredMaterials.value[idx],
        top: r * rowH + GRID_GAP,
        left: `${c * (CARD_W + GRID_GAP) + GRID_GAP}px`,
        width: `${CARD_W}px`,
      })
    }
  }
  return items
})

let gridResizeObs = null
onMounted(() => {
  if (gridContainerEl.value) {
    gridContainerHeight.value = gridContainerEl.value.clientHeight
    gridResizeObs = new ResizeObserver(entries => {
      for (const e of entries) gridContainerHeight.value = e.contentRect.height
    })
    gridResizeObs.observe(gridContainerEl.value)
  }
})
onUnmounted(() => gridResizeObs?.disconnect())

const onGridScroll = (e) => { gridScrollTop.value = e.target.scrollTop }
</script>

<style scoped>
.materials-panel {
  padding: 8px 12px;
  position: relative;
}

/* 拖拽遮罩 */
.drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: rgba(64, 158, 255, 0.1);
  border: 2px dashed var(--el-color-primary);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--el-color-primary);
  font-size: 14px;
  font-weight: 500;
}

/* 工具栏 */
.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}
.search-input { width: 140px; }
.toolbar-right { display: flex; gap: 8px; }

/* 筛选标签 */
.filter-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.filter-tag { cursor: pointer; }
.tag-filter-select { width: 120px; flex-shrink: 0; }

/* 批量操作栏 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--el-color-primary-light-9);
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 12px;
}
.batch-info { font-weight: 600; }

/* 上传进度 */
.upload-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.upload-progress :deep(.el-progress) { flex: 1; }

/* 网格视图 */
.materials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
}
.materials-grid-virtual {
  flex: 1;
  overflow-y: auto;
  position: relative;
}
.virtual-spacer { position: relative; }
.mat-card {
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.mat-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.mat-thumb {
  aspect-ratio: 16/9;
  background: var(--el-fill-color-lighter);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.mat-thumb-icon { color: var(--el-text-color-placeholder); }
.mat-thumb-img { width: 100%; height: 100%; object-fit: cover; border-radius: 6px; }
.thumb-image .mat-thumb-icon { display: none; }
.mat-duration {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 10px;
  color: #fff;
  background: rgba(0,0,0,0.6);
  padding: 0 4px;
  border-radius: 2px;
}
.mat-card-info { padding: 4px 6px; }
.mat-card-name {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mat-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  margin-top: 2px;
}
.mat-badge {
  position: absolute;
  top: 2px;
  left: 4px;
  font-size: 9px;
  padding: 0 3px;
  border-radius: 2px;
  line-height: 1.4;
}
.mat-badge.analyzed { background: var(--el-color-success-light-7); color: var(--el-color-success); }
.mat-badge.analyzing { background: var(--el-color-warning-light-7); color: var(--el-color-warning); animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.filter-sep { color: var(--el-border-color); margin: 0 2px; font-size: 12px; line-height: 24px; }
.online-search { display: flex; flex-direction: column; gap: 8px; min-height: 200px; }
.online-search-bar { display: flex; gap: 6px; }
.online-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; max-height: 400px; overflow-y: auto; }
.online-card { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; overflow: hidden; position: relative; cursor: pointer; transition: border-color 0.2s; }
.online-provider { position: absolute; top: 4px; left: 4px; font-size: 9px; background: rgba(0,0,0,0.6); color: #fff; padding: 1px 4px; border-radius: 3px; z-index: 1; }
.online-card:hover { border-color: var(--el-color-primary); }
.online-card:hover .online-play-icon { opacity: 1; }
.online-thumb { width: 100%; height: 80px; object-fit: cover; display: block; }
.online-play-icon { position: absolute; top: 28px; left: 50%; transform: translateX(-50%); opacity: 0; transition: opacity 0.2s; color: #fff; text-shadow: 0 1px 4px rgba(0,0,0,0.5); pointer-events: none; }
.online-info { display: flex; align-items: center; justify-content: space-between; padding: 4px 6px; }
.online-duration { font-size: 10px; color: var(--el-text-color-secondary); font-family: monospace; }
.online-preview-video { width: 100%; max-height: 360px; background: #000; }
.online-preview-info { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
.url-download-tab { padding: 20px 0; }
.tag-editor { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.cell-tags { display: flex; flex-wrap: wrap; gap: 2px; }
.cell-tag { font-size: 10px; height: 18px; line-height: 16px; padding: 0 4px; }
.mat-card-tags { display: flex; flex-wrap: wrap; gap: 2px; margin-top: 2px; }
.mat-card-tags .el-tag { font-size: 9px; height: 16px; line-height: 14px; }
.mat-card-actions {
  padding: 0 6px 4px;
  display: flex;
  justify-content: center;
}

.manager-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.material-name { cursor: pointer; color: var(--el-color-primary); }
.material-name:hover { text-decoration: underline; }
.text-ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 100%; }
.desc-clickable { cursor: pointer; }
.desc-clickable:hover { color: var(--el-color-primary); }
.desc-tooltip { max-width: 360px; }
.seg-item { display: flex; gap: 6px; margin-bottom: 4px; font-size: 12px; line-height: 1.5; }
.seg-time { color: var(--el-color-primary); white-space: nowrap; font-weight: 600; }
.seg-desc { color: #ddd; }
.action-btns { display: flex; align-items: center; gap: 0; font-size: 12px; white-space: nowrap; }
.action-link { cursor: pointer; color: var(--el-color-primary); }
.action-link:hover { text-decoration: underline; }
.action-link.disabled { pointer-events: none; color: var(--el-text-color-disabled); }
.action-link.danger { color: var(--el-color-danger); }
.action-disabled { color: var(--el-text-color-disabled); font-size: 12px; }

/* 素材详情侧边栏 */
.detail-sidebar {
  position: absolute;
  top: 0;
  right: 0;
  width: 280px;
  height: 100%;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-lighter);
  z-index: 15;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.08);
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  font-size: 13px;
}
.detail-body { flex: 1; overflow-y: auto; padding: 12px; }
.detail-thumb {
  aspect-ratio: 16/9;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-bottom: 12px;
  color: var(--el-text-color-placeholder);
}
.detail-field { margin-bottom: 10px; }
.detail-field label {
  display: block;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 2px;
  font-weight: 600;
}
.detail-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
}
.detail-actions { display: flex; gap: 8px; margin-top: 16px; }
.slide-enter-active, .slide-leave-active { transition: transform 0.25s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }
</style>

<template>
  <div class="knowledge-base">
    <!-- 搜索 -->
    <div class="toolbar">
      <el-input v-model="searchQuery" placeholder="搜索知识库..." clearable style="width: 240px"
                @keyup.enter="doSearch">
        <template #append>
          <el-button @click="doSearch" :loading="searching">搜索</el-button>
        </template>
      </el-input>
      <el-select v-model="searchMode" size="small" style="width: 90px" placeholder="检索模式">
        <el-option label="混合" value="hybrid" />
        <el-option label="关键词" value="bm25" />
        <el-option label="语义" value="vector" />
      </el-select>
      <el-button type="primary" @click="showAdd = true">添加记录</el-button>
      <el-button size="small" @click="loadStats">统计</el-button>
    </div>

    <!-- 统计信息 -->
    <div v-if="stats.total_documents" class="kb-stats">
      <el-tag type="info" size="small">共 {{ stats.total_documents }} 条</el-tag>
      <el-tag v-for="(count, cat) in stats.categories" :key="cat" size="small">{{ cat }}: {{ count }}</el-tag>
    </div>

    <!-- 搜索结果 -->
    <div v-if="results.length" style="margin-top: 12px">
      <h4>搜索结果 ({{ results.length }})</h4>
      <div v-if="results.length > 50" ref="kbListEl" class="kb-virtual-list" @scroll="onKbScroll">
        <div :style="{ height: kbTotalHeight + 'px', position: 'relative' }">
          <div v-for="item in kbVisibleItems" :key="item.index" class="kb-row"
               :style="{ position: 'absolute', top: item.top + 'px', left: 0, right: 0 }">
            <span class="kb-content">{{ item.data.content }}</span>
            <span class="kb-source">{{ item.data.source }}</span>
            <span class="kb-score">{{ (item.data.score * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
      <el-table v-else :data="results" stripe size="small">
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="score" label="相关度" width="80">
          <template #default="{ row }">{{ (row.score * 100).toFixed(0) }}%</template>
        </el-table-column>
      </el-table>
    </div>

    <el-empty v-if="!results.length && searched" description="未找到相关记录" />

    <!-- 添加对话框 -->
    <el-dialog v-model="showAdd" title="添加知识记录" width="500px" append-to-body>
      <el-form label-width="60px">
        <el-form-item label="内容">
          <el-input v-model="addForm.content" type="textarea" :rows="4" placeholder="输入要记录的内容" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="addForm.source" placeholder="可选，如：素材分析、用户备注" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="addForm.tagsStr" placeholder="逗号分隔，如：分析, 备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="doAdd">添加</el-button>
      </template>
    </el-dialog>

    <el-empty v-if="!searched" description="输入关键词搜索知识库" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useProjectStore } from '@/store/modules/project'
import { agentApi } from '@/api/modules'

const { t } = useI18n()
const store = useProjectStore()
const searchQuery = ref('')
const searching = ref(false)
const searched = ref(false)
const results = ref([])
const showAdd = ref(false)
const adding = ref(false)
const addForm = ref({ content: '', source: '', tagsStr: '' })
const searchMode = ref('hybrid')
const stats = ref({})

const doSearch = async () => {
  if (!searchQuery.value.trim()) return
  if (!store.projectId) return ElMessage.warning('请先打开项目')
  searching.value = true
  searched.value = true
  try {
    const res = await agentApi.execute({
      tool_name: 'knowledge_search',
      arguments: { query: searchQuery.value, project_id: store.projectId, mode: searchMode.value },
    })
    results.value = res?.results || []
  } catch {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

const doAdd = async () => {
  if (!addForm.value.content.trim()) return ElMessage.warning('请输入内容')
  if (!store.projectId) return ElMessage.warning('请先打开项目')
  adding.value = true
  try {
    const tags = addForm.value.tagsStr ? addForm.value.tagsStr.split(',').map(t => t.trim()).filter(Boolean) : []
    await agentApi.execute({
      tool_name: 'knowledge_add',
      arguments: {
        content: addForm.value.content,
        source: addForm.value.source,
        tags,
        project_id: store.projectId,
      },
    })
    ElMessage.success('已添加')
    showAdd.value = false
    addForm.value = { content: '', source: '', tagsStr: '' }
  } catch {
    ElMessage.error('添加失败')
  } finally {
    adding.value = false
  }
}

const loadStats = async () => {
  if (!store.projectId) return
  try {
    const res = await agentApi.execute({ tool: 'knowledge_stats', params: { project_id: store.projectId } })
    if (res?.stats) stats.value = res.stats
  } catch {}
}

// --- 知识库虚拟列表（> 50 条结果时启用） ---
const kbListEl = ref(null)
const kbScrollTop = ref(0)
const kbContainerH = ref(400)
const KB_ROW_H = 48
const KB_BUF = 5

const kbTotalHeight = computed(() => results.value.length * KB_ROW_H)

const kbVisibleItems = computed(() => {
  const first = Math.max(0, Math.floor(kbScrollTop.value / KB_ROW_H) - KB_BUF)
  const last = Math.min(results.value.length, Math.ceil((kbScrollTop.value + kbContainerH.value) / KB_ROW_H) + KB_BUF)
  const items = []
  for (let i = first; i < last; i++) {
    items.push({ data: results.value[i], index: i, top: i * KB_ROW_H })
  }
  return items
})

let kbResizeObs = null
onMounted(() => {
  if (kbListEl.value) {
    kbContainerH.value = kbListEl.value.clientHeight
    kbResizeObs = new ResizeObserver(entries => {
      for (const e of entries) kbContainerH.value = e.contentRect.height
    })
    kbResizeObs.observe(kbListEl.value)
  }
})
onUnmounted(() => kbResizeObs?.disconnect())

const onKbScroll = (e) => { kbScrollTop.value = e.target.scrollTop }
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.kb-stats {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.kb-virtual-list {
  height: 400px;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
}
.kb-row {
  height: 48px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  font-size: 13px;
}
.kb-row:hover { background: var(--el-fill-color-light); }
.kb-content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-source { width: 100px; color: var(--el-text-color-secondary); flex-shrink: 0; }
.kb-score { width: 50px; text-align: right; color: var(--el-color-primary); font-weight: 600; flex-shrink: 0; }
</style>

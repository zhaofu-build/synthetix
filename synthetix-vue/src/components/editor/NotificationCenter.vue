<template>
  <el-popover placement="bottom-end" :width="320" trigger="click">
    <template #reference>
      <el-badge :value="unread" :hidden="!unread" :max="99">
        <el-button text circle><el-icon :size="18"><Bell /></el-icon></el-button>
      </el-badge>
    </template>
    <div class="notif-panel">
      <div class="notif-header">
        <span class="notif-title">通知</span>
        <el-button text size="small" @click="markAllRead" :disabled="!unread">全部已读</el-button>
      </div>
      <div class="notif-list">
        <div v-for="n in notifications.slice(0, 20)" :key="n.id"
             class="notif-item" :class="{ unread: !n.read, [n.type]: true }"
             @click="markRead(n.id)">
          <el-icon class="notif-icon">
            <CircleCheck v-if="n.type === 'success'" />
            <Warning v-else-if="n.type === 'warning'" />
            <CircleClose v-else-if="n.type === 'error'" />
            <InfoFilled v-else />
          </el-icon>
          <div class="notif-body">
            <div class="notif-msg">{{ n.title }}</div>
            <div v-if="n.message" class="notif-detail">{{ n.message }}</div>
            <div class="notif-time">{{ formatNotifTime(n.time) }}</div>
          </div>
        </div>
        <div v-if="!notifications.length" class="notif-empty">暂无通知</div>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { Bell, CircleCheck, Warning, CircleClose, InfoFilled } from '@element-plus/icons-vue'
import { useNotification } from '@/composables/useNotification'

const { notifications, unread, markRead, markAllRead } = useNotification()

const formatNotifTime = (iso) => {
  const d = new Date(iso)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<style scoped>
.notif-panel { max-height: 400px; display: flex; flex-direction: column; }
.notif-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.notif-title { font-weight: 600; font-size: 14px; }
.notif-list { overflow-y: auto; max-height: 340px; }
.notif-item { display: flex; gap: 8px; padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.notif-item:hover { background: var(--el-fill-color-light); }
.notif-item.unread { background: var(--el-color-primary-light-9); }
.notif-icon { flex-shrink: 0; margin-top: 2px; }
.notif-item.success .notif-icon { color: var(--el-color-success); }
.notif-item.warning .notif-icon { color: var(--el-color-warning); }
.notif-item.error .notif-icon { color: var(--el-color-danger); }
.notif-item.info .notif-icon { color: var(--el-color-info); }
.notif-body { flex: 1; min-width: 0; }
.notif-msg { font-size: 13px; font-weight: 500; }
.notif-detail { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }
.notif-time { font-size: 10px; color: var(--el-text-color-placeholder); margin-top: 2px; }
.notif-empty { text-align: center; padding: 20px; color: var(--el-text-color-placeholder); font-size: 13px; }
</style>

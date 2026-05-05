import { ref, computed } from 'vue'

const notifications = ref([])
let idCounter = 0

export function useNotification() {
  const unread = computed(() => notifications.value.filter(n => !n.read).length)

  const push = (type, title, message = '') => {
    notifications.value.unshift({
      id: ++idCounter,
      type,
      title,
      message,
      time: new Date().toISOString(),
      read: false,
    })
    if (notifications.value.length > 100) {
      notifications.value = notifications.value.slice(0, 100)
    }
  }

  const markRead = (id) => {
    const n = notifications.value.find(n => n.id === id)
    if (n) n.read = true
  }

  const markAllRead = () => {
    notifications.value.forEach(n => n.read = true)
  }

  const clearAll = () => {
    notifications.value = []
  }

  const remove = (id) => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  return { notifications, unread, push, markRead, markAllRead, clearAll, remove }
}

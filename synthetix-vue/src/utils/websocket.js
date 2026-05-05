/**
 * WebSocket 客户端
 *
 * 连接后端 /ws 端点，提供实时消息推送。
 * 支持自动重连、按 channel 订阅、事件回调。
 */
import { API_HOST } from '@/utils/request'

class WSClient {
  constructor() {
    this._ws = null
    this._listeners = new Map() // event -> Set<callback>
    this._reconnectTimer = null
    this._reconnectAttempts = 0
    this._maxReconnectDelay = 30000
    this._connected = false
  }

  get connected() {
    return this._connected
  }

  connect(channel = '') {
    if (this._ws && this._ws.readyState <= 1) return

    const base = API_HOST.replace(/^http/, 'ws')
    const url = `${base}/ws${channel ? '/' + channel : ''}`

    this._ws = new WebSocket(url)

    this._ws.onopen = () => {
      this._connected = true
      this._reconnectAttempts = 0
      this._emit('_connected', {})
    }

    this._ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this._emit(data.type || data.event || 'message', data)
      } catch {
        this._emit('message', { raw: event.data })
      }
    }

    this._ws.onclose = () => {
      this._connected = false
      this._emit('_disconnected', {})
      this._scheduleReconnect(channel)
    }

    this._ws.onerror = () => {
      this._connected = false
    }
  }

  disconnect() {
    clearTimeout(this._reconnectTimer)
    if (this._ws) {
      this._ws.close()
      this._ws = null
    }
    this._connected = false
  }

  send(data) {
    if (this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  on(event, callback) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, new Set())
    }
    this._listeners.get(event).add(callback)
    return () => this.off(event, callback)
  }

  off(event, callback) {
    this._listeners.get(event)?.delete(callback)
  }

  _emit(event, data) {
    this._listeners.get(event)?.forEach((cb) => {
      try { cb(data) } catch { /* ignore */ }
    })
    this._listeners.get('*')?.forEach((cb) => {
      try { cb(event, data) } catch { /* ignore */ }
    })
  }

  _scheduleReconnect(channel) {
    if (this._reconnectAttempts >= 10) return
    const delay = Math.min(1000 * 2 ** this._reconnectAttempts, this._maxReconnectDelay)
    this._reconnectAttempts++
    this._reconnectTimer = setTimeout(() => this.connect(channel), delay)
  }
}

// 单例
const wsClient = new WSClient()

export default wsClient

/**
 * Vue composable: 在组件中使用 WebSocket
 * @param {string} channel - ws 子通道（如 'render'、'system'）
 */
export function useWebSocket(channel = '') {
  const connect = () => wsClient.connect(channel)
  const disconnect = () => wsClient.disconnect()
  const send = (data) => wsClient.send(data)
  const on = (event, cb) => wsClient.on(event, cb)
  const off = (event, cb) => wsClient.off(event, cb)

  return { connect, disconnect, send, on, off, connected: wsClient.connected }
}

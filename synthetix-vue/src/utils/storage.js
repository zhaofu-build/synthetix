// 本地存储工具
import { APP_CONSTANTS } from '@/constants'

class StorageUtil {
  // 获取数据
  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : defaultValue
    } catch (error) {
      console.warn(`Error getting item from localStorage: ${key}`, error)
      return defaultValue
    }
  }

  // 设置数据
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch (error) {
      console.error(`Error setting item to localStorage: ${key}`, error)
    }
  }

  // 删除数据
  remove(key) {
    try {
      localStorage.removeItem(key)
    } catch (error) {
      console.error(`Error removing item from localStorage: ${key}`, error)
    }
  }

  // 清空所有数据
  clear() {
    try {
      localStorage.clear()
    } catch (error) {
      console.error('Error clearing localStorage', error)
    }
  }

  // 检查是否存在某个键
  has(key) {
    return localStorage.getItem(key) !== null
  }

  // 获取所有键
  keys() {
    try {
      return Object.keys(localStorage)
    } catch (error) {
      console.error('Error getting localStorage keys', error)
      return []
    }
  }
  
  // 专门用于主题的获取和设置
  getTheme(defaultValue = 'dark') {
    return this.get(APP_CONSTANTS.STORAGE_KEYS.THEME, defaultValue)
  }
  
  setTheme(theme) {
    this.set(APP_CONSTANTS.STORAGE_KEYS.THEME, theme)
  }
  
  // 专门用于用户信息的获取和设置
  getUserInfo(defaultValue = null) {
    return this.get(APP_CONSTANTS.STORAGE_KEYS.USER_INFO, defaultValue)
  }
  
  setUserInfo(userInfo) {
    this.set(APP_CONSTANTS.STORAGE_KEYS.USER_INFO, userInfo)
  }
  
  // 专门用于配置的获取和设置
  getConfig(defaultValue = null) {
    return this.get(APP_CONSTANTS.STORAGE_KEYS.CONFIG, defaultValue)
  }
  
  setConfig(config) {
    this.set(APP_CONSTANTS.STORAGE_KEYS.CONFIG, config)
  }
}

export const storage = new StorageUtil()
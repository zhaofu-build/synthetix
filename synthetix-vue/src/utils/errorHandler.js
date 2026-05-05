// 全局错误处理工具
import { ElMessage } from 'element-plus'

class ErrorHandler {
  constructor() {
    this.errorHandlers = []
    this.setupGlobalErrorHandler()
  }

  // 设置全局错误处理
  setupGlobalErrorHandler() {
    // 捕获 JavaScript 运行时错误
    window.addEventListener('error', (event) => {
      this.handleError({
        type: 'javascript',
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error
      })
    })

    // 捕获 Promise 拒绝错误
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError({
        type: 'promise',
        message: event.reason?.message || event.reason,
        error: event.reason
      })
    })
  }

  // 添加错误处理函数
  addErrorHandler(handler) {
    if (typeof handler === 'function') {
      this.errorHandlers.push(handler)
    }
  }

  // 处理错误
  handleError(errorInfo) {
    console.error('Global Error Handler:', errorInfo)
    
    // 执行所有注册的错误处理函数
    this.errorHandlers.forEach(handler => {
      try {
        handler(errorInfo)
      } catch (handlerError) {
        console.error('Error in error handler:', handlerError)
      }
    })
  }

  // 格式化错误信息
  formatError(error) {
    if (error instanceof Error) {
      return {
        name: error.name,
        message: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString()
      }
    }
    
    return {
      message: String(error),
      timestamp: new Date().toISOString()
    }
  }

  // 报告错误
  reportError(error, context = {}) {
    const errorInfo = {
      ...this.formatError(error),
      context,
      userAgent: navigator.userAgent,
      url: window.location.href
    }

    // 这里可以添加发送错误到服务器的逻辑
    console.group('Error Report')
    console.log('Error:', errorInfo)
    console.groupEnd()
  }
}

const errorHandler = new ErrorHandler()

// 导出设置函数以符合 pixGallery-vue 的模式
export function setupErrorHandler(app) {
  // 在开发环境中添加错误处理
  if (!import.meta.env.PROD) {
    errorHandler.addErrorHandler((errorInfo) => {
      ElMessage.error(`错误: ${errorInfo.message || '发生未知错误'}`)
    })
  }

  // 将错误处理器添加到 Vue 应用实例
  app.config.errorHandler = (err, instance, info) => {
    errorHandler.handleError({
      type: 'vue',
      message: err.message,
      error: err,
      info,
      component: instance
    })
  }
}

export default errorHandler
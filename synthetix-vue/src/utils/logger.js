// 简单的日志系统
class Logger {
  constructor() {
    this.isEnabled = !import.meta.env.PROD
  }

  log(level, message, ...args) {
    if (!this.isEnabled) return

    const timestamp = new Date().toISOString()
    const logMessage = `[${timestamp}] ${level.toUpperCase()}: ${message}`

    switch (level.toLowerCase()) {
      case 'error':
        console.error(logMessage, ...args)
        break
      case 'warn':
        console.warn(logMessage, ...args)
        break
      case 'info':
        console.info(logMessage, ...args)
        break
      case 'debug':
        console.debug(logMessage, ...args)
        break
      default:
        console.log(logMessage, ...args)
    }
  }

  info(message, ...args) {
    this.log('info', message, ...args)
  }

  warn(message, ...args) {
    this.log('warn', message, ...args)
  }

  error(message, ...args) {
    this.log('error', message, ...args)
  }

  debug(message, ...args) {
    this.log('debug', message, ...args)
  }
}

export default new Logger()
// 性能监控工具
class PerformanceMonitor {
  constructor() {
    this.isEnabled = !import.meta.env.PROD
    this.metrics = {}
  }

  // 记录开始时间
  start(markName) {
    if (!this.isEnabled) return

    performance.mark(markName)
  }

  // 记录结束时间并计算差值
  end(markName, measureName) {
    if (!this.isEnabled) return

    performance.mark(`${markName}-end`)
    performance.measure(measureName, markName, `${markName}-end`)

    const measure = performance.getEntriesByName(measureName)[0]
    this.metrics[measureName] = measure.duration
    console.log(`${measureName}: ${measure.duration.toFixed(2)}ms`)
    
    return measure.duration
  }

  // 获取性能指标
  getMetrics() {
    return this.metrics
  }

  // 清除性能数据
  clear() {
    this.metrics = {}
    performance.clearMarks()
    performance.clearMeasures()
  }

  // 监控函数执行时间
  async monitorAsync(fn, name) {
    if (!this.isEnabled) {
      return await fn()
    }

    this.start(name)
    try {
      const result = await fn()
      this.end(name, name)
      return result
    } catch (error) {
      this.end(name, name)
      throw error
    }
  }

  // 监控同步函数执行时间
  monitorSync(fn, name) {
    if (!this.isEnabled) {
      return fn()
    }

    this.start(name)
    try {
      const result = fn()
      this.end(name, name)
      return result
    } catch (error) {
      this.end(name, name)
      throw error
    }
  }
}

export default new PerformanceMonitor()
import { rippleDirective } from './ripple'

// 导出设置函数以符合 pixGallery-vue 的模式
export function setupDirectives(app) {
  app.directive('ripple', rippleDirective)
}

export default {
  install(app) {
    setupDirectives(app)
  }
}
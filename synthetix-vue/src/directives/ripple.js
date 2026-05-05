// 波纹效果指令
export const rippleDirective = {
  mounted(el, binding) {
    // 创建波纹效果
    createRippleEffect(el, binding)
  },
  updated(el, binding) {
    // 更新波纹效果
    createRippleEffect(el, binding)
  },
  unmounted(el) {
    // 移除事件监听器
    el.removeEventListener('mousedown', el._rippleMouseDownHandler)
  }
}

function createRippleEffect(el, binding) {
  // 检查是否启用波纹效果
  const enabled = binding.value !== false
  
  if (!enabled) {
    // 如果禁用，移除事件监听器
    el.removeEventListener('mousedown', el._rippleMouseDownHandler)
    return
  }

  // 如果已经添加了事件监听器，则先移除
  if (el._rippleMouseDownHandler) {
    el.removeEventListener('mousedown', el._rippleMouseDownHandler)
  }

  // 创建波纹效果的事件处理函数
  el._rippleMouseDownHandler = function(event) {
    // 创建波纹元素
    const ripple = document.createElement('span')
    const rect = el.getBoundingClientRect()
    
    // 计算点击位置相对于元素的坐标
    const size = Math.max(rect.width, rect.height)
    const x = event.clientX - rect.left - size / 2
    const y = event.clientY - rect.top - size / 2
    
    // 设置波纹样式
    ripple.style.width = `${size}px`
    ripple.style.height = `${size}px`
    ripple.style.left = `${x}px`
    ripple.style.top = `${y}px`
    ripple.style.position = 'absolute'
    ripple.style.borderRadius = '50%'
    ripple.style.backgroundColor = 'rgba(255, 255, 255, 0.6)'
    ripple.style.transform = 'scale(0)'
    ripple.style.animation = 'ripple 0.6s linear'
    ripple.style.pointerEvents = 'none'
    ripple.style.overflow = 'hidden'
    
    // 添加必要的 CSS 动画
    if (!document.querySelector('#ripple-style')) {
      const style = document.createElement('style')
      style.id = 'ripple-style'
      style.textContent = `
        @keyframes ripple {
          to {
            transform: scale(2);
            opacity: 0;
          }
        }
      `
      document.head.appendChild(style)
    }
    
    // 将波纹元素添加到目标元素中
    el.style.position = el.style.position || 'relative'
    el.style.overflow = 'hidden'
    el.appendChild(ripple)
    
    // 动画结束后移除波纹元素
    setTimeout(() => {
      if (ripple && ripple.parentNode === el) {
        el.removeChild(ripple)
      }
    }, 600)
  }

  // 添加事件监听器
  el.addEventListener('mousedown', el._rippleMouseDownHandler)
}
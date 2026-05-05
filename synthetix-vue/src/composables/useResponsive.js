import { ref, onMounted, onUnmounted, computed } from 'vue'

export function useResponsive() {
  const width = ref(window.innerWidth)
  const height = ref(window.innerHeight)

  const onResize = () => {
    width.value = window.innerWidth
    height.value = window.innerHeight
  }

  onMounted(() => window.addEventListener('resize', onResize))
  onUnmounted(() => window.removeEventListener('resize', onResize))

  const isMobile = computed(() => width.value < 768)
  const isTablet = computed(() => width.value >= 768 && width.value < 1024)
  const isDesktop = computed(() => width.value >= 1024)
  const isLargeDesktop = computed(() => width.value >= 1440)

  return { width, height, isMobile, isTablet, isDesktop, isLargeDesktop }
}

import { createRouter, createWebHistory } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/editor',
    children: [
      {
        path: '/editor',
        name: 'UnifiedEditor',
        component: () => import('@/components/editor/UnifiedEditor.vue'),
        meta: { title: 'AI剪辑工作台' }
      },
      // 旧页面兼容（仍可通过 URL 直接访问）
      {
        path: '/ai-clip',
        name: 'AIClip',
        component: () => import('@/components/AIClip.vue'),
        meta: { title: '对话式AI剪辑' }
      },
      {
        path: '/video-stitching',
        name: 'VideoStitching',
        component: () => import('@/components/VideoStitching.vue'),
        meta: { title: '工作流AI剪辑' }
      },
      {
        path: '/comic-drama',
        name: 'ComicDrama',
        component: () => import('@/components/ComicDrama.vue'),
        meta: { title: '漫剧制作' }
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  NProgress.start()
  document.title = to.meta.title || 'Synthetix'
  next()
})

router.afterEach(() => {
  NProgress.done()
})

export default router

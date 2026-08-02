// @ai-generated
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/system-config',
    children: [
      {
        path: '/system-config',
        name: 'SystemConfig',
        component: () => import('@/views/config/SystemConfig.vue')
      },
      {
        path: '/pay-config',
        name: 'PayConfig',
        component: () => import('@/views/config/PayConfig.vue')
      },
      {
        path: '/cloud-config',
        name: 'CloudConfig',
        component: () => import('@/views/config/CloudConfig.vue')
      },
      {
        path: '/channel-mapping',
        name: 'ChannelMapping',
        component: () => import('@/views/config/ChannelMapping.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('admin_token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
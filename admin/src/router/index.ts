// @ai-generated
/**
 * 路由配置
 *
 * 路由分层：
 * 1. /login               登录页（无需鉴权）
 * 2. /                    Layout 容器（需登录）
 *    ├── /dashboard        工作台首页（dashboard:view）
 *    ├── /goods/list       商品列表（goods:manage）
 *    ├── /goods/detail/:goodsId  商品详情（goods:manage）
 *    ├── /goods/edit       新增商品（goods:manage）
 *    ├── /goods/edit/:goodsId    编辑商品（goods:manage）
 *    ├── /system-config    系统配置（config:manage）
 *    ├── /pay-config       支付配置（config:manage）
 *    ├── /cloud-config     云资源配置（config:manage）
 *    ├── /channel-mapping  渠道字段映射（config:manage）
 *    ├── /message/template    消息模板管理（message:manage）
 *    ├── /message/push-record 推送记录（message:manage）
 *    ├── /message/subscribe   订阅绑定（message:manage）
 *    ├── /channel/config      渠道参数配置（config:manage）
 *    ├── /channel/key-test    渠道密钥测试（channel:test）
 * 3. /403                 无权限页
 * 4. /:pathMatch(.*)*     404 兜底
 *
 * 路由守卫：
 * - 无 token 跳 login（携带 redirect）
 * - token 存在但 userInfo 为空时调 fetchUserInfo 重建会话
 * - 路由 meta.permissions 校验，无权限跳 /403
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（顶栏显示） */
    title?: string
    /** 菜单图标（Element Plus 图标组件名） */
    icon?: string
    /** 所需权限码（数组为"或"关系，超管 * 自动通过） */
    permissions?: string[]
    /** 是否在菜单中隐藏 */
    hidden?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Index.vue'),
        meta: { title: '工作台', icon: 'Odometer', permissions: ['dashboard:view'] },
      },
      // ── 商品管理 ──────────────
      {
        path: '/goods/list',
        name: 'GoodsList',
        component: () => import('@/views/goods/List.vue'),
        meta: { title: '商品列表', icon: 'Goods', permissions: ['goods:manage'] },
      },
      {
        path: '/goods/detail/:goodsId',
        name: 'GoodsDetail',
        component: () => import('@/views/goods/Detail.vue'),
        meta: { title: '商品详情', permissions: ['goods:manage'], hidden: true },
      },
      {
        path: '/goods/edit',
        name: 'GoodsAdd',
        component: () => import('@/views/goods/Edit.vue'),
        meta: { title: '新增商品', permissions: ['goods:manage'], hidden: true },
      },
      {
        path: '/goods/edit/:goodsId',
        name: 'GoodsEdit',
        component: () => import('@/views/goods/Edit.vue'),
        meta: { title: '编辑商品', permissions: ['goods:manage'], hidden: true },
      },
      // ── 系统配置（现有保留） ──────────────
      {
        path: '/system-config',
        name: 'SystemConfig',
        component: () => import('@/views/config/SystemConfig.vue'),
        meta: { title: '系统全局配置', icon: 'Setting', permissions: ['config:manage'] },
      },
      {
        path: '/pay-config',
        name: 'PayConfig',
        component: () => import('@/views/config/PayConfig.vue'),
        meta: { title: '支付渠道配置', icon: 'Wallet', permissions: ['config:manage'] },
      },
      {
        path: '/cloud-config',
        name: 'CloudConfig',
        component: () => import('@/views/config/CloudConfig.vue'),
        meta: { title: '云资源配置', icon: 'Cloudy', permissions: ['config:manage'] },
      },
      {
        path: '/channel-mapping',
        name: 'ChannelMapping',
        component: () => import('@/views/config/ChannelMapping.vue'),
        meta: { title: '渠道字段映射', icon: 'Connection', permissions: ['config:manage'] },
      },
      // ── 订单管理（F02） ──────────────
      {
        path: '/order/list',
        name: 'OrderList',
        component: () => import('@/views/order/List.vue'),
        meta: { title: '订单列表', icon: 'List', permissions: ['order:manage'] },
      },
      {
        path: '/order/abnormal',
        name: 'AbnormalOrderList',
        component: () => import('@/views/order/AbnormalList.vue'),
        meta: { title: '异常订单', icon: 'WarningFilled', permissions: ['order:manage'] },
      },
      // ── 提现管理（F02） ──────────────
      {
        path: '/withdraw/list',
        name: 'WithdrawList',
        component: () => import('@/views/withdraw/List.vue'),
        meta: { title: '提现审核', icon: 'Money', permissions: ['withdraw:manage'] },
      },
      // ── 用户/会员 管理（F02） ──────────────
      {
        path: '/user/list',
        name: 'UserList',
        component: () => import('@/views/user/List.vue'),
        meta: { title: '用户管理', icon: 'User', permissions: ['user:manage'] },
      },
      // ── 会员套餐管理（X02-1） ──────────────
      {
        path: '/member/package',
        name: 'MemberPackageList',
        component: () => import('@/views/member/PackageList.vue'),
        meta: { title: '会员套餐管理', icon: 'Medal', permissions: ['member:manage'] },
      },
      {
        path: '/member/record',
        name: 'MemberRecordList',
        component: () => import('@/views/member/RecordList.vue'),
        meta: { title: '会员记录', icon: 'Tickets', permissions: ['member:view'] },
      },
      // ── 权限管理（F03） ──────────────
      {
        path: '/rbac/role',
        name: 'RoleList',
        component: () => import('@/views/rbac/RoleList.vue'),
        meta: { title: '角色管理', icon: 'UserFilled', permissions: ['rbac:manage'] },
      },
      {
        path: '/rbac/admin',
        name: 'AdminList',
        component: () => import('@/views/rbac/AdminList.vue'),
        meta: { title: '管理员账号', icon: 'Avatar', permissions: ['rbac:manage'] },
      },
      {
        path: '/rbac/audit',
        name: 'AuditLog',
        component: () => import('@/views/rbac/AuditLog.vue'),
        meta: { title: '审计日志', icon: 'Document', permissions: ['audit:view'] },
      },
      // ── 营销消息（F04） ──────────────
      {
        path: '/message/template',
        name: 'MessageTemplate',
        component: () => import('@/views/message/TemplateList.vue'),
        meta: { title: '消息模板', icon: 'ChatDotRound', permissions: ['message:manage'] },
      },
      {
        path: '/message/push-record',
        name: 'MessagePushRecord',
        component: () => import('@/views/message/PushRecord.vue'),
        meta: { title: '推送记录', icon: 'Promotion', permissions: ['message:manage'] },
      },
      {
        path: '/message/subscribe',
        name: 'MessageSubscribe',
        component: () => import('@/views/message/SubscribeBinding.vue'),
        meta: { title: '订阅绑定', icon: 'Bell', permissions: ['message:manage'] },
      },
      // ── 渠道配置（F04） ──────────────
      {
        path: '/channel/config',
        name: 'ChannelConfig',
        component: () => import('@/views/channel/Config.vue'),
        meta: { title: '渠道参数配置', icon: 'Connection', permissions: ['config:manage'] },
      },
      {
        path: '/channel/key-test',
        name: 'ChannelKeyTest',
        component: () => import('@/views/channel/KeyTest.vue'),
        meta: { title: '渠道密钥测试', icon: 'Key', permissions: ['channel:test'] },
      },
    ],
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403.vue'),
    meta: { title: '无权限' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** 标记是否已尝试刷新用户信息（避免循环） */
let userInfoFetched = false

router.beforeEach(async (to, _from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 金角大王管理后台`
  }

  const userStore = useUserStore()

  // 登录页直接放行
  if (to.path === '/login') {
    // 已登录访问登录页，跳首页
    if (userStore.isLoggedIn) {
      next('/dashboard')
      return
    }
    next()
    return
  }

  // 无 token 跳登录
  if (!userStore.isLoggedIn) {
    next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
    return
  }

  // token 存在但 userInfo 为空（如刷新页面后 sessionStorage 清空），重建会话
  if (!userStore.userInfo && !userInfoFetched) {
    userInfoFetched = true
    const info = await userStore.fetchUserInfo()
    if (!info) {
      // token 失效，跳登录
      next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
      return
    }
  }

  // 权限校验
  const requiredPerms = to.meta.permissions
  if (requiredPerms && requiredPerms.length > 0) {
    if (!userStore.hasPermission(requiredPerms)) {
      next('/403')
      return
    }
  }

  next()
})

router.afterEach(() => {
  userInfoFetched = false
})

export default router

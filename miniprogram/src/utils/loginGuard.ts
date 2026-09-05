// @ai-generated
/**
 * 登录拦截守卫（M03 新建）
 *
 * 职责：
 * 1. 在需要登录的页面 onLoad/onShow 中调用 requireLogin() 拦截未登录用户
 * 2. 未登录自动跳转登录页，登录后回跳原页面
 * 3. token 过期自动跳转登录页重新授权
 *
 * 使用方式：
 *   import { requireLogin } from '@/utils/loginGuard'
 *   onShow(() => { requireLogin() })  // 未登录则跳转登录页
 *
 * 白名单页面（无需登录即可访问）：
 *   - pages/index/index      首页
 *   - pages/search/list      搜索页
 *   - pages/product/detail   商品详情（可浏览，转链时才需登录）
 *   - pages/login/index      登录页
 */
import auth from './auth'

/** 白名单：无需登录即可访问的页面路径 */
const PUBLIC_PAGES: string[] = [
  'pages/index/index',
  'pages/search/list',
  'pages/product/detail',
  'pages/login/index'
]

/**
 * 获取当前页面路径（不含查询参数）
 */
function getCurrentPageRoute(): string {
  const pages = getCurrentPages()
  if (pages.length === 0) return ''
  return pages[pages.length - 1].route || ''
}

/**
 * 获取当前页面完整路径（含查询参数）
 */
function getCurrentPageFullPath(): string {
  const pages = getCurrentPages()
  if (pages.length === 0) return '/pages/index/index'
  const current = pages[pages.length - 1]
  const route = '/' + current.route
  const options = (current as any).options || {}
  const keys = Object.keys(options)
  if (keys.length === 0) return route
  const query = keys.map((k) => `${k}=${encodeURIComponent(options[k])}`).join('&')
  return `${route}?${query}`
}

/**
 * 拦截未登录用户，跳转登录页
 *
 * @param options 配置项
 *   - redirectAfterLogin: 登录后回跳路径（默认当前页完整路径）
 *   - silent: 是否静默跳转（不弹 toast）
 * @returns 是否已登录（true=已登录可继续，false=已跳转登录页）
 */
export function requireLogin(options?: {
  redirectAfterLogin?: string
  silent?: boolean
}): boolean {
  // 已登录且 token 有效 → 放行
  if (auth.isLoginValid()) {
    return true
  }

  const route = getCurrentPageRoute()

  // 已在登录页则不再跳转（避免死循环）
  if (route === 'pages/login/index') {
    return false
  }

  // 白名单页面不拦截（但会清除过期的 token）
  if (PUBLIC_PAGES.includes(route)) {
    // token 存在但已过期 → 清除本地登录态
    if (auth.isLoggedIn() && !auth.isLoginValid()) {
      auth.logout()
    }
    return false
  }

  // 需登录页面 → 跳转登录页，登录后回跳
  const redirect = options?.redirectAfterLogin || getCurrentPageFullPath()
  if (!options?.silent) {
    uni.showToast({ title: '请先登录', icon: 'none', duration: 1500 })
  }

  setTimeout(() => {
    uni.navigateTo({
      url: `/pages/login/index?redirect=${encodeURIComponent(redirect)}`
    })
  }, 500)

  return false
}

/**
 * 判断当前页面是否在白名单中
 */
export function isPublicPage(): boolean {
  const route = getCurrentPageRoute()
  return PUBLIC_PAGES.includes(route)
}

export default {
  requireLogin,
  isPublicPage,
  PUBLIC_PAGES
}

// @ai-generated
/**
 * 全局分享组件（M03 新建）
 *
 * 职责：
 * 1. 统一封装 onShareAppMessage / onShareTimeline 配置
 * 2. 支持商品页、首页自定义分享标题、路径、图片
 * 3. 内置默认分享文案，兜底空值
 * 4. 分享路径自动携带分享者 user_id（用于后续返利溯源）
 *
 * 使用方式：
 *   import { setupProductShare, setupHomeShare } from '@/utils/share'
 *   import { onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
 *
 *   // 商品页（传入 getter 函数，分享时懒求值，保证数据已加载）
 *   setupProductShare(onShareAppMessage, () => ({ title, params: { goods_id }, imageUrl }))
 *
 *   // 首页（静态配置）
 *   setupHomeShare(onShareAppMessage, onShareTimeline)
 */
import auth from './auth'

/** 分享配置选项 */
export interface ShareOptions {
  /** 分享标题（不传用默认文案） */
  title?: string
  /** 分享落地页路径（不含参数部分） */
  path?: string
  /** 分享落地页查询参数（自动拼接，含分享者 user_id） */
  params?: Record<string, string | number>
  /** 分享配图 URL */
  imageUrl?: string
}

/** 默认分享文案 */
const DEFAULT_SHARE_TITLE = '金角大王 - 购物先搜券，下单拿返利'
const DEFAULT_SHARE_PATH = '/pages/index/index'
const DEFAULT_SHARE_IMAGE = ''

/** 首页分享文案（兜底） */
const HOME_SHARE_TITLES = [
  '金角大王 - 购物先搜券，下单拿返利',
  '淘宝购物前先搜券，最高省90%',
  '一样的商品，更低的价格，还能拿返利'
]

/**
 * 拼接分享路径 + 查询参数
 * 自动注入 share_uid（分享者 user_id，用于返利溯源）
 */
function buildSharePath(path: string, params?: Record<string, string | number>): string {
  let fullPath = path || DEFAULT_SHARE_PATH
  if (!fullPath.startsWith('/')) {
    fullPath = '/' + fullPath
  }

  const queryParams: Record<string, string> = {}
  if (params) {
    for (const key of Object.keys(params)) {
      const val = params[key]
      if (val !== '' && val !== undefined && val !== null) {
        queryParams[key] = String(val)
      }
    }
  }

  // 自动注入分享者 user_id（仅当已登录且未显式传入 share_uid 时）
  if (!queryParams.share_uid) {
    const userInfo = auth.getStoredUserInfo()
    if (userInfo && userInfo.user_id > 0) {
      queryParams.share_uid = String(userInfo.user_id)
    }
  }

  const keys = Object.keys(queryParams)
  if (keys.length === 0) return fullPath
  const query = keys.map((k) => `${k}=${encodeURIComponent(queryParams[k])}`).join('&')
  return `${fullPath}?${query}`
}

/**
 * 配置商品页分享（懒求值模式）
 *
 * 分享触发时才调用 optionsGetter 获取最新配置，保证商品数据已加载。
 *
 * @param onShareAppMessageHook uni-app onShareAppMessage 钩子
 * @param optionsGetter 返回分享配置的函数（分享时懒求值）
 */
export function setupProductShare(
  onShareAppMessageHook: (
    callback: () => { title: string; path: string; imageUrl: string }
  ) => void,
  optionsGetter: () => ShareOptions
): void {
  onShareAppMessageHook(() => {
    const options = optionsGetter()
    const title = options.title || DEFAULT_SHARE_TITLE
    const path = buildSharePath(options.path || '/pages/product/detail', options.params)
    const imageUrl = options.imageUrl || DEFAULT_SHARE_IMAGE
    return { title, path, imageUrl }
  })
}

/**
 * 配置首页分享（同时配置 onShareAppMessage 和 onShareTimeline）
 *
 * @param onShareAppMessageHook uni-app onShareAppMessage 钩子
 * @param onShareTimelineHook uni-app onShareTimeline 钩子
 */
export function setupHomeShare(
  onShareAppMessageHook: (
    callback: () => { title: string; path: string; imageUrl: string }
  ) => void,
  onShareTimelineHook?: (
    callback: () => { title: string; query: string; imageUrl: string }
  ) => void
): void {
  onShareAppMessageHook(() => {
    const title = HOME_SHARE_TITLES[0]
    const path = buildSharePath(DEFAULT_SHARE_PATH)
    return { title, path, imageUrl: DEFAULT_SHARE_IMAGE }
  })

  if (onShareTimelineHook) {
    onShareTimelineHook(() => {
      const userInfo = auth.getStoredUserInfo()
      const query = userInfo?.user_id
        ? `share_uid=${encodeURIComponent(userInfo.user_id)}`
        : ''
      return {
        title: HOME_SHARE_TITLES[0],
        query,
        imageUrl: DEFAULT_SHARE_IMAGE
      }
    })
  }
}

/**
 * 构造自定义分享配置（供特殊页面使用）
 */
export function buildShareConfig(options: ShareOptions): {
  title: string
  path: string
  imageUrl: string
} {
  return {
    title: options.title || DEFAULT_SHARE_TITLE,
    path: buildSharePath(options.path || DEFAULT_SHARE_PATH, options.params),
    imageUrl: options.imageUrl || DEFAULT_SHARE_IMAGE
  }
}

export default {
  setupProductShare,
  setupHomeShare,
  buildShareConfig
}

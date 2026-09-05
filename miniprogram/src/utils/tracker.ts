// @ai-generated
/**
 * 行为埋点 & 批量上报引擎（M04 新建）
 *
 * 核心能力：
 * 1. 行为埋点：page_view / goods_click / share / order_create / withdraw_apply
 * 2. 防抖合并：队列累计 30 条或 5s 定时 flush
 * 3. 本地缓存：上报失败写入 uni.storage，不丢失数据
 * 4. 断网重传：监听网络恢复事件，自动重传缓存队列
 * 5. 会话标识：App 启动生成 sessionId，串联同一次会话的所有行为
 *
 * 上报接口：POST /api/v1/track/event（批量，最多50条/次）
 * 设计约束：埋点不能影响业务，所有上报静默执行（不弹 toast、不抛异常）
 */

/** 事件类型枚举 */
export type EventType =
  | 'page_view'
  | 'goods_click'
  | 'share'
  | 'order_create'
  | 'withdraw_apply'
  | 'subscribe_popup_show'
  | 'subscribe_accept'
  | 'subscribe_reject'
  | 'subscribe_expired'
  | 'subscribe_unsubscribe'

/** 单条埋点事件结构（与后端 TrackEventItem 对齐） */
export interface TrackEventItem {
  event_type: string
  event_name: string
  page_path: string
  params: Record<string, any>
  device_info: Record<string, any>
  session_id: string
  client_timestamp: number
}

// ─────────────────────────────────────────────────────
// 配置常量
// ─────────────────────────────────────────────────────

const TRACK_ENDPOINT = '/api/v1/track/event'
const TRACK_CACHE_KEY = 'track_event_cache' // 本地缓存键
const MAX_BATCH_SIZE = 30 // 队列达到此条数立即 flush
const FLUSH_INTERVAL = 5000 // 定时 flush 间隔（ms）
const MAX_CACHE_SIZE = 500 // 本地缓存上限（防止无限增长）
const FLUSH_TIMEOUT = 8000 // 上报超时（ms）

// 平台判断：uni.getSystemInfoSync().uniPlatform 在 H5 为 'web'，微信小程序为 'mp-weixin'
const PLATFORM: 'h5' | 'mp' = (() => {
  try {
    const sysInfo = uni.getSystemInfoSync()
    return sysInfo.uniPlatform === 'web' ? 'h5' : 'mp'
  } catch {
    return 'h5'
  }
})()
const BASE_URL = PLATFORM === 'h5' ? '' : 'https://api.dftsh.top'

// ─────────────────────────────────────────────────────
// 会话 & 设备信息
// ─────────────────────────────────────────────────────

/** 生成会话ID（App 启动一次生成一次） */
function generateSessionId(): string {
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).substring(2, 10)
  return `${ts}_${rand}`
}

let sessionId = generateSessionId()
let deviceInfo: Record<string, any> = {}
let initialized = false

/** 缓存设备信息（仅初始化时获取一次） */
function initDeviceInfo(): void {
  try {
    const sysInfo = uni.getSystemInfoSync()
    deviceInfo = {
      platform: sysInfo.platform,
      system: sysInfo.system,
      brand: sysInfo.brand,
      model: sysInfo.model,
      version: sysInfo.version,
      SDKVersion: (sysInfo as any).SDKVersion || '',
      screenWidth: sysInfo.screenWidth,
      screenHeight: sysInfo.screenHeight,
      pixelRatio: sysInfo.pixelRatio,
      app: 'gaking-miniapp'
    }
  } catch {
    deviceInfo = { app: 'gaking-miniapp' }
  }
}

// ─────────────────────────────────────────────────────
// 批量上报引擎
// ─────────────────────────────────────────────────────

const eventQueue: TrackEventItem[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null
let flushing = false

/**
 * 获取当前页面路径
 */
function getCurrentPagePath(): string {
  try {
    const pages = getCurrentPages()
    if (pages.length === 0) return ''
    return '/' + (pages[pages.length - 1].route || '')
  } catch {
    return ''
  }
}

/**
 * 从本地缓存加载未上报的事件（App 启动时重传）
 */
function loadCachedEvents(): TrackEventItem[] {
  try {
    const cached = uni.getStorageSync(TRACK_CACHE_KEY) as string
    if (!cached) return []
    const arr = JSON.parse(cached) as TrackEventItem[]
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

/**
 * 保存事件到本地缓存（断网/上报失败时）
 */
function saveCachedEvents(events: TrackEventItem[]): void {
  try {
    if (events.length === 0) {
      uni.removeStorageSync(TRACK_CACHE_KEY)
      return
    }
    // 超过上限时丢弃最旧的事件（FIFO）
    const trimmed = events.length > MAX_CACHE_SIZE
      ? events.slice(events.length - MAX_CACHE_SIZE)
      : events
    uni.setStorageSync(TRACK_CACHE_KEY, JSON.stringify(trimmed))
  } catch {
    // storage 写入失败静默忽略
  }
}

/**
 * 上报一批事件到后端（使用 uni.request 直接调用，不走 request.ts 拦截器）
 */
function uploadBatch(events: TrackEventItem[]): Promise<boolean> {
  return new Promise((resolve) => {
    uni.request({
      url: BASE_URL + TRACK_ENDPOINT,
      method: 'POST',
      data: { events },
      header: { 'Content-Type': 'application/json' },
      timeout: FLUSH_TIMEOUT,
      success: (res) => {
        // HTTP 200 即视为成功（后端写入失败也返回 200，不阻断前端）
        resolve(res.statusCode >= 200 && res.statusCode < 300)
      },
      fail: () => {
        resolve(false)
      }
    })
  })
}

/**
 * 执行一次 flush：上报队列 + 失败缓存
 */
async function flush(): Promise<void> {
  if (flushing) return
  if (eventQueue.length === 0) return

  flushing = true
  // 取出当前队列（清空内存队列，允许新事件继续入队）
  const batch = eventQueue.splice(0, eventQueue.length)

  // 合并本地缓存的失败事件（先上报旧的）
  const cached = loadCachedEvents()
  const allEvents = [...cached, ...batch]

  if (allEvents.length === 0) {
    flushing = false
    return
  }

  // 分批上传（每批最多 50 条，后端限制）
  const CHUNK_SIZE = 50
  const failedEvents: TrackEventItem[] = []

  for (let i = 0; i < allEvents.length; i += CHUNK_SIZE) {
    const chunk = allEvents.slice(i, i + CHUNK_SIZE)
    const ok = await uploadBatch(chunk)
    if (!ok) {
      failedEvents.push(...chunk)
    }
  }

  // 失败的事件写回本地缓存，等待下次重传
  if (failedEvents.length > 0) {
    saveCachedEvents(failedEvents)
  } else {
    // 全部成功，清空缓存
    saveCachedEvents([])
  }

  flushing = false
}

/**
 * 启动定时 flush
 */
function startAutoFlush(): void {
  if (flushTimer) {
    clearTimeout(flushTimer)
  }
  flushTimer = setTimeout(() => {
    flush().finally(() => {
      startAutoFlush() // 递归调度下一次
    })
  }, FLUSH_INTERVAL)
}

/**
 * 停止定时 flush
 */
function stopAutoFlush(): void {
  if (flushTimer) {
    clearTimeout(flushTimer)
    flushTimer = null
  }
}

// ─────────────────────────────────────────────────────
// 公开 API
// ─────────────────────────────────────────────────────

/**
 * 上报一条行为事件
 * @param eventType 事件类型
 * @param eventName 事件名称（可选）
 * @param params 事件参数（可选）
 */
function track(
  eventType: EventType,
  eventName?: string,
  params?: Record<string, any>
): void {
  if (!initialized) {
    // 未初始化时静默初始化（防御性）
    initDeviceInfo()
    initialized = true
  }

  const item: TrackEventItem = {
    event_type: eventType,
    event_name: eventName || '',
    page_path: getCurrentPagePath(),
    params: params || {},
    device_info: deviceInfo,
    session_id: sessionId,
    client_timestamp: Date.now()
  }

  eventQueue.push(item)

  // 达到批量上限立即 flush
  if (eventQueue.length >= MAX_BATCH_SIZE) {
    flush()
  }
}

/**
 * 页面浏览埋点（便捷方法）
 * @param pageName 页面名称
 * @param params 额外参数
 */
function trackPageView(pageName: string, params?: Record<string, any>): void {
  track('page_view', pageName, params)
}

/**
 * 商品点击埋点
 * @param goodsId 商品ID
 * @param goodsTitle 商品标题
 */
function trackGoodsClick(goodsId: string, goodsTitle?: string): void {
  track('goods_click', '商品点击', { goods_id: goodsId, goods_title: goodsTitle || '' })
}

/**
 * 分享埋点
 * @param shareType 分享类型：friend/timeline
 * @param params 额外参数
 */
function trackShare(shareType: 'friend' | 'timeline', params?: Record<string, any>): void {
  track('share', '分享', { share_type: shareType, ...params })
}

/**
 * 下单埋点
 * @param orderId 订单ID
 * @param amount 支付金额
 */
function trackOrderCreate(orderId: string, amount: number): void {
  track('order_create', '下单', { order_id: orderId, pay_amount: amount })
}

/**
 * 提现申请埋点
 * @param applyAmount 提现金额
 * @param applyNo 提现单号
 */
function trackWithdrawApply(applyAmount: number, applyNo?: string): void {
  track('withdraw_apply', '提现申请', { apply_amount: applyAmount, apply_no: applyNo || '' })
}

/**
 * 订阅弹窗展示埋点
 * @param templateId 模板ID
 * @param templateName 模板名称
 */
function trackSubscribePopupShow(templateId: number, templateName: string): void {
  track('subscribe_popup_show', '订阅弹窗展示', { template_id: templateId, template_name: templateName })
}

/**
 * 订阅同意埋点
 * @param templateId 模板ID
 * @param templateName 模板名称
 */
function trackSubscribeAccept(templateId: number, templateName: string): void {
  track('subscribe_accept', '订阅同意', { template_id: templateId, template_name: templateName })
}

/**
 * 订阅拒绝埋点
 * @param templateId 模板ID
 * @param templateName 模板名称
 */
function trackSubscribeReject(templateId: number, templateName: string): void {
  track('subscribe_reject', '订阅拒绝', { template_id: templateId, template_name: templateName })
}

/**
 * 订阅过期埋点
 * @param templateId 模板ID
 * @param templateName 模板名称
 */
function trackSubscribeExpired(templateId: number, templateName: string): void {
  track('subscribe_expired', '订阅过期', { template_id: templateId, template_name: templateName })
}

/**
 * 取消订阅埋点
 * @param templateId 模板ID
 * @param templateName 模板名称
 */
function trackUnsubscribe(templateId: number, templateName: string): void {
  track('subscribe_unsubscribe', '取消订阅', { template_id: templateId, template_name: templateName })
}

/**
 * 初始化埋点系统
 * - 获取设备信息
 * - 启动定时 flush
 * - 监听网络恢复重传
 * - 重传上次未上报的缓存事件
 *
 * 应在 App.onLaunch 中调用
 */
function init(): void {
  if (initialized) return
  initialized = true

  initDeviceInfo()
  startAutoFlush()

  // 监听网络状态变化：网络恢复时重传缓存
  uni.onNetworkStatusChange((res) => {
    if (res.isConnected) {
      // 网络恢复，尝试重传缓存
      flush()
    }
  })

  // 启动时重传上次会话遗留的缓存事件（延迟 2s，避免与启动流程抢资源）
  setTimeout(() => {
    flush()
  }, 2000)
}

/**
 * 销毁埋点系统（App.onHide 时 flush 一次，确保数据不丢）
 */
function destroy(): void {
  flush()
}

export const tracker = {
  init,
  destroy,
  track,
  trackPageView,
  trackGoodsClick,
  trackShare,
  trackOrderCreate,
  trackWithdrawApply,
  trackSubscribePopupShow,
  trackSubscribeAccept,
  trackSubscribeReject,
  trackSubscribeExpired,
  trackUnsubscribe,
  flush,
  /** 获取当前会话ID（供 errorReporter 同步） */
  getSessionId: () => sessionId
}

export default tracker

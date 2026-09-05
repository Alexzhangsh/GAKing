// @ai-generated
/**
 * 前端错误捕获 & 上报（M04 新建）
 *
 * 核心能力：
 * 1. JS 运行时异常捕获：uni.onError / wx.onError
 * 2. Promise 拒绝捕获：uni.onUnhandledRejection / wx.onUnhandledRejection
 * 3. 接口报错收集：request.ts 拦截器调用 reportApiError()
 * 4. 批量上报 + 本地缓存 + 断网重传（复用与 tracker 相同的机制）
 *
 * 上报接口：POST /api/v1/track/error（批量，最多50条/次）
 * event_type 区分：js_error / api_error / promise_reject
 *
 * 设计约束：错误上报本身不能抛异常（try-catch 兜底），不影响业务流程
 */

/** 错误事件类型 */
export type ErrorEventType = 'js_error' | 'api_error' | 'promise_reject'

/** 单条错误事件结构（与后端 TrackEventItem 对齐） */
interface ErrorEventItem {
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

const ERROR_ENDPOINT = '/api/v1/track/error'
const ERROR_CACHE_KEY = 'track_error_cache'
const MAX_BATCH_SIZE = 20 // 错误队列达到此条数立即 flush
const FLUSH_INTERVAL = 8000 // 错误 flush 间隔（ms，比行为埋点更长）
const MAX_CACHE_SIZE = 200 // 本地缓存上限
const FLUSH_TIMEOUT = 8000

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
// 会话 & 设备信息（与 tracker 共享 sessionId 逻辑）
// ─────────────────────────────────────────────────────

function generateSessionId(): string {
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).substring(2, 10)
  return `${ts}_${rand}`
}

let sessionId = generateSessionId()
let deviceInfo: Record<string, any> = {}
let initialized = false

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
      app: 'gaking-miniapp'
    }
  } catch {
    deviceInfo = { app: 'gaking-miniapp' }
  }
}

/** 设置会话ID（由 tracker.init 统一设置，保证两边一致） */
function setSessionId(sid: string): void {
  sessionId = sid
}

// ─────────────────────────────────────────────────────
// 批量上报引擎（与 tracker.ts 相同机制，独立队列）
// ─────────────────────────────────────────────────────

const errorQueue: ErrorEventItem[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null
let flushing = false

function getCurrentPagePath(): string {
  try {
    const pages = getCurrentPages()
    if (pages.length === 0) return ''
    return '/' + (pages[pages.length - 1].route || '')
  } catch {
    return ''
  }
}

function loadCachedErrors(): ErrorEventItem[] {
  try {
    const cached = uni.getStorageSync(ERROR_CACHE_KEY) as string
    if (!cached) return []
    const arr = JSON.parse(cached) as ErrorEventItem[]
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function saveCachedErrors(errors: ErrorEventItem[]): void {
  try {
    if (errors.length === 0) {
      uni.removeStorageSync(ERROR_CACHE_KEY)
      return
    }
    const trimmed = errors.length > MAX_CACHE_SIZE
      ? errors.slice(errors.length - MAX_CACHE_SIZE)
      : errors
    uni.setStorageSync(ERROR_CACHE_KEY, JSON.stringify(trimmed))
  } catch {
    // 静默忽略
  }
}

function uploadBatch(errors: ErrorEventItem[]): Promise<boolean> {
  return new Promise((resolve) => {
    uni.request({
      url: BASE_URL + ERROR_ENDPOINT,
      method: 'POST',
      data: { events: errors },
      header: { 'Content-Type': 'application/json' },
      timeout: FLUSH_TIMEOUT,
      success: (res) => {
        resolve(res.statusCode >= 200 && res.statusCode < 300)
      },
      fail: () => {
        resolve(false)
      }
    })
  })
}

async function flush(): Promise<void> {
  if (flushing) return
  if (errorQueue.length === 0) return

  flushing = true
  const batch = errorQueue.splice(0, errorQueue.length)
  const cached = loadCachedErrors()
  const allErrors = [...cached, ...batch]

  if (allErrors.length === 0) {
    flushing = false
    return
  }

  const CHUNK_SIZE = 50
  const failed: ErrorEventItem[] = []

  for (let i = 0; i < allErrors.length; i += CHUNK_SIZE) {
    const chunk = allErrors.slice(i, i + CHUNK_SIZE)
    const ok = await uploadBatch(chunk)
    if (!ok) {
      failed.push(...chunk)
    }
  }

  if (failed.length > 0) {
    saveCachedErrors(failed)
  } else {
    saveCachedErrors([])
  }

  flushing = false
}

function startAutoFlush(): void {
  if (flushTimer) {
    clearTimeout(flushTimer)
  }
  flushTimer = setTimeout(() => {
    flush().finally(() => {
      startAutoFlush()
    })
  }, FLUSH_INTERVAL)
}

// ─────────────────────────────────────────────────────
// 错误入队 API
// ─────────────────────────────────────────────────────

/**
 * 添加一条错误事件到队列
 */
function addError(
  errorType: ErrorEventType,
  errorName: string,
  params: Record<string, any>
): void {
  try {
    const item: ErrorEventItem = {
      event_type: errorType,
      event_name: errorName,
      page_path: getCurrentPagePath(),
      params,
      device_info: deviceInfo,
      session_id: sessionId,
      client_timestamp: Date.now()
    }

    errorQueue.push(item)

    if (errorQueue.length >= MAX_BATCH_SIZE) {
      flush()
    }
  } catch {
    // 错误上报本身失败静默忽略
  }
}

// ─────────────────────────────────────────────────────
// 公开 API
// ─────────────────────────────────────────────────────

/**
 * 上报 JS 运行时异常
 * @param error 错误对象或错误消息
 * @param context 额外上下文
 */
function reportJsError(error: string | Error, context?: Record<string, any>): void {
  const errorMsg = typeof error === 'string' ? error : (error?.message || String(error))
  const stack = typeof error === 'object' && error?.stack ? error.stack : ''
  addError('js_error', errorMsg, {
    message: errorMsg,
    stack: stack ? stack.substring(0, 2000) : '', // 截断过长的堆栈
    ...context
  })
}

/**
 * 上报接口报错
 * @param url 请求URL
 * @param statusCode HTTP状态码
 * @param errorMsg 错误消息
 * @param params 额外参数
 */
function reportApiError(
  url: string,
  statusCode: number,
  errorMsg: string,
  params?: Record<string, any>
): void {
  addError('api_error', `API ${statusCode}: ${url}`, {
    url,
    status_code: statusCode,
    message: errorMsg.substring(0, 1000),
    ...params
  })
}

/**
 * 上报未处理的 Promise 拒绝
 * @param reason 拒绝原因
 */
function reportPromiseReject(reason: any): void {
  const reasonStr = reason instanceof Error
    ? reason.message
    : (typeof reason === 'string' ? reason : JSON.stringify(reason))
  const stack = reason instanceof Error && reason.stack ? reason.stack : ''
  addError('promise_reject', reasonStr, {
    reason: reasonStr.substring(0, 1000),
    stack: stack ? stack.substring(0, 2000) : ''
  })
}

/**
 * 初始化错误捕获系统
 * - 注册 uni.onError / uni.onUnhandledRejection 全局监听
 * - 获取设备信息
 * - 启动定时 flush
 * - 监听网络恢复重传
 *
 * 应在 App.onLaunch 中调用
 */
function init(): void {
  if (initialized) return
  initialized = true

  initDeviceInfo()
  startAutoFlush()

  // 捕获 JS 运行时异常
  try {
    // 微信小程序：wx.onError；uni-app：uni.onError
    if (typeof uni !== 'undefined' && typeof (uni as any).onError === 'function') {
      ;(uni as any).onError((error: string) => {
        reportJsError(error)
      })
    }
  } catch {
    // 某些平台不支持 onError，静默忽略
  }

  // 捕获未处理的 Promise 拒绝
  try {
    if (typeof uni !== 'undefined' && typeof (uni as any).onUnhandledRejection === 'function') {
      ;(uni as any).onUnhandledRejection((res: { reason: any; promise: Promise<any> }) => {
        reportPromiseReject(res.reason)
      })
    }
  } catch {
    // 静默忽略
  }

  // 监听网络恢复重传
  uni.onNetworkStatusChange((res) => {
    if (res.isConnected) {
      flush()
    }
  })

  // 启动时重传缓存的错误（延迟 3s）
  setTimeout(() => {
    flush()
  }, 3000)
}

/**
 * 销毁（App.onHide 时 flush 一次）
 */
function destroy(): void {
  flush()
}

export const errorReporter = {
  init,
  destroy,
  setSessionId,
  reportJsError,
  reportApiError,
  reportPromiseReject,
  flush
}

export default errorReporter

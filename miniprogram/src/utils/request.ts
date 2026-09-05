// @ai-generated
/**
 * 全局统一请求封装（M04 增强：异常分类 + 统一弹窗 + 401跳登录 + 错误上报）
 *
 * 后端统一响应体（src/schemas/cps.py: ApiResponse）：
 *   { code: 200, msg: "success", data: any, request_id: string }
 *
 * 异常分类与统一提示：
 *   - 网络异常（code=-1）：  "网络连接失败，请检查网络"
 *   - 登录失效（code=401）：  清除登录态 → 跳转登录页 → "登录已超时，请重新登录"
 *   - 权限不足（code=403）：  "当前账号无操作权限"
 *   - 限流（code=429）：      "服务繁忙，请稍后重试"
 *   - 服务异常（code=5xx）：  "操作失败，请稍后重试"
 *   - 业务异常（其他code）：   显示后端 msg
 *
 * 错误上报：
 *   - 接口报错自动调用 errorReporter.reportApiError（埋点接口本身不上报，避免循环）
 *
 * H5 开发环境通过 vite.config.ts 代理 /api → http://localhost:3001
 * 微信小程序环境 baseUrl 直接指向后端域名（需在 manifest.json 配置合法域名）
 */
// UniApp 命名空间由 @dcloudio/types 全局提供（tsconfig 已配置 types），无需 import

import errorReporter from './errorReporter'

// 小程序环境需配置后端域名；H5 走 vite 代理用空串即可
const PLATFORM = typeof uni !== 'undefined' && typeof uni.getSystemInfoSync === 'function' ? 'mp' : 'h5'
const BASE_URL = PLATFORM === 'h5' ? '' : 'https://api.dftsh.top'

/** 后端统一响应体（与后端 src/schemas/cps.py: ApiResponse 对齐） */
export interface ApiResponse<T = any> {
  code: number
  msg: string
  data: T
  request_id?: string
}

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

/** 请求额外选项 */
interface RequestOptionsExtras {
  /** 是否静默处理（不弹 toast），默认 false */
  silent?: boolean
  /** 自定义超时（ms） */
  timeout?: number
  /** 额外请求头 */
  header?: Record<string, string>
  /** 是否跳过自动登录态校验（公开接口用），默认 false */
  skipAuth?: boolean
  /** 是否跳过错误上报（埋点接口用），默认 false */
  skipReport?: boolean
  /** 网络失败自动重试次数（仅 GET 请求，默认 1 次） */
  retry?: number
}

/** 业务错误（含 code + msg），便于调用方精确捕获 */
export class BizError extends Error {
  code: number
  data: any
  constructor(code: number, msg: string, data?: any) {
    super(msg)
    this.name = 'BizError'
    this.code = code
    this.data = data
  }
}

/** 错误类型枚举（用于统一提示分类） */
export enum ErrorType {
  NETWORK = 'network',
  AUTH = 'auth',
  PERMISSION = 'permission',
  RATE_LIMIT = 'rate_limit',
  SERVER = 'server',
  BUSINESS = 'business'
}

const SUCCESS_CODE = 200

/** 埋点接口前缀（不上报错误，避免循环） */
const TRACK_URL_PREFIX = '/api/v1/track/'

// ─────────────────────────────────────────────────────
// 统一提示 & 错误上报
// ─────────────────────────────────────────────────────

/**
 * 根据 code 判断错误类型
 */
function classifyError(code: number): ErrorType {
  if (code === -1) return ErrorType.NETWORK
  if (code === 401) return ErrorType.AUTH
  if (code === 403) return ErrorType.PERMISSION
  if (code === 429) return ErrorType.RATE_LIMIT
  if (code >= 500) return ErrorType.SERVER
  return ErrorType.BUSINESS
}

/**
 * 统一弹窗提示（根据错误类型选择文案）
 */
function showErrorToast(errorType: ErrorType, msg: string): void {
  const defaultMsgMap: Record<ErrorType, string> = {
    [ErrorType.NETWORK]: '网络连接失败，请检查网络',
    [ErrorType.AUTH]: '登录已超时，请重新登录',
    [ErrorType.PERMISSION]: '当前账号无操作权限',
    [ErrorType.RATE_LIMIT]: '服务繁忙，请稍后重试',
    [ErrorType.SERVER]: '操作失败，请稍后重试',
    [ErrorType.BUSINESS]: msg || '请求失败'
  }
  uni.showToast({
    title: defaultMsgMap[errorType] || msg,
    icon: 'none'
  })
}

/**
 * 上报接口错误到 errorReporter（埋点接口本身不上报）
 */
function reportApiError(
  url: string,
  statusCode: number,
  errorMsg: string,
  options?: RequestOptionsExtras
): void {
  // 埋点接口不上报（避免循环）+ 显式 skipReport 不上报
  if (url.startsWith(TRACK_URL_PREFIX) || options?.skipReport) return
  try {
    errorReporter.reportApiError(url, statusCode, errorMsg)
  } catch {
    // 上报失败静默忽略
  }
}

/**
 * 获取当前页面路径（用于 401 回跳）
 */
function getCurrentPageFullPath(): string {
  try {
    const pages = getCurrentPages()
    if (pages.length === 0) return '/pages/index/index'
    const current = pages[pages.length - 1]
    const route = '/' + current.route
    const opts = (current as any).options || {}
    const keys = Object.keys(opts)
    if (keys.length === 0) return route
    const query = keys.map((k) => `${k}=${encodeURIComponent(opts[k])}`).join('&')
    return `${route}?${query}`
  } catch {
    return '/pages/index/index'
  }
}

/**
 * 处理 401 登录失效：清除登录态 → 跳转登录页
 * 避免在登录页重复跳转
 */
function handleAuthExpired(): void {
  // 清除登录态（token + userInfo + token_exp）
  uni.removeStorageSync('token')
  uni.removeStorageSync('userInfo')
  uni.removeStorageSync('token_exp')

  // 检查当前是否已在登录页（避免死循环）
  try {
    const pages = getCurrentPages()
    if (pages.length > 0) {
      const currentRoute = pages[pages.length - 1].route || ''
      if (currentRoute === 'pages/login/index') {
        return // 已在登录页，不重复跳转
      }
    }
  } catch {
    // 忽略
  }

  // 跳转登录页，携带回跳路径
  const redirect = getCurrentPageFullPath()
  setTimeout(() => {
    uni.navigateTo({
      url: `/pages/login/index?redirect=${encodeURIComponent(redirect)}`
    })
  }, 1200)
}

// ─────────────────────────────────────────────────────
// 核心请求方法（含弱网自动重试）
// ─────────────────────────────────────────────────────

/** 网络重试延迟（ms） */
const RETRY_DELAY = 1000

/**
 * 单次请求（不含重试逻辑）
 * 网络失败时不弹 toast、不上报，由外层 request 决定是否重试
 */
const singleRequest = <T = any>(
  url: string,
  method: RequestMethod,
  data: Record<string, any> | undefined,
  options: RequestOptionsExtras | undefined
): Promise<{ ok: true; res: ApiResponse<T> } | { ok: false; error: BizError; isNetwork: boolean }> => {
  return new Promise((resolve) => {
    const token = uni.getStorageSync('token')

    const header: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options?.header || {})
    }
    if (token && !options?.skipAuth) {
      header['Authorization'] = `Bearer ${token}`
    }

    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header,
      timeout: options?.timeout || 10000,
      success: (res: UniApp.RequestSuccessCallbackResult) => {
        const result = res.data as ApiResponse<T>

        // HTTP 层失败（非 2xx）
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const httpCode = res.statusCode
          const msg = result?.msg || `请求失败(${httpCode})`
          resolve({ ok: false, error: new BizError(httpCode, msg, result?.data), isNetwork: false })
          return
        }

        // 业务层成功
        if (result.code === SUCCESS_CODE) {
          resolve({ ok: true, res: result })
          return
        }

        // 业务层错误（code != 200）
        const bizMsg = result.msg || '请求失败'
        resolve({ ok: false, error: new BizError(result.code, bizMsg, result.data), isNetwork: false })
        return
      },
      fail: (error) => {
        resolve({
          ok: false,
          error: new BizError(-1, error.errMsg || '网络连接失败'),
          isNetwork: true
        })
      }
    })
  })
}

/**
 * 核心请求方法（含弱网自动重试）
 *
 * 重试策略：
 * - 仅对网络失败（fail 回调）自动重试，业务错误不重试
 * - 仅 GET 请求默认重试 1 次（可通过 retry 选项自定义）
 * - 重试时延迟 1s，避免瞬时抖动
 * - 最终失败才弹 toast + 上报错误
 *
 * @throws BizError 业务异常（含 code）
 */
const request = async <T = any>(
  url: string,
  method: RequestMethod = 'GET',
  data?: Record<string, any>,
  options?: RequestOptionsExtras
): Promise<ApiResponse<T>> => {
  // 默认重试次数：GET 请求 1 次，其他 0 次
  const maxRetry = options?.retry ?? (method === 'GET' ? 1 : 0)
  let lastError: BizError | null = null

  for (let attempt = 0; attempt <= maxRetry; attempt++) {
    const result = await singleRequest<T>(url, method, data, options)

    if (result.ok) {
      return result.res
    }

    lastError = result.error

    // 网络失败 + 还有重试次数 → 延迟后重试
    if (result.isNetwork && attempt < maxRetry) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY))
      continue
    }

    // 非网络错误或重试次数用尽 → 跳出循环处理错误
    break
  }

  // 最终失败处理
  const error = lastError!
  const errorType = classifyError(error.code)

  // 弹窗提示（silent 模式不弹）
  if (!options?.silent) {
    showErrorToast(errorType, error.message)
  }

  // 上报错误（埋点接口除外）
  reportApiError(url, error.code, error.message, options)

  // 401 → 跳转登录页
  if (error.code === 401) {
    handleAuthExpired()
  }

  throw error
}

const http = {
  get: <T = any>(url: string, params?: Record<string, any>, options?: RequestOptionsExtras) =>
    request<T>(url, 'GET', params, options),
  post: <T = any>(url: string, data?: Record<string, any>, options?: RequestOptionsExtras) =>
    request<T>(url, 'POST', data, options),
  put: <T = any>(url: string, data?: Record<string, any>, options?: RequestOptionsExtras) =>
    request<T>(url, 'PUT', data, options),
  delete: <T = any>(url: string, params?: Record<string, any>, options?: RequestOptionsExtras) =>
    request<T>(url, 'DELETE', params, options)
}

export default http

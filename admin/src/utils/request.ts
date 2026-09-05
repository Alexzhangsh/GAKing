// @ai-generated
/**
 * 全局 Axios 请求封装
 *
 * 后端统一响应外壳（src/schemas/cps.py ApiResponse）：
 *   { code: 200, msg: "success", data: {...}, request_id: "req_xxx" }
 *   - HTTP 200 + code 200 = 成功
 *   - HTTP 200 + code 400 = 业务校验错误（拦截器提示 msg 并 reject）
 *   - HTTP 401 = JWT 失效/过期（清 token 跳登录）
 *   - HTTP 403 = 角色权限不足
 *   - HTTP 429 = 限流
 *   - HTTP 5xx = 服务异常
 *
 * 拦截器剥离 ApiResponse 外壳，业务层直接拿到 data 字段。
 * 导出的 request 包装对象方法返回 Promise<T>（T 为业务数据类型，非 AxiosResponse）。
 */
import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

/** 后端统一响应体外壳 */
export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
  request_id?: string
}

/** 后端统一分页响应（B13/B14 等 list 接口的 data 结构） */
export interface PageResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
  /** 旧接口兼容字段（config.py 的 list 接口用 data 而非 items） */
  data?: T[]
}

const service: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

/** 生成请求ID（链路追踪，与后端 get_request_id 对齐） */
function genRequestId(): string {
  return `req_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`
}

// ── 请求拦截器：自动携带 Token + 请求ID ──────────────
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // 链路追踪头（与后端 X-Request-Id 对齐）
    if (!config.headers['X-Request-Id']) {
      config.headers['X-Request-Id'] = genRequestId()
    }
    return config
  },
  (error) => Promise.reject(error)
)

/** 401 处理标志，避免重复弹窗 */
let isRedirecting = false

/** 401 跳登录（避免重复跳转） */
function redirectToLogin(): void {
  if (isRedirecting) return
  isRedirecting = true
  localStorage.removeItem('admin_token')
  sessionStorage.removeItem('admin_user_info')
  ElMessage.error('登录已超时，请重新登录')
  // 用 location 跳转避免路由守卫循环
  window.location.href = `/login?redirect=${encodeURIComponent(
    window.location.pathname + window.location.search
  )}`
  setTimeout(() => {
    isRedirecting = false
  }, 1000)
}

// ── 响应拦截器：剥离 ApiResponse 外壳 + 统一错误处理 ──────────────
// 兼容两种后端响应格式：
// 1. 新接口（B13/B14）：{ code, msg, data, request_id } —— 剥离外壳返回 data
// 2. 旧接口（config.py）：直接返回业务对象或 { total, page, page_size, data } —— 原样返回
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // 文件流下载等非 JSON 响应直接返回原始数据
    const contentType = String(response.headers['content-type'] || '')
    if (
      response.config.responseType === 'blob' ||
      contentType.includes('application/octet-stream')
    ) {
      return response.data as unknown
    }

    const body = response.data
    // 非对象或无 code 字段 → 旧接口直接返回业务数据
    if (
      body === null ||
      typeof body !== 'object' ||
      typeof (body as Record<string, unknown>).code !== 'number'
    ) {
      return body
    }

    // 新接口 ApiResponse 外壳处理
    const apiBody = body as ApiResponse
    if (apiBody.code === 200) {
      return apiBody.data
    }
    // 业务错误（HTTP 200 但 code !== 200）
    const errMsg = apiBody.msg || '请求失败'
    ElMessage.error(errMsg)
    return Promise.reject(new Error(errMsg))
  },
  (error) => {
    if (!error.response) {
      // 网络错误 / 超时
      ElMessage.error(
        error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络连接失败'
      )
      return Promise.reject(error)
    }
    const { status, data } = error.response
    const msg = data?.msg || data?.detail || data?.message
    switch (status) {
      case 401:
        redirectToLogin()
        break
      case 403:
        ElMessage.error(msg || '当前账号无操作权限')
        break
      case 404:
        ElMessage.error(msg || '请求资源不存在')
        break
      case 429:
        ElMessage.error(msg || '操作过于频繁，请稍后重试')
        break
      default:
        if (status >= 500) {
          ElMessage.error(msg || '服务器内部错误，请稍后重试')
        } else {
          ElMessage.error(msg || `请求失败（${status}）`)
        }
    }
    return Promise.reject(error)
  }
)

/**
 * 业务层 request 封装
 *
 * 拦截器已剥离 ApiResponse 外壳，方法返回 Promise<T>（T 为业务数据类型）。
 *
 * 用法：
 *   import request from '@/utils/request'
 *   const data = await request.get<GoodsItem[]>('/v1/admin/goods')
 *   const page = await request.get<PageResponse<GoodsItem>>('/v1/admin/goods', { params })
 */
const request = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.get(url, config) as unknown as Promise<T>
  },
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return service.post(url, data, config) as unknown as Promise<T>
  },
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return service.put(url, data, config) as unknown as Promise<T>
  },
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.delete(url, config) as unknown as Promise<T>
  },
}

export default request

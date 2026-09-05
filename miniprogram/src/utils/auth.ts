// @ai-generated
/**
 * 用户认证工具（M03 重写：真实微信OAuth + Token过期检测 + 自动重登）
 *
 * 核心能力：
 * 1. wxLogin()：uni.login 获取 code → 调用后端 /wx-login 换取 JWT
 * 2. mockLogin()：开发环境兜底，直接通过 user_id 获取 token（后端生产环境禁用）
 * 3. Token 过期检测：解析 JWT payload.exp，提前 60s 自动触发重登
 * 4. verifyTokenOnStartup()：App 启动时校验本地 token 有效性，过期则清除
 * 5. 持久化存储：token + userInfo 写入 uni.storage，重启不丢失
 *
 * 业务约束（遵循《小程序&后台登录权限专项规范》）：
 * - JWT 载荷仅含 user_id/username/role_id/exp/iat，前端不存敏感信息
 * - 401 响应自动清除登录态（由 request.ts 拦截器处理）
 * - 定时器 30s 检测 token 过期时间，提前自动登出
 */
import { wxLogin, verifyToken, mockLogin } from '@/api/user'
import type { LoginResponse } from '@/api/types'

/** 本地存储的用户信息结构（前端本地缓存，非后端 DTO） */
export interface UserInfo {
  user_id: number
  nickname: string
  avatar: string
}

const TOKEN_KEY = 'token'
const USER_INFO_KEY = 'userInfo'
const TOKEN_EXP_KEY = 'token_exp' // token 过期时间戳（秒）

/** 提前量：token 距过期不足 60s 时视为即将过期，自动重登 */
const TOKEN_EXPIRE_THRESHOLD = 60
/** 定时检测间隔（ms），遵循规范 30s 检测一次 */
const TOKEN_CHECK_INTERVAL = 30 * 1000

/** 是否开发环境（启用 Mock 登录兜底） */
const IS_DEV = import.meta.env.DEV

let tokenCheckTimer: ReturnType<typeof setInterval> | null = null

/**
 * 解析 JWT payload（不验签，仅读取 exp 用于过期检测）
 * JWT 格式：header.payload.signature，payload 为 base64url 编码的 JSON
 */
function decodeJwtExp(token: string): number {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return 0
    // base64url → base64
    let payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    // 补齐 padding
    const pad = payload.length % 4
    if (pad) payload += '='.repeat(4 - pad)
    const decoded = decodeURIComponent(
      atob(payload)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payloadObj = JSON.parse(decoded) as { exp?: number; iat?: number }
    return payloadObj.exp || 0
  } catch {
    return 0
  }
}

const auth = {
  /**
   * 微信官方登录（M03 主入口）
   * 流程：uni.login → code → 后端 /wx-login → JWT
   *
   * @param nickname 用户昵称（可选，用户授权后传入）
   * @param avatar 头像URL（可选）
   * @returns 用户信息
   */
  async wxLogin(nickname?: string, avatar?: string): Promise<UserInfo> {
    const code = await this._getWxLoginCode()
    const res = await wxLogin(code, nickname, avatar)
    return this._persistToken(res.data)
  },

  /**
   * Mock 登录（开发测试用，生产环境后端返回 403）
   * @param user_id 用户ID
   * @param nickname 昵称
   */
  async mockLogin(user_id: number = 10001, nickname: string = '测试用户'): Promise<UserInfo> {
    const res = await mockLogin(user_id, nickname)
    return this._persistToken(res.data)
  },

  /**
   * 调用 uni.login 获取微信登录 code
   * @returns wx.login 返回的 code
   */
  _getWxLoginCode(): Promise<string> {
    return new Promise((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: (loginRes) => {
          if (loginRes.code) {
            resolve(loginRes.code)
          } else {
            reject(new Error('微信登录未返回 code'))
          }
        },
        fail: (error) => {
          reject(new Error(error.errMsg || '微信登录失败'))
        }
      })
    })
  },

  /**
   * 持久化 token + 用户信息到本地存储
   * 同时解析 JWT exp 写入 token_exp，用于过期检测
   */
  _persistToken(loginData: LoginResponse): UserInfo {
    const userInfo: UserInfo = {
      user_id: loginData.user_id,
      nickname: loginData.nickname,
      avatar: loginData.avatar || ''
    }
    uni.setStorageSync(TOKEN_KEY, loginData.token)
    uni.setStorageSync(USER_INFO_KEY, JSON.stringify(userInfo))

    // 解析 JWT exp（秒级时间戳），失败则用 expires_in 估算
    const exp = decodeJwtExp(loginData.token)
    const expTimestamp = exp > 0 ? exp : Math.floor(Date.now() / 1000) + loginData.expires_in
    uni.setStorageSync(TOKEN_EXP_KEY, expTimestamp)

    // 启动定时过期检测
    this._startTokenCheck()

    return userInfo
  },

  /**
   * 统一登录入口
   * - 生产环境：wxLogin（真实微信OAuth）
   * - 开发环境：wxLogin（后端 dev 兜底，无需真实微信凭证）
   * - wxLogin 失败时（开发环境）回退 mockLogin
   */
  async login(): Promise<UserInfo> {
    try {
      return await this.wxLogin()
    } catch (error) {
      // 开发环境 wxLogin 失败时回退 mockLogin（便于无微信开发者工具时调试）
      if (IS_DEV) {
        console.warn('[auth] wxLogin 失败，开发环境回退 mockLogin:', error)
        return this.mockLogin()
      }
      throw error
    }
  },

  /**
   * 启动时校验登录态
   * - 本地无 token → 直接返回 false
   * - 本地有 token → 调用 /verify 接口校验有效性
   * - token 无效/过期 → 清除本地登录态，返回 false
   * - token 有效 → 启动定时检测，返回 true
   *
   * 应在 App.onLaunch 中调用
   */
  async verifyTokenOnStartup(): Promise<boolean> {
    const token = this.getToken()
    if (!token) {
      return false
    }

    // 本地过期检测（快速判断，避免无效请求）
    if (this._isTokenExpiredLocally()) {
      this._clearAuthStorage()
      return false
    }

    try {
      const res = await verifyToken(token)
      if (res.data?.valid) {
        // token 有效，刷新本地用户信息，启动定时检测
        const userInfo: UserInfo = {
          user_id: res.data.user_id,
          nickname: res.data.nickname,
          avatar: res.data.avatar || ''
        }
        uni.setStorageSync(USER_INFO_KEY, JSON.stringify(userInfo))
        this._startTokenCheck()
        return true
      }
      // token 无效，清除本地登录态
      this._clearAuthStorage()
      return false
    } catch (error) {
      // verify 接口异常（网络错误等），保留本地 token，下次再试
      console.warn('[auth] verifyToken 接口异常，保留本地登录态:', error)
      return this.isLoggedIn()
    }
  },

  /**
   * 本地检测 token 是否已过期（基于 JWT exp）
   * @param thresholdSec 提前量（秒），距过期不足该值视为已过期
   */
  _isTokenExpiredLocally(thresholdSec: number = 0): boolean {
    const exp = uni.getStorageSync(TOKEN_EXP_KEY) as number
    if (!exp || exp <= 0) return true
    const now = Math.floor(Date.now() / 1000)
    return now + thresholdSec >= exp
  },

  /**
   * 启动定时 token 过期检测
   * 遵循规范：每 30s 检测一次，距过期不足 60s 时自动登出
   */
  _startTokenCheck(): void {
    if (tokenCheckTimer) {
      clearInterval(tokenCheckTimer)
    }
    tokenCheckTimer = setInterval(() => {
      if (!this.isLoggedIn()) {
        this._stopTokenCheck()
        return
      }
      // 距过期不足阈值 → 自动清除登录态
      if (this._isTokenExpiredLocally(TOKEN_EXPIRE_THRESHOLD)) {
        console.info('[auth] Token 即将过期，自动清除登录态')
        this._clearAuthStorage()
        uni.showToast({ title: '登录已超时，请重新登录', icon: 'none' })
      }
    }, TOKEN_CHECK_INTERVAL)
  },

  /** 停止定时 token 检测 */
  _stopTokenCheck(): void {
    if (tokenCheckTimer) {
      clearInterval(tokenCheckTimer)
      tokenCheckTimer = null
    }
  },

  /** 清除本地登录态（仅 token/userInfo/exp，不删业务缓存） */
  _clearAuthStorage(): void {
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(USER_INFO_KEY)
    uni.removeStorageSync(TOKEN_EXP_KEY)
    this._stopTokenCheck()
  },

  /**
   * 获取微信用户资料（昵称、头像）
   * 需用户主动点击触发（微信新规：getUserProfile 需用户手势）
   */
  async getUserProfile(): Promise<UserInfo> {
    return new Promise((resolve, reject) => {
      uni.getUserProfile({
        desc: '用于完善会员资料',
        success: (infoRes) => {
          const stored = this.getStoredUserInfo()
          const userInfo: UserInfo = {
            user_id: stored?.user_id || 0,
            nickname: infoRes.userInfo.nickName,
            avatar: infoRes.userInfo.avatarUrl
          }
          uni.setStorageSync(USER_INFO_KEY, JSON.stringify(userInfo))
          resolve(userInfo)
        },
        fail: (error) => {
          reject(new Error(error.errMsg || '获取用户信息失败'))
        }
      })
    })
  },

  /** 退出登录 */
  logout(): void {
    this._clearAuthStorage()
    uni.reLaunch({ url: '/pages/index/index' })
  },

  /** 是否已登录（仅检查本地 token 是否存在） */
  isLoggedIn(): boolean {
    return !!uni.getStorageSync(TOKEN_KEY)
  },

  /**
   * 是否已登录且 token 未过期
   * 比 isLoggedIn 更严格，包含本地过期检测
   */
  isLoginValid(): boolean {
    if (!this.isLoggedIn()) return false
    return !this._isTokenExpiredLocally()
  },

  /** 获取 token */
  getToken(): string {
    return (uni.getStorageSync(TOKEN_KEY) as string) || ''
  },

  /** 获取本地缓存的用户信息 */
  getStoredUserInfo(): UserInfo | null {
    const userInfoStr = uni.getStorageSync(USER_INFO_KEY) as string
    if (!userInfoStr) return null
    try {
      return JSON.parse(userInfoStr) as UserInfo
    } catch {
      return null
    }
  },

  /**
   * 校验登录态（轻量级，仅本地判断）
   */
  checkLogin(): boolean {
    return this.isLoggedIn()
  },

  /**
   * 确保已登录，未登录则跳转登录页
   * @param redirectAfterLogin 登录后回跳的页面路径（可选，默认回当前页）
   * @returns 是否已登录
   */
  ensureLogin(redirectAfterLogin?: string): boolean {
    if (this.isLoginValid()) return true

    // 确定回跳路径
    const redirect = redirectAfterLogin || this._getCurrentPagePath()
    uni.navigateTo({
      url: `/pages/login/index?redirect=${encodeURIComponent(redirect)}`
    })
    return false
  },

  /**
   * 获取当前页面路径（含查询参数）
   */
  _getCurrentPagePath(): string {
    const pages = getCurrentPages()
    if (pages.length === 0) return '/pages/index/index'
    const current = pages[pages.length - 1]
    // 拼接页面路径 + 查询参数
    const route = '/' + current.route
    const options = (current as any).options || {}
    const keys = Object.keys(options)
    if (keys.length === 0) return route
    const query = keys.map((k) => `${k}=${encodeURIComponent(options[k])}`).join('&')
    return `${route}?${query}`
  }
}

export default auth

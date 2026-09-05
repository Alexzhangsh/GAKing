// @ai-generated
/**
 * 管理员用户状态管理（Pinia）
 *
 * 职责：
 * 1. 管理 token、用户信息、权限码列表
 * 2. 登录/登出/刷新用户信息
 * 3. 权限校验 hasPermission（超管 * 通配）
 *
 * 持久化策略：
 * - token → localStorage.admin_token（长期有效，关闭浏览器仍保留）
 * - userInfo / permissions → sessionStorage（关闭标签页清空，安全考量）
 *   登录后若 sessionStorage 为空但 token 存在，路由守卫会调 fetchUserInfo 重建
 */
import { defineStore } from 'pinia'
import { authApi, type AdminLoginRequest, type AdminUserInfoResponse } from '@/api/auth'

const TOKEN_KEY = 'admin_token'
const USER_INFO_KEY = 'admin_user_info'

/** 从 sessionStorage 读取用户信息 */
function loadUserInfoFromStorage(): AdminUserInfoResponse | null {
  try {
    const raw = sessionStorage.getItem(USER_INFO_KEY)
    return raw ? (JSON.parse(raw) as AdminUserInfoResponse) : null
  } catch {
    return null
  }
}

interface UserState {
  token: string
  userInfo: AdminUserInfoResponse | null
  /** 权限码列表（含 * 表示超管） */
  permissions: string[]
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    userInfo: loadUserInfoFromStorage(),
    permissions: loadUserInfoFromStorage()?.permissions || [],
  }),

  getters: {
    /** 是否已登录 */
    isLoggedIn: (state): boolean => !!state.token,
    /** 是否超管（permissions 含 *） */
    isSuperAdmin: (state): boolean => state.permissions.includes('*'),
    /** 用户显示名（优先 real_name，其次 username） */
    displayName: (state): string =>
      state.userInfo?.real_name || state.userInfo?.username || '管理员',
    /** 角色名 */
    roleName: (state): string => state.userInfo?.role_name || '',
  },

  actions: {
    /**
     * 登录
     * @returns 登录响应（含 must_change_password 标志）
     */
    async login(params: AdminLoginRequest) {
      const res = await authApi.login(params)
      this.token = res.token
      localStorage.setItem(TOKEN_KEY, res.token)

      // 登录响应已含 permissions，先初始化避免后续 fetchUserInfo 期间无权限态
      this.permissions = res.permissions || []
      // 构造 userInfo 雏形，fetchUserInfo 会补全 phone/email 等字段
      this.userInfo = {
        user_id: res.user_id,
        username: res.username,
        real_name: res.real_name,
        phone: '',
        email: '',
        role_id: res.role_id,
        role_name: res.role_name,
        permissions: res.permissions || [],
      }
      sessionStorage.setItem(USER_INFO_KEY, JSON.stringify(this.userInfo))
      return res
    },

    /** 登出（调后端记录审计日志 + 清前端状态） */
    async logout() {
      try {
        await authApi.logout()
      } catch {
        // 即使后端登出失败（如 token 已过期），也要清前端状态
      } finally {
        this.clearAuthState()
      }
    },

    /** 清除本地登录态 */
    clearAuthState() {
      this.token = ''
      this.userInfo = null
      this.permissions = []
      localStorage.removeItem(TOKEN_KEY)
      sessionStorage.removeItem(USER_INFO_KEY)
    },

    /** 刷新用户信息（用于 token 存在但 sessionStorage 为空的场景） */
    async fetchUserInfo() {
      if (!this.token) return null
      try {
        const info = await authApi.getMe()
        this.userInfo = info
        this.permissions = info.permissions || []
        sessionStorage.setItem(USER_INFO_KEY, JSON.stringify(info))
        return info
      } catch {
        // token 失效，清除
        this.clearAuthState()
        return null
      }
    },

    /**
     * 权限校验
     * @param code 权限码字符串或数组（数组为"或"关系，满足任一即通过）
     * @returns 是否有权限
     */
    hasPermission(code: string | string[]): boolean {
      if (!code) return true
      if (this.permissions.includes('*')) return true
      const codes = Array.isArray(code) ? code : [code]
      return codes.some((c) => this.permissions.includes(c))
    },
  },
})

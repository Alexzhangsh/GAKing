// @ai-generated
/**
 * 后台管理员认证 API
 * 对接后端路由：/api/v1/admin/auth
 * 字段与 src/schemas/b14_auth.py 严格对齐（snake_case）
 */
import request from '@/utils/request'

/** 管理员登录请求体 */
export interface AdminLoginRequest {
  username: string
  password: string
}

/** 管理员登录响应体 */
export interface AdminLoginResponse {
  token: string
  expires_in: number
  user_id: number
  username: string
  real_name: string
  role_id: number
  role_name: string
  permissions: string[]
  must_change_password: boolean
}

/** 管理员个人信息响应体（/auth/me） */
export interface AdminUserInfoResponse {
  user_id: number
  username: string
  real_name: string
  phone: string
  email: string
  role_id: number
  role_name: string
  permissions: string[]
}

/** 管理员修改密码请求体 */
export interface AdminChangePasswordRequest {
  old_password: string
  new_password: string
}

export const authApi = {
  /** 管理员登录（无需 JWT，独立防爆破） */
  login(data: AdminLoginRequest) {
    return request.post<AdminLoginResponse>('/v1/admin/auth/login', data)
  },
  /** 管理员登出（记录审计日志，前端清 token） */
  logout() {
    return request.post<{ user_id: number }>('/v1/admin/auth/logout')
  },
  /** 获取当前登录管理员信息（含角色 + 权限码列表） */
  getMe() {
    return request.get<AdminUserInfoResponse>('/v1/admin/auth/me')
  },
  /** 管理员自助修改密码（校验原密码） */
  changePassword(data: AdminChangePasswordRequest) {
    return request.put<{ user_id: number }>('/v1/admin/auth/password', data)
  },
}

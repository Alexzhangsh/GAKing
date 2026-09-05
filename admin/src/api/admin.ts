// @ai-generated
/**
 * 管理员账号管理 API
 * 对接后端路由：/api/v1/admin/accounts（权限码：rbac:manage）
 * 字段与后端管理员表严格对齐
 *
 * 业务模型：
 * - 管理员账号绑定单一角色
 * - 状态：NORMAL 正常 / FROZEN 冻结
 * - 支持重置密码、启用/冻结
 */
import request from '@/utils/request'

/** 管理员状态 */
export const AdminStatus = {
  NORMAL: 'NORMAL',
  FROZEN: 'FROZEN',
} as const

/** 管理员列表项 */
export interface AdminItem {
  id: number
  username: string
  real_name: string
  phone: string
  email: string
  role_id: number
  role_name: string
  status: boolean
  create_time: string | null
}

/** 管理员列表响应 */
export interface AdminListResponse {
  items: AdminItem[]
  total: number
  page: number
  page_size: number
}

/** 管理员列表查询参数 */
export interface AdminListParams {
  page: number
  page_size: number
  keyword?: string
  role_id?: number
  status?: string
}

/** 创建管理员请求 */
export interface AdminCreateRequest {
  username: string
  real_name: string
  password: string
  phone?: string
  email?: string
  role_id: number
}

/** 更新管理员请求 */
export interface AdminUpdateRequest {
  real_name?: string
  phone?: string
  email?: string
  role_id?: number
  status?: boolean
}

/** 重置密码请求 */
export interface AdminResetPasswordRequest {
  new_password: string
}

/** 冻结/解冻请求 */
export interface AdminStatusUpdateRequest {
  target_status: string
  reason?: string
}

export const adminApi = {
  /** 管理员列表 */
  list(params: AdminListParams) {
    return request.get<AdminListResponse>('/v1/admin/rbac/users', { params })
  },

  /** 创建管理员账号 */
  create(data: AdminCreateRequest) {
    return request.post<AdminItem>('/v1/admin/rbac/users', data)
  },

  /** 更新管理员信息（分配角色） */
  update(adminId: number, data: AdminUpdateRequest) {
    return request.put<AdminItem>(`/v1/admin/rbac/users/${adminId}`, data)
  },

  /** 删除管理员账号（危险操作） */
  remove(adminId: number) {
    return request.delete<{ success: boolean }>(`/v1/admin/rbac/users/${adminId}`)
  },

  /** 重置密码 */
  resetPassword(adminId: number, data: AdminResetPasswordRequest) {
    return request.put(`/v1/admin/rbac/users/${adminId}/password`, data)
  },

  /** 冻结账号 */
  freeze(adminId: number, data: AdminStatusUpdateRequest) {
    return request.put(`/v1/admin/rbac/users/${adminId}/freeze`, data)
  },

  /** 解冻账号 */
  unfreeze(adminId: number, data: AdminStatusUpdateRequest) {
    return request.put(`/v1/admin/rbac/users/${adminId}/unfreeze`, data)
  },
}

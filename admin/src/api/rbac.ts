// @ai-generated
/**
 * RBAC 角色管理 API
 * 对接后端路由：/api/v1/admin/rbac（权限码：rbac:manage）
 * 字段与后端角色表严格对齐
 *
 * 业务模型：
 * - 角色 → 权限码（多对多）
 * - 管理员 → 角色（多对一）
 * - 权限码列表由后端统一暴露
 */
import request from '@/utils/request'

/** 角色状态 */
export const RoleStatus = {
  ENABLED: 'ENABLED',
  DISABLED: 'DISABLED',
} as const

/** 角色列表项 */
export interface RoleItem {
  id: number
  role_name: string
  role_desc: string
  status: boolean
  /** 已绑定权限码列表 */
  permissions: string[]
  /** 关联管理员数量 */
  admin_user_count: number
  create_time: string | null
  update_time: string | null
}

/** 角色列表响应 */
export interface RoleListResponse {
  items: RoleItem[]
  total: number
  page: number
  page_size: number
}

/** 角色列表查询参数 */
export interface RoleListParams {
  page: number
  page_size: number
  keyword?: string
  status?: string
}

/** 创建角色请求 */
export interface RoleCreateRequest {
  role_name: string
  role_desc?: string
  permissions: string[]
  status?: boolean
}

/** 更新角色请求 */
export interface RoleUpdateRequest {
  role_name?: string
  role_desc?: string
  permissions?: string[]
  status?: boolean
}

/** 权限码目录项（树形扁平结构，用于前端勾选） */
export interface PermissionCatalogItem {
  /** 权限码，如 order:manage */
  code: string
  /** 分组/模块名，如 "订单管理" */
  group: string
  /** 显示标签 */
  label: string
  /** 描述 */
  description?: string
}

/** 角色绑定权限码请求 */
export interface RoleBindPermissionsRequest {
  permission_codes: string[]
}

export const rbacApi = {
  /** 角色列表 */
  list(params: RoleListParams) {
    return request.get<RoleListResponse>('/v1/admin/rbac/roles', { params })
  },

  /** 角色详情（含已绑定权限码） */
  getDetail(roleId: number) {
    return request.get<RoleItem>(`/v1/admin/rbac/roles/${roleId}`)
  },

  /** 创建角色 */
  create(data: RoleCreateRequest) {
    return request.post<RoleItem>('/v1/admin/rbac/roles', data)
  },

  /** 更新角色（含权限码绑定） */
  update(roleId: number, data: RoleUpdateRequest) {
    return request.put<RoleItem>(`/v1/admin/rbac/roles/${roleId}`, data)
  },

  /** 删除角色（需无关联管理员） */
  remove(roleId: number) {
    return request.delete<{ success: boolean }>(`/v1/admin/rbac/roles/${roleId}`)
  },

  /** 启用角色 */
  enable(roleId: number) {
    return request.put(`/v1/admin/rbac/roles/${roleId}/enable`, {
      status: RoleStatus.ENABLED,
    })
  },

  /** 禁用角色 */
  disable(roleId: number) {
    return request.put(`/v1/admin/rbac/roles/${roleId}/disable`, {
      status: RoleStatus.DISABLED,
    })
  },

  /** 获取全量权限码目录（用于勾选） */
  getPermissionCatalog() {
    return request.get<PermissionCatalogItem[]>('/v1/admin/rbac/permissions')
  },
}

// @ai-generated
/**
 * 用户/会员/资产 管理后台 API
 * 对接后端路由：/api/v1/admin/user（权限码：user:manage）
 * 字段与 src/services/user_service.py 对齐
 *
 * 业务模型：
 * - 普通用户 / 付费会员双体系
 * - 金角币流水（gold_coin_flows）
 * - 佣金账户（commission_accounts）
 * - 用户状态：NORMAL 正常 / FROZEN 冻结
 */
import request from '@/utils/request'

/** 用户状态枚举 */
export const UserStatus = {
  NORMAL: 'NORMAL',
  FROZEN: 'FROZEN',
} as const

export type UserStatusCode = (typeof UserStatus)[keyof typeof UserStatus]

/** 用户类型 */
export const UserType = {
  NORMAL: 'NORMAL',
  VIP: 'VIP',
} as const

/** 用户列表项 */
export interface UserItem {
  id: number
  nickname: string
  avatar: string
  phone: string
  user_type: string
  status: string
  gold_coin_balance: string
  commission_balance: string
  total_earned_commission: string
  total_withdrawn: string
  order_count: number
  register_time: string | null
  last_login_time: string | null
}

/** 用户列表响应 */
export interface UserListResponse {
  items: UserItem[]
  total: number
  page: number
  page_size: number
}

/** 用户列表查询参数 */
export interface UserListParams {
  page: number
  page_size: number
  keyword?: string
  user_type?: string
  status?: string
}

/** 用户详情（含资产） */
export interface UserDetail extends UserItem {
  /** 金角币流水 */
  gold_coin_flows: GoldCoinFlowItem[]
  /** 佣金账户流水 */
  commission_flows: CommissionAccountFlowItem[]
}

/** 金角币流水项 */
export interface GoldCoinFlowItem {
  id: number
  flow_type: string
  amount: string
  balance_after: string
  remark: string
  related_order_id: number | null
  create_time: string | null
}

/** 佣金账户流水项 */
export interface CommissionAccountFlowItem {
  id: number
  flow_type: string
  amount: string
  balance_after: string
  settle_status: string
  related_order_id: number | null
  remark: string
  create_time: string | null
}

/** 冻结/解冻请求 */
export interface UserStatusUpdateRequest {
  target_status: string
  reason?: string
}

export const userApi = {
  /** 用户列表（多条件筛选） */
  list(params: UserListParams) {
    return request.get<UserListResponse>('/v1/admin/users-manage', { params })
  },

  /** 用户详情（含金角币/佣金流水） */
  getDetail(userId: number) {
    return request.get<UserDetail>(`/v1/admin/users-manage/${userId}`)
  },

  /** 冻结账户 */
  freeze(userId: number, data: UserStatusUpdateRequest) {
    return request.put(`/v1/admin/users-manage/${userId}/freeze`, data)
  },

  /** 解冻账户 */
  unfreeze(userId: number, data: UserStatusUpdateRequest) {
    return request.put(`/v1/admin/users-manage/${userId}/unfreeze`, data)
  },
}

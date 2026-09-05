// @ai-generated
/**
 * 提现审核后台 API
 * 对接后端路由：/api/v1/admin/withdraw（权限码：withdraw:review）
 * 字段与 src/services/withdraw_service.py 对齐
 *
 * 提现状态机：
 *   PENDING 待审核 → APPROVED 审核通过 → PROCESSING 打款中 → SUCCESS 打款成功
 *   PENDING → REJECTED 驳回 / 审核失败
 *   APPROVED/PROCESSING → REJECTED 打款失败退回
 */
import request from '@/utils/request'

/** 提现状态码 */
export const WithdrawStatus = {
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  PROCESSING: 'PROCESSING',
  SUCCESS: 'SUCCESS',
  REJECTED: 'REJECTED',
} as const

export type WithdrawStatusCode = (typeof WithdrawStatus)[keyof typeof WithdrawStatus]

/** 提现状态元数据 */
export const WithdrawStatusMeta: Record<
  string,
  { label: string; type: 'warning' | 'success' | 'info' | 'danger' }
> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '审核通过', type: 'info' },
  PROCESSING: { label: '打款中', type: 'info' },
  SUCCESS: { label: '已到账', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
}

/** 提现申请列表项 */
export interface WithdrawApplyItem {
  id: number
  user_id: number
  apply_amount: string
  fee: string
  actual_amount: string
  status: string
  bank_name: string
  bank_card_no: string
  apply_time: string | null
  review_time: string | null
  review_user_id: number | null
  review_remark: string
  reject_reason: string
  transfer_batch_id: string
  fail_time: string | null
  fail_reason: string
  create_time: string | null
  update_time: string | null
}

/** 提现列表响应 */
export interface WithdrawListResponse {
  list: WithdrawApplyItem[]
  total: number
  page: number
  page_size: number
}

/** 提现列表查询参数 */
export interface WithdrawListParams {
  page: number
  page_size: number
  user_id?: number
  status?: string
}

/** 审核通过请求 */
export interface WithdrawApproveRequest {
  review_remark?: string
}

/** 驳回请求 */
export interface WithdrawRejectRequest {
  reject_reason: string
}

/** 打款完成请求 */
export interface WithdrawCompleteRequest {
  transfer_batch_id: string
}

/** 打款失败退回请求 */
export interface WithdrawFailRequest {
  reason: string
}

export const withdrawApi = {
  /** 提现申请列表（后台审核工作台） */
  list(params: WithdrawListParams) {
    return request.get<WithdrawListResponse>('/v1/admin/withdraw/applies', { params })
  },

  /** 审核通过（PENDING → APPROVED） */
  approve(applyId: number, data: WithdrawApproveRequest) {
    return request.put(`/v1/admin/withdraw/applies/${applyId}/approve`, data)
  },

  /** 驳回（PENDING → REJECTED） */
  reject(applyId: number, data: WithdrawRejectRequest) {
    return request.put(`/v1/admin/withdraw/applies/${applyId}/reject`, data)
  },

  /** 标记打款完成（APPROVED/PROCESSING → SUCCESS） */
  complete(applyId: number, data: WithdrawCompleteRequest) {
    return request.put(`/v1/admin/withdraw/applies/${applyId}/complete`, data)
  },

  /** 打款失败退回（APPROVED/PROCESSING → REJECTED） */
  fail(applyId: number, data: WithdrawFailRequest) {
    return request.put(`/v1/admin/withdraw/applies/${applyId}/fail`, data)
  },
}

// @ai-generated
/**
 * 异常订单管理后台 API
 * 对接后端路由：/api/v1/admin/abnormal-orders
 * 字段与 AbnormalOrder.to_dict() 严格对齐
 */
import request from '@/utils/request'

/** 异常订单复核状态 */
export const ReviewStatus = {
  PENDING: 'PENDING',
  REVIEWED: 'REVIEWED',
  IGNORED: 'IGNORED',
} as const

export type ReviewStatusCode = (typeof ReviewStatus)[keyof typeof ReviewStatus]

/** 复核状态元数据（前端展示用） */
export const ReviewStatusMeta: Record<
  string,
  { label: string; type: 'warning' | 'success' | 'info' | 'danger' }
> = {
  PENDING: { label: '待审核', type: 'warning' },
  REVIEWED: { label: '已复核', type: 'success' },
  IGNORED: { label: '已忽略', type: 'info' },
}

/** 渠道标签 */
export const ChannelMeta: Record<string, { label: string; type: string }> = {
  myq: { label: '喵有券', type: 'primary' },
  orderx: { label: '订单侠', type: 'success' },
  dta: { label: '大淘客', type: 'warning' },
}

/** 异常订单列表项 */
export interface AbnormalOrderItem {
  id: number
  out_order_no: string
  channel_code: string
  goods_id: string
  goods_title: string
  /** 支付金额（元） */
  pay_amount: number
  /** 总佣金（元） */
  total_commission: number
  order_status: string
  pay_time: string | null
  abnormal_reason: string
  matched_click_key: string
  matched_user_id: number
  /** 复核指定归属用户ID */
  assigned_user_id: number
  review_status: string
  review_remark: string
  create_time: string | null
}

/** 异常订单分页列表响应 */
export interface AbnormalOrderListResponse {
  total: number
  page: number
  page_size: number
  items: AbnormalOrderItem[]
}

/** 异常订单统计响应 */
export interface AbnormalOrderStats {
  total: number
  pending: number
  reviewed: number
  ignored: number
}

/** 复核请求体 */
export interface ReviewRequest {
  review_status: string
  review_remark: string
  /** 手动指定归属用户ID（0=不指定） */
  assigned_user_id?: number
}

/** 编辑请求体（复核后修改） */
export interface EditRequest {
  /** 手动指定归属用户ID（0=不指定） */
  assigned_user_id: number
  /** 复核备注 */
  review_remark: string
}

export const abnormalOrderApi = {
  /** 异常订单分页列表 */
  list(params: {
    page: number
    page_size: number
    review_status?: string
    channel_code?: string
    keyword?: string
  }) {
    return request.get<AbnormalOrderListResponse>('/v1/admin/abnormal-orders/list', { params })
  },

  /** 复核异常订单 */
  review(itemId: number, data: ReviewRequest) {
    return request.put<{ id: number; review_status: string }>(
      `/v1/admin/abnormal-orders/${itemId}/review`,
      data
    )
  },

  /** 编辑异常订单（复核后修改归属/备注） */
  edit(itemId: number, data: EditRequest) {
    return request.put<{ id: number; assigned_user_id: number }>(
      `/v1/admin/abnormal-orders/${itemId}/edit`,
      data
    )
  },

  /** 异常订单统计 */
  stats() {
    return request.get<AbnormalOrderStats>('/v1/admin/abnormal-orders/stats')
  },
}
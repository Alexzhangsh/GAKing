// @ai-generated
/**
 * 订单管理后台 API
 * 对接后端路由：/api/v1/cps/order
 * 字段与 src/services/order_service.py → Order.to_dict() 严格对齐
 *
 * 注意：
 * 1. 订单列表返回 { list, total, page, page_size }（list 非 items，与 B13 商品接口不同）
 * 2. Decimal 字段序列化为 string
 * 3. 订单状态码：10=PENDING待付款 / 30=PAID已付款 / 40=SETTLED已结算 / 50=EXPIRED失效 / 60=REFUNDED退款
 */
import request from '@/utils/request'

/** 订单状态枚举 */
export const OrderStatus = {
  PENDING: 10,
  PAID: 30,
  SETTLED: 40,
  EXPIRED: 50,
  REFUNDED: 60,
} as const

export type OrderStatusCode = (typeof OrderStatus)[keyof typeof OrderStatus]

/** 订单状态元数据（前端展示用） */
export const OrderStatusMeta: Record<
  number,
  { label: string; type: 'warning' | 'success' | 'info' | 'danger' }
> = {
  10: { label: '待付款', type: 'warning' },
  30: { label: '已付款', type: 'info' },
  40: { label: '已结算', type: 'success' },
  50: { label: '已失效', type: 'info' },
  60: { label: '已退款', type: 'danger' },
}

/** 渠道标签 */
export const ChannelMeta: Record<string, { label: string; type: string }> = {
  myq: { label: '喵有券', type: 'primary' },
  orderx: { label: '订单侠', type: 'success' },
  dta: { label: '大淘客', type: 'warning' },
}

/** 订单列表项（Order.to_dict() 序列化结果） */
export interface OrderItem {
  id: number
  out_order_no: string
  internal_order_no: string
  user_id: number
  goods_title: string
  goods_img: string
  /** 支付金额（元，string） */
  pay_amount: string
  /** 总佣金（元，string） */
  total_commission: string
  /** 用户佣金（元，string） */
  user_commission: string
  /** 平台佣金（元，string） */
  platform_commission: string
  channel_code: string
  /** 订单状态码 10/30/40/50/60 */
  order_status: number
  transfer_status: string
  pay_time: string | null
  settle_time: string | null
  create_time: string | null
  update_time: string | null
  is_delete: boolean
}

/** 订单详情（含佣金流水） */
export interface OrderDetail extends OrderItem {
  commission_flows: CommissionFlowItem[]
}

/** 佣金流水项 */
export interface CommissionFlowItem {
  id: number
  order_id: number
  user_id: number
  flow_type: string
  flow_amount: string
  transfer_status: string
  settle_time: string | null
  remark: string
  create_time: string | null
}

/** 订单列表响应（后端返回 list 非 items） */
export interface OrderListResponse {
  list: OrderItem[]
  total: number
  page: number
  page_size: number
}

/** 订单列表查询参数 */
export interface OrderListParams {
  page: number
  page_size: number
  channel_code?: string
  order_status?: number
  user_id?: number
}

/** 订单状态变更请求 */
export interface OrderStatusUpdateRequest {
  order_id: number
  target_status: number
}

export const orderApi = {
  /** 订单列表（多条件筛选） */
  list(params: OrderListParams) {
    return request.get<OrderListResponse>('/v1/cps/order', { params })
  },

  /** 订单详情（含佣金流水） */
  getDetail(orderId: number) {
    return request.get<OrderDetail>(`/v1/cps/order/${orderId}`)
  },

  /** 手动变更订单状态 */
  updateStatus(data: OrderStatusUpdateRequest) {
    return request.put<OrderItem>('/v1/cps/order/status', data)
  },
}

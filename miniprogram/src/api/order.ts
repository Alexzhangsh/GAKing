// @ai-generated
/**
 * CPS 订单 API（对接后端 src/api/v1/cps_order.py）
 *
 * 接口清单：
 * 1. GET  /api/v1/cps/order           订单分页列表（多条件筛选：渠道/状态/用户）
 * 2. GET  /api/v1/cps/order/{id}      订单详情（含佣金流水）
 *
 * 注意：订单列表 user_id 为查询参数（后端一期设计），C 端调用时传入当前登录用户 ID
 */
import http from '@/utils/request'
import type {
  ApiResponse,
  OrderDetailResponse,
  OrderListResponse,
  OrderStatus
} from './types'

/**
 * 查询我的订单列表（分页 + 状态筛选）
 * @param user_id 用户ID
 * @param page 页码（从1开始）
 * @param page_size 每页条数
 * @param order_status 订单状态筛选（可选）
 */
export function listMyOrders(
  user_id: number,
  page: number = 1,
  page_size: number = 20,
  order_status?: OrderStatus
): Promise<ApiResponse<OrderListResponse>> {
  const params: Record<string, any> = {
    user_id,
    page,
    page_size
  }
  if (order_status !== undefined && order_status !== null) {
    params.order_status = order_status
  }
  return http.get<OrderListResponse>('/api/v1/cps/order', params)
}

/**
 * 查询订单详情（含佣金流水）
 * @param order_id 订单ID
 */
export function getOrderDetail(
  order_id: number
): Promise<ApiResponse<OrderDetailResponse>> {
  return http.get<OrderDetailResponse>(`/api/v1/cps/order/${order_id}`)
}

export default {
  listMyOrders,
  getOrderDetail
}

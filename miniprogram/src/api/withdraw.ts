// @ai-generated
/**
 * 用户佣金提现 API（对接后端 src/api/v1/withdraw.py）
 *
 * 接口清单：
 * 1. GET  /api/v1/withdraw/account   查询我的佣金账户余额
 * 2. POST /api/v1/withdraw/apply     发起提现（扣可用→冻结，生成 PENDING 申请）
 * 3. GET  /api/v1/withdraw/applies   我的提现记录（分页）
 *
 * 身份识别：JWT（Authorization: Bearer <token>），由 request.ts 自动注入
 */
import http from '@/utils/request'
import type {
  ApiResponse,
  UserAccount,
  WithdrawApplyItem,
  WithdrawApplyRequest,
  WithdrawListResponse
} from './types'

/**
 * 查询我的佣金账户余额
 * - 走读穿缓存，账户不存在返回零余额占位结构
 */
export function getMyAccount(): Promise<ApiResponse<UserAccount>> {
  return http.get<UserAccount>('/api/v1/withdraw/account')
}

/**
 * 发起提现申请
 * @param apply_amount 申请提现金额(元)，需 >= 10 元
 * - 手续费：fee = max(apply_amount × 0.1%, 1元)；actual_amount = apply_amount - fee
 * - 余额联动：available -= apply_amount, frozen += apply_amount
 */
export function applyWithdraw(
  apply_amount: number
): Promise<ApiResponse<WithdrawApplyItem>> {
  const body: WithdrawApplyRequest = { apply_amount }
  return http.post<WithdrawApplyItem>('/api/v1/withdraw/apply', body)
}

/**
 * 查询我的提现记录（分页，按创建时间倒序）
 * @param page 页码（从1开始）
 * @param page_size 每页条数
 */
export function listMyWithdraws(
  page: number = 1,
  page_size: number = 20
): Promise<ApiResponse<WithdrawListResponse>> {
  return http.get<WithdrawListResponse>('/api/v1/withdraw/applies', {
    page,
    page_size
  })
}

export default {
  getMyAccount,
  applyWithdraw,
  listMyWithdraws
}

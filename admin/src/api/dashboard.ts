// @ai-generated
/**
 * 数据大盘 API
 * 对接后端路由：/api/v1/admin/dashboard（权限码：dashboard:view）
 * 字段与 src/schemas/b14_dashboard.py 严格对齐（snake_case）
 */
import request, { PageResponse } from '@/utils/request'

/** 首页 5 张卡片聚合数据 */
export interface DashboardCards {
  total_orders: number
  pending_settle_commission: string
  settled_commission: string
  total_withdrawn: string
  pending_review_withdraws: number
}

/** 佣金统计分组维度 */
export type CommissionGroupBy = 'date' | 'channel' | 'user'

/** 订单趋势分组维度 */
export type OrderTrendGroupBy = 'day' | 'week' | 'month'

/** 佣金统计查询参数 */
export interface CommissionStatsParams {
  group_by: CommissionGroupBy
  /** 起始日期（含，YYYY-MM-DD） */
  start_date: string
  /** 截止日期（不含，YYYY-MM-DD） */
  end_date: string
  page?: number
  page_size?: number
}

/** 订单趋势查询参数 */
export interface OrderTrendParams {
  start_date: string
  end_date: string
  group_by?: OrderTrendGroupBy
}

/** 提现趋势查询参数（复用订单趋势维度） */
export interface WithdrawTrendParams {
  start_date: string
  end_date: string
  group_by?: OrderTrendGroupBy
}

/** 按日期分组佣金统计项 */
export interface CommissionStatsByDateItem {
  date: string
  total_commission: string
  order_count: number
}

/** 按渠道分组佣金统计项 */
export interface CommissionStatsByChannelItem {
  channel_code: string
  total_commission: string
  order_count: number
}

/** 按用户分组佣金统计项 */
export interface CommissionStatsByUserItem {
  user_id: number
  total_commission: string
  order_count: number
}

/** 订单趋势折线数据项 */
export interface OrderTrendItem {
  date: string
  order_count: number
  total_commission: string
}

/** 提现趋势数据项 */
export interface WithdrawTrendItem {
  date: string
  apply_count: number
  withdraw_amount: string
  success_amount: string
}

// ── B17 多渠道聚合统计 ──────────────────────────────

/** 渠道聚合统计单渠道项 */
export interface ChannelAggregateItem {
  channel_code: string
  order_count: number
  total_commission: string
  user_commission: string
  platform_commission: string
  pay_amount: string
  deal_count: number
  deal_amount: string
}

/** 渠道聚合统计响应 */
export interface ChannelAggregateStats {
  channels: Record<string, ChannelAggregateItem>
  total: {
    order_count: number
    total_commission: string
    user_commission: string
    platform_commission: string
    pay_amount: string
    deal_count: number
    deal_amount: string
  }
}

/** 渠道订单趋势项 */
export interface ChannelOrderTrendItem {
  date: string
  channel_code: string
  order_count: number
  total_commission: string
  user_commission: string
  deal_count: number
  deal_amount: string
}

/** 渠道对账差异汇总项 */
export interface ChannelDiffSummaryItem {
  channel_code: string
  diff_count: number
  diff_amount: string
  pending_count: number
  critical_count: number
}

/** 渠道对账差异汇总响应 */
export interface ChannelDiffSummary {
  channels: Record<string, ChannelDiffSummaryItem>
  total: {
    diff_count: number
    pending_count: number
    critical_count: number
    diff_amount: string
  }
}

export const dashboardApi = {
  /** 首页 5 张卡片聚合数据 */
  getCards() {
    return request.get<DashboardCards>('/v1/admin/dashboard/cards')
  },

  /** 多维度佣金统计（按日期/渠道/用户分组） */
  getCommissionStats(params: CommissionStatsParams) {
    return request.get<
      | CommissionStatsByDateItem[]
      | CommissionStatsByChannelItem[]
      | PageResponse<CommissionStatsByUserItem>
    >('/v1/admin/dashboard/commission-stats', { params })
  },

  /** 订单趋势折线数据（按天/周/月分组） */
  getOrderTrend(params: OrderTrendParams) {
    return request.get<OrderTrendItem[]>('/v1/admin/dashboard/order-trend', {
      params,
    })
  },

  /** 提现趋势数据（按天/周/月分组） */
  getWithdrawTrend(params: WithdrawTrendParams) {
    return request.get<{
      group_by: string
      start_date: string
      end_date: string
      total: number
      items: WithdrawTrendItem[]
    }>('/v1/admin/dashboard/withdraw-trend', {
      params,
    })
  },

  // ── B17 多渠道聚合统计 ──────────────────────────────

  /** 多渠道聚合统计（佣金/订单/成交分渠道汇总） */
  getChannelAggregateStats(params: {
    start_date: string
    end_date: string
  }) {
    return request.get<ChannelAggregateStats>(
      '/v1/admin/channel-reconciliation/aggregate-stats',
      { params },
    )
  },

  /** 渠道订单趋势（按天/周/月，支持单渠道筛选） */
  getChannelOrderTrend(params: {
    start_date: string
    end_date: string
    group_by?: OrderTrendGroupBy
    channel_code?: string
  }) {
    return request.get<{
      group_by: string
      start_date: string
      end_date: string
      channel_code: string | null
      total: number
      items: ChannelOrderTrendItem[]
    }>('/v1/admin/channel-reconciliation/order-trend', { params })
  },

  /** 渠道对账差异汇总（按渠道分组） */
  getChannelDiffSummary(params?: {
    start_date?: string
    end_date?: string
  }) {
    return request.get<ChannelDiffSummary>(
      '/v1/admin/channel-reconciliation/summary',
      { params },
    )
  },
}

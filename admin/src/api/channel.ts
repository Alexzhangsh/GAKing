// @ai-generated
/**
 * F04 渠道配置 API
 * 对接后端路由：/api/v1/admin/channel（权限码：config:manage / channel:test）
 */
import request, { PageResponse } from '@/utils/request'

// ── 渠道配置 ──────────────

export interface ChannelConfig {
  id: number
  channel_code: string
  channel_name: string
  api_token: string
  api_secret: string  // 后端脱敏返回 ***
  pid: string
  settle_rate: number
  status: boolean
  remark: string
  create_time: string | null
  update_time: string | null
}

export interface ChannelConfigCreate {
  channel_code: string
  channel_name?: string
  api_token?: string
  api_secret?: string
  pid?: string
  settle_rate?: number
  status?: boolean
  remark?: string
}

export interface ChannelConfigUpdate {
  channel_name?: string
  api_token?: string
  api_secret?: string
  pid?: string
  settle_rate?: number
  status?: boolean
  remark?: string
}

export const channelConfigApi = {
  list: (params: { page: number; page_size: number }) =>
    request.get<PageResponse<ChannelConfig>>('/v1/admin/channel/list', { params }),
  get: (channelCode: string) =>
    request.get<ChannelConfig>(`/v1/admin/channel/${channelCode}`),
  create: (data: ChannelConfigCreate) =>
    request.post<ChannelConfig>('/v1/admin/channel', data),
  update: (channelCode: string, data: ChannelConfigUpdate) =>
    request.put<ChannelConfig>(`/v1/admin/channel/${channelCode}`, data),
  delete: (channelCode: string) =>
    request.delete(`/v1/admin/channel/${channelCode}`),
}

// ── 渠道密钥测试 ──────────────

export interface ChannelKeyTestRequest {
  channel_code: string
  api_token: string
  api_secret?: string
}

export interface ChannelKeyTestResult {
  success: boolean
  message: string
  channel_code: string
  token_length?: number
  secret_length?: number
}

export const channelTestApi = {
  testKey: (data: ChannelKeyTestRequest) =>
    request.post<ChannelKeyTestResult>('/v1/admin/channel/test-key', data),
}

// ── 渠道佣金策略（F04-2）──────────────

export interface CommissionTier {
  id?: number
  strategy_id?: number
  user_type: number  // 1-普通用户 2-付费会员
  user_type_label?: string
  tier_name: string
  tier_min: number
  tier_max: number  // 0 表示无上限
  user_commission_rate: number  // 0~1
  platform_retention_rate: number  // 0~1
  sort_order: number
}

export interface CommissionStrategy {
  id: number
  channel_code: string
  strategy_name: string
  enabled: boolean
  tier_dimension: number  // 1-按订单金额 2-按订单数量
  tier_dimension_label?: string
  remark: string
  tiers: CommissionTier[]
  create_time: string | null
  update_time: string | null
}

export interface CommissionStrategyCreate {
  channel_code: string
  strategy_name: string
  enabled: boolean
  tier_dimension: number
  remark: string
  tiers: CommissionTier[]
}

export interface CommissionStrategyUpdate {
  strategy_name?: string
  enabled?: boolean
  tier_dimension?: number
  remark?: string
  tiers?: CommissionTier[]
}

export interface CommissionPreviewRequest {
  channel_code: string
  user_type: number
  amount: number
  order_count: number
}

export interface CommissionPreviewResult {
  channel_code: string
  enabled: boolean
  tier_dimension?: number
  matched_tier: CommissionTier | null
  result: {
    total_commission: number
    user_commission: number
    platform_commission: number
    user_rate: number
    platform_rate: number
  } | null
  message: string
}

export interface StrategyAuditLog {
  id: number
  user_id: number
  user_name: string
  action: string
  target_type: string
  target_id: number
  details: Record<string, unknown> | string | null
  ip_address: string
  create_time: string | null
}

export const channelCommissionApi = {
  listStrategies: (params: { page: number; page_size: number; channel_code?: string; enabled?: boolean }) =>
    request.get<PageResponse<CommissionStrategy>>('/v1/admin/channel-commission/strategies', { params }),
  getStrategy: (channelCode: string) =>
    request.get<CommissionStrategy>(`/v1/admin/channel-commission/strategies/${channelCode}`),
  createStrategy: (data: CommissionStrategyCreate) =>
    request.post<CommissionStrategy>('/v1/admin/channel-commission/strategies', data),
  updateStrategy: (channelCode: string, data: CommissionStrategyUpdate) =>
    request.put<CommissionStrategy>(`/v1/admin/channel-commission/strategies/${channelCode}`, data),
  toggleStrategy: (channelCode: string, enabled: boolean) =>
    request.put<{ channel_code: string; enabled: boolean }>(`/v1/admin/channel-commission/strategies/${channelCode}/toggle`, { enabled }),
  preview: (data: CommissionPreviewRequest) =>
    request.post<CommissionPreviewResult>('/v1/admin/channel-commission/preview', data),
  listAuditLogs: (params: { page: number; page_size: number; channel_code?: string }) =>
    request.get<PageResponse<StrategyAuditLog>>('/v1/admin/channel-commission/audit-logs', { params }),
}

// @ai-generated
/**
 * 系统审计日志 API
 * 对接后端路由：/api/v1/admin/audit（权限码：audit:view）
 * 字段与后端审计日志表严格对齐
 *
 * 业务模型：
 * - 记录所有敏感操作（CRUD、登录、权限变更等）
 * - 支持操作人/IP/时间/行为多维度筛选
 */
import request from '@/utils/request'

/** 审计日志列表项（对接后端 AuditLogs 模型） */
export interface AuditLogItem {
  id: number
  /** 操作人 ID */
  user_id: number
  /** 操作人用户名 */
  user_name: string
  /** 操作类型 */
  action: string
  /** 操作目标对象类型 */
  target_type: string
  /** 操作目标 ID */
  target_id: number | null
  /** 详细数据（JSON 字符串） */
  details: string | null
  /** 请求 IP */
  ip_address: string
  /** User-Agent */
  user_agent: string
  /** 操作时间 */
  create_time: string | null
}

/** 审计日志列表响应 */
export interface AuditLogListResponse {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

/** 审计日志列表查询参数 */
export interface AuditLogListParams {
  page: number
  page_size: number
  user_id?: number
  action?: string
  target_type?: string
  start_time?: string
  end_time?: string
}

export const auditApi = {
  /** 审计日志列表（多条件筛选） */
  list(params: AuditLogListParams) {
    return request.get<AuditLogListResponse>('/v1/admin/audit/logs', { params })
  },

  /** 审计日志详情 */
  getDetail(logId: number) {
    return request.get<AuditLogItem>(`/v1/admin/audit/logs/${logId}`)
  },
}
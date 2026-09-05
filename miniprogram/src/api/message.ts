// @ai-generated
/**
 * 站内消息 & 营销消息订阅 API（对接后端 b10_message.py + b15_message_user.py）
 *
 * 接口清单：
 * 1. GET  /api/v1/message/list                   消息列表（分页，按类型筛选）
 * 2. GET  /api/v1/message/unread-count           未读消息数
 * 3. PUT  /api/v1/message/read                   标记已读（单条/全部）
 * 4. GET  /api/v1/message/subscribe/templates    可订阅模板列表
 * 5. GET  /api/v1/message/subscribe/status       我的订阅状态（含过期标记）
 * 6. POST /api/v1/message/subscribe              记录订阅授权结果（accept/reject/expired）
 * 7. POST /api/v1/message/unsubscribe            取消订阅
 */
import http from '@/utils/request'
import type {
  ApiResponse,
  MarkReadRequest,
  MessageListResponse,
  SubscribeRequest,
  SubscribeStatusItem,
  SubscribeTemplate,
  UnreadCountResponse,
  UnsubscribeRequest
} from './types'

/**
 * 1. 查询我的消息列表（分页，按创建时间倒序）
 * @param page 页码（从1开始）
 * @param pageSize 每页条数
 * @param messageType 消息类型筛选（可选）
 */
export function getMessageList(
  page: number = 1,
  pageSize: number = 20,
  messageType?: string
): Promise<ApiResponse<MessageListResponse>> {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (messageType) params.message_type = messageType
  return http.get<MessageListResponse>('/api/v1/message/list', params)
}

/**
 * 2. 查询未读消息数
 */
export function getUnreadCount(): Promise<ApiResponse<UnreadCountResponse>> {
  return http.get<UnreadCountResponse>('/api/v1/message/unread-count')
}

/**
 * 3. 标记消息已读（单条或全部）
 * @param messageId 消息ID（为空时标记全部已读）
 */
export function markMessageRead(messageId?: number): Promise<ApiResponse<{ updated: number; message_id: number | null }>> {
  const body: MarkReadRequest = messageId ? { message_id: messageId } : {}
  return http.put<{ updated: number; message_id: number | null }>('/api/v1/message/read', body)
}

/**
 * 4. 查询可订阅模板列表（启用中的微信订阅消息模板）
 */
export function getSubscribeTemplates(): Promise<ApiResponse<{ list: SubscribeTemplate[] }>> {
  return http.get<{ list: SubscribeTemplate[] }>('/api/v1/message/subscribe/templates')
}

/**
 * 5. 查询我的订阅状态（含过期标记）
 */
export function getSubscribeStatus(): Promise<ApiResponse<{ list: SubscribeStatusItem[] }>> {
  return http.get<{ list: SubscribeStatusItem[] }>('/api/v1/message/subscribe/status')
}

/**
 * 6. 记录订阅授权结果
 * @param templateId 消息模板ID
 * @param action 授权结果：accept=已同意 reject=用户拒绝 expired=授权过期/不可用
 * @param tmplId 微信订阅消息模板ID（可选）
 */
export function recordSubscribe(
  templateId: number,
  action: SubscribeRequest['action'],
  tmplId?: string
): Promise<ApiResponse<any>> {
  const body: SubscribeRequest = { template_id: templateId, action, ...(tmplId ? { tmpl_id: tmplId } : {}) }
  return http.post<any>('/api/v1/message/subscribe', body)
}

/**
 * 7. 取消订阅
 * @param templateId 消息模板ID
 */
export function unsubscribeMessage(templateId: number): Promise<ApiResponse<any>> {
  const body: UnsubscribeRequest = { template_id: templateId }
  return http.post<any>('/api/v1/message/unsubscribe', body)
}

export default {
  getMessageList,
  getUnreadCount,
  markMessageRead,
  getSubscribeTemplates,
  getSubscribeStatus,
  recordSubscribe,
  unsubscribeMessage
}

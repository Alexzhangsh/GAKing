// @ai-generated
/**
 * F04 营销消息 API
 * 对接后端路由：/api/v1/admin/message（权限码：message:manage）
 */
import request, { PageResponse } from '@/utils/request'

// ── 消息模板 ──────────────

export interface MessageTemplate {
  id: number
  template_name: string
  template_type: number  // 1=微信订阅消息 2=站内消息
  tmpl_id: string
  title: string
  content: string
  keywords: string[] | null
  status: number  // 1=启用 0=停用
  remark: string
  create_time: string | null
  update_time: string | null
}

export interface MessageTemplateCreate {
  template_name: string
  template_type: number
  tmpl_id?: string
  title?: string
  content: string
  keywords?: string[]
  remark?: string
}

export interface MessageTemplateUpdate {
  template_name?: string
  template_type?: number
  tmpl_id?: string
  title?: string
  content?: string
  keywords?: string[]
  remark?: string
}

export interface MessageTemplateListParams {
  page: number
  page_size: number
  template_type?: number
  status?: number
}

export const messageTemplateApi = {
  list: (params: MessageTemplateListParams) =>
    request.get<PageResponse<MessageTemplate>>('/v1/admin/message/templates', { params }),
  get: (id: number) =>
    request.get<MessageTemplate>(`/v1/admin/message/templates/${id}`),
  create: (data: MessageTemplateCreate) =>
    request.post<MessageTemplate>('/v1/admin/message/templates', data),
  update: (id: number, data: MessageTemplateUpdate) =>
    request.put<MessageTemplate>(`/v1/admin/message/templates/${id}`, data),
  delete: (id: number) =>
    request.delete(`/v1/admin/message/templates/${id}`),
  toggle: (id: number) =>
    request.put<MessageTemplate>(`/v1/admin/message/templates/${id}/toggle`),
}

// ── 推送记录 ──────────────

export interface PushRecord {
  id: number
  template_id: string
  user_id: string
  push_status: number  // 1=成功 2=失败 3=待发送
  push_time: string | null
  error_msg: string
  create_time: string | null
}

export interface PushRecordListParams {
  page: number
  page_size: number
  template_id?: number
  user_id?: number
  push_status?: number
}

export const pushRecordApi = {
  list: (params: PushRecordListParams) =>
    request.get<PageResponse<PushRecord>>('/v1/admin/message/push-records', { params }),
}

// ── 订阅绑定 ──────────────

export interface SubscribeBinding {
  id: number
  user_id: string
  template_id: string
  subscribe_status: number  // 1=已订阅 0=已取消
  subscribe_time: string | null
  expire_time: string | null
  create_time: string | null
}

export interface SubscribeBindingListParams {
  page: number
  page_size: number
  user_id?: number
  template_id?: number
  subscribe_status?: number
}

export const subscribeBindingApi = {
  list: (params: SubscribeBindingListParams) =>
    request.get<PageResponse<SubscribeBinding>>('/v1/admin/message/subscriptions', { params }),
}

// @ai-generated
import request, { PageResponse } from '@/utils/request'

export interface SystemConfig {
  id: number
  config_key: string
  config_value: string
  config_name: string
  remark: string
  create_time: string
  update_time: string
}

export interface SystemConfigCreate {
  config_key: string
  config_value: string
  config_name: string
  remark?: string
}

export interface SystemConfigUpdate {
  config_value?: string
  config_name?: string
  remark?: string
}

export const systemConfigApi = {
  list: (params: { page: number; page_size: number; config_key?: string }) => request.get<PageResponse<SystemConfig>>('/v1/admin/config/', { params }),
  get: (configKey: string) => request.get<SystemConfig>(`/v1/admin/config/${configKey}`),
  create: (data: SystemConfigCreate) => request.post<SystemConfig>('/v1/admin/config/', data),
  update: (configKey: string, data: SystemConfigUpdate) => request.put<SystemConfig>(`/v1/admin/config/${configKey}`, data),
  delete: (configKey: string) => request.delete(`/v1/admin/config/${configKey}`),
  listRegistry: () => request.get('/v1/admin/config/registry'),
  refreshCache: () => request.post('/v1/admin/config/cache/refresh'),
  batchUpdate: (data: { items: Array<{ config_key: string; config_value: string }> }) => request.put('/v1/admin/config/batch', data),
}

export interface PayConfig {
  id: number
  pay_type: number
  mch_id: string
  api_key: string
  cert_path: string
  notify_url: string
  withdraw_rate: number
  withdraw_min: number
  withdraw_fixed_fee: number
  status: boolean
  remark: string
  create_time: string
  update_time: string
}

export interface PayConfigCreate {
  pay_type?: number
  mch_id?: string
  api_key?: string
  cert_path?: string
  notify_url?: string
  withdraw_rate?: number
  withdraw_min?: number
  withdraw_fixed_fee?: number
  status?: boolean
  remark?: string
}

export interface PayConfigUpdate {
  pay_type?: number
  mch_id?: string
  api_key?: string
  cert_path?: string
  notify_url?: string
  withdraw_rate?: number
  withdraw_min?: number
  withdraw_fixed_fee?: number
  status?: boolean
  remark?: string
}

export const payConfigApi = {
  create: (data: PayConfigCreate) => request.post('/admin/pay-config', data),
  get: (id: number) => request.get<PayConfig>(`/admin/pay-config/${id}`),
  list: (params: { page: number; page_size: number; pay_type?: number }) => request.get<PageResponse<PayConfig>>('/admin/pay-config', { params }),
  update: (id: number, data: PayConfigUpdate) => request.put<PayConfig>(`/admin/pay-config/${id}`, data),
  delete: (id: number) => request.delete(`/admin/pay-config/${id}`)
}

export interface CloudConfig {
  id: number
  config_name: string
  cdn_domain: string
  obs_bucket: string
  obs_endpoint: string
  access_key: string
  secret_key: string
  status: boolean
  remark: string
  create_time: string
  update_time: string
}

export interface CloudConfigCreate {
  config_name: string
  cdn_domain?: string
  obs_bucket?: string
  obs_endpoint?: string
  access_key?: string
  secret_key?: string
  status?: boolean
  remark?: string
}

export interface CloudConfigUpdate {
  config_name?: string
  cdn_domain?: string
  obs_bucket?: string
  obs_endpoint?: string
  access_key?: string
  secret_key?: string
  status?: boolean
  remark?: string
}

export const cloudConfigApi = {
  create: (data: CloudConfigCreate) => request.post('/admin/cloud-config', data),
  get: (id: number) => request.get<CloudConfig>(`/admin/cloud-config/${id}`),
  list: (params: { page: number; page_size: number; status?: boolean }) => request.get<PageResponse<CloudConfig>>('/admin/cloud-config', { params }),
  update: (id: number, data: CloudConfigUpdate) => request.put<CloudConfig>(`/admin/cloud-config/${id}`, data),
  delete: (id: number) => request.delete(`/admin/cloud-config/${id}`)
}

export interface ChannelMapping {
  id: number
  channel_code: string
  third_field: string
  system_field: string
  field_desc: string
  status: boolean
  sort_num: number
  remark: string
  create_time: string
  update_time: string
}

export interface ChannelMappingCreate {
  channel_code: string
  third_field: string
  system_field: string
  field_desc?: string
  status?: boolean
  sort_num?: number
  remark?: string
}

export interface ChannelMappingUpdate {
  third_field?: string
  system_field?: string
  field_desc?: string
  status?: boolean
  sort_num?: number
  remark?: string
}

export const channelMappingApi = {
  create: (data: ChannelMappingCreate) => request.post('/admin/channel-mapping', data),
  get: (id: number) => request.get<ChannelMapping>(`/admin/channel-mapping/${id}`),
  list: (params: { page: number; page_size: number; channel_code?: string }) => request.get<PageResponse<ChannelMapping>>('/admin/channel-mapping', { params }),
  update: (id: number, data: ChannelMappingUpdate) => request.put<ChannelMapping>(`/admin/channel-mapping/${id}`, data),
  delete: (id: number) => request.delete(`/admin/channel-mapping/${id}`)
}
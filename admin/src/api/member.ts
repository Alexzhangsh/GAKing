// @ai-generated
/**
 * X02-1 会员套餐管理 API
 * 对接后端路由：
 *   /api/v1/admin/member-package（权限码：member:manage）
 *   /api/v1/admin/member-record（权限码：member:view / member:export）
 */
import request, { PageResponse } from '@/utils/request'

// ── 会员套餐 ──────────────

export interface MemberPackage {
  id: number
  package_code: string
  package_name: string
  price: number
  duration_days: number
  member_commission_rate: number
  status: number // 1-上架 0-下架
  status_label?: string
  sort_order: number
  description: string
  create_time: string | null
  update_time: string | null
}

export interface MemberPackageCreate {
  package_code: string
  package_name: string
  price: number
  duration_days: number
  member_commission_rate: number
  status: number
  sort_order: number
  description: string
}

export interface MemberPackageUpdate {
  package_name?: string
  price?: number
  duration_days?: number
  member_commission_rate?: number
  status?: number
  sort_order?: number
  description?: string
}

export const memberPackageApi = {
  list: (params: { page: number; page_size: number; status?: number; keyword?: string }) =>
    request.get<PageResponse<MemberPackage>>('/v1/admin/member-package/packages', { params }),
  onShelf: () =>
    request.get<{ items: MemberPackage[] }>('/v1/admin/member-package/packages/on-shelf'),
  get: (id: number) =>
    request.get<MemberPackage>(`/v1/admin/member-package/packages/${id}`),
  create: (data: MemberPackageCreate) =>
    request.post<MemberPackage>('/v1/admin/member-package/packages', data),
  update: (id: number, data: MemberPackageUpdate) =>
    request.put<MemberPackage>(`/v1/admin/member-package/packages/${id}`, data),
  updateStatus: (id: number, status: number) =>
    request.put<{ id: number; status: number }>(`/v1/admin/member-package/packages/${id}/status`, { status }),
  remove: (id: number) =>
    request.delete<{ id: number }>(`/v1/admin/member-package/packages/${id}`),
}

// ── 会员记录 ──────────────

export interface MemberRecord {
  id: number
  user_id: number
  package_id: number
  package_name: string
  member_commission_rate: number
  status: string // active / expired / revoked
  status_label?: string
  started_at: string
  expire_at: string
  order_id: number | null
  remark: string
  create_time: string
}

export interface MemberRecordStats {
  active_count: number
  expired_count: number
  total_count: number
}

export interface MemberRecordExportResult {
  file_name: string
  file_path: string
  file_size: number
  row_count: number
}

export const memberRecordApi = {
  list: (params: {
    page: number
    page_size: number
    user_id?: number
    status?: string
    package_id?: number
    keyword?: string
    start_time?: string
    end_time?: string
  }) => request.get<PageResponse<MemberRecord>>('/v1/admin/member-record/records', { params }),
  stats: () =>
    request.get<MemberRecordStats>('/v1/admin/member-record/stats'),
  export: (data: {
    user_id?: number
    status?: string
    package_id?: number
    keyword?: string
    start_time?: string
    end_time?: string
  }) => request.post<MemberRecordExportResult>('/v1/admin/member-record/export', data),
}

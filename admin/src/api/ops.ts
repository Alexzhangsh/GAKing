// @ai-generated
/**
 * 运维监控 API（M07-2）
 * 对接后端路由：/api/v1/admin/ops-monitor（权限码：ops:monitor）
 */
import request from '@/utils/request'

/** 定时任务概览统计项 */
export interface TaskStatItem {
  task_name: string
  total_runs: number
  success_count: number
  failed_count: number
  partial_count: number
  success_rate: number
  last_run_at: string
}

/** 任务最近执行状态项 */
export interface RecentStatusItem {
  task_name: string
  status: string
  started_at: string
  duration_seconds: number
  error_message: string
}

/** 失败清单项 */
export interface FailedLogItem {
  id: number
  task_name: string
  status: string
  started_at: string
  duration_seconds: number
  error_message: string
}

/** 渠道报错统计 */
export interface ChannelErrorStats {
  source: 'local_log'
  channels: Record<
    string,
    {
      error_count: number
      last_error_at: string
    }
  >
}

/** 运维监控总览响应 */
export interface OpsOverview {
  days: number
  task_stats: TaskStatItem[]
  recent_status: RecentStatusItem[]
  failed_list: FailedLogItem[]
  channel_errors: ChannelErrorStats
}

export const opsApi = {
  /** 运维监控总览（任务成功率/最近状态/失败清单/渠道报错） */
  getOverview(days = 7) {
    return request.get<OpsOverview>('/v1/admin/ops-monitor/overview', {
      params: { days },
    })
  },
}

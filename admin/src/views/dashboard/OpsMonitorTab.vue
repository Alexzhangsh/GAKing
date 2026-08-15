<!-- @ai-generated -->
<!--
  运维监控子标签页（M07-2）
  对接：GET /api/v1/admin/ops-monitor/overview（权限码：ops:monitor）
  展示：定时任务成功率 / 最近执行状态 / 失败清单 / 渠道报错计数
-->
<template>
  <div class="ops-monitor">
    <!-- 工具栏 -->
    <div class="ops-toolbar">
      <div class="ops-title">
        <span>运维监控</span>
        <el-tag size="small" type="info" effect="plain" class="source-tag">
          渠道报错来源：{{ channelSourceLabel }}
        </el-tag>
      </div>
      <div class="ops-controls">
        <el-radio-group v-model="days" size="small" @change="loadOverview">
          <el-radio-button :label="7">近 7 天</el-radio-button>
          <el-radio-button :label="14">近 14 天</el-radio-button>
          <el-radio-button :label="30">近 30 天</el-radio-button>
        </el-radio-group>
        <el-button size="small" :icon="Refresh" circle @click="loadOverview" />
      </div>
    </div>

    <!-- 渠道报错计数（本地日志统计） -->
    <el-card shadow="never" class="ops-card">
      <template #header>
        <div class="card-header">
          <span>渠道报错计数（本地日志统计）</span>
        </div>
      </template>
      <div v-loading="loading" class="channel-error-grid">
        <div
          v-for="item in channelRows"
          :key="item.code"
          class="channel-error-item"
        >
          <div class="channel-error__name">{{ item.name }}</div>
          <div class="channel-error__count" :class="item.error_count > 0 ? 'color-danger' : 'color-success'">
            {{ item.error_count }}
          </div>
          <div class="channel-error__label">报错数</div>
          <div class="channel-error__last">
            最近：{{ item.last_error_at || '--' }}
          </div>
        </div>
        <el-empty
          v-if="channelRows.length === 0 && !loading"
          description="暂无渠道数据"
          :image-size="60"
        />
      </div>
    </el-card>

    <!-- 任务成功率 + 最近执行状态 -->
    <el-row :gutter="16" class="ops-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="ops-card">
          <template #header>
            <div class="card-header">
              <span>定时任务成功率（近 {{ days }} 天）</span>
            </div>
          </template>
          <el-table :data="taskStats" v-loading="loading" size="small" max-height="320">
            <el-table-column label="任务名称" prop="task_name" min-width="180" show-overflow-tooltip />
            <el-table-column label="运行次数" prop="total_runs" width="90" align="right" />
            <el-table-column label="成功" prop="success_count" width="70" align="right" />
            <el-table-column label="失败" prop="failed_count" width="70" align="right">
              <template #default="{ row }">
                <span :class="row.failed_count > 0 ? 'color-danger' : ''">{{ row.failed_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="部分成功" prop="partial_count" width="90" align="right" />
            <el-table-column label="成功率" width="100" align="right">
              <template #default="{ row }">
                <span :class="getRateClass(row.success_rate)">{{ row.success_rate }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="最近运行" prop="last_run_at" min-width="150" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="ops-card">
          <template #header>
            <div class="card-header">
              <span>最近执行状态</span>
            </div>
          </template>
          <el-table :data="recentStatus" v-loading="loading" size="small" max-height="320">
            <el-table-column label="任务名称" prop="task_name" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="80" align="right">
              <template #default="{ row }">{{ row.duration_seconds }}s</template>
            </el-table-column>
            <el-table-column label="开始时间" prop="started_at" min-width="140" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 失败清单 -->
    <el-card shadow="never" class="ops-card">
      <template #header>
        <div class="card-header">
          <span>最近失败清单</span>
          <el-tag v-if="failedList.length > 0" type="danger" size="small" effect="plain">
            {{ failedList.length }} 条
          </el-tag>
        </div>
      </template>
      <el-table :data="failedList" v-loading="loading" size="small" max-height="300">
        <el-table-column label="任务名称" prop="task_name" min-width="180" show-overflow-tooltip />
        <el-table-column label="开始时间" prop="started_at" min-width="150" />
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">{{ row.duration_seconds }}s</template>
        </el-table-column>
        <el-table-column label="错误信息" prop="error_message" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="error-msg">{{ row.error_message || '--' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="failedList.length === 0 && !loading" description="近 {{ days }} 天无失败任务" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, computed, onMounted } from 'vue'
import { ElCard, ElRow, ElCol, ElTag, ElRadioGroup, ElRadioButton, ElButton, ElTable, ElTableColumn, ElEmpty } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { opsApi, type TaskStatItem, type RecentStatusItem, type FailedLogItem } from '@/api/ops'

const loading = ref(false)
const days = ref(7)
const taskStats = ref<TaskStatItem[]>([])
const recentStatus = ref<RecentStatusItem[]>([])
const failedList = ref<FailedLogItem[]>([])
const channelErrors = ref<Record<string, { error_count: number; last_error_at: string }>>({})
const channelSource = ref<'local_log'>('local_log')

const channelSourceLabel = computed(() => '本地日志')

const channelRows = computed(() => {
  const nameMap: Record<string, string> = {
    myq: '喵有券',
    orderx: '订单侠',
    dta: '大淘客',
  }
  return Object.entries(channelErrors.value).map(([code, v]) => ({
    code,
    name: nameMap[code] || code,
    error_count: v.error_count,
    last_error_at: v.last_error_at,
  }))
})

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    partial: '部分成功',
    running: '运行中',
  }
  return map[status] || status
}

function statusTagType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'partial') return 'warning'
  return 'info'
}

function getRateClass(rate: number): string {
  if (rate >= 99) return 'color-success'
  if (rate >= 90) return 'color-warning'
  return 'color-danger'
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await opsApi.getOverview(days.value)
    taskStats.value = res.task_stats || []
    recentStatus.value = res.recent_status || []
    failedList.value = res.failed_list || []
    channelErrors.value = res.channel_errors?.channels || {}
    channelSource.value = res.channel_errors?.source || 'local_log'
  } catch {
    taskStats.value = []
    recentStatus.value = []
    failedList.value = []
    channelErrors.value = {}
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.ops-monitor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ops-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.ops-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.source-tag {
  font-weight: 300;
}

.ops-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ops-row {
  margin: 0 !important;
}

.ops-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 渠道报错卡片 */
.channel-error-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 60px;
}

.channel-error-item {
  flex: 1 1 calc(25% - 12px);
  min-width: 160px;
  padding: 16px;
  background: #f7f9fc;
  border-radius: 8px;
  border-left: 3px solid #409eff;
  text-align: center;
}

.channel-error__name {
  font-size: 13px;
  color: #606266;
  font-weight: 300;
  margin-bottom: 8px;
}

.channel-error__count {
  font-size: 28px;
  font-weight: 500;
  line-height: 1.2;
}

.channel-error__label {
  font-size: 12px;
  color: #909399;
  font-weight: 300;
  margin: 4px 0 8px;
}

.channel-error__last {
  font-size: 12px;
  color: #909399;
  font-weight: 300;
}

.error-msg {
  color: #f56c6c;
  font-weight: 300;
}

.color-success {
  color: #67c23a !important;
}

.color-warning {
  color: #e6a23c !important;
}

.color-danger {
  color: #f56c6c !important;
}

/* 表格字体 300 */
:deep(.el-table) {
  font-weight: 300;
}
</style>

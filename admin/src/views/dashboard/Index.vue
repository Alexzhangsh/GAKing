<!-- @ai-generated -->
<!--
  工作台首页（数据大盘）
  对接 B14 接口：
  - GET /api/v1/admin/dashboard/cards          5 张统计卡片
  - GET /api/v1/admin/dashboard/order-trend    订单/佣金柱状图
  - GET /api/v1/admin/dashboard/commission-stats  佣金多维度统计
  - GET /api/v1/admin/dashboard/withdraw-trend  提现趋势折线图
  权限：dashboard:view
-->
<template>
  <div class="dashboard-page">
    <el-tabs v-model="activeTab" class="dashboard-tabs">
      <!-- 数据总览 Tab -->
      <el-tab-pane label="数据总览" name="overview">
    <!-- 欢迎条 -->
    <el-card class="welcome-card" shadow="never">
      <div class="welcome-inner">
        <div>
          <h2>{{ greeting }}，{{ userStore.displayName }}</h2>
          <p class="welcome-sub">角色：{{ userStore.roleName || '管理员' }} · 今日是 {{ todayStr }}</p>
        </div>
        <div class="welcome-actions">
          <el-button type="primary" @click="$router.push('/order/list')">
            <el-icon><List /></el-icon>订单管理
          </el-button>
          <el-button @click="$router.push('/withdraw/list')">
            <el-icon><Money /></el-icon>提现审核
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 5 张统计卡片 -->
    <div class="cards-row">
      <el-card
        v-for="card in cards"
        :key="card.key"
        class="stat-card"
        shadow="hover"
        :body-style="{ padding: '20px' }"
      >
        <div class="stat-card__inner">
          <div class="stat-card__icon" :style="{ background: card.color }">
            <el-icon :size="24"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-card__content">
            <div class="stat-card__label">{{ card.label }}</div>
            <div class="stat-card__value" :title="String(card.value)">{{ card.value }}</div>
            <div class="stat-card__unit">{{ card.unit }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 订单/佣金柱状图 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>订单与佣金趋势（近 30 天）</span>
              <div class="header-controls">
                <el-select
                  v-model="trendChannel"
                  size="small"
                  style="width: 110px; margin-right: 8px"
                  @change="loadOrderTrend"
                >
                  <el-option label="全部渠道" value="" />
                  <el-option label="喵有券" value="myq" />
                  <el-option label="订单侠" value="orderx" />
                </el-select>
                <el-radio-group v-model="trendGroupBy" size="small" @change="loadOrderTrend">
                  <el-radio-button label="day">按天</el-radio-button>
                  <el-radio-button label="week">按周</el-radio-button>
                  <el-radio-button label="month">按月</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          <div v-loading="trendLoading" class="trend-chart">
            <div v-if="trendData.length === 0 && !trendLoading" class="empty-tip">
              <el-empty description="暂无数据" :image-size="60" />
            </div>
            <div v-else class="bars">
              <div
                v-for="item in trendData"
                :key="item.date"
                class="bar-item"
                :title="`${item.date}：${item.order_count} 单 / ¥${item.total_commission}`"
              >
                <div class="bar-track">
                  <div class="bar-fill bar-fill--order" :style="{ height: getOrderBarHeight(item.order_count) + '%' }"></div>
                  <div class="bar-fill bar-fill--commission" :style="{ height: getCommissionBarHeight(item.total_commission) + '%' }"></div>
                </div>
                <div class="bar-label">{{ formatBarLabel(item.date) }}</div>
              </div>
            </div>
            <div class="trend-legend">
              <span class="legend-item"><i class="dot dot--order"></i>订单数</span>
              <span class="legend-item"><i class="dot dot--commission"></i>佣金金额</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 佣金统计（多维度） -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>佣金统计</span>
              <el-radio-group v-model="commissionGroupBy" size="small" @change="loadCommissionStats">
                <el-radio-button label="date">按日期</el-radio-button>
                <el-radio-button label="channel">按渠道</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="commissionData" v-loading="commissionLoading" size="small" max-height="320">
            <el-table-column
              :label="commissionGroupBy === 'date' ? '日期' : '渠道'"
              :prop="commissionGroupBy === 'date' ? 'date' : 'channel_code'"
              min-width="120"
            />
            <el-table-column label="订单数" prop="order_count" width="90" align="right" />
            <el-table-column label="佣金总额" prop="total_commission" min-width="110" align="right">
              <template #default="{ row }">¥{{ row.total_commission }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 渠道成交统计 + 渠道对账差异（B17） -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>渠道成交统计（近 30 天）</span>
              <el-select
                v-model="aggChannel"
                size="small"
                style="width: 110px"
                @change="loadChannelAggregate"
              >
                <el-option label="全部渠道" value="" />
                <el-option label="喵有券" value="myq" />
                <el-option label="订单侠" value="orderx" />
              </el-select>
            </div>
          </template>
          <el-table
            :data="channelAggRows"
            v-loading="channelAggLoading"
            size="small"
            max-height="320"
          >
            <el-table-column label="渠道" min-width="90">
              <template #default="{ row }">
                <el-tag :type="row.channel_code === 'myq' ? 'primary' : 'warning'" size="small">
                  {{ channelName(row.channel_code) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="订单数" prop="order_count" width="80" align="right" />
            <el-table-column label="成交单数" prop="deal_count" width="90" align="right" />
            <el-table-column label="成交金额" min-width="100" align="right">
              <template #default="{ row }">¥{{ row.deal_amount }}</template>
            </el-table-column>
            <el-table-column label="总佣金" min-width="100" align="right">
              <template #default="{ row }">¥{{ row.total_commission }}</template>
            </el-table-column>
            <el-table-column label="用户佣金" min-width="100" align="right">
              <template #default="{ row }">¥{{ row.user_commission }}</template>
            </el-table-column>
            <el-table-column label="平台佣金" min-width="100" align="right">
              <template #default="{ row }">¥{{ row.platform_commission }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 渠道对账差异汇总 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>渠道对账差异汇总</span>
              <el-button link type="primary" size="small" @click="loadChannelDiffSummary">
                刷新
              </el-button>
            </div>
          </template>
          <el-table :data="channelDiffRows" v-loading="channelDiffLoading" size="small" max-height="320">
            <el-table-column label="渠道" min-width="90">
              <template #default="{ row }">
                <el-tag :type="row.channel_code === 'myq' ? 'primary' : 'warning'" size="small">
                  {{ channelName(row.channel_code) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="差异数" prop="diff_count" width="80" align="right" />
            <el-table-column label="差异金额" min-width="100" align="right">
              <template #default="{ row }">¥{{ row.diff_amount }}</template>
            </el-table-column>
            <el-table-column label="待复核" prop="pending_count" width="80" align="right" />
            <el-table-column label="严重" width="80" align="right">
              <template #default="{ row }">
                <span :class="row.critical_count > 0 ? 'color-danger' : ''">
                  {{ row.critical_count }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 提现趋势折线图 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>提现趋势（近 30 天）</span>
              <el-radio-group v-model="withdrawGroupBy" size="small" @change="loadWithdrawTrend">
                <el-radio-button label="day">按天</el-radio-button>
                <el-radio-button label="week">按周</el-radio-button>
                <el-radio-button label="month">按月</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div v-loading="withdrawLoading" class="withdraw-chart">
            <div v-if="withdrawData.length === 0 && !withdrawLoading" class="empty-tip">
              <el-empty description="暂无数据" :image-size="60" />
            </div>
            <!-- 纯 CSS/SVG 折线图 -->
            <svg v-else viewBox="0 0 600 240" preserveAspectRatio="none" class="line-svg">
              <!-- 网格 -->
              <g class="grid">
                <line v-for="i in 5" :key="'h'+i" :x1="0" :y1="(i-1)*60" :x2="600" :y2="(i-1)*60" />
              </g>
              <!-- 成功金额折线 -->
              <polyline
                fill="none"
                stroke="#67c23a"
                stroke-width="2"
                :points="buildWithdrawLinePoints('success')"
              />
              <!-- 申请金额折线 -->
              <polyline
                fill="none"
                stroke="#e6a23c"
                stroke-width="2"
                stroke-dasharray="4 2"
                :points="buildWithdrawLinePoints('apply')"
              />
              <!-- 数据点 -->
              <g v-for="(item, idx) in withdrawData" :key="'d'+idx">
                <circle
                  v-for="type in ['success', 'apply']"
                  :key="type"
                  :cx="getWithdrawX(idx)"
                  :cy="getWithdrawY(item, type as 'success' | 'apply')"
                  :r="3"
                  :fill="type === 'success' ? '#67c23a' : '#e6a23c'"
                />
              </g>
            </svg>
            <div class="withdraw-x-labels">
              <span v-for="(item, idx) in withdrawData" :key="item.date" :style="{ left: `${getWithdrawX(idx) / 6}%` }">
                {{ formatBarLabel(item.date) }}
              </span>
            </div>
            <div class="trend-legend">
              <span class="legend-item"><i class="dot dot--success"></i>成功到账金额</span>
              <span class="legend-item"><i class="dot dot--apply"></i>申请金额</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 关键指标 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>关键指标速览</span>
            </div>
          </template>
          <div class="kpi-list">
            <div class="kpi-item">
              <span class="kpi-label">累计成交订单</span>
              <span class="kpi-value">{{ cardsData?.total_orders ?? '--' }} <small>单</small></span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">待结算佣金</span>
              <span class="kpi-value color-warning">¥{{ cardsData?.pending_settle_commission ?? '--' }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">已结算佣金</span>
              <span class="kpi-value color-success">¥{{ cardsData?.settled_commission ?? '--' }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">累计提现</span>
              <span class="kpi-value color-info">¥{{ cardsData?.total_withdrawn ?? '--' }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">待审核提现</span>
              <span class="kpi-value color-danger">{{ cardsData?.pending_review_withdraws ?? '--' }} <small>笔</small></span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
      </el-tab-pane>

      <!-- 运维监控 Tab（M07-2，仅 ops:monitor 权限可见） -->
      <el-tab-pane v-if="canViewOps" label="运维监控" name="ops">
        <OpsMonitorTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, computed, onMounted } from 'vue'
import {
  ElCard,
  ElRow,
  ElCol,
  ElButton,
  ElIcon,
  ElRadioGroup,
  ElRadioButton,
  ElTable,
  ElTableColumn,
  ElEmpty,
  ElSelect,
  ElOption,
  ElTag,
  ElTabs,
  ElTabPane,
} from 'element-plus'
import { List, Money, ShoppingCart, Wallet, TrendCharts, Bell, Coin } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import OpsMonitorTab from './OpsMonitorTab.vue'
import {
  dashboardApi,
  type DashboardCards,
  type OrderTrendItem,
  type OrderTrendGroupBy,
  type CommissionGroupBy,
  type CommissionStatsByDateItem,
  type CommissionStatsByChannelItem,
  type WithdrawTrendItem,
  type ChannelAggregateItem,
  type ChannelDiffSummaryItem,
} from '@/api/dashboard'

const userStore = useUserStore()

// M07-2 运维监控 Tab 权限控制（仅 ops:monitor 权限可见）
const activeTab = ref('overview')
const canViewOps = computed(() => userStore.hasPermission('ops:monitor'))

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
})

// ── 5 张统计卡片 ──────────────
const cardsData = ref<DashboardCards | null>(null)
const cardsLoading = ref(false)

const cards = computed(() => {
  const d = cardsData.value
  return [
    {
      key: 'total_orders',
      label: '累计订单数',
      value: d?.total_orders ?? '--',
      unit: '单',
      icon: ShoppingCart,
      color: '#409eff',
    },
    {
      key: 'pending_settle',
      label: '待结算佣金',
      value: d?.pending_settle_commission ?? '--',
      unit: '元',
      icon: Wallet,
      color: '#e6a23c',
    },
    {
      key: 'settled',
      label: '已结算佣金',
      value: d?.settled_commission ?? '--',
      unit: '元',
      icon: TrendCharts,
      color: '#67c23a',
    },
    {
      key: 'total_withdrawn',
      label: '提现总额',
      value: d?.total_withdrawn ?? '--',
      unit: '元',
      icon: Coin,
      color: '#909399',
    },
    {
      key: 'pending_review',
      label: '待审核提现',
      value: d?.pending_review_withdraws ?? '--',
      unit: '笔',
      icon: Bell,
      color: '#f56c6c',
    },
  ]
})

async function loadCards() {
  cardsLoading.value = true
  try {
    cardsData.value = await dashboardApi.getCards()
  } catch {
    // 拦截器已提示
  } finally {
    cardsLoading.value = false
  }
}

// ── 订单/佣金趋势 ──────────────
const trendData = ref<OrderTrendItem[]>([])
const trendLoading = ref(false)
const trendGroupBy = ref<OrderTrendGroupBy>('day')
const trendChannel = ref('')

function getDateRange(days: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date(end.getTime() - days * 24 * 3600 * 1000)
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { start: fmt(start), end: fmt(end) }
}

const orderMax = computed(() =>
  Math.max(1, ...trendData.value.map((i) => i.order_count))
)
const commissionMax = computed(() =>
  Math.max(
    0.01,
    ...trendData.value.map((i) => Number(i.total_commission) || 0)
  )
)
function getOrderBarHeight(count: number): number {
  return Math.max(2, Math.round((count / orderMax.value) * 100))
}
function getCommissionBarHeight(amount: string): number {
  const v = Number(amount) || 0
  return Math.max(2, Math.round((v / commissionMax.value) * 100))
}

function formatBarLabel(date: string): string {
  const parts = date.split('-')
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : date
}

async function loadOrderTrend() {
  trendLoading.value = true
  try {
    const range = getDateRange(30)
    const res = await dashboardApi.getChannelOrderTrend({
      start_date: range.start,
      end_date: range.end,
      group_by: trendGroupBy.value,
      channel_code: trendChannel.value || undefined,
    })
    // 后端返回 { group_by, start_date, end_date, total, items }，取 items 数组
    trendData.value = (res as unknown as { items: OrderTrendItem[] })?.items ?? []
  } catch {
    trendData.value = []
  } finally {
    trendLoading.value = false
  }
}

// ── 佣金多维度统计 ──────────────
const commissionData = ref<(CommissionStatsByDateItem | CommissionStatsByChannelItem)[]>([])
const commissionLoading = ref(false)
const commissionGroupBy = ref<CommissionGroupBy>('date')

async function loadCommissionStats() {
  commissionLoading.value = true
  try {
    const range = getDateRange(30)
    const res = await dashboardApi.getCommissionStats({
      group_by: commissionGroupBy.value,
      start_date: range.start,
      end_date: range.end,
    })
    // 后端返回 { group_by, start_date, end_date, total, items }，取 items 数组
    commissionData.value =
      (res as unknown as { items: (CommissionStatsByDateItem | CommissionStatsByChannelItem)[] })?.items ?? []
  } catch {
    commissionData.value = []
  } finally {
    commissionLoading.value = false
  }
}

// ── B17 渠道成交统计 ──────────────
const channelAggRows = ref<ChannelAggregateItem[]>([])
const channelAggLoading = ref(false)
const aggChannel = ref('')

function channelName(code: string): string {
  if (code === 'myq') return '喵有券'
  if (code === 'orderx') return '订单侠'
  return code || '未知'
}

async function loadChannelAggregate() {
  channelAggLoading.value = true
  try {
    const range = getDateRange(30)
    const res = await dashboardApi.getChannelAggregateStats({
      start_date: range.start,
      end_date: range.end,
    })
    const channels = res?.channels ?? {}
    let rows = Object.values(channels)
    if (aggChannel.value) {
      rows = rows.filter((r) => r.channel_code === aggChannel.value)
    }
    // 追加合计行
    if (res?.total) {
      rows = [
        ...rows,
        {
          channel_code: '合计',
          order_count: res.total.order_count,
          total_commission: res.total.total_commission,
          user_commission: res.total.user_commission,
          platform_commission: res.total.platform_commission,
          pay_amount: res.total.pay_amount,
          deal_count: res.total.deal_count,
          deal_amount: res.total.deal_amount,
        },
      ]
    }
    channelAggRows.value = rows
  } catch {
    channelAggRows.value = []
  } finally {
    channelAggLoading.value = false
  }
}

// ── B17 渠道对账差异汇总 ──────────────
const channelDiffRows = ref<ChannelDiffSummaryItem[]>([])
const channelDiffLoading = ref(false)

async function loadChannelDiffSummary() {
  channelDiffLoading.value = true
  try {
    const range = getDateRange(30)
    const res = await dashboardApi.getChannelDiffSummary({
      start_date: range.start,
      end_date: range.end,
    })
    const channels = res?.channels ?? {}
    const rows = Object.values(channels)
    if (res?.total) {
      rows.push({
        channel_code: '合计',
        diff_count: res.total.diff_count,
        diff_amount: res.total.diff_amount,
        pending_count: res.total.pending_count,
        critical_count: res.total.critical_count,
      })
    }
    channelDiffRows.value = rows
  } catch {
    channelDiffRows.value = []
  } finally {
    channelDiffLoading.value = false
  }
}

// ── 提现趋势折线图 ──────────────
const withdrawData = ref<WithdrawTrendItem[]>([])
const withdrawLoading = ref(false)
const withdrawGroupBy = ref<OrderTrendGroupBy>('day')

async function loadWithdrawTrend() {
  withdrawLoading.value = true
  try {
    const range = getDateRange(30)
    const res = await dashboardApi.getWithdrawTrend({
      start_date: range.start,
      end_date: range.end,
      group_by: withdrawGroupBy.value,
    })
    withdrawData.value = (res as unknown as { items: WithdrawTrendItem[] })?.items ?? []
  } catch {
    withdrawData.value = []
  } finally {
    withdrawLoading.value = false
  }
}

/** 折线图坐标计算：SVG viewBox 600x240，左右留 30px 边距 */
const lineLeftPad = 30
const lineRightPad = 10
const lineTopPad = 20
const lineBottomPad = 20
const lineW = 600
const lineH = 240

const withdrawSuccessMax = computed(() =>
  Math.max(0.01, ...withdrawData.value.map((i) => Number(i.success_amount) || 0))
)
const withdrawApplyMax = computed(() =>
  Math.max(0.01, ...withdrawData.value.map((i) => Number(i.withdraw_amount) || 0))
)
const withdrawYMax = computed(() =>
  Math.max(withdrawSuccessMax.value, withdrawApplyMax.value)
)

function getWithdrawX(idx: number): number {
  if (withdrawData.value.length <= 1) return lineLeftPad
  const usable = lineW - lineLeftPad - lineRightPad
  return lineLeftPad + (usable * idx) / (withdrawData.value.length - 1)
}

function getWithdrawY(item: WithdrawTrendItem, type: 'success' | 'apply'): number {
  const val = type === 'success' ? Number(item.success_amount) || 0 : Number(item.withdraw_amount) || 0
  const usable = lineH - lineTopPad - lineBottomPad
  const ratio = val / withdrawYMax.value
  return lineH - lineBottomPad - ratio * usable
}

function buildWithdrawLinePoints(type: 'success' | 'apply'): string {
  if (withdrawData.value.length === 0) return ''
  return withdrawData.value
    .map((item, idx) => `${getWithdrawX(idx)},${getWithdrawY(item, type)}`)
    .join(' ')
}

onMounted(() => {
  loadCards()
  loadOrderTrend()
  loadCommissionStats()
  loadWithdrawTrend()
  loadChannelAggregate()
  loadChannelDiffSummary()
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.dashboard-tabs :deep(.el-tabs__item) {
  font-weight: 400;
}

.welcome-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.welcome-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.welcome-inner h2 {
  margin: 0 0 6px;
  font-size: 20px;
  color: #303133;
}

.welcome-sub {
  margin: 0;
  font-size: 13px;
  color: #909399;
  font-weight: 300;
}

.welcome-actions {
  display: flex;
  gap: 12px;
}

.cards-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.cards-row .stat-card {
  flex: 1 1 calc(20% - 12px);
  min-width: 180px;
  border-radius: 8px;
}

.stat-card {
  border-radius: 8px;
}

.stat-card__inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.stat-card__content {
  flex: 1;
  min-width: 0;
}

.stat-card__label {
  font-size: 13px;
  color: #909399;
  font-weight: 300;
  margin-bottom: 4px;
}

.stat-card__value {
  font-size: 22px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-card__unit {
  font-size: 12px;
  color: #c0c4cc;
  font-weight: 300;
  margin-top: 2px;
}

.chart-row {
  margin: 0 !important;
}

.chart-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  align-items: center;
}

/* 订单/佣金柱状图 */
.trend-chart {
  height: 340px;
  position: relative;
  padding-bottom: 28px;
}

.empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 280px;
  padding: 12px 0;
  overflow-x: auto;
  position: relative;
}

.bar-item {
  flex: 1;
  min-width: 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}

.bar-track {
  width: 100%;
  height: 240px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
}

.bar-fill {
  width: 45%;
  border-radius: 3px 3px 0 0;
  transition: height 0.3s;
  min-height: 2px;
}

.bar-fill--order {
  background: linear-gradient(180deg, #409eff 0%, #79bbff 100%);
}

.bar-fill--commission {
  background: linear-gradient(180deg, #e6a23c 0%, #f0c78a 100%);
}

.bar-label {
  font-size: 10px;
  color: #909399;
  font-weight: 300;
  margin-top: 6px;
  white-space: nowrap;
}

.trend-legend {
  position: absolute;
  bottom: 0;
  left: 12px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
  font-weight: 300;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.dot--order {
  background: #409eff;
}

.dot--commission {
  background: #e6a23c;
}

.dot--success {
  background: #67c23a;
}

.dot--apply {
  background: #e6a23c;
}

/* 提现折线图 */
.withdraw-chart {
  height: 340px;
  position: relative;
}

.line-svg {
  width: 100%;
  height: 280px;
  display: block;
}

.line-svg .grid line {
  stroke: #ebeef5;
  stroke-dasharray: 2 2;
}

.withdraw-x-labels {
  position: relative;
  height: 18px;
  margin-top: -4px;
}

.withdraw-x-labels span {
  position: absolute;
  transform: translateX(-50%);
  font-size: 10px;
  color: #909399;
  font-weight: 300;
  white-space: nowrap;
}

/* 关键指标 */
.kpi-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kpi-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #f7f9fc;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.kpi-label {
  font-size: 13px;
  color: #606266;
  font-weight: 300;
}

.kpi-value {
  font-size: 18px;
  font-weight: 500;
  color: #303133;
}

.kpi-value small {
  font-size: 12px;
  color: #909399;
  font-weight: 300;
  margin-left: 2px;
}

.color-warning {
  color: #e6a23c !important;
}

.color-success {
  color: #67c23a !important;
}

.color-info {
  color: #909399 !important;
}

.color-danger {
  color: #f56c6c !important;
}

/* 表格字体 300 */
:deep(.el-table) {
  font-weight: 300;
}
</style>

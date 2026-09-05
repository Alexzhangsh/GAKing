<!-- @ai-generated -->
<!--
  提现记录页
  - 提现申请列表（按创建时间倒序）
  - 每条记录：单号、金额、手续费、实际到账、状态标签、时间
  - 状态筛选 Tab（全部/审核中/已到账/已驳回）
  - 下拉刷新 + 上拉分页 + 空兜底
  - 驳回记录展示驳回原因
-->
<template>
  <view class="page-container">
    <!-- 状态筛选 Tab -->
    <view class="tab-bar">
      <view
        v-for="tab in tabs"
        :key="tab.value || 'all'"
        class="tab-item"
        :class="{ active: activeTab === tab.value }"
        @click="switchTab(tab.value)"
      >
        <text class="tab-text">{{ tab.label }}</text>
      </view>
    </view>

    <!-- 提现记录列表 -->
    <scroll-view
      scroll-y
      class="list-scroll"
      @scrolltolower="loadMore"
      :lower-threshold="100"
      refresher-enabled
      :refresher-triggered="refreshing"
      @refresherrefresh="onRefresh"
    >
      <view v-if="applies.length > 0" class="apply-list">
        <view v-for="item in applies" :key="item.id" class="apply-card">
          <view class="card-header">
            <view class="header-left">
              <text class="apply-amount">¥{{ formatPrice(item.apply_amount) }}</text>
              <text class="apply-no">{{ item.apply_no }}</text>
            </view>
            <text class="status-tag" :class="getStatusClass(item.status)">
              {{ getStatusText(item.status) }}
            </text>
          </view>

          <view class="card-body">
            <view class="detail-row">
              <text class="label">手续费</text>
              <text class="value">¥{{ formatPrice(item.fee) }}</text>
            </view>
            <view class="detail-row">
              <text class="label">实际到账</text>
              <text class="value highlight">¥{{ formatPrice(item.actual_amount) }}</text>
            </view>
            <view class="detail-row">
              <text class="label">申请时间</text>
              <text class="value">{{ item.create_time }}</text>
            </view>
            <view v-if="item.transfer_time" class="detail-row">
              <text class="label">到账时间</text>
              <text class="value">{{ item.transfer_time }}</text>
            </view>
          </view>

          <!-- 驳回原因 -->
          <view v-if="item.status === 'REJECTED' && item.reject_reason" class="reject-section">
            <text class="reject-label">驳回原因：</text>
            <text class="reject-reason">{{ item.reject_reason }}</text>
          </view>
        </view>
      </view>

      <view v-if="applies.length > 0" class="load-status">
        <text v-if="loading" class="status-text">加载中...</text>
        <text v-else-if="!hasMore" class="status-text">没有更多了</text>
      </view>

      <Empty
        v-if="!loading && applies.length === 0"
        :type="errorType"
        :text="errorText"
        :action-text="errorType === 'error' ? '重新加载' : ''"
        @action="handleRetry"
      />
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import Empty from '@/components/Empty.vue'
import { listMyWithdraws } from '@/api/withdraw'
import auth from '@/utils/auth'
import { BizError } from '@/utils/request'
import {
  WithdrawStatus,
  WITHDRAW_STATUS_TEXT,
  type WithdrawApplyItem
} from '@/api/types'
import { formatPrice } from '@/utils/format'

/** Tab 定义（value 为空串表示全部） */
interface TabItem {
  label: string
  value: string
}

const tabs: TabItem[] = [
  { label: '全部', value: '' },
  { label: '审核中', value: WithdrawStatus.PENDING },
  { label: '已到账', value: WithdrawStatus.SUCCESS },
  { label: '已驳回', value: WithdrawStatus.REJECTED }
]

const activeTab = ref('')
const applies = ref<WithdrawApplyItem[]>([])
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const refreshing = ref(false)
const hasMore = ref(true)

const errorType = ref<'empty' | 'error' | 'network' | 'search'>('empty')
const errorText = ref('')

/** 加载提现记录 */
const loadApplies = async (resetPage = false) => {
  if (!auth.isLoggedIn()) {
    errorType.value = 'empty'
    errorText.value = '请先登录后查看提现记录'
    return
  }

  if (resetPage) {
    page.value = 1
    applies.value = []
    hasMore.value = true
  }

  loading.value = true

  try {
    const res = await listMyWithdraws(page.value, pageSize)
    let items = res.data?.list || []

    // 前端二次筛选状态（后端 list_my_applies 不支持 status 筛选）
    if (activeTab.value) {
      items = items.filter((item) => item.status === activeTab.value)
    }

    if (resetPage) {
      applies.value = items
    } else {
      applies.value = applies.value.concat(items)
    }

    const total = res.data?.total || 0
    hasMore.value = applies.value.length < total && (res.data?.list || []).length >= pageSize

    if (applies.value.length === 0) {
      errorType.value = 'empty'
      errorText.value = '暂无提现记录'
    }
  } catch (error) {
    if (error instanceof BizError) {
      if (error.code >= 500) {
        errorType.value = 'network'
        errorText.value = '网络异常，请检查网络后重试'
      } else {
        errorType.value = 'error'
        errorText.value = error.message || '加载失败'
      }
    } else {
      errorType.value = 'network'
      errorText.value = '网络连接失败，请检查网络设置'
    }
    applies.value = []
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

/** 切换 Tab */
const switchTab = (value: string) => {
  if (activeTab.value === value) return
  activeTab.value = value
  loadApplies(true)
}

/** 上拉加载更多 */
const loadMore = () => {
  if (loading.value || !hasMore.value) return
  page.value++
  loadApplies(false)
}

/** 下拉刷新 */
const onRefresh = () => {
  refreshing.value = true
  loadApplies(true)
}

/** 重试 */
const handleRetry = () => {
  loadApplies(true)
}

/** 状态中文 */
const getStatusText = (status: string): string => {
  return WITHDRAW_STATUS_TEXT[status] || status
}

/** 状态样式 */
const getStatusClass = (status: string): string => {
  const map: Record<string, string> = {
    [WithdrawStatus.PENDING]: 'status-pending',
    [WithdrawStatus.APPROVED]: 'status-approved',
    [WithdrawStatus.PROCESSING]: 'status-processing',
    [WithdrawStatus.SUCCESS]: 'status-success',
    [WithdrawStatus.REJECTED]: 'status-rejected'
  }
  return map[status] || 'status-default'
}

onShow(() => {
  loadApplies(true)
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
}

.tab-bar {
  display: flex;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 100;

  .tab-item {
    flex: 1;
    text-align: center;
    padding: 24rpx 0;
    position: relative;

    .tab-text {
      font-size: 26rpx;
      color: #666;
    }

    &.active {
      .tab-text {
        color: var(--amber, #ff9500);
        font-weight: 600;
      }

      &::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 48rpx;
        height: 4rpx;
        background: var(--amber, #ff9500);
        border-radius: 2rpx;
      }
    }
  }
}

.list-scroll {
  flex: 1;
  height: 0;
}

.apply-list {
  padding: 20rpx;
}

.apply-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 20rpx;
    border-bottom: 2rpx solid #f5f5f5;

    .header-left {
      display: flex;
      flex-direction: column;
      gap: 6rpx;

      .apply-amount {
        font-size: 36rpx;
        font-weight: 700;
        color: #333;
      }

      .apply-no {
        font-size: 22rpx;
        color: #bbb;
      }
    }

    .status-tag {
      font-size: 24rpx;
      padding: 6rpx 16rpx;
      border-radius: 6rpx;

      &.status-pending {
        color: #faad14;
        background: #fff7e6;
      }
      &.status-approved {
        color: #1890ff;
        background: #e6f7ff;
      }
      &.status-processing {
        color: #722ed1;
        background: #f9f0ff;
      }
      &.status-success {
        color: #52c41a;
        background: #f6ffed;
      }
      &.status-rejected {
        color: #ff4d4f;
        background: #fff1f0;
      }
    }
  }

  .card-body {
    padding: 20rpx 0;

    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 8rpx 0;

      .label {
        font-size: 26rpx;
        color: #999;
      }

      .value {
        font-size: 26rpx;
        color: #333;

        &.highlight {
          color: var(--amber, #ff9500);
          font-weight: 600;
        }
      }
    }
  }

  .reject-section {
    margin-top: 12rpx;
    padding: 16rpx;
    background: #fff1f0;
    border-radius: 8rpx;
    display: flex;
    gap: 8rpx;

    .reject-label {
      font-size: 24rpx;
      color: #ff4d4f;
      flex-shrink: 0;
    }

    .reject-reason {
      font-size: 24rpx;
      color: #666;
      flex: 1;
    }
  }
}

.load-status {
  text-align: center;
  padding: 30rpx 0 60rpx;

  .status-text {
    font-size: 24rpx;
    color: #999;
  }
}
</style>

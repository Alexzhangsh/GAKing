<!-- @ai-generated -->
<!--
  佣金资产页
  - 顶部账户余额卡（可提现/累计收益/冻结中/已提现）
  - 状态筛选 Tab（待结算/已结算/收益明细）
    · 待结算：SETTLABLE 订单，佣金待入账
    · 已结算：SETTLED 订单，佣金已入账
    · 收益明细：SETTLED 订单的佣金明细（含结算时间）
  - 订单卡片复用列表样式，展示佣金金额
  - 下拉刷新 + 上拉分页 + 空兜底
  - 底部提现按钮 → 提现申请页
  - 顶部提现记录入口 → 提现记录页
-->
<template>
  <view class="page-container">
    <!-- 账户余额卡 -->
    <view class="account-card">
      <view class="account-header">
        <view class="available">
          <text class="label">可提现佣金(元)</text>
          <view class="amount">
            <text class="symbol">¥</text>
            <text class="value">{{ formatPrice(account.available_balance) }}</text>
          </view>
        </view>
        <view class="withdraw-entry" @click="goWithdrawList">
          <text class="entry-text">提现记录</text>
          <text class="entry-arrow"><IconLine name="chevron" style="--size:26rpx;color:#ffd400" /></text>
        </view>
      </view>
      <view class="account-grid">
        <view class="grid-item">
          <text class="grid-value">¥{{ formatPrice(account.total_balance) }}</text>
          <text class="grid-label">累计收益</text>
        </view>
        <view class="grid-item">
          <text class="grid-value">¥{{ formatPrice(account.frozen_balance) }}</text>
          <text class="grid-label">冻结中</text>
        </view>
        <view class="grid-item">
          <text class="grid-value">¥{{ formatPrice(account.cumulative_withdrawn) }}</text>
          <text class="grid-label">已提现</text>
        </view>
      </view>
    </view>

    <!-- 状态筛选 Tab -->
    <view class="tab-bar">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        class="tab-item"
        :class="{ active: activeTab === tab.value }"
        @click="switchTab(tab.value)"
      >
        <text class="tab-text">{{ tab.label }}</text>
      </view>
    </view>

    <!-- 订单/收益列表 -->
    <scroll-view
      scroll-y
      class="list-scroll"
      @scrolltolower="loadMore"
      :lower-threshold="100"
      refresher-enabled
      :refresher-triggered="refreshing"
      @refresherrefresh="onRefresh"
    >
      <view v-if="orders.length > 0" class="order-list">
        <view
          v-for="order in orders"
          :key="order.id"
          class="order-card"
          @click="goOrderDetail(order.id)"
        >
          <view class="card-header">
            <text class="goods-name">{{ order.goods_title || '商品订单' }}</text>
            <text class="status-tag" :class="getStatusClass(order.order_status)">
              {{ getStatusText(order.order_status) }}
            </text>
          </view>
          <view class="card-body">
            <view class="info-left">
              <text class="info-label">{{ activeTab === 'settled' ? '已入账佣金' : '预估佣金' }}</text>
              <text class="info-value">¥{{ formatPrice(order.user_commission) }}</text>
            </view>
            <view class="info-right">
              <text class="info-label">支付金额</text>
              <text class="info-value gray">¥{{ formatPrice(order.pay_amount) }}</text>
            </view>
          </view>
          <view class="card-footer">
            <text class="time-label">
              {{ activeTab === 'settled' && order.settle_time ? '结算时间' : '支付时间' }}
            </text>
            <text class="time-value">
              {{ (activeTab === 'settled' && order.settle_time) ? order.settle_time : (order.pay_time || order.create_time) }}
            </text>
          </view>
        </view>
      </view>

      <view v-if="orders.length > 0" class="load-status">
        <text v-if="loading" class="status-text">加载中...</text>
        <text v-else-if="!hasMore" class="status-text">没有更多了</text>
      </view>

      <Empty
        v-if="!loading && orders.length === 0"
        :type="errorType"
        :text="errorText"
        :action-text="errorType === 'error' ? '重新加载' : ''"
        @action="handleRetry"
      />
    </scroll-view>

    <!-- 底部提现按钮 -->
    <view class="bottom-bar safe-area-bottom">
      <view
        class="withdraw-btn"
        :class="{ disabled: account.available_balance < 10 }"
        @click="goWithdrawApply"
      >
        <text>申请提现</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { getMyAccount } from '@/api/withdraw'
import { listMyOrders } from '@/api/order'
import auth from '@/utils/auth'
import { BizError } from '@/utils/request'
import {
  OrderStatus,
  ORDER_STATUS_TEXT,
  type OrderItem,
  type UserAccount
} from '@/api/types'
import { formatPrice } from '@/utils/format'

/** Tab 类型 */
type TabValue = 'settlable' | 'settled'

const tabs: { label: string; value: TabValue }[] = [
  { label: '待结算', value: 'settlable' },
  { label: '已结算', value: 'settled' },
  { label: '收益明细', value: 'settled' }
]

const account = ref<UserAccount>({
  user_id: 0,
  total_balance: 0,
  available_balance: 0,
  frozen_balance: 0,
  cumulative_withdrawn: 0,
  cumulative_fee: 0,
  last_settle_date: null,
  version: 0
})

const activeTab = ref<TabValue>('settlable')
const orders = ref<OrderItem[]>([])
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const refreshing = ref(false)
const hasMore = ref(true)

const errorType = ref<'empty' | 'error' | 'network' | 'search'>('empty')
const errorText = ref('')

const userId = computed(() => auth.getStoredUserInfo()?.user_id || 0)

/** 当前 Tab 对应的订单状态 */
const currentOrderStatus = computed<OrderStatus>(() => {
  return activeTab.value === 'settlable' ? OrderStatus.SETTLABLE : OrderStatus.SETTLED
})

/** 加载账户余额 */
const loadAccount = async () => {
  try {
    const res = await getMyAccount()
    if (res.data) {
      account.value = res.data
    }
  } catch (error) {
    // 账户加载失败不阻断页面，使用零余额兜底
    console.warn('[佣金资产] 账户加载失败:', error)
  }
}

/** 加载订单列表 */
const loadOrders = async (resetPage = false) => {
  if (!userId.value) {
    errorType.value = 'empty'
    errorText.value = '请先登录后查看佣金记录'
    return
  }

  if (resetPage) {
    page.value = 1
    orders.value = []
    hasMore.value = true
  }

  loading.value = true

  try {
    const res = await listMyOrders(
      userId.value,
      page.value,
      pageSize,
      currentOrderStatus.value
    )
    const items = res.data?.list || []

    if (resetPage) {
      orders.value = items
    } else {
      orders.value = orders.value.concat(items)
    }

    const total = res.data?.total || 0
    hasMore.value = orders.value.length < total && items.length >= pageSize

    if (orders.value.length === 0) {
      errorType.value = 'empty'
      const tabLabel = activeTab.value === 'settlable' ? '待结算' : '已结算'
      errorText.value = `暂无${tabLabel}订单`
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
    orders.value = []
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

/** 切换 Tab */
const switchTab = (value: TabValue) => {
  if (activeTab.value === value) return
  activeTab.value = value
  loadOrders(true)
}

/** 上拉加载更多 */
const loadMore = () => {
  if (loading.value || !hasMore.value) return
  page.value++
  loadOrders(false)
}

/** 下拉刷新 */
const onRefresh = () => {
  refreshing.value = true
  loadAccount()
  loadOrders(true)
}

/** 重试 */
const handleRetry = () => {
  loadAccount()
  loadOrders(true)
}

/** 跳转订单详情 */
const goOrderDetail = (orderId: number) => {
  uni.navigateTo({
    url: `/pages/order/detail?id=${orderId}`
  })
}

/** 跳转提现申请页 */
const goWithdrawApply = () => {
  if (account.value.available_balance < 10) {
    uni.showToast({ title: '可提现余额不足10元', icon: 'none' })
    return
  }
  if (!auth.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/withdraw/apply' })
}

/** 跳转提现记录页 */
const goWithdrawList = () => {
  uni.navigateTo({ url: '/pages/withdraw/list' })
}

/** 状态相关工具方法 */
const getStatusText = (status: number): string => ORDER_STATUS_TEXT[status] || '未知'
const getStatusClass = (status: number): string => {
  const map: Record<number, string> = {
    [OrderStatus.SETTLABLE]: 'status-settlable',
    [OrderStatus.SETTLED]: 'status-settled'
  }
  return map[status] || 'status-default'
}

onMounted(() => {
  loadAccount()
  loadOrders(true)
})

onShow(() => {
  // 从提现页返回时刷新账户余额
  loadAccount()
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
  padding-bottom: 140rpx;
}

/* 账户余额卡 */
.account-card {
  background: linear-gradient(160deg, #2b2a24 0%, #111111 100%);
  padding: 40rpx 30rpx 30rpx;
  color: #fff;

  .account-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 30rpx;

    .available {
      display: flex;
      flex-direction: column;
      gap: 12rpx;

      .label {
        font-size: 26rpx;
        color: rgba(255, 255, 255, 0.85);
      }

      .amount {
        display: flex;
        align-items: baseline;

        .symbol {
          font-size: 32rpx;
          font-weight: 600;
          color: #ffd400;
        }

        .value {
          font-size: 64rpx;
          font-weight: 700;
          line-height: 1;
          color: #ffd400;
        }
      }
    }

    .withdraw-entry {
      display: flex;
      align-items: center;
      gap: 4rpx;
      padding: 12rpx 24rpx;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 30rpx;

      .entry-text {
        font-size: 24rpx;
        color: #fff;
      }

      .entry-arrow {
        font-size: 28rpx;
        color: #fff;
      }
    }
  }

  .account-grid {
    display: flex;
    justify-content: space-around;

    .grid-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8rpx;

      .grid-value {
        font-size: 32rpx;
        font-weight: 600;
        color: #ffd400;
      }

      .grid-label {
        font-size: 24rpx;
        color: rgba(255, 255, 255, 0.8);
      }
    }
  }
}

/* Tab */
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
      font-size: 28rpx;
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

.order-list {
  padding: 20rpx;
}

.order-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);

  &:active {
    transform: scale(0.99);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20rpx;

    .goods-name {
      flex: 1;
      font-size: 28rpx;
      color: #333;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-right: 16rpx;
    }

    .status-tag {
      font-size: 22rpx;
      padding: 6rpx 16rpx;
      border-radius: 6rpx;

      &.status-settlable {
        color: #1890ff;
        background: #e6f7ff;
      }
      &.status-settled {
        color: #52c41a;
        background: #f6ffed;
      }
    }
  }

  .card-body {
    display: flex;
    justify-content: space-between;
    padding-bottom: 20rpx;
    border-bottom: 2rpx solid #f5f5f5;

    .info-left,
    .info-right {
      display: flex;
      flex-direction: column;
      gap: 8rpx;
    }

    .info-label {
      font-size: 22rpx;
      color: #999;
    }

    .info-value {
      font-size: 32rpx;
      font-weight: 700;
      color: var(--amber, #ff9500);

      &.gray {
        color: #666;
        font-weight: 500;
      }
    }
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    padding-top: 16rpx;

    .time-label {
      font-size: 22rpx;
      color: #bbb;
    }

    .time-value {
      font-size: 22rpx;
      color: #999;
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

/* 底部提现按钮 */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 20rpx 24rpx;
  box-shadow: 0 -2rpx 12rpx rgba(0, 0, 0, 0.05);
  z-index: 100;

  .withdraw-btn {
    text-align: center;
    padding: 24rpx 0;
    background: var(--ink, #1a1a1a);
    border-radius: 40rpx;

    text {
      color: var(--yellow, #ffd400);
      font-size: 30rpx;
      font-weight: 600;
    }

    &.disabled {
      background: #d4d4d4;

      text {
        color: #fff;
      }
    }

    &:active:not(.disabled) {
      opacity: 0.85;
    }
  }
}
</style>

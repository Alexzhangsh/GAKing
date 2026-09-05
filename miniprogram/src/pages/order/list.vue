<!-- @ai-generated -->
<!--
  我的订单列表页
  - 顶部状态筛选 Tab（全部/待结算/已结算/已失效）
  - 订单卡片（商品图+标题+支付金额+用户佣金+状态标签）
  - 下拉刷新（onPullDownRefresh）
  - 上拉分页加载（scroll-view scrolltolower）
  - 空状态兜底 + 网络异常兜底
  - 点击订单卡片跳转订单详情
-->
<template>
  <view class="page-container">
    <!-- 顶部状态筛选 Tab -->
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

    <!-- 订单列表 -->
    <scroll-view
      scroll-y
      class="order-scroll"
      @scrolltolower="loadMore"
      :lower-threshold="100"
      refresher-enabled
      :refresher-triggered="refreshing"
      @refresherrefresh="onRefresh"
    >
      <!-- 订单卡片列表 -->
      <view v-if="orders.length > 0" class="order-list">
        <view
          v-for="order in orders"
          :key="order.id"
          class="order-card"
          @click="goDetail(order.id)"
        >
          <view class="order-header">
            <text class="order-no">订单号: {{ order.out_order_no }}</text>
            <text class="order-status" :class="getStatusClass(order.order_status)">
              {{ getStatusText(order.order_status) }}
            </text>
          </view>
          <view class="order-body">
            <view class="goods-img">
              <image
                v-if="order.goods_img"
                :src="order.goods_img"
                mode="aspectFill"
                class="image"
              />
              <text v-else class="img-placeholder"><IconLine name="order" style="--size:52rpx;color:#bbb" /></text>
            </view>
            <view class="goods-info">
              <text class="goods-title">{{ order.goods_title || '商品信息同步中' }}</text>
              <view class="goods-meta">
                <text class="pay-amount">支付 ¥{{ formatPrice(order.pay_amount) }}</text>
                <text class="pay-time">{{ order.pay_time || order.create_time }}</text>
              </view>
            </view>
          </view>
          <view class="order-footer">
            <view class="commission">
              <text class="commission-label">预估返利</text>
              <text class="commission-value">¥{{ formatPrice(order.user_commission) }}</text>
            </view>
            <text class="detail-link">查看详情 ›</text>
          </view>
        </view>
      </view>

      <!-- 加载状态 -->
      <view v-if="orders.length > 0" class="load-status">
        <text v-if="loading" class="status-text">加载中...</text>
        <text v-else-if="!hasMore" class="status-text">没有更多了</text>
      </view>

      <!-- 空状态 / 异常兜底 -->
      <Empty
        v-if="!loading && orders.length === 0"
        :type="errorType"
        :text="errorText"
        :action-text="errorType === 'error' ? '重新加载' : ''"
        @action="handleRetry"
      />
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { listMyOrders } from '@/api/order'
import auth from '@/utils/auth'
import { BizError } from '@/utils/request'
import tracker from '@/utils/tracker'
import { formatPrice } from '@/utils/format'
import {
  OrderStatus,
  ORDER_STATUS_TEXT,
  type OrderItem
} from '@/api/types'

/** 状态筛选 Tab 定义（value 为 undefined 表示全部） */
interface TabItem {
  label: string
  value: OrderStatus | undefined
}

const tabs: TabItem[] = [
  { label: '全部', value: undefined },
  { label: '待结算', value: OrderStatus.SETTLABLE },
  { label: '已结算', value: OrderStatus.SETTLED },
  { label: '已失效', value: OrderStatus.INVALID }
]

const activeTab = ref<OrderStatus | undefined>(undefined)
const orders = ref<OrderItem[]>([])
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const refreshing = ref(false)
const hasMore = ref(true)
const hasSearched = ref(false)

/** 异常兜底 */
const errorType = ref<'empty' | 'error' | 'network' | 'search'>('empty')
const errorText = ref('')

/** 当前用户ID */
const userId = computed(() => {
  return auth.getStoredUserInfo()?.user_id || 0
})

/** 获取状态中文 */
const getStatusText = (status: number): string => {
  return ORDER_STATUS_TEXT[status] || '未知'
}

/** 获取状态样式类 */
const getStatusClass = (status: number): string => {
  const map: Record<number, string> = {
    [OrderStatus.PENDING]: 'status-pending',
    [OrderStatus.FROZEN]: 'status-frozen',
    [OrderStatus.SETTLABLE]: 'status-settlable',
    [OrderStatus.SETTLED]: 'status-settled',
    [OrderStatus.INVALID]: 'status-invalid',
    [OrderStatus.REFUNDED]: 'status-refunded'
  }
  return map[status] || 'status-default'
}

/** 加载订单列表 */
const loadOrders = async (resetPage = false) => {
  if (!userId.value) {
    errorType.value = 'empty'
    errorText.value = '请先登录后查看订单'
    return
  }

  if (resetPage) {
    page.value = 1
    orders.value = []
    hasMore.value = true
  }

  loading.value = true
  hasSearched.value = true

  try {
    const res = await listMyOrders(
      userId.value,
      page.value,
      pageSize,
      activeTab.value
    )
    const items = res.data?.list || []

    if (resetPage) {
      orders.value = items
    } else {
      orders.value = orders.value.concat(items)
    }

    const total = res.data?.total || 0
    hasMore.value = orders.value.length < total && items.length >= pageSize

    // 无结果兜底
    if (orders.value.length === 0) {
      errorType.value = 'empty'
      errorText.value = '暂无订单记录'
    }
  } catch (error) {
    if (error instanceof BizError) {
      if (error.code >= 500) {
        errorType.value = 'network'
        errorText.value = '网络异常，请检查网络后重试'
      } else {
        errorType.value = 'error'
        errorText.value = error.message || '订单加载失败'
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
const switchTab = (value: OrderStatus | undefined) => {
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
  loadOrders(true)
}

/** 重试 */
const handleRetry = () => {
  loadOrders(true)
}

/** 跳转订单详情 */
const goDetail = (orderId: number) => {
  uni.navigateTo({
    url: `/pages/order/detail?id=${orderId}`
  })
}

onShow(() => {
  // 每次展示时刷新（从详情页返回同步状态）
  loadOrders(true)
  // 订单列表浏览埋点
  tracker.trackPageView('我的订单')
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
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.03);

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

.order-scroll {
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

  .order-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 20rpx;
    border-bottom: 2rpx solid #f5f5f5;

    .order-no {
      font-size: 24rpx;
      color: #999;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .order-status {
      font-size: 24rpx;
      padding: 6rpx 16rpx;
      border-radius: 6rpx;
      margin-left: 16rpx;

      &.status-pending {
        color: #999;
        background: #f5f5f5;
      }
      &.status-frozen {
        color: #faad14;
        background: #fff7e6;
      }
      &.status-settlable {
        color: #1890ff;
        background: #e6f7ff;
      }
      &.status-settled {
        color: #52c41a;
        background: #f6ffed;
      }
      &.status-invalid {
        color: #999;
        background: #f5f5f5;
      }
      &.status-refunded {
        color: #ff4d4f;
        background: #fff1f0;
      }
    }
  }

  .order-body {
    display: flex;
    padding: 20rpx 0;
    gap: 20rpx;

    .goods-img {
      width: 120rpx;
      height: 120rpx;
      border-radius: 12rpx;
      background: #f5f5f5;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      .image {
        width: 100%;
        height: 100%;
        border-radius: 12rpx;
      }

      .img-placeholder {
        font-size: 40rpx;
      }
    }

    .goods-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;

      .goods-title {
        font-size: 28rpx;
        color: #333;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
      }

      .goods-meta {
        display: flex;
        justify-content: space-between;

        .pay-amount {
          font-size: 24rpx;
          color: #666;
        }

        .pay-time {
          font-size: 22rpx;
          color: #bbb;
        }
      }
    }
  }

  .order-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 20rpx;
    border-top: 2rpx solid #f5f5f5;

    .commission {
      display: flex;
      align-items: baseline;
      gap: 8rpx;

      .commission-label {
        font-size: 24rpx;
        color: #999;
      }

      .commission-value {
        font-size: 32rpx;
        color: var(--amber, #ff9500);
        font-weight: 700;
      }
    }

    .detail-link {
      font-size: 24rpx;
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
</style>

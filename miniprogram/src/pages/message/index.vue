<!-- @ai-generated -->
<!--
  消息中心页面（F05 新建）
  - 消息列表：按类型 Tab 筛选（全部/佣金/提现/订单/退款）
  - 未读状态展示 + 单条已读 + 全部已读
  - 订阅管理入口：未订阅/已过期时展示订阅引导 Banner，点击弹出订阅弹窗
  - 下拉刷新 + 触底加载更多
  - 订阅状态展示：已订阅/已过期
-->
<template>
  <view class="page-container">
    <!-- 订阅引导 Banner（未订阅或已过期时展示） -->
    <view v-if="showSubscribeBanner" class="subscribe-banner" @click="handleOpenSubscribe">
      <view class="banner-left">
        <text class="banner-icon"><IconLine name="bell" style="--size:40rpx;color:#1a1a1a" /></text>
        <view class="banner-text">
          <text class="banner-title">开启消息订阅</text>
          <text class="banner-desc">{{ subscribeDesc }}</text>
        </view>
      </view>
      <view class="banner-arrow">
        <text><IconLine name="chevron" style="--size:28rpx;color:#1a1a1a" /></text>
      </view>
    </view>

    <!-- 类型 Tab -->
    <view class="tabs-bar">
      <scroll-view scroll-x class="tabs-scroll" :show-scrollbar="false">
        <view
          v-for="tab in tabs"
          :key="tab.value"
          class="tab-item"
          :class="{ 'tab-item--active': activeTab === tab.value }"
          @click="handleTabChange(tab.value)"
        >
          <text>{{ tab.label }}</text>
        </view>
      </scroll-view>
      <view class="read-all-btn" @click="handleReadAll">
        <text>全部已读</text>
      </view>
    </view>

    <!-- 消息列表 -->
    <view v-if="loading && list.length === 0" class="list-loading">
      <Loading text="加载中..." />
    </view>

    <view v-else-if="list.length === 0" class="list-empty">
      <Empty :type="loadError ? 'error' : 'empty'" :text="loadError ? '加载失败，请稍后重试' : '暂无消息'" @action="handleRetry" />
    </view>

    <scroll-view
      v-else
      scroll-y
      class="message-scroll"
      refresher-enabled
      :refresher-triggered="refreshing"
      @refresherrefresh="handleRefresh"
      @scrolltolower="handleLoadMore"
    >
      <view class="message-list">
        <view
          v-for="item in list"
          :key="item.id"
          class="message-item"
          :class="{ 'message-item--unread': item.is_read === 0 }"
          @click="handleMessageClick(item)"
        >
          <view class="message-type-icon">
            <IconLine :name="typeIconMap[item.message_type] || 'mail'" style="--size:38rpx;color:#1a1a1a" />
          </view>
          <view class="message-content">
            <view class="message-title-row">
              <text class="message-title ellipsis">{{ item.title }}</text>
              <text v-if="item.is_read === 0" class="unread-dot"></text>
            </view>
            <text class="message-body ellipsis-2">{{ item.content }}</text>
            <view class="message-meta">
              <text class="message-type-tag">{{ typeTextMap[item.message_type] || '通知' }}</text>
              <text class="message-time">{{ formatTime(item.create_time) }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 加载更多状态 -->
      <view v-if="hasMore" class="load-more">
        <Loading text="加载中..." />
      </view>
      <view v-else-if="list.length > 0" class="load-more">
        <text class="load-more-text">没有更多了</text>
      </view>
    </scroll-view>

    <!-- 订阅弹窗 -->
    <SubscribePopup
      v-model:visible="showSubscribePopup"
      :status-map="subscribeStatusMap"
      @subscribed="handleSubscribed"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { getMessageList, getSubscribeStatus, markMessageRead } from '@/api/message'
import type { MessageItem, SubscribeStatusItem } from '@/api/types'
import Empty from '@/components/Empty.vue'
import Loading from '@/components/Loading.vue'
import SubscribePopup from '@/components/SubscribePopup.vue'
import IconLine from '@/components/IconLine.vue'
import { requireLogin } from '@/utils/loginGuard'
import tracker from '@/utils/tracker'

/** Tab 配置 */
const tabs = [
  { label: '全部', value: '' },
  { label: '佣金', value: 'commission' },
  { label: '提现', value: 'withdraw' },
  { label: '订单', value: 'order' },
  { label: '退款', value: 'refund' }
]

/** 消息类型图标映射（对应 IconLine 组件 name） */
const typeIconMap: Record<string, string> = {
  commission: 'yuan',
  withdraw: 'bank',
  order: 'order',
  refund: 'refresh'
}

/** 消息类型文字映射 */
const typeTextMap: Record<string, string> = {
  commission: '佣金',
  withdraw: '提现',
  order: '订单',
  refund: '退款'
}

/** 当前激活 Tab */
const activeTab = ref('')
/** 消息列表 */
const list = ref<MessageItem[]>([])
/** 当前页码 */
const page = ref(1)
/** 每页条数 */
const pageSize = 20
/** 总条数 */
const total = ref(0)
/** 是否还有更多 */
const hasMore = computed(() => list.value.length < total.value)
/** 加载中 */
const loading = ref(false)
/** 下拉刷新中 */
const refreshing = ref(false)
/** 加载失败 */
const loadError = ref(false)

/** 订阅状态列表 */
const subscribeStatusList = ref<SubscribeStatusItem[]>([])
/** 订阅状态映射（template_id → 状态项） */
const subscribeStatusMap = computed(() => {
  const map: Record<number, SubscribeStatusItem> = {}
  subscribeStatusList.value.forEach((item) => {
    map[item.template_id] = item
  })
  return map
})

/** 是否展示订阅引导 Banner（存在未订阅或已过期的模板） */
const showSubscribeBanner = computed(() => {
  return subscribeStatusList.value.some((item) => item.subscribe_status === 0 || item.expired)
})

/** 订阅引导文案 */
const subscribeDesc = computed(() => {
  const expiredCount = subscribeStatusList.value.filter((item) => item.expired).length
  if (expiredCount > 0) return `有 ${expiredCount} 项订阅已过期，点击重新开启`
  return '开启后不错过每一笔收益通知'
})

/** 订阅弹窗显示 */
const showSubscribePopup = ref(false)

/** 加载消息列表 */
const loadMessages = async (reset: boolean = false): Promise<void> => {
  if (loading.value) return
  loading.value = true
  loadError.value = false

  const targetPage = reset ? 1 : page.value
  try {
    const res = await getMessageList(targetPage, pageSize, activeTab.value || undefined)
    const data = res.data
    total.value = data.total
    if (reset) {
      list.value = data.list
      page.value = 1
    } else {
      list.value = [...list.value, ...data.list]
      page.value = targetPage + 1
    }
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

/** 加载订阅状态 */
const loadSubscribeStatus = async (): Promise<void> => {
  try {
    const res = await getSubscribeStatus()
    subscribeStatusList.value = res.data?.list || []
  } catch {
    // 订阅状态加载失败不阻断消息列表
  }
}

/** 切换 Tab */
const handleTabChange = (value: string): void => {
  if (activeTab.value === value) return
  activeTab.value = value
  loadMessages(true)
}

/** 下拉刷新 */
const handleRefresh = (): void => {
  refreshing.value = true
  Promise.all([loadMessages(true), loadSubscribeStatus()])
}

/** 触底加载更多 */
const handleLoadMore = (): void => {
  if (hasMore.value && !loading.value) {
    loadMessages(false)
  }
}

/** 重试 */
const handleRetry = (): void => {
  loadMessages(true)
}

/** 点击消息：标记已读 + 跳转 */
const handleMessageClick = (item: MessageItem): void => {
  // 未读 → 标记已读
  if (item.is_read === 0) {
    item.is_read = 1
    markMessageRead(item.id).catch(() => {
      // 标记失败回滚，下次点击重试
      item.is_read = 0
    })
  }

  // 跳转关联业务页
  if (item.route_url && item.biz_id) {
    uni.navigateTo({ url: `${item.route_url}?id=${item.biz_id}` })
  }
}

/** 全部已读 */
const handleReadAll = (): void => {
  if (list.value.length === 0) return
  uni.showModal({
    title: '提示',
    content: '确认将全部消息标记为已读？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await markMessageRead()
        list.value.forEach((item) => {
          item.is_read = 1
        })
        uni.showToast({ title: '已全部标记为已读', icon: 'success' })
      } catch {
        // 失败提示由 request 统一处理
      }
    }
  })
}

/** 打开订阅弹窗 */
const handleOpenSubscribe = (): void => {
  showSubscribePopup.value = true
}

/** 订阅成功回调 */
const handleSubscribed = (templateId: number, templateName: string): void => {
  // 刷新订阅状态
  loadSubscribeStatus()
}

/** 时间格式化 */
const formatTime = (time: string): string => {
  if (!time) return ''
  const date = new Date(time.replace(/-/g, '/'))
  if (isNaN(date.getTime())) return time
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)}分钟前`
  if (diff < day) return `${Math.floor(diff / hour)}小时前`
  if (diff < 7 * day) return `${Math.floor(diff / day)}天前`
  // 更早的显示日期
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

onLoad(() => {
  // 未登录跳转登录页
  requireLogin()
  loadMessages(true)
  loadSubscribeStatus()
})

onShow(() => {
  // 从订阅弹窗返回时刷新订阅状态
  loadSubscribeStatus()
  tracker.trackPageView('消息中心')
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: var(--color-bg);
}

/* 订阅引导 Banner */
.subscribe-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20rpx;
  padding: 24rpx 28rpx;
  background: linear-gradient(135deg, #ffd400 0%, #ffb800 100%);
  border-radius: var(--radius-md);

  .banner-left {
    display: flex;
    align-items: center;
    gap: 20rpx;
    flex: 1;

    .banner-icon {
      font-size: 44rpx;
    }

    .banner-text {
      display: flex;
      flex-direction: column;
      gap: 4rpx;

      .banner-title {
        font-size: 30rpx;
        font-weight: var(--font-weight-bold);
        color: #1a1a1a;
      }

      .banner-desc {
        font-size: 22rpx;
        color: rgba(26, 26, 26, 0.72);
      }
    }
  }

  .banner-arrow {
    font-size: 40rpx;
    color: rgba(26, 26, 26, 0.72);
  }
}

/* 类型 Tab */
.tabs-bar {
  display: flex;
  align-items: center;
  background: #fff;
  padding: 16rpx 20rpx;

  .tabs-scroll {
    flex: 1;
    white-space: nowrap;

    .tab-item {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12rpx 28rpx;
      margin-right: 16rpx;
      border-radius: var(--radius-full);
      background: var(--color-bg);

      text {
        font-size: 26rpx;
        color: var(--color-text-secondary);
      }

      &--active {
        background: var(--color-primary-bg);

        text {
          color: var(--color-primary);
          font-weight: var(--font-weight-medium);
        }
      }
    }
  }

  .read-all-btn {
    flex-shrink: 0;
    padding: 12rpx 20rpx;

    text {
      font-size: 24rpx;
      color: var(--color-text-placeholder);
    }
  }
}

/* 消息列表 */
.message-scroll {
  height: calc(100vh - 240rpx);
}

.message-list {
  padding: 20rpx;

  .message-item {
    display: flex;
    gap: 20rpx;
    background: #fff;
    border-radius: var(--radius-md);
    padding: 24rpx;
    margin-bottom: 20rpx;
    box-shadow: var(--shadow-card);

    &--unread {
      border-left: 6rpx solid var(--color-primary);
    }

    .message-type-icon {
      width: 72rpx;
      height: 72rpx;
      border-radius: var(--radius-md);
      background: var(--color-primary-bg);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      text {
        font-size: 36rpx;
      }
    }

    .message-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8rpx;
      min-width: 0;

      .message-title-row {
        display: flex;
        align-items: center;
        gap: 12rpx;

        .message-title {
          flex: 1;
          font-size: 30rpx;
          font-weight: var(--font-weight-medium);
          color: var(--color-text);
        }

        .unread-dot {
          width: 16rpx;
          height: 16rpx;
          border-radius: 50%;
          background: var(--color-danger);
          flex-shrink: 0;
        }
      }

      .message-body {
        font-size: 26rpx;
        color: var(--color-text-secondary);
        line-height: 1.5;
      }

      .message-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;

        .message-type-tag {
          font-size: 20rpx;
          color: var(--color-primary);
          background: var(--color-primary-bg);
          padding: 4rpx 12rpx;
          border-radius: var(--radius-full);
        }

        .message-time {
          font-size: 22rpx;
          color: var(--color-text-placeholder);
        }
      }
    }
  }
}

/* 加载状态 */
.list-loading {
  padding-top: 80rpx;
}

.list-empty {
  padding-top: 40rpx;
}

.load-more {
  padding: 30rpx 0;
  text-align: center;

  .load-more-text {
    font-size: 24rpx;
    color: var(--color-text-placeholder);
  }
}
</style>

<!-- @ai-generated -->
<!--
  我的页面（黄黑·闲鱼风 × 民宿风格圆角卡片 · 重设计）
  - 黄色英雄区：头像/登录态 / 消息铃铛
  - 资产卡：累计返利 / 可提现余额 / 收藏好物
  - 快捷功能网格 + 服务列表（白色圆角卡片）
-->
<template>
  <view class="page">
    <!-- 黄色英雄区 -->
    <view class="hero">
      <view class="hero-inner">
        <view class="hero-top">
          <text class="hero-brand">金角大王</text>
          <view class="hero-actions">
            <view class="round-btn" @click="handleMenuClick('message')">
              <image class="rb-icon" :src="ICON_BELL" mode="aspectFit" />
              <text v-if="unreadCount > 0" class="rb-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</text>
            </view>
          </view>
        </view>

        <view class="profile" @click="handleLogin">
          <view class="avatar-wrap">
            <image class="avatar-img" :src="userInfo?.avatar || '/static/avatar-default.png'" mode="aspectFill" />
            <view class="avatar-ring"></view>
          </view>
          <view class="pdetail">
            <view class="pname-row">
              <text class="pname">{{ userInfo?.nickname || '登录享购物奖励' }}</text>
              <text v-if="userInfo" class="pid-tag">ID {{ userInfo.user_id }}</text>
            </view>
            <text class="psub">{{ userInfo ? '欢迎回来，继续薅好物返利' : '点击登录 · 解锁专属返利权益' }}</text>
          </view>
          <view v-if="!userInfo" class="pcta"><text>去登录</text></view>
        </view>
      </view>
    </view>

    <!-- 资产卡 -->
    <view class="asset-card">
      <view class="asset-head">
        <text class="asset-title">我的资产</text>
        <text class="asset-tip">返利实时到账</text>
      </view>
      <view class="asset-row">
        <view class="asset-item" @click="handleMenuClick('commission')">
          <text class="asset-num">{{ stats.totalCommission }}</text>
          <text class="asset-label">累计返利</text>
        </view>
        <view class="asset-sep"></view>
        <view class="asset-item" @click="handleMenuClick('commission')">
          <text class="asset-num amber">{{ stats.available }}</text>
          <text class="asset-label">可提现余额</text>
        </view>
        <view class="asset-sep"></view>
        <view class="asset-item" @click="handleMenuClick('favorite')">
          <text class="asset-num">{{ stats.favoriteCount }}</text>
          <text class="asset-label">收藏好物</text>
        </view>
      </view>
      <view class="asset-cta" @click="handleMenuClick('commission')">
        <text>去提现</text>
      </view>
    </view>

    <!-- 快捷功能网格 -->
    <view class="card grid-card">
      <view class="grid-item" v-for="g in grid" :key="g.type" @click="handleMenuClick(g.type)">
        <view class="chip"><image class="chip-img" :src="g.icon" mode="aspectFit" /></view>
        <text class="grid-label">{{ g.label }}</text>
      </view>
    </view>

    <!-- 服务列表 -->
    <view class="card menu-group">
      <view class="menu-item" v-for="m in services" :key="m.type" @click="handleMenuClick(m.type)">
        <view class="chip chip-sm" :class="{ 'chip-danger': m.danger }"><image class="chip-img" :src="m.icon" mode="aspectFit" /></view>
        <text class="menu-text" :class="{ 'text-danger': m.danger }">{{ m.label }}</text>
        <text v-if="m.type === 'message' && unreadCount > 0" class="menu-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</text>
        <image v-if="!m.danger" class="menu-arrow" :src="ICON_CHEVRON" mode="aspectFit" />
      </view>
    </view>

    <view class="foot-note">金角大王 · 省出好生活</view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getUnreadCount } from '@/api/message'
import auth, { type UserInfo } from '@/utils/auth'
import { getFavoriteCount } from '@/utils/favorite'
import tracker from '@/utils/tracker'

/* ── 黑色线性图标（Base64 SVG，黄黑主题复用） ── */
const ICON_ORDER = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNNSA3aDE0djE0SDV6Ii8+PHBhdGggZD0iTTkgNGg2djNIOXoiLz48cGF0aCBkPSJNOSAxM2wyIDIgNC00Ii8+PC9zdmc+'
const ICON_YUAN = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNNCAzbDQgNU0yMCAzbC00IDUiLz48cGF0aCBkPSJNNS41IDhoMTMiLz48cGF0aCBkPSJNMTIgOHYxMCIvPjxwYXRoIGQ9Ik04LjUgMTJoNyIvPjxwYXRoIGQ9Ik05LjUgMThoNSIvPjwvc3ZnPg=='
const ICON_HEART = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTIgMjAuM1M1IDE2LjEgMi45IDExLjlDMS40IDguNiAzLjcgNS42IDYuNyA1LjZjMS45IDAgMy4zIDEuMSA0LjIgMi4zLjQuNS42LjguOCAxLjEuMi0uMy40LS42LjgtMS4xLjktMS4yIDIuMy0yLjMgNC4yLTIuMyAzIDAgNS4zIDMgMy44IDYuM0MxOSAxNi4xIDEyIDIwLjMgMTIgMjAuM3oiLz48L3N2Zz4='
const ICON_BANK = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNNCA5LjVMMTIgNWw4IDQuNSIvPjxwYXRoIGQ9Ik02IDkuNXY2TTEwIDkuNXY2TTE0IDkuNXY2TTE4IDkuNXY2Ii8+PHBhdGggZD0iTTUgMTguNWgxNCIvPjwvc3ZnPg=='
const ICON_BELL = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTggMTYuNXYtNS4yYTYuMiA2LjIgMCAwIDAtMTIgMHY1LjJsLTIgM2gxNnoiLz48cGF0aCBkPSJNMTAgMjFhMiAyIDAgMCAwIDQgMCIvPjwvc3ZnPg=='
const ICON_HELP = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSI5Ii8+PHBhdGggZD0iTTkuNiA5LjJhMi40IDIuNCAwIDEgMSAzLjYgMi4xYy0xIC42LTEuMiAxLjEtMS4yIDIuMiIvPjxwYXRoIGQ9Ik0xMiAxNi45aC4wMSIvPjwvc3ZnPg=='
const ICON_INFO = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTMgMi41YTkgOSAwIDEgMCA4LjUgOC41QTkgOSAwIDAgMCAxMyAyLjV6Ii8+PHBhdGggZD0iTTEzIDEwdjciLz48cGF0aCBkPSJNMTMgN2guMDEiLz48L3N2Zz4='
const ICON_CHEVRON = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjYjBiMGIwIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTkgNmw2IDYtNiA2Ii8+PC9zdmc+'
const ICON_USER = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjgiIHI9IjQiLz48cGF0aCBkPSJNNCAyMWMwLTQgNC02IDgtNnM4IDIgOCA2Ii8+PC9zdmc+'
const ICON_LOGOUT = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMWExYTFhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNOSAyMUg1YTIgMiAwIDAgMS0yLTJWNWEyIDIgMCAwIDEgMi0yaDQiLz48cGF0aCBkPSJNMTYgMTdsNS01LTUtNSIvPjxwYXRoIGQ9Ik0yMSAxMkg5Ii8+PC9zdmc+'

const grid = [
  { type: 'orders', label: '我的订单', icon: ICON_ORDER },
  { type: 'commission', label: '我的佣金', icon: ICON_YUAN },
  { type: 'favorite', label: '我的收藏', icon: ICON_HEART },
  { type: 'withdraw', label: '提现记录', icon: ICON_BANK }
]

const services = [
  { type: 'message', label: '消息中心', icon: ICON_BELL },
  { type: 'profile', label: '个人资料', icon: ICON_USER },
  { type: 'help', label: '购物流程帮助', icon: ICON_HELP },
  { type: 'about', label: '关于我们', icon: ICON_INFO },
  { type: 'logout', label: '退出登录', icon: ICON_LOGOUT, danger: true }
]

const userInfo = ref<UserInfo | null>(null)

const stats = ref({
  totalCommission: '¥0.00',
  available: '¥0.00',
  favoriteCount: 0
})

/** 未读消息数 */
const unreadCount = ref(0)

const refreshStats = () => {
  stats.value.favoriteCount = getFavoriteCount()
}

/** 加载未读消息数 */
const refreshUnreadCount = async () => {
  if (!auth.isLoginValid()) {
    unreadCount.value = 0
    return
  }
  try {
    const res = await getUnreadCount()
    unreadCount.value = res.data?.unread_count || 0
  } catch {
    // 未读数加载失败不阻断页面
  }
}

const handleLogin = () => {
  if (userInfo.value) {
    // 已登录 → 跳转个人资料页（微信新规：chooseAvatar 更换头像 / nickname input 编辑昵称）
    uni.navigateTo({ url: '/pages/user/profile' })
    return
  }

  // 未登录 → 跳转登录页（携带回跳路径）
  uni.navigateTo({
    url: `/pages/login/index?redirect=${encodeURIComponent('/pages/mine/mine')}`
  })
}

const handleLogout = () => {
  uni.showModal({
    title: '提示',
    content: '确认退出登录？',
    success: (res) => {
      if (res.confirm) {
        auth.logout()
        userInfo.value = null
      }
    }
  })
}

const handleMenuClick = (type: string) => {
  // 退出登录
  if (type === 'logout') {
    handleLogout()
    return
  }

  // 收藏夹 tabBar 已存在，直接 switchTab
  if (type === 'favorite') {
    uni.switchTab({ url: '/pages/favorite/list' })
    return
  }

  if (type === 'about' || type === 'help') {
    uni.navigateTo({
      url: `/pages/webview/index?type=${type}`
    })
    return
  }

  // 订单/佣金/提现记录/消息/个人资料需登录：未登录跳转登录页（携带回跳路径）
  const routeMap: Record<string, string> = {
    orders: '/pages/order/list',
    commission: '/pages/commission/index',
    withdraw: '/pages/withdraw/list',
    message: '/pages/message/index',
    profile: '/pages/user/profile'
  }
  const url = routeMap[type]
  if (!url) return

  if (!auth.ensureLogin(url)) {
    // 未登录，ensureLogin 已跳转登录页
    return
  }

  uni.navigateTo({ url })
}

onMounted(() => {
  userInfo.value = auth.getStoredUserInfo()
  refreshStats()
  refreshUnreadCount()
  tracker.trackPageView('我的')
})

onShow(() => {
  userInfo.value = auth.getStoredUserInfo()
  refreshStats()
  refreshUnreadCount()
})
</script>

<style lang="scss" scoped>
/* ── 主题变量（黄黑 · 闲鱼风） ── */
.page {
  --yellow: #ffd400;
  --amber: #ff9500;
  --yellow-soft: #fff0b0;
  --yellow-line: rgba(255, 212, 0, 0.5);
  --ink: #1a1a1a;
  --ink-sub: #8a8a8a;

  min-height: 100vh;
  background: #f2f3f5;
  padding-bottom: 50rpx;
}

/* ── 黄色英雄区 ── */
.hero {
  position: relative;
  background: var(--yellow);
  padding: 30rpx 30rpx 108rpx;
}

.hero-inner { position: relative; z-index: 1; }

.hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 40rpx;
}

.hero-brand {
  font-size: 26rpx;
  letter-spacing: 2rpx;
  color: var(--ink);
  font-weight: 600;
}

.hero-actions { display: flex; gap: 20rpx; }

.round-btn {
  position: relative;
  width: 72rpx;
  height: 72rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.rb-icon { width: 34rpx; height: 34rpx; }

.rb-badge {
  position: absolute;
  top: -4rpx;
  right: -6rpx;
  min-width: 36rpx;
  height: 36rpx;
  padding: 0 8rpx;
  border-radius: 999rpx;
  background: #e2473f;
  color: #fff;
  font-size: 20rpx;
  line-height: 36rpx;
  text-align: center;
  box-sizing: border-box;
}

/* 用户档案 */
.profile {
  display: flex;
  align-items: center;
  gap: 26rpx;
}

.avatar-wrap {
  position: relative;
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.avatar-img {
  width: 116rpx;
  height: 116rpx;
  border-radius: 50%;
  position: absolute;
  left: 6rpx;
  top: 6rpx;
  background: #fff;
}

.avatar-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 3rpx solid var(--ink);
  pointer-events: none;
}

.pdetail { flex: 1; display: flex; flex-direction: column; gap: 12rpx; }

.pname-row { display: flex; align-items: center; gap: 16rpx; }

.pname {
  font-size: 38rpx;
  color: var(--ink);
  font-weight: 700;
  max-width: 360rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pid-tag {
  padding: 2rpx 14rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  color: var(--ink);
  border: 1px solid rgba(0, 0, 0, 0.6);
  background: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.psub {
  font-size: 24rpx;
  color: rgba(26, 26, 26, 0.6);
}

.pcta {
  width: 132rpx;
  height: 64rpx;
  border-radius: 999rpx;
  background: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 6rpx 16rpx rgba(0, 0, 0, 0.18);

  text {
    font-size: 26rpx;
    color: var(--yellow);
    font-weight: 600;
  }
}

/* ── 资产卡 ── */
.asset-card {
  position: relative;
  z-index: 2;
  margin: -64rpx 28rpx 0;
  background: #ffffff;
  border-radius: 30rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.05);
  padding: 30rpx 30rpx 26rpx;
}

.asset-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 26rpx;
}

.asset-title { font-size: 30rpx; color: var(--ink); font-weight: 600; }

.asset-tip { font-size: 22rpx; color: var(--ink-sub); }

.asset-row {
  display: flex;
  align-items: center;
}

.asset-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
}

.asset-num {
  font-size: 40rpx;
  font-weight: 700;
  color: var(--ink);
  font-variant-numeric: tabular-nums;

  &.amber { color: var(--amber); }
}

.asset-label { font-size: 24rpx; color: var(--ink-sub); }

.asset-sep {
  width: 2rpx;
  height: 56rpx;
  background: #f0f0f0;
}

.asset-cta {
  margin: 26rpx 0 0;
  height: 76rpx;
  border-radius: 999rpx;
  background: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6rpx 16rpx rgba(0, 0, 0, 0.14);

  text {
    font-size: 28rpx;
    color: var(--yellow);
    font-weight: 600;
  }
}

/* ── 通用卡片 ── */
.card {
  margin: 22rpx 28rpx 0;
  background: #ffffff;
  border-radius: 28rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

/* 黄色图标底 */
.chip {
  width: 92rpx;
  height: 92rpx;
  border-radius: 28rpx;
  background: var(--yellow-soft);
  display: flex;
  align-items: center;
  justify-content: center;

  &.chip-sm {
    width: 76rpx;
    height: 76rpx;
    border-radius: 22rpx;
    flex-shrink: 0;
  }

  &.chip-danger {
    background: #ffe5e5;
  }
}

.text-danger {
  color: #e2473f;
}

.chip-img { width: 46rpx; height: 46rpx; }
.chip-sm .chip-img { width: 40rpx; height: 40rpx; }

/* ── 快捷功能网格 ── */
.grid-card {
  display: flex;
  padding: 30rpx 0;
}

.grid-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18rpx;
}

.grid-label { font-size: 26rpx; color: var(--ink); }

/* ── 服务列表 ── */
.menu-group {
  .menu-item {
    display: flex;
    align-items: center;
    gap: 22rpx;
    padding: 26rpx 30rpx;
    border-bottom: 1px solid #f4f4f4;

    &:last-child { border-bottom: none; }

    &:active { background: #fafafa; }
  }
}

.menu-text {
  flex: 1;
  font-size: 28rpx;
  color: var(--ink);
}

.menu-badge {
  min-width: 36rpx;
  height: 36rpx;
  padding: 0 10rpx;
  border-radius: 999rpx;
  background: #e2473f;
  color: #fff;
  font-size: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-arrow { width: 30rpx; height: 30rpx; }

.foot-note {
  margin-top: 44rpx;
  text-align: center;
  font-size: 22rpx;
  letter-spacing: 2rpx;
  color: #a8a8a8;
}
</style>
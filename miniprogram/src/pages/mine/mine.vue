<!-- @ai-generated -->
<template>
  <view class="page-container">
    <view class="user-section">
      <view class="user-info">
        <view class="avatar" @click="handleLogin">
          <image v-if="userInfo" :src="userInfo.avatar" mode="aspectFill" class="avatar-image" />
          <text v-else class="avatar-placeholder">👤</text>
        </view>
        <view class="user-detail">
          <text class="nickname">{{ userInfo?.nickname || '登录享返利' }}</text>
          <text class="user-id">用户ID: {{ userInfo?.user_id || '未登录' }}</text>
        </view>
      </view>
      <view v-if="userInfo" class="logout-btn" @click="handleLogout">
        <text>退出</text>
      </view>
    </view>

    <view class="stats-section">
      <view class="stat-item">
        <text class="stat-value">{{ stats.totalCommission }}</text>
        <text class="stat-label">累计返利</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.available }}</text>
        <text class="stat-label">可提现</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.orders }}</text>
        <text class="stat-label">订单数</text>
      </view>
    </view>

    <view class="menu-section">
      <view class="menu-group">
        <view class="menu-item" @click="handleMenuClick('orders')">
          <text class="menu-icon">📋</text>
          <text class="menu-text">我的订单</text>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="handleMenuClick('coupons')">
          <text class="menu-icon">🎫</text>
          <text class="menu-text">优惠券</text>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="handleMenuClick('withdraw')">
          <text class="menu-icon">💰</text>
          <text class="menu-text">提现记录</text>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="handleMenuClick('invite')">
          <text class="menu-icon">👥</text>
          <text class="menu-text">邀请好友</text>
          <text class="menu-arrow">›</text>
        </view>
      </view>

      <view class="menu-group">
        <view class="menu-item" @click="handleMenuClick('settings')">
          <text class="menu-icon">⚙️</text>
          <text class="menu-text">设置</text>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="handleMenuClick('about')">
          <text class="menu-icon">ℹ️</text>
          <text class="menu-text">关于我们</text>
          <text class="menu-arrow">›</text>
        </view>
      </view>
    </view>

    <view class="footer">
      <text class="version">版本 1.0.0</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import auth, { UserInfo } from '@/utils/auth'

const userInfo = ref<UserInfo | null>(null)

const stats = ref({
  totalCommission: '¥0.00',
  available: '¥0.00',
  orders: 0
})

const handleLogin = async () => {
  if (userInfo.value) return
  
  try {
    await auth.login()
    userInfo.value = auth.getStoredUserInfo()
    uni.showToast({
      title: '登录成功',
      icon: 'success'
    })
  } catch (error) {
    console.error('登录失败:', error)
    uni.showToast({
      title: '登录失败',
      icon: 'none'
    })
  }
}

const handleLogout = () => {
  auth.logout()
  userInfo.value = null
}

const handleMenuClick = (type: string) => {
  if (!auth.isLoggedIn() && type !== 'about') {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    return
  }

  const routes: Record<string, string> = {
    orders: '/pages/orders/list',
    coupons: '/pages/coupons/list',
    withdraw: '/pages/withdraw/list',
    invite: '/pages/invite/index',
    settings: '/pages/settings/index',
    about: '/pages/about/index'
  }

  if (routes[type]) {
    uni.navigateTo({
      url: routes[type]
    })
  }
}

onMounted(() => {
  userInfo.value = auth.getStoredUserInfo()
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
}

.user-section {
  background: linear-gradient(135deg, #ff6b00 0%, #ff8c00 100%);
  padding: 40rpx 30rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .user-info {
    display: flex;
    align-items: center;
    gap: 24rpx;

    .avatar {
      width: 100rpx;
      height: 100rpx;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      border: 4rpx solid rgba(255, 255, 255, 0.5);

      .avatar-image {
        width: 100%;
        height: 100%;
        border-radius: 50%;
      }

      .avatar-placeholder {
        font-size: 48rpx;
      }
    }

    .user-detail {
      display: flex;
      flex-direction: column;
      gap: 8rpx;

      .nickname {
        font-size: 32rpx;
        color: #fff;
        font-weight: 600;
      }

      .user-id {
        font-size: 24rpx;
        color: rgba(255, 255, 255, 0.8);
      }
    }
  }

  .logout-btn {
    padding: 12rpx 24rpx;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 20rpx;
    color: #fff;
    font-size: 26rpx;
  }
}

.stats-section {
  display: flex;
  justify-content: space-around;
  align-items: center;
  background: #fff;
  padding: 30rpx;
  margin: -20rpx 20rpx 20rpx;
  border-radius: 16rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.05);

  .stat-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8rpx;

    .stat-value {
      font-size: 36rpx;
      font-weight: 700;
      color: #ff6b00;
    }

    .stat-label {
      font-size: 24rpx;
      color: #999;
    }
  }

  .stat-divider {
    width: 2rpx;
    height: 60rpx;
    background: #f0f0f0;
  }
}

.menu-section {
  padding: 0 20rpx;

  .menu-group {
    background: #fff;
    border-radius: 16rpx;
    margin-bottom: 20rpx;
    overflow: hidden;

    .menu-item {
      display: flex;
      align-items: center;
      padding: 30rpx;
      border-bottom: 2rpx solid #f5f5f5;

      &:last-child {
        border-bottom: none;
      }

      &:active {
        background: #f9f9f9;
      }

      .menu-icon {
        font-size: 36rpx;
        margin-right: 20rpx;
      }

      .menu-text {
        flex: 1;
        font-size: 28rpx;
        color: #333;
      }

      .menu-arrow {
        font-size: 32rpx;
        color: #ccc;
      }
    }
  }
}

.footer {
  padding: 40rpx;
  text-align: center;

  .version {
    font-size: 24rpx;
    color: #ccc;
  }
}
</style>
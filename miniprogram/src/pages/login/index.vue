<!-- @ai-generated -->
<!--
  登录授权页（M03 新建）
  - 品牌展示区（Logo + 标语）
  - 微信一键登录按钮（调用 auth.wxLogin）
  - 登录后回跳原页面（redirect 参数）
  - 用户协议与隐私政策入口
  - 登录失败重试机制
-->
<template>
  <view class="login-page">
    <!-- 品牌展示区 -->
    <view class="brand-section">
      <view class="logo">
        <text class="logo-icon"><IconLine name="crown" style="--size:72rpx;color:#1a1a1a" /></text>
      </view>
      <text class="brand-name">金角大王</text>
      <text class="brand-slogan">购物先搜券 · 下单拿返利</text>
    </view>

    <!-- 福利展示区 -->
    <view class="benefits-section">
      <view class="benefit-item">
        <text class="benefit-icon"><IconLine name="yuan" style="--size:44rpx;color:#1a1a1a" /></text>
        <view class="benefit-text">
          <text class="benefit-title">购物返利</text>
          <text class="benefit-desc">下单即返佣，最高可达30%</text>
        </view>
      </view>
      <view class="benefit-item">
        <text class="benefit-icon"><IconLine name="search" style="--size:44rpx;color:#1a1a1a" /></text>
        <view class="benefit-text">
          <text class="benefit-title">全网比价</text>
          <text class="benefit-desc">淘宝/天猫商品一键转链</text>
        </view>
      </view>
      <view class="benefit-item">
        <text class="benefit-icon"><IconLine name="bolt" style="--size:44rpx;color:#1a1a1a" /></text>
        <view class="benefit-text">
          <text class="benefit-title">极速提现</text>
          <text class="benefit-desc">微信到账，安全便捷</text>
        </view>
      </view>
    </view>

    <!-- 登录按钮区 -->
    <view class="login-actions">
      <view
        class="login-btn"
        :class="{ disabled: logging }"
        @click="handleWxLogin"
      >
        <text v-if="logging" class="btn-text">登录中...</text>
        <text v-else class="btn-text">微信一键登录</text>
      </view>

      <view v-if="IS_DEV" class="mock-login-btn" @click="handleMockLogin">
        <text>开发环境 Mock 登录</text>
      </view>

      <view class="skip-btn" @click="handleSkip">
        <text>暂不登录，先逛逛</text>
      </view>
    </view>

    <!-- 协议说明 -->
    <view class="agreement-section">
      <view class="agreement-row" @click="toggleAgreement">
        <view class="checkbox" :class="{ checked: agreed }">
          <IconLine v-if="agreed" name="check" class="check-icon" style="--size:24rpx;color:#fff" />
        </view>
        <text class="agreement-text">
          我已阅读并同意
          <text class="agreement-link" @click.stop="openAgreement">《用户协议与隐私政策》</text>
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import IconLine from '@/components/IconLine.vue'
import { onLoad } from '@dcloudio/uni-app'
import auth from '@/utils/auth'

const IS_DEV = import.meta.env.DEV

const logging = ref(false)
const agreed = ref(false)
const redirectUrl = ref('/pages/index/index')

onLoad((options: any) => {
  if (options?.redirect) {
    redirectUrl.value = decodeURIComponent(options.redirect)
  }
})

/** 切换协议同意状态 */
const toggleAgreement = () => {
  agreed.value = !agreed.value
}

/** 微信一键登录 */
const handleWxLogin = async () => {
  if (logging.value) return

  if (!agreed.value) {
    uni.showToast({ title: '请先同意用户协议和隐私政策', icon: 'none' })
    return
  }

  logging.value = true
  try {
    await auth.wxLogin()
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      redirectToTarget()
    }, 800)
  } catch (error) {
    const msg = error instanceof Error ? error.message : '登录失败，请重试'
    uni.showToast({ title: msg, icon: 'none', duration: 2500 })
  } finally {
    logging.value = false
  }
}

/** 开发环境 Mock 登录 */
const handleMockLogin = async () => {
  if (logging.value) return
  if (!agreed.value) {
    uni.showToast({ title: '请先同意用户协议和隐私政策', icon: 'none' })
    return
  }

  logging.value = true
  try {
    await auth.mockLogin()
    uni.showToast({ title: 'Mock 登录成功', icon: 'success' })
    setTimeout(() => {
      redirectToTarget()
    }, 800)
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Mock 登录失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    logging.value = false
  }
}

/** 暂不登录 → 回首页 */
const handleSkip = () => {
  uni.switchTab({ url: '/pages/index/index' })
}

/** 登录后回跳目标页面 */
const redirectToTarget = () => {
  const target = redirectUrl.value
  // tabBar 页面用 switchTab，普通页面用 redirectTo
  const tabBarPages = ['/pages/index/index', '/pages/favorite/list', '/pages/mine/mine']

  // 首次登录/未完善资料引导：从首页直接登录且昵称为默认"微信用户"时，跳个人资料页引导完善头像昵称
  const stored = auth.getStoredUserInfo()
  const isDefaultNickname = !stored?.nickname || stored.nickname === '微信用户'
  const isFromDefaultPage = target === '/pages/index/index'

  if (isFromDefaultPage && isDefaultNickname) {
    uni.redirectTo({
      url: '/pages/user/profile',
      fail: () => {
        uni.switchTab({ url: '/pages/index/index' })
      }
    })
    return
  }

  if (tabBarPages.includes(target)) {
    uni.switchTab({ url: target })
  } else {
    uni.redirectTo({ url: target, fail: () => {
      // 回跳失败兜底回首页
      uni.switchTab({ url: '/pages/index/index' })
    } })
  }
}

/** 打开协议页面 */
const openAgreement = () => {
  uni.navigateTo({
    url: `/pages/webview/index?type=user`
  })
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #ffd400 0%, #fff4c7 32%, #f2f3f5 55%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 40rpx 60rpx;
}

/* 品牌展示区 */
.brand-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 80rpx;

  .logo {
    width: 160rpx;
    height: 160rpx;
    border-radius: 40rpx;
    background: linear-gradient(135deg, #ffd400 0%, #ffb800 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24rpx;
    box-shadow: 0 8rpx 24rpx rgba(255, 212, 0, 0.35);

    .logo-icon {
      font-size: 80rpx;
    }
  }

  .brand-name {
    font-size: 44rpx;
    font-weight: 700;
    color: #333;
    margin-bottom: 12rpx;
  }

  .brand-slogan {
    font-size: 26rpx;
    color: #999;
  }
}

/* 福利展示区 */
.benefits-section {
  width: 100%;
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx 40rpx;
  margin-bottom: 60rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);

  .benefit-item {
    display: flex;
    align-items: center;
    gap: 24rpx;
    padding: 24rpx 0;

    &:not(:last-child) {
      border-bottom: 2rpx solid #f5f5f5;
    }

    .benefit-icon {
      font-size: 48rpx;
    }

    .benefit-text {
      display: flex;
      flex-direction: column;
      gap: 6rpx;

      .benefit-title {
        font-size: 30rpx;
        font-weight: 600;
        color: #333;
      }

      .benefit-desc {
        font-size: 24rpx;
        color: #999;
      }
    }
  }
}

/* 登录按钮区 */
.login-actions {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;

  .login-btn {
    width: 100%;
    padding: 28rpx 0;
    background: linear-gradient(135deg, #ffd400 0%, #ffb800 100%);
    border-radius: 48rpx;
    text-align: center;
    box-shadow: 0 6rpx 16rpx rgba(255, 212, 0, 0.35);

    &:active {
      opacity: 0.85;
    }

    &.disabled {
      opacity: 0.6;
    }

    .btn-text {
      color: #1a1a1a;
      font-size: 32rpx;
      font-weight: 700;
    }
  }

  .mock-login-btn {
    padding: 16rpx 40rpx;
    background: #f5f5f5;
    border-radius: 32rpx;

    text {
      font-size: 26rpx;
      color: #666;
    }

    &:active {
      opacity: 0.7;
    }
  }

  .skip-btn {
    padding: 16rpx 0;

    text {
      font-size: 26rpx;
      color: #999;
    }

    &:active {
      opacity: 0.7;
    }
  }
}

/* 协议说明 */
.agreement-section {
  margin-top: 60rpx;
  width: 100%;

  .agreement-row {
    display: flex;
    align-items: flex-start;
    gap: 12rpx;
    justify-content: center;

    .checkbox {
      width: 32rpx;
      height: 32rpx;
      border: 2rpx solid #ccc;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 4rpx;

      &.checked {
        background: #1a1a1a;
        border-color: #1a1a1a;

        .check-icon {
          color: #fff;
          font-size: 20rpx;
          font-weight: 700;
        }
      }
    }

    .agreement-text {
      font-size: 24rpx;
      color: #999;
      line-height: 1.6;

      .agreement-link {
        color: var(--amber, #ff9500);
      }
    }
  }
}
</style>

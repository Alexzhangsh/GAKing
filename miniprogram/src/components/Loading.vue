<!-- @ai-generated -->
<!--
  全局 Loading 组件（M05 新建）
  - 内联加载动画（3点跳动 spinner）
  - 支持自定义文案
  - 支持全屏遮罩模式
  用法：
    <Loading text="加载中..." />
    <Loading text="提交中..." fullscreen />
-->
<template>
  <view v-if="fullscreen" class="loading-mask" @touchmove.stop.prevent>
    <view class="loading-box">
      <view class="loading-spinner">
        <view class="dot dot-1"></view>
        <view class="dot dot-2"></view>
        <view class="dot dot-3"></view>
      </view>
      <text v-if="text" class="loading-text">{{ text }}</text>
    </view>
  </view>
  <view v-else class="loading-inline">
    <view class="loading-spinner">
      <view class="dot dot-1"></view>
      <view class="dot dot-2"></view>
      <view class="dot dot-3"></view>
    </view>
    <text v-if="text" class="loading-text">{{ text }}</text>
  </view>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  text?: string
  fullscreen?: boolean
}>(), {
  text: '加载中...',
  fullscreen: false
})
</script>

<style lang="scss" scoped>
/* 全屏遮罩模式 */
.loading-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;

  .loading-box {
    background: rgba(0, 0, 0, 0.75);
    border-radius: 16rpx;
    padding: 40rpx 50rpx;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20rpx;
    min-width: 160rpx;

    .loading-text {
      color: #fff;
      font-size: 26rpx;
    }
  }
}

/* 内联模式 */
.loading-inline {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60rpx 0;
  gap: 20rpx;

  .loading-text {
    color: var(--color-text-placeholder, #999);
    font-size: 26rpx;
  }
}

/* 三点跳动 spinner */
.loading-spinner {
  display: flex;
  align-items: center;
  gap: 12rpx;

  .dot {
    width: 16rpx;
    height: 16rpx;
    border-radius: 50%;
    background: var(--color-primary, #ff9500);
    animation: dot-bounce 1.4s infinite ease-in-out both;

    &.dot-1 {
      animation-delay: -0.32s;
    }
    &.dot-2 {
      animation-delay: -0.16s;
    }
  }

  .loading-mask & .dot {
    background: #fff;
  }
}

@keyframes dot-bounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>

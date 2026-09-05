<!-- @ai-generated -->
<!--
  空状态/异常兜底组件（M05 优化：新增 loading 类型 + 全局变量）
  统一处理无数据、网络异常、加载失败、加载中等空场景
-->
<template>
  <view class="empty-container">
    <!-- loading 类型使用三点动画 -->
    <template v-if="type === 'loading'">
      <view class="loading-spinner">
        <view class="dot dot-1"></view>
        <view class="dot dot-2"></view>
        <view class="dot dot-3"></view>
      </view>
    </template>
    <!-- 其他类型使用 emoji 图标 -->
    <view v-else class="empty-icon">{{ iconMap[type] }}</view>
    <text class="empty-text">{{ text }}</text>
    <view v-if="actionText" class="empty-action" @click="handleAction">
      <text>{{ actionText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type EmptyType = 'empty' | 'error' | 'network' | 'search' | 'loading'

const props = withDefaults(
  defineProps<{
    /** 空状态类型 */
    type?: EmptyType
    /** 自定义文案（不传则使用默认文案） */
    text?: string
    /** 操作按钮文案 */
    actionText?: string
  }>(),
  {
    type: 'empty',
    text: '',
    actionText: ''
  }
)

const emit = defineEmits<{
  (e: 'action'): void
}>()

const iconMap: Record<string, string> = {
  empty: '📦',
  error: '⚠️',
  network: '📡',
  search: '🔍',
  loading: ''
}

const defaultTextMap: Record<string, string> = {
  empty: '暂无数据',
  error: '加载失败，请稍后重试',
  network: '网络异常，请检查网络设置',
  search: '暂无相关商品，换个关键词试试',
  loading: '加载中...'
}

const text = computed(() => props.text || defaultTextMap[props.type] || '暂无数据')

const handleAction = () => {
  emit('action')
}
</script>

<style lang="scss" scoped>
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 40rpx;

  .empty-icon {
    font-size: 96rpx;
    margin-bottom: 24rpx;
    opacity: 0.6;
  }

  .empty-text {
    font-size: 28rpx;
    color: var(--color-text-placeholder, #999);
    text-align: center;
    line-height: 1.5;
  }

  .empty-action {
    margin-top: 32rpx;
    padding: 16rpx 48rpx;
    background: var(--color-primary, #ff9500);
    border-radius: var(--radius-full, 40rpx);

    text {
      color: #fff;
      font-size: 26rpx;
    }

    &:active {
      opacity: 0.85;
    }
  }
}

/* loading 三点动画 */
.loading-spinner {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;

  .dot {
    width: 16rpx;
    height: 16rpx;
    border-radius: 50%;
    background: var(--color-primary, #ff9500);
    animation: dot-bounce 1.4s infinite ease-in-out both;

    &.dot-1 { animation-delay: -0.32s; }
    &.dot-2 { animation-delay: -0.16s; }
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

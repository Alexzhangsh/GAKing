<!-- @ai-generated -->
<!--
  搜索框组件
  支持关键词搜索 + 粘贴电商链接转链
  - confirm 事件：用户点击搜索/回车
  - paste-link 事件：检测到粘贴的是电商链接，触发转链
-->
<template>
  <view class="search-bar" :class="{ focused: isFocused }">
    <view class="search-icon">🔍</view>
    <input
      class="search-input"
      :placeholder="placeholder"
      :value="modelValue"
      :confirm-type="'search'"
      @input="handleInput"
      @confirm="handleConfirm"
      @focus="handleFocus"
      @blur="handleBlur"
      @paste="handlePaste"
    />
    <view
      v-if="modelValue"
      class="clear-btn"
      @click="handleClear"
    >
      <text>✕</text>
    </view>
    <view v-if="showSearchBtn" class="search-btn" @click="handleConfirm">
      <text>搜索</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { isEcommerceLink } from '@/utils/clipboard'

const props = withDefaults(
  defineProps<{
    /** 双向绑定的搜索值 */
    modelValue: string
    /** 占位提示文案 */
    placeholder?: string
    /** 是否展示右侧搜索按钮 */
    showSearchBtn?: boolean
  }>(),
  {
    placeholder: '搜索商品 / 粘贴淘宝京东链接',
    showSearchBtn: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'confirm', value: string): void
  (e: 'paste-link', url: string): void
}>()

const isFocused = ref(false)

const handleInput = (e: any) => {
  const val = e.detail.value as string
  emit('update:modelValue', val)
}

const handleConfirm = () => {
  const val = props.modelValue.trim()
  if (!val) {
    uni.showToast({ title: '请输入搜索内容', icon: 'none' })
    return
  }
  emit('confirm', val)
}

const handleFocus = () => {
  isFocused.value = true
}

const handleBlur = () => {
  isFocused.value = false
  // 失焦时检测是否粘贴了电商链接
  const val = props.modelValue.trim()
  if (isEcommerceLink(val)) {
    emit('paste-link', val)
  }
}

const handlePaste = (e: any) => {
  // 微信小程序 paste 事件 detail 含 pastedValue
  const pasted = e.detail?.pastedValue || e.detail?.value || ''
  if (pasted && isEcommerceLink(pasted)) {
    emit('paste-link', pasted)
  }
}

const handleClear = () => {
  emit('update:modelValue', '')
}
</script>

<style lang="scss" scoped>
.search-bar {
  display: flex;
  align-items: center;
  background: #f5f5f5;
  border-radius: 40rpx;
  padding: 14rpx 24rpx;
  transition: all 0.2s;

  &.focused {
    background: #fff;
    border: 2rpx solid var(--amber, #ff9500);
  }

  .search-icon {
    font-size: 28rpx;
    margin-right: 12rpx;
  }

  .search-input {
    flex: 1;
    font-size: 28rpx;
    background: transparent;
    color: #333;
  }

  .clear-btn {
    width: 40rpx;
    height: 40rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-left: 8rpx;

    text {
      font-size: 24rpx;
      color: #ccc;
    }
  }

  .search-btn {
    margin-left: 12rpx;
    padding: 8rpx 30rpx;
    background: var(--ink, #1a1a1a);
    border-radius: 30rpx;

    text {
      color: var(--yellow, #ffd400);
      font-size: 26rpx;
      font-weight: 600;
    }

    &:active {
      opacity: 0.85;
    }
  }
}
</style>

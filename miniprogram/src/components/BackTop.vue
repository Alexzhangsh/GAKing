<!-- @ai-generated -->
<template>
  <view 
    class="back-top" 
    :class="{ show: visible }"
    @click="handleClick"
  >
    <text class="icon">↑</text>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const visible = ref(false)
let scrollTop = 0

const handleScroll = () => {
  const query = uni.createSelectorQuery()
  query.selectViewport().scrollOffset((res) => {
    // res 类型为 NodeInfo | NodeInfo[]，取单个节点的 scrollTop
    const node = Array.isArray(res) ? res[0] : res
    if (node && typeof node.scrollTop === 'number') {
      scrollTop = node.scrollTop
      visible.value = scrollTop > 400
    }
  }).exec()
}

const handleClick = () => {
  uni.pageScrollTo({
    scrollTop: 0,
    duration: 300
  })
}

onMounted(() => {
  uni.$on('pageScroll', handleScroll)
})

onUnmounted(() => {
  uni.$off('pageScroll', handleScroll)
})
</script>

<style lang="scss" scoped>
.back-top {
  position: fixed;
  right: 20rpx;
  bottom: 120rpx;
  width: 80rpx;
  height: 80rpx;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
  z-index: 999;

  &.show {
    opacity: 1;
    pointer-events: auto;
  }

  .icon {
    color: #fff;
    font-size: 32rpx;
    font-weight: bold;
  }
}
</style>
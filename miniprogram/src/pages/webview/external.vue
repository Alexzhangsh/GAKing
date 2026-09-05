<!-- @ai-generated -->
<!--
  外部链接 WebView 页
  用于打开第三方电商链接（淘宝/天猫/大淘客）
  从详情页复制成功弹窗的"去购买"按钮跳转至此
-->
<template>
  <view class="webview-container">
    <web-view :src="targetUrl" @message="handleMessage" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const targetUrl = ref('')

onLoad((options) => {
  const raw = options?.url ? decodeURIComponent(options.url as string) : ''
  if (raw) {
    targetUrl.value = raw
    uni.setNavigationBarTitle({
      title: '去购买'
    })
  } else {
    uni.showToast({ title: '链接无效', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
  }
})

const handleMessage = (e: any) => {
  // web-view 消息回调（预留）
  console.log('[webview] message:', e.detail)
}
</script>

<style scoped>
.webview-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}
</style>
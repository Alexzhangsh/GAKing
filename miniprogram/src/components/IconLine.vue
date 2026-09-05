<!--
  统一线性图标（描边风格与底部 tabBar 一致：2px 圆角圆头线性图标）
  通过本地 PNG 静态资源渲染为 <image>，解决 base64 SVG 在 Android 真机不渲染的问题。
  props:
    name   图标名 search/home/heart/heart-fill/order/yuan/bank/bell/mail/gift/chart/bolt/crown/link/clip/check/clock/cart/question/info/chevron/back/refresh
    color  保留参数：PNG 为固定黑色描边，暂不支持动态变色（原实现同样未生效）
    size   图标边长 rpx（默认 40）
-->
<template>
  <image class="icon-line" :src="iconSrc" :style="{ width: `${size}rpx`, height: `${size}rpx` }" mode="aspectFit" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ name: string; color?: string; size?: number }>(),
  { color: '#1a1a1a', size: 40 }
)

// 图标名 -> 本地 PNG 静态资源（线性描边，与底部 tabBar 风格一致）
const ICON_MAP: Record<string, string> = {
  search: '/static/icons/search.png',
  home: '/static/icons/home.png',
  heart: '/static/icons/heart.png',
  'heart-fill': '/static/icons/heart-fill.png',
  order: '/static/icons/order.png',
  yuan: '/static/icons/yuan.png',
  bank: '/static/icons/bank.png',
  bell: '/static/icons/bell.png',
  mail: '/static/icons/mail.png',
  gift: '/static/icons/gift.png',
  chart: '/static/icons/chart.png',
  bolt: '/static/icons/bolt.png',
  crown: '/static/icons/crown.png',
  link: '/static/icons/link.png',
  clip: '/static/icons/clip.png',
  check: '/static/icons/check.png',
  clock: '/static/icons/clock.png',
  cart: '/static/icons/cart.png',
  question: '/static/icons/question.png',
  info: '/static/icons/info.png',
  chevron: '/static/icons/chevron.png',
  back: '/static/icons/back.png',
  refresh: '/static/icons/refresh.png'
}

const iconSrc = computed(() => ICON_MAP[props.name] || ICON_MAP.chevron)
</script>

<style lang="scss" scoped>
.icon-line {
  display: block;
  flex-shrink: 0;
}
</style>

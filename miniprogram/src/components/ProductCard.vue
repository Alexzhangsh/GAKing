<!-- @ai-generated -->
<!--
  商品卡片组件
  严格复用后端 GoodsItem 字段（src/schemas/cps_goods.py: GoodsItemResponse）
  - 非会员：展示券后价 + 预估返利
  - 点击卡片跳转商品详情页
-->
<template>
  <view class="product-card" @click="handleClick">
    <view class="product-image">
      <image
        :src="imageUrl"
        mode="aspectFill"
        class="image"
        lazy-load
        @error="handleImgError"
      />
      <view v-if="item.invalid" class="invalid-tag">已失效</view>
    </view>
    <view class="product-info">
      <text class="product-title">{{ item.goods_title }}</text>
      <view class="product-price-row">
        <view class="price-main">
          <text class="price-symbol">¥</text>
          <text class="price-value">{{ formatPrice(item.sale_price) }}</text>
        </view>
        <text v-if="item.original_price > item.sale_price" class="original-price">
          ¥{{ formatPrice(item.original_price) }}
        </text>
      </view>
      <view class="shop-row">
        <text class="shop-name">{{ item.shop_name || '未知店铺' }}</text>
        <text class="arrow-icon">›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CdnUrlUtil from '@/utils/cdn'
import type { GoodsItem } from '@/api/types'

export type ProductCardItem = GoodsItem & {
  invalid?: boolean
}

const props = defineProps<{
  item: ProductCardItem
}>()

const emit = defineEmits<{
  (e: 'click', item: ProductCardItem): void
}>()

const imgError = ref(false)

const imageUrl = computed(() => {
  if (imgError.value || !props.item.goods_img) {
    return '/static/placeholder.png'
  }
  return CdnUrlUtil.buildFitUrl(props.item.goods_img, 300, 300)
})

const handleClick = () => {
  emit('click', props.item)
}

const handleImgError = () => {
  imgError.value = true
}

const formatPrice = (val: number): string => {
  if (val === null || val === undefined || isNaN(val)) return '0'
  return Math.floor(val).toString()
}
</script>

<style lang="scss" scoped>
.product-card {
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.08);

  &:active {
    transform: scale(0.98);
    transition: transform 0.1s;
  }
}

.product-image {
  position: relative;
  width: 100%;
  height: 320rpx;
  background: #f5f5f5;

  .image {
    width: 100%;
    height: 100%;
  }

  .invalid-tag {
    position: absolute;
    top: 16rpx;
    right: 16rpx;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    font-size: 22rpx;
    padding: 6rpx 16rpx;
    border-radius: 6rpx;
  }
}

.product-info {
  padding: 20rpx 20rpx 24rpx;
}

.product-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 28rpx;
  color: #1a1a1a;
  line-height: 1.4;
  margin-bottom: 16rpx;
  font-weight: 500;
  min-height: 78rpx;
}

.product-price-row {
  display: flex;
  align-items: baseline;
  gap: 12rpx;
  margin-bottom: 12rpx;

  .price-main {
    display: flex;
    align-items: baseline;

    .price-symbol {
      font-size: 26rpx;
      color: var(--amber, #ff9500);
      font-weight: 600;
    }

    .price-value {
      font-size: 44rpx;
      color: var(--amber, #ff9500);
      font-weight: 700;
      line-height: 1;
    }
  }

  .original-price {
    font-size: 24rpx;
    color: #bbb;
    text-decoration: line-through;
  }
}

.shop-row {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .shop-name {
    font-size: 22rpx;
    color: #999;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .arrow-icon {
    font-size: 32rpx;
    color: #ccc;
    margin-left: 8rpx;
  }
}
</style>

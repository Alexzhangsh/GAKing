<!-- @ai-generated -->
<template>
  <view class="product-card" @click="handleClick">
    <view class="product-image">
      <image :src="cdnUrl" mode="aspectFill" class="image" />
      <view v-if="item.discount" class="discount-tag">{{ item.discount }}折</view>
    </view>
    <view class="product-info">
      <text class="product-title">{{ item.title }}</text>
      <text class="product-desc">{{ item.desc }}</text>
      <view class="product-price-row">
        <view class="price-area">
          <text class="price-symbol">¥</text>
          <text class="price-value">{{ item.price }}</text>
        </view>
        <text class="original-price">¥{{ item.original_price }}</text>
      </view>
      <view class="product-bottom">
        <text class="commission">佣金 ¥{{ item.commission }}</text>
        <view class="sales">
          <text class="sales-icon">🔥</text>
          <text class="sales-count">{{ item.sales }}人购买</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CdnUrlUtil from '@/utils/cdn'

interface ProductCardProps {
  item: {
    id: number
    title: string
    desc: string
    image_url: string
    price: string | number
    original_price: string | number
    discount?: number
    commission: string | number
    sales: number
  }
}

const props = defineProps<ProductCardProps>()
const emit = defineEmits<{
  (e: 'click', item: ProductCardProps['item']): void
}>()

const cdnUrl = computed(() => {
  return CdnUrlUtil.buildFitUrl(props.item.image_url, 300, 300)
})

const handleClick = () => {
  emit('click', props.item)
}
</script>

<style lang="scss" scoped>
.product-card {
  background: #fff;
  border-radius: 12rpx;
  overflow: hidden;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);

  &:active {
    transform: scale(0.98);
    transition: transform 0.1s;
  }
}

.product-image {
  position: relative;
  width: 100%;
  height: 300rpx;

  .image {
    width: 100%;
    height: 100%;
  }

  .discount-tag {
    position: absolute;
    top: 16rpx;
    left: 16rpx;
    background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
    color: #fff;
    font-size: 22rpx;
    padding: 6rpx 16rpx;
    border-radius: 6rpx;
    font-weight: 500;
  }
}

.product-info {
  padding: 20rpx;

  .product-title {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    font-size: 28rpx;
    color: #333;
    line-height: 1.4;
    margin-bottom: 12rpx;
    font-weight: 500;
  }

  .product-desc {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
    overflow: hidden;
    font-size: 24rpx;
    color: #999;
    margin-bottom: 16rpx;
  }

  .product-price-row {
    display: flex;
    align-items: baseline;
    gap: 12rpx;
    margin-bottom: 12rpx;

    .price-area {
      display: flex;
      align-items: baseline;

      .price-symbol {
        font-size: 24rpx;
        color: #ff6b00;
        font-weight: 600;
      }

      .price-value {
        font-size: 40rpx;
        color: #ff6b00;
        font-weight: 700;
      }
    }

    .original-price {
      font-size: 24rpx;
      color: #bbb;
      text-decoration: line-through;
    }
  }

  .product-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .commission {
      font-size: 24rpx;
      color: #52c41a;
      font-weight: 500;
    }

    .sales {
      display: flex;
      align-items: center;
      gap: 4rpx;

      .sales-icon {
        font-size: 22rpx;
      }

      .sales-count {
        font-size: 22rpx;
        color: #999;
      }
    }
  }
}
</style>
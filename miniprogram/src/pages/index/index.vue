<!-- @ai-generated -->
<template>
  <view class="page-container">
    <view class="header">
      <view class="search-bar">
        <text class="search-icon">🔍</text>
        <input 
          class="search-input" 
          placeholder="搜索商品" 
          v-model="searchKeyword"
          @confirm="handleSearch"
        />
      </view>
    </view>

    <view class="banner">
      <swiper 
        class="banner-swiper" 
        :indicator-dots="true" 
        :autoplay="true" 
        :interval="3000" 
        :circular="true"
        indicator-color="rgba(255,255,255,0.5)"
        indicator-active-color="#fff"
      >
        <swiper-item v-for="(item, index) in banners" :key="index">
          <image :src="item.image" mode="aspectFill" class="banner-image" />
        </swiper-item>
      </swiper>
    </view>

    <view class="category">
      <view class="category-item" v-for="(item, index) in categories" :key="index">
        <view class="category-icon">{{ item.icon }}</view>
        <text class="category-name">{{ item.name }}</text>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">热门推荐</text>
        <text class="section-more">更多 ›</text>
      </view>
      <view class="product-list">
        <ProductCard 
          v-for="item in products" 
          :key="item.id" 
          :item="item"
          @click="handleProductClick"
        />
      </view>
    </view>

    <BackTop />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ProductCard from '@/components/ProductCard.vue'
import BackTop from '@/components/BackTop.vue'

const searchKeyword = ref('')

const banners = ref([
  { image: 'https://cdn.example.com/banner1.jpg' },
  { image: 'https://cdn.example.com/banner2.jpg' },
  { image: 'https://cdn.example.com/banner3.jpg' }
])

const categories = ref([
  { icon: '🏠', name: '首页' },
  { icon: '📦', name: '商品' },
  { icon: '🎁', name: '优惠券' },
  { icon: '💰', name: '返利' },
  { icon: '👤', name: '我的' }
])

const products = ref([
  {
    id: 1,
    title: '超值商品标题示例，展示商品的核心卖点信息',
    desc: '商品描述信息，简短介绍产品特点',
    image_url: 'https://cdn.example.com/product1.jpg',
    price: '99.00',
    original_price: '199.00',
    discount: 5,
    commission: '10.00',
    sales: 1234
  },
  {
    id: 2,
    title: '精选优质商品，品质保证值得信赖',
    desc: '精选商品描述，品质优良',
    image_url: 'https://cdn.example.com/product2.jpg',
    price: '159.00',
    original_price: '299.00',
    commission: '15.00',
    sales: 567
  },
  {
    id: 3,
    title: '限时特惠商品，错过不再有',
    desc: '限时特惠，数量有限',
    image_url: 'https://cdn.example.com/product3.jpg',
    price: '49.00',
    original_price: '99.00',
    discount: 5,
    commission: '5.00',
    sales: 2345
  }
])

const handleSearch = () => {
  if (searchKeyword.value.trim()) {
    uni.showToast({
      title: `搜索: ${searchKeyword.value}`,
      icon: 'none'
    })
  }
}

const handleProductClick = (item: any) => {
  uni.navigateTo({
    url: `/pages/product/detail?id=${item.id}`
  })
}

onMounted(() => {
  console.log('Index page mounted')
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  padding: 20rpx;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 100;

  .search-bar {
    display: flex;
    align-items: center;
    background: #f5f5f5;
    border-radius: 40rpx;
    padding: 16rpx 24rpx;

    .search-icon {
      font-size: 28rpx;
      margin-right: 12rpx;
    }

    .search-input {
      flex: 1;
      font-size: 28rpx;
      background: transparent;
    }
  }
}

.banner {
  padding: 0 20rpx 20rpx;

  .banner-swiper {
    height: 300rpx;
    border-radius: 16rpx;
    overflow: hidden;
  }

  .banner-image {
    width: 100%;
    height: 100%;
  }
}

.category {
  display: flex;
  justify-content: space-around;
  padding: 20rpx;
  background: #fff;
  margin-bottom: 20rpx;

  .category-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12rpx;

    .category-icon {
      width: 80rpx;
      height: 80rpx;
      background: #f5f5f5;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 36rpx;
    }

    .category-name {
      font-size: 24rpx;
      color: #666;
    }
  }
}

.section {
  padding: 0 20rpx;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20rpx;

    .section-title {
      font-size: 32rpx;
      font-weight: 600;
      color: #333;
    }

    .section-more {
      font-size: 26rpx;
      color: #999;
    }
  }

  .product-list {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
  }
}
</style>
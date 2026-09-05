<!-- @ai-generated -->
<!--
  首页
  - 自定义导航栏：大标题 + 搜索框
  - 热门推荐商品流（两列网格布局）
  - 剪贴板链接检测
  - 返回顶部组件
-->
<template>
  <view class="page-container">
    <!-- 自定义导航栏 -->
    <view class="custom-nav" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="nav-title">金角大王</view>
      <view class="nav-search">
        <view class="search-icon"><IconLine name="search" style="--size:30rpx" /></view>
        <input
          class="search-input"
          placeholder="搜索商品 / 粘贴淘宝京东链接"
          :value="searchKeyword"
          :confirm-type="'search'"
          @input="handleSearchInput"
          @confirm="handleSearch"
        />
        <view class="search-btn" @click="handleSearch">
          <text>搜索</text>
        </view>
      </view>
    </view>

    <!-- 热门推荐区域 -->
    <view class="section">
      <view class="section-header">
        <text class="section-title">热门推荐</text>
        <text class="section-more" @click="handleSearchMore">更多 ›</text>
      </view>

      <!-- 加载中 -->
      <view v-if="loading && products.length === 0" class="loading-wrap">
        <text class="loading-text">加载中...</text>
      </view>

      <!-- 商品列表 -->
      <view v-else-if="products.length > 0" class="product-list">
        <view class="product-card-wrapper" v-for="item in products" :key="item.goods_id">
          <ProductCard
            :item="item"
            @click="handleProductClick"
          />
        </view>
      </view>

      <!-- 空状态兜底 -->
      <Empty
        v-else
        type="error"
        text="推荐商品加载失败，请稍后重试"
        action-text="重新加载"
        @action="loadRecommendProducts"
      />
    </view>

    <!-- 剪贴板转链提示弹窗 -->
    <view v-if="clipboardTipVisible" class="clipboard-tip-mask" @click="dismissClipboardTip">
      <view class="clipboard-tip" @click.stop>
        <view class="tip-header">
          <text class="tip-icon"><IconLine name="link" style="--size:34rpx;vertical-align:middle" /></text>
          <text class="tip-title">检测到商品链接</text>
        </view>
        <text class="tip-content">{{ clipboardUrl }}</text>
        <view class="tip-actions">
          <view class="tip-btn cancel" @click="dismissClipboardTip">
            <text>取消</text>
          </view>
          <view class="tip-btn confirm" @click="goConvertLink">
            <text>立即转链</text>
          </view>
        </view>
      </view>
    </view>

    <BackTop />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import ProductCard from '@/components/ProductCard.vue'
import BackTop from '@/components/BackTop.vue'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { searchGoods } from '@/api/goods'
import { checkClipboardLink } from '@/utils/clipboard'
import { setupHomeShare } from '@/utils/share'
import { setPendingProduct } from '@/utils/product-store'
import tracker from '@/utils/tracker'
import type { GoodsItem } from '@/api/types'

setupHomeShare(onShareAppMessage, onShareTimeline)

const statusBarHeight = ref(20)

uni.getSystemInfo({
  success: (res) => {
    statusBarHeight.value = res.statusBarHeight || 20
  }
})

const searchKeyword = ref('')
const products = ref<GoodsItem[]>([])
const loading = ref(false)
const clipboardTipVisible = ref(false)
const clipboardUrl = ref('')

const handleSearchInput = (e: any) => {
  searchKeyword.value = e.detail.value
}

const loadRecommendProducts = async () => {
  loading.value = true
  try {
    const res = await searchGoods('热销', 1, 20, 'myq')
    products.value = res.data?.items || []
  } catch (error) {
    console.warn('[首页] 推荐商品加载失败:', error)
    products.value = []
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    uni.showToast({ title: '请输入搜索内容', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/search/list?keyword=${encodeURIComponent(keyword)}`
  })
}

const handleSearchMore = () => {
  uni.navigateTo({
    url: `/pages/search/list?keyword=${encodeURIComponent('热销')}`
  })
}

const handleProductClick = (item: GoodsItem) => {
  tracker.trackGoodsClick(item.goods_id, item.goods_title)
  setPendingProduct(item)
  uni.navigateTo({
    url: `/pages/product/detail?goods_id=${encodeURIComponent(item.goods_id)}`
  })
}

const checkClipboard = async () => {
  const url = await checkClipboardLink()
  if (url) {
    clipboardUrl.value = url
    clipboardTipVisible.value = true
  }
}

const goConvertLink = () => {
  clipboardTipVisible.value = false
  uni.navigateTo({
    url: `/pages/product/detail?url=${encodeURIComponent(clipboardUrl.value)}`
  })
  uni.setClipboardData({ data: '' })
}

const dismissClipboardTip = () => {
  clipboardTipVisible.value = false
}

onMounted(() => {
  loadRecommendProducts()
  tracker.trackPageView('首页')
})

onShow(() => {
  checkClipboard()
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #ffffff;
  padding-bottom: 40rpx;
}

.custom-nav {
  background: #ffffff;
  padding: 0 32rpx 24rpx;
}

.nav-title {
  font-size: 40rpx;
  font-weight: 700;
  color: #1a1a1a;
  text-align: center;
  margin-bottom: 24rpx;
  letter-spacing: 2rpx;
}

.nav-search {
  display: flex;
  align-items: center;
  background: #f5f5f5;
  border-radius: 40rpx;
  padding: 16rpx 16rpx 16rpx 28rpx;
}

.search-icon {
  font-size: 28rpx;
  margin-right: 16rpx;
  color: #999;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
  color: #333;
  background: transparent;
}

.search-btn {
  background: #1a1a1a;
  color: #fff;
  font-size: 26rpx;
  padding: 12rpx 28rpx;
  border-radius: 32rpx;
  margin-left: 16rpx;

  text {
    color: #fff;
  }

  &:active {
    opacity: 0.8;
  }
}

.section {
  padding: 32rpx 24rpx 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28rpx;
}

.section-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #1a1a1a;
}

.section-more {
  font-size: 26rpx;
  color: #999;
}

.product-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;

  .product-card-wrapper {
    width: 48.5%;
    margin-bottom: 24rpx;
  }
}

.loading-wrap {
  padding: 120rpx 0;
  text-align: center;
}

.loading-text {
  font-size: 28rpx;
  color: #999;
}

.clipboard-tip-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.clipboard-tip {
  width: 600rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx;
}

.tip-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}

.tip-icon {
  font-size: 36rpx;
}

.tip-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
}

.tip-content {
  display: block;
  font-size: 26rpx;
  color: #666;
  line-height: 1.5;
  margin-bottom: 32rpx;
  word-break: break-all;
  max-height: 120rpx;
  overflow: hidden;
}

.tip-actions {
  display: flex;
  gap: 20rpx;
}

.tip-btn {
  flex: 1;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 40rpx;

  text {
    font-size: 28rpx;
  }

  &.cancel {
    background: #f5f5f5;
    text {
      color: #666;
    }
  }

  &.confirm {
    background: var(--ink, #1a1a1a);
    text {
      color: var(--yellow, #ffd400);
      font-weight: 600;
    }
  }
}
</style>

<!-- @ai-generated -->
<!--
  商品搜索结果页
  - 顶部搜索框（回显关键词，支持二次搜索）
  - 搜索结果列表（两列卡片，对接 B01 商品搜索接口）
  - 分页加载（滚动到底部加载下一页，每页20条）
  - 异常兜底（网络异常、限流、无结果）
  - 返回顶部组件
-->
<template>
  <view class="page-container">
    <!-- 顶部搜索栏 -->
    <view class="header">
      <view class="back-btn" @click="handleBack">
        <IconLine name="back" style="--size:36rpx;color:#1a1a1a" />
      </view>
      <view class="nav-search">
        <view class="search-icon"><IconLine name="search" style="--size:30rpx" /></view>
        <input
          class="search-input"
          placeholder="搜索商品 / 粘贴链接"
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

    <!-- 搜索结果统计 -->
    <view v-if="!loading && products.length > 0" class="result-summary">
      <text class="summary-text">共找到 {{ total }} 件商品</text>
    </view>

    <!-- 商品列表 -->
    <scroll-view
      v-if="products.length > 0 || loading"
      scroll-y
      class="product-scroll"
      @scrolltolower="loadMore"
      :lower-threshold="100"
    >
      <view class="product-list">
        <view class="product-card-wrapper" v-for="item in products" :key="item.goods_id">
          <ProductCard
            :item="item"
            @click="handleProductClick"
          />
        </view>
      </view>

      <!-- 加载状态 -->
      <view class="load-status">
        <text v-if="loading" class="status-text">加载中...</text>
        <text v-else-if="!hasMore" class="status-text">没有更多了</text>
        <text v-else class="status-text" @click="loadMore">加载更多</text>
      </view>
    </scroll-view>

    <!-- 空状态 / 异常兜底 -->
    <view v-else-if="!loading && hasSearched" class="empty-wrap">
      <Empty
        :type="errorType"
        :text="errorText"
        :action-text="errorType === 'error' ? '重新加载' : ''"
        @action="handleRetry"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import ProductCard from '@/components/ProductCard.vue'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { searchGoods } from '@/api/goods'
import tracker from '@/utils/tracker'
import { setPendingProduct } from '@/utils/product-store'
import type { GoodsItem } from '@/api/types'
import { BizError } from '@/utils/request'

const searchKeyword = ref('')
const products = ref<GoodsItem[]>([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)
const hasMore = ref(true)
const hasSearched = ref(false)

// 异常兜底类型
const errorType = ref<'empty' | 'error' | 'network' | 'search'>('search')
const errorText = ref('')

const handleSearchInput = (e: any) => {
  searchKeyword.value = e.detail.value
}

/** 执行搜索 */
const doSearch = async (keyword: string, resetPage = true) => {
  if (!keyword.trim()) {
    uni.showToast({ title: '请输入搜索内容', icon: 'none' })
    return
  }

  if (resetPage) {
    page.value = 1
    products.value = []
    hasMore.value = true
  }

  loading.value = true
  hasSearched.value = true

  try {
    const res = await searchGoods(keyword, page.value, size, 'myq')
    const items = res.data?.items || []

    if (resetPage) {
      products.value = items
    } else {
      products.value = products.value.concat(items)
    }

    total.value = res.data?.total || 0
    // 判断是否还有更多
    hasMore.value = products.value.length < total.value && items.length >= size

    // 无结果兜底
    if (products.value.length === 0) {
      errorType.value = 'search'
      errorText.value = '暂无相关商品，换个关键词试试'
    }
  } catch (error) {
    // 异常兜底：区分网络异常 / 限流 / 服务异常
    if (error instanceof BizError) {
      if (error.code === 429) {
        errorType.value = 'error'
        errorText.value = '搜索太频繁，请稍后再试'
      } else if (error.code >= 500) {
        errorType.value = 'network'
        errorText.value = '网络异常，请检查网络后重试'
      } else {
        errorType.value = 'search'
        errorText.value = error.message || '暂无相关商品'
      }
    } else {
      errorType.value = 'network'
      errorText.value = '网络连接失败，请检查网络设置'
    }
    products.value = []
  } finally {
    loading.value = false
  }
}

/** 搜索按钮 / 回车 */
const handleSearch = () => {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    uni.showToast({ title: '请输入搜索内容', icon: 'none' })
    return
  }
  doSearch(keyword, true)
}

/** 加载更多 */
const loadMore = async () => {
  if (loading.value || !hasMore.value) return
  page.value++
  await doSearch(searchKeyword.value, false)
}

/** 重试 */
const handleRetry = () => {
  doSearch(searchKeyword.value, true)
}

/** 商品点击 → 商品详情页 */
const handleProductClick = (item: GoodsItem) => {
  // 商品点击埋点
  tracker.trackGoodsClick(item.goods_id, item.goods_title)
  setPendingProduct(item)
  uni.navigateTo({
    url: `/pages/product/detail?goods_id=${encodeURIComponent(item.goods_id)}`
  })
}

/** 返回 */
const handleBack = () => {
  uni.navigateBack({ delta: 1 })
}

onLoad((options: any) => {
  const keyword = options?.keyword ? decodeURIComponent(options.keyword) : ''
  if (keyword) {
    searchKeyword.value = keyword
    doSearch(keyword, true)
  }
  // 搜索页浏览埋点
  tracker.trackPageView('搜索结果', { keyword: keyword || '' })
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #ffffff;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 20rpx 32rpx;
  background: #ffffff;
  position: sticky;
  top: 0;
  z-index: 100;

  .back-btn {
    width: 60rpx;
    height: 60rpx;
    display: flex;
    align-items: center;
    justify-content: center;

    text {
      font-size: 48rpx;
      color: #1a1a1a;
      line-height: 1;
    }
  }

  .nav-search {
    flex: 1;
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
}

.result-summary {
  padding: 16rpx 32rpx;

  .summary-text {
    font-size: 24rpx;
    color: #999;
  }
}

.product-scroll {
  flex: 1;
  height: 0;

  .product-list {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    padding: 0 24rpx;

    .product-card-wrapper {
      width: 48.5%;
      margin-bottom: 24rpx;
    }
  }

  .load-status {
    text-align: center;
    padding: 30rpx 0 60rpx;

    .status-text {
      font-size: 26rpx;
      color: #999;
    }
  }
}

.empty-wrap {
  flex: 1;
}
</style>
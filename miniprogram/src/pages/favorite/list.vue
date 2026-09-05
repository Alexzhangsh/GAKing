<!-- @ai-generated -->
<!--
  收藏夹页
  - 收藏列表（两列卡片，按收藏时间倒序）
  - 分类筛选（基于收藏商品的 category 字段）
  - 一键清理已失效商品
  - 商品下架后展示"已失效"，点击提示后从列表移除
  - 返回顶部组件
-->
<template>
  <view class="page-container">
    <!-- 顶部 -->
    <view class="header">
      <view class="back-btn" @click="handleBack">
        <IconLine name="back" style="--size:36rpx;color:#1a1a1a" />
      </view>
      <view class="title">
        <text>我的收藏</text>
      </view>
      <view
        v-if="invalidCount > 0"
        class="clean-btn"
        @click="handleCleanInvalid"
      >
        <text>清理失效({{ invalidCount }})</text>
      </view>
    </view>

    <!-- 分类筛选 -->
    <view v-if="categories.length > 0" class="category-filter">
      <scroll-view scroll-x class="category-scroll" :show-scrollbar="false">
        <view class="category-list">
          <view
            class="category-chip"
            :class="{ active: activeCategory === '' }"
            @click="selectCategory('')"
          >
            <text>全部({{ totalCount }})</text>
          </view>
          <view
            v-for="cat in categories"
            :key="cat"
            class="category-chip"
            :class="{ active: activeCategory === cat }"
            @click="selectCategory(cat)"
          >
            <text>{{ cat }}({{ getCategoryCount(cat) }})</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 收藏列表 -->
    <view v-if="filteredList.length > 0" class="product-list">
      <view class="product-card-wrapper" v-for="item in filteredList" :key="item.goods_id">
        <ProductCard
          :item="item"
          @click="handleProductClick"
        />
      </view>
    </view>

    <!-- 空状态 -->
    <Empty
      v-else
      type="empty"
      text="还未收藏任何商品"
      action-text="去逛逛"
      @action="goHome"
    />

    <BackTop />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import ProductCard, { type ProductCardItem } from '@/components/ProductCard.vue'
import BackTop from '@/components/BackTop.vue'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import {
  getFavorites,
  getFavoriteCategories,
  clearInvalidFavorites,
  removeFavorite
} from '@/utils/favorite'
import { setPendingProduct } from '@/utils/product-store'
import type { FavoriteItem } from '@/api/types'

const favorites = ref<FavoriteItem[]>([])
const categories = ref<string[]>([])
const activeCategory = ref('')

/** 按类目筛选后的列表 */
const filteredList = computed(() => {
  if (!activeCategory.value) return favorites.value
  return favorites.value.filter((item) => item.category === activeCategory.value)
})

/** 失效商品数 */
const invalidCount = computed(() => {
  return favorites.value.filter((item) => item.invalid).length
})

/** 总收藏数 */
const totalCount = computed(() => favorites.value.length)

/** 类目下商品数 */
const getCategoryCount = (category: string): number => {
  return favorites.value.filter((item) => item.category === category).length
}

/** 刷新收藏列表 */
const refreshFavorites = () => {
  favorites.value = getFavorites()
  categories.value = getFavoriteCategories()
}

/** 选择类目 */
const selectCategory = (category: string) => {
  activeCategory.value = category
}

/** 商品点击 → 商品详情页 */
const handleProductClick = (item: ProductCardItem) => {
  if (item.invalid) {
    // 已失效商品：提示后从列表移除（保留快照查看一次）
    uni.showModal({
      title: '提示',
      content: '该商品优惠已失效，请选择其他商品',
      showCancel: false,
      confirmText: '知道了',
      success: () => {
        removeFavorite(item.goods_id)
        refreshFavorites()
      }
    })
    return
  }
  setPendingProduct(item)
  uni.navigateTo({
    url: `/pages/product/detail?goods_id=${encodeURIComponent(item.goods_id)}`
  })
}

/** 一键清理失效商品 */
const handleCleanInvalid = () => {
  if (invalidCount.value === 0) {
    uni.showToast({ title: '无失效商品可清理', icon: 'none' })
    return
  }
  uni.showModal({
    title: '提示',
    content: `确认清理 ${invalidCount.value} 件失效商品？`,
    success: (res) => {
      if (res.confirm) {
        const count = clearInvalidFavorites()
        refreshFavorites()
        uni.showToast({
          title: `已清理 ${count} 件失效商品`,
          icon: 'success'
        })
      }
    }
  })
}

/** 返回 */
const handleBack = () => {
  uni.navigateBack({ delta: 1 })
}

/** 去首页 */
const goHome = () => {
  uni.switchTab({ url: '/pages/index/index' })
}

onMounted(() => {
  refreshFavorites()
})

// onShow 时刷新（从详情页取消收藏后同步）
onShow(() => {
  refreshFavorites()
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  background: #fff;
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
      color: #333;
      line-height: 1;
    }
  }

  .title {
    flex: 1;
    text-align: center;

    text {
      font-size: 34rpx;
      font-weight: 600;
      color: #333;
    }
  }

  .clean-btn {
    padding: 12rpx 24rpx;
    background: var(--yellow-soft, #fff0b0);
    border-radius: 30rpx;

    text {
      font-size: 24rpx;
      color: #1a1a1a;
      font-weight: 600;
    }
  }
}

.category-filter {
  background: #fff;
  padding: 16rpx 0;
  margin-bottom: 20rpx;

  .category-scroll {
    width: 100%;
  }

  .category-list {
    display: flex;
    gap: 16rpx;
    padding: 0 24rpx;
    white-space: nowrap;

    .category-chip {
      display: inline-block;
      padding: 12rpx 28rpx;
      background: #f5f5f5;
      border-radius: 30rpx;

      text {
        font-size: 24rpx;
        color: #666;
      }

      &.active {
        background: var(--ink, #1a1a1a);

        text {
          color: var(--yellow, #ffd400);
          font-weight: 600;
        }
      }
    }
  }
}

.product-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0 20rpx;

  .product-card-wrapper {
    width: 48.5%;
    margin-bottom: 24rpx;
  }
}
</style>

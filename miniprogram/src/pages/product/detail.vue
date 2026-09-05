<!-- @ai-generated -->
<!--
  商品详情页
  - 商品主图（轮播）
  - 商品标题、店铺、类目
  - 多渠道价格区块（原价、券后价、预估返利）
  - 复制购买链接（对接 B02 转链接口）
  - 收藏 / 取消收藏（本地缓存快照）
  - 微信小程序分享能力（onShareAppMessage）
  - 异常兜底（转链失败、商品不存在）
-->
<template>
  <view class="page-container">
    <!-- 加载中 -->
    <view v-if="loading && !goods.goods_id" class="loading-wrap">
      <text class="loading-text">商品加载中...</text>
    </view>

    <!-- 商品详情内容 -->
    <view v-else-if="goods.goods_id" class="detail-content">
      <!-- 商品主图轮播 -->
      <view class="image-swiper">
        <swiper
          class="swiper"
          :indicator-dots="goodsImgList.length > 1"
          :autoplay="false"
          :circular="true"
          indicator-color="rgba(255,255,255,0.5)"
          indicator-active-color="#fff"
        >
          <swiper-item v-for="(img, index) in goodsImgList" :key="index">
            <image
              :src="img"
              mode="aspectFill"
              class="goods-image"
              @click="previewImage(index)"
            />
          </swiper-item>
        </swiper>
      </view>

      <!-- 商品标题 -->
      <view class="title-section">
        <view class="price-row">
          <view class="sale-price">
            <text class="symbol">¥</text>
            <text class="value">{{ formatPrice(goods.sale_price) }}</text>
          </view>
          <view v-if="goods.original_price > goods.sale_price" class="original-price">
            <text>¥{{ formatPrice(goods.original_price) }}</text>
          </view>
          <view v-if="discountText" class="discount-tag">{{ discountText }}</view>
        </view>
        <text class="goods-title">{{ goods.goods_title }}</text>
        <view class="meta-row">
          <text v-if="goods.shop_name" class="shop-name">{{ goods.shop_name }}</text>
          <text v-if="goods.category" class="category">分类：{{ goods.category }}</text>
          <text class="sales">销量 {{ formatSales(goods.sales_volume) }}</text>
        </view>
      </view>

      <!-- 返利区块 -->
      <view class="commission-section">
        <view class="commission-card">
          <view class="commission-left">
            <text class="commission-label">预估返利</text>
            <view class="commission-value">
              <text class="symbol">¥</text>
              <text class="value">{{ formatPrice(goods.estimate_commission) }}</text>
            </view>
          </view>
          <view class="commission-right">
            <text class="rate">佣金比例 {{ goods.commission_rate }}%</text>
            <text class="source">来源：{{ channelText }}</text>
          </view>
        </view>
      </view>

      <!-- 转链结果区块 -->
      <view v-if="convertResult" class="convert-section">
        <view class="section-title">
          <text>购买链接已生成</text>
        </view>
        <view class="convert-info">
          <text class="convert-url">{{ convertResult.promote_url }}</text>
          <view class="convert-meta">
            <text v-if="convertResult.estimate_commission > 0" class="commission-tip">
              预估返利 ¥{{ formatPrice(convertResult.estimate_commission) }}
            </text>
          </view>
        </view>
        <view class="convert-actions">
          <view class="action-btn primary" @click="copyPromoteUrl">
            <text>复制购买链接</text>
          </view>
          <view class="action-btn secondary" @click="openPromoteUrl">
            <text>打开链接</text>
          </view>
        </view>
      </view>

      <!-- 图文介绍占位 -->
      <view class="desc-section">
        <view class="section-title">
          <text>商品详情</text>
        </view>
        <view class="desc-content">
          <text class="desc-text">{{ goods.goods_title }}</text>
          <text class="desc-tip">如需查看完整图文详情，请复制链接到对应电商平台查看</text>
        </view>
      </view>
    </view>

    <!-- 异常兜底 -->
    <view v-else class="empty-wrap">
      <Empty
        type="error"
        :text="errorText"
        action-text="返回首页"
        @action="goHome"
      />
    </view>

    <!-- 底部操作栏 -->
    <view v-if="goods.goods_id" class="bottom-bar safe-area-bottom">
      <view class="bottom-left">
        <view class="icon-btn" @click="goHome">
          <IconLine name="home" class="icon" style="--size:40rpx;color:#1a1a1a" />
          <text class="label">首页</text>
        </view>
        <view class="icon-btn" @click="toggleFav">
          <IconLine :name="isFav ? 'heart-fill' : 'heart'" class="icon" style="--size:40rpx" :style="{ color: isFav ? '#ffd400' : '#1a1a1a' }" />
          <text class="label">{{ isFav ? '已收藏' : '收藏' }}</text>
        </view>
      </view>
      <view class="bottom-right">
        <view
          class="action-btn convert"
          :class="{ disabled: converting }"
          @click="handleConvertLink"
        >
          <text>{{ converting ? '转链中...' : convertResult ? '重新转链' : '复制购买链接' }}</text>
        </view>
      </view>
    </view>

    <!-- 复制成功弹窗 -->
    <view v-if="copySuccessVisible" class="copy-success-mask" @click="dismissCopySuccess">
      <view class="copy-success-dialog" @click.stop>
        <view class="dialog-icon"><IconLine name="check" style="--size:88rpx;color:#ffd400" /></view>
        <text class="dialog-title">{{ copiedIsTpwd ? '淘口令已复制' : '链接已复制' }}</text>
        <text class="dialog-content">{{ copiedIsTpwd ? '请打开【淘宝App】，将自动识别商品并跳转购买' : `您已成功复制购买链接，请打开【${channelText}】购买商品` }}</text>
        <!-- 时效提示 -->
        <view class="timeout-tip">
          <text class="timeout-icon"><IconLine name="clock" style="--size:28rpx;color:#e6a23c" /></text>
          <text class="timeout-text">链接72小时内有效，请尽快下单以确保返利正常追踪，超时将无法自动归属</text>
        </view>
        <!-- 双按钮 -->
        <view class="dialog-actions">
          <view class="dialog-btn secondary" @click="dismissCopySuccess">
            <text>确认</text>
          </view>
          <view class="dialog-btn primary" @click="handleGoBuy">
            <text>去购买</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad, onShareAppMessage } from '@dcloudio/uni-app'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { searchGoods, convertLink } from '@/api/goods'
import auth from '@/utils/auth'
import { isFavorited, toggleFavorite, markInvalid } from '@/utils/favorite'
import { setClipboardData } from '@/utils/clipboard'
import { setupProductShare } from '@/utils/share'
import { takePendingProduct } from '@/utils/product-store'
import tracker from '@/utils/tracker'
import type { ConvertLinkResponse, GoodsItem } from '@/api/types'
import { formatPrice } from '@/utils/format'

const goods = ref<GoodsItem>({} as GoodsItem)
const loading = ref(false)
const converting = ref(false)
const convertResult = ref<ConvertLinkResponse | null>(null)
const isFav = ref(false)
const errorText = ref('商品信息加载失败')

const copySuccessVisible = ref(false)
const copiedIsTpwd = ref(false)

/** 商品图片列表（一期单图，预留多图） */
const goodsImgList = computed(() => {
  return goods.value.goods_img ? [goods.value.goods_img] : []
})

/** 折扣文案 */
const discountText = computed(() => {
  const { original_price, sale_price } = goods.value
  if (!original_price || original_price <= sale_price || sale_price <= 0) return ''
  const discount = Math.round((sale_price / original_price) * 10)
  return discount > 0 && discount < 10 ? `${discount}折` : ''
})

/** 渠道名称中文映射 */
const channelText = computed(() => {
  const map: Record<string, string> = {
    myq: '淘宝/天猫',
    orderx: '淘宝/天猫',
    dta: '大淘客'
  }
  return map[goods.value.source_channel || 'myq'] || '电商'
})

/** 销量格式化 */
const formatSales = (val: number): string => {
  if (val >= 10000) return `${(val / 10000).toFixed(1)}万`
  return `${val}`
}

/** 加载商品详情（通过 goods_id 重新搜索获取） */
const loadGoodsDetail = async (goods_id: string) => {
  loading.value = true
  try {
    // 一期后端无单商品详情接口，通过搜索关键词复用商品列表数据
    // 若从首页/搜索页跳入，商品数据已缓存在全局，这里做兜底搜索
    const res = await searchGoods(goods_id, 1, 20, 'myq')
    const item = res.data?.items?.find((g) => g.goods_id === goods_id)
    if (item) {
      goods.value = item
      isFav.value = isFavorited(item.goods_id)
      // 商品详情页浏览埋点
      tracker.trackPageView('商品详情', { goods_id: item.goods_id })
    } else {
      errorText.value = '商品不存在或已下架'
    }
  } catch (error) {
    console.warn('[商品详情] 加载失败:', error)
    errorText.value = '商品信息加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/** 通过粘贴链接进入：直接转链获取商品信息 */
const loadFromUrl = async (url: string) => {
  loading.value = true
  try {
    await doConvertLink(url)
  } finally {
    loading.value = false
  }
}

/** 执行转链 */
const doConvertLink = async (url?: string) => {
  // 转链需要用户身份标识，确保已登录
  if (!auth.ensureLogin()) return

  const originalUrl = url || goods.value.promote_url || ''
  if (!originalUrl) {
    uni.showToast({ title: '无有效商品链接', icon: 'none' })
    return
  }

  // 获取用户渠道溯源标识（一期使用 user_id）
  const userInfo = auth.getStoredUserInfo()
  const userChannelId = String(userInfo?.user_id || 'anonymous')

  converting.value = true
  try {
    const res = await convertLink(originalUrl, userChannelId, 'myq')
    convertResult.value = res.data

    // 若通过粘贴链接进入且商品信息为空，构造基础商品信息
    if (!goods.value.goods_id && res.data.goods_id) {
      goods.value = {
        goods_id: res.data.goods_id,
        goods_title: '粘贴链接转链商品',
        goods_img: '',
        original_price: 0,
        sale_price: 0,
        commission_rate: 0,
        estimate_commission: res.data.estimate_commission,
        category: '',
        promote_url: res.data.promote_url,
        shop_name: '',
        sales_volume: 0,
        source_channel: res.data.channel_code
      } as GoodsItem
    }

    // 更新收藏状态
    if (goods.value.goods_id) {
      isFav.value = isFavorited(goods.value.goods_id)
    }
  } catch (error) {
    // 转链失败兜底
    const errMsg =
      error instanceof Error ? error.message : '转链失败，请稍后重试'
    uni.showToast({ title: errMsg, icon: 'none', duration: 2500 })
  } finally {
    converting.value = false
  }
}

/** 点击转链 / 重新转链 */
const handleConvertLink = () => {
  if (converting.value) return
  if (convertResult.value) {
    // 已转链，直接复制
    copyPromoteUrl()
  } else {
    doConvertLink()
  }
}

/** 复制购买链接（优先复制淘口令，淘宝App打开自动识别） */
const copyPromoteUrl = async () => {
  if (!convertResult.value?.promote_url && !convertResult.value?.tpwd) {
    // 未转链则先转链
    await doConvertLink()
    if (!convertResult.value?.promote_url && !convertResult.value?.tpwd) return
  }
  // 优先复制淘口令（淘宝App打开自动识别商品），无淘口令时复制推广链接
  const hasTpwd = !!(convertResult.value?.tpwd && convertResult.value.tpwd.trim())
  const copyContent = hasTpwd
    ? convertResult.value!.tpwd
    : (convertResult.value?.promote_url || '')
  if (!copyContent) {
    uni.showToast({ title: '无有效购买链接', icon: 'none' })
    return
  }
  const ok = await setClipboardData(copyContent)
  if (ok) {
    copiedIsTpwd.value = hasTpwd
    copySuccessVisible.value = true
  } else {
    uni.showToast({ title: '复制失败，请手动复制', icon: 'none' })
  }
}

/** 打开链接（H5 环境） */
const openPromoteUrl = () => {
  if (!convertResult.value?.promote_url) {
    uni.showToast({ title: '请先转链', icon: 'none' })
    return
  }
  // #ifdef H5
  window.open(convertResult.value.promote_url, '_blank')
  // #endif
  // #ifndef H5
  copyPromoteUrl()
  // #endif
}

/** 切换收藏 */
const toggleFav = () => {
  if (!goods.value.goods_id) return
  if (!auth.ensureLogin()) return

  const wasFav = isFav.value
  isFav.value = toggleFavorite(goods.value)

  uni.showToast({
    title: wasFav ? '已取消收藏' : '商品已收藏',
    icon: 'none'
  })
}

/** 预览图片 */
const previewImage = (index: number) => {
  uni.previewImage({
    current: index,
    urls: goodsImgList.value
  })
}

/** 返回首页 */
const goHome = () => {
  uni.switchTab({ url: '/pages/index/index' })
}

/** 关闭复制成功弹窗 */
const dismissCopySuccess = () => {
  copySuccessVisible.value = false
}

/** 去购买：跳转 webview 打开第三方电商链接 */
const handleGoBuy = () => {
  copySuccessVisible.value = false
  if (!convertResult.value?.promote_url) {
    uni.showToast({ title: '暂无购买链接', icon: 'none' })
    return
  }
  // 跳转 webview 页打开链接
  const url = encodeURIComponent(convertResult.value.promote_url)
  uni.navigateTo({ url: `/pages/webview/external?url=${url}` })
}

/** 微信小程序分享（使用全局分享组件，懒求值保证商品数据已加载） */
setupProductShare(onShareAppMessage, () => {
  // 分享埋点
  tracker.trackShare('friend', { goods_id: goods.value.goods_id || '' })
  return {
    title: goods.value.goods_title || '金角大王 - 购物返利省不停',
    path: '/pages/product/detail',
    params: { goods_id: goods.value.goods_id || '' },
    imageUrl: goods.value.goods_img || ''
  }
})

onLoad((options: any) => {
  const goodsId = options?.goods_id ? decodeURIComponent(options.goods_id) : ''
  const url = options?.url ? decodeURIComponent(options.url) : ''

  // 优先使用列表页传递的商品数据（避免 hash ID 搜索不到的问题）
  const pending = takePendingProduct()
  if (pending && pending.goods_id === goodsId) {
    goods.value = pending
    isFav.value = isFavorited(pending.goods_id)
    tracker.trackPageView('商品详情', { goods_id: pending.goods_id })
    return
  }

  if (url) {
    // 通过粘贴链接进入 → 直接转链
    loadFromUrl(url)
  } else if (goodsId) {
    // 通过商品ID进入 → 加载详情（兜底搜索）
    loadGoodsDetail(goodsId)
  } else {
    errorText.value = '商品参数缺失'
  }
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 140rpx;
}

.loading-wrap {
  padding: 200rpx 0;
  text-align: center;

  .loading-text {
    font-size: 28rpx;
    color: #999;
  }
}

.detail-content {
  .image-swiper {
    background: #fff;

    .swiper {
      width: 100%;
      height: 750rpx;

      .goods-image {
        width: 100%;
        height: 100%;
      }
    }
  }

  .title-section {
    background: #fff;
    padding: 24rpx;
    margin-bottom: 20rpx;

    .price-row {
      display: flex;
      align-items: baseline;
      gap: 16rpx;
      margin-bottom: 16rpx;

      .sale-price {
        display: flex;
        align-items: baseline;

        .symbol {
          font-size: 28rpx;
          color: var(--amber, #ff9500);
          font-weight: 600;
        }

        .value {
          font-size: 56rpx;
          color: var(--amber, #ff9500);
          font-weight: 700;
        }
      }

      .original-price {
        text {
          font-size: 28rpx;
          color: #bbb;
          text-decoration: line-through;
        }
      }

      .discount-tag {
        background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
        color: #fff;
        font-size: 22rpx;
        padding: 6rpx 16rpx;
        border-radius: 6rpx;
        font-weight: 500;
      }
    }

    .goods-title {
      display: block;
      font-size: 32rpx;
      color: #333;
      line-height: 1.5;
      font-weight: 500;
      margin-bottom: 16rpx;
    }

    .meta-row {
      display: flex;
      flex-wrap: wrap;
      gap: 20rpx;

      text {
        font-size: 24rpx;
        color: #999;
      }
    }
  }

  .commission-section {
    padding: 0 24rpx;
    margin-bottom: 20rpx;

    .commission-card {
      background: linear-gradient(135deg, #fff0b0 0%, #ffe58a 100%);
      border-radius: 24rpx;
      padding: 30rpx;
      display: flex;
      justify-content: space-between;
      align-items: center;

      .commission-left {
        display: flex;
        flex-direction: column;
        gap: 8rpx;

        .commission-label {
          font-size: 24rpx;
          color: #999;
        }

        .commission-value {
          display: flex;
          align-items: baseline;

          .symbol {
            font-size: 28rpx;
            color: var(--amber, #ff9500);
            font-weight: 600;
          }

          .value {
            font-size: 48rpx;
            color: var(--amber, #ff9500);
            font-weight: 700;
          }
        }
      }

      .commission-right {
        text-align: right;
        display: flex;
        flex-direction: column;
        gap: 8rpx;

        .rate {
          font-size: 24rpx;
          color: #666;
        }

        .source {
          font-size: 22rpx;
          color: #999;
        }
      }
    }
  }

  .convert-section,
  .desc-section {
    background: #fff;
    margin-bottom: 20rpx;
    padding: 24rpx;

    .section-title {
      margin-bottom: 20rpx;

      text {
        font-size: 30rpx;
        font-weight: 600;
        color: #333;
      }
    }
  }

  .convert-section {
    .convert-info {
      background: #f9f9f9;
      border-radius: 12rpx;
      padding: 20rpx;
      margin-bottom: 20rpx;

      .convert-url {
        display: block;
        font-size: 24rpx;
        color: #666;
        word-break: break-all;
        line-height: 1.5;
        margin-bottom: 12rpx;
      }

      .convert-meta {
        .commission-tip {
          font-size: 24rpx;
          color: #52c41a;
        }
      }
    }

    .convert-actions {
      display: flex;
      gap: 20rpx;

      .action-btn {
        flex: 1;
        text-align: center;
        padding: 20rpx 0;
        border-radius: 40rpx;

        text {
          font-size: 28rpx;
        }

        &.primary {
          background: var(--ink, #1a1a1a);

          text {
            color: var(--yellow, #ffd400);
            font-weight: 600;
          }
        }

        &.secondary {
          background: var(--yellow-soft, #fff0b0);

          text {
            color: #1a1a1a;
          }
        }
      }
    }
  }

  .desc-section {
    .desc-content {
      .desc-text {
        display: block;
        font-size: 28rpx;
        color: #333;
        line-height: 1.6;
        margin-bottom: 16rpx;
      }

      .desc-tip {
        font-size: 24rpx;
        color: #999;
      }
    }
  }
}

.empty-wrap {
  padding-top: 80rpx;
}

/* 底部操作栏 */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120rpx;
  background: #fff;
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  box-shadow: 0 -2rpx 12rpx rgba(0, 0, 0, 0.05);
  z-index: 100;

  .bottom-left {
    display: flex;
    gap: 40rpx;
    padding-right: 20rpx;

    .icon-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4rpx;

      .icon {
        font-size: 36rpx;
      }

      .label {
        font-size: 22rpx;
        color: #666;
      }
    }
  }

  .bottom-right {
    flex: 1;

    .action-btn {
      text-align: center;
      padding: 24rpx 0;
      background: var(--ink, #1a1a1a);
      border-radius: 40rpx;

      text {
        color: var(--yellow, #ffd400);
        font-size: 30rpx;
        font-weight: 600;
      }

      &.disabled {
        opacity: 0.6;
      }

      &.convert {
        &:active {
          opacity: 0.85;
        }
      }
    }
  }
}

/* 复制成功弹窗 */
.copy-success-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.copy-success-dialog {
  width: 560rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 48rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;

  .dialog-icon {
    font-size: 80rpx;
    margin-bottom: 24rpx;
  }

  .dialog-title {
    font-size: 34rpx;
    font-weight: 600;
    color: #333;
    margin-bottom: 16rpx;
  }

  .dialog-content {
    font-size: 26rpx;
    color: #666;
    text-align: center;
    line-height: 1.5;
    margin-bottom: 32rpx;
  }

  .timeout-tip {
    display: flex;
    align-items: flex-start;
    gap: 8rpx;
    background: #fff8e1;
    border-radius: 12rpx;
    padding: 16rpx 20rpx;
    margin-bottom: 32rpx;
    width: 100%;

    .timeout-icon {
      font-size: 28rpx;
      flex-shrink: 0;
      margin-top: 2rpx;
    }

    .timeout-text {
      font-size: 24rpx;
      color: #e6a23c;
      line-height: 1.5;
    }
  }

  .dialog-actions {
    width: 100%;
    display: flex;
    gap: 20rpx;

    .dialog-btn {
      flex: 1;
      text-align: center;
      padding: 20rpx 0;
      border-radius: 40rpx;

      text {
        font-size: 30rpx;
        font-weight: 500;
      }

      &.primary {
        background: var(--ink, #1a1a1a);

        text {
          color: var(--yellow, #ffd400);
          font-weight: 600;
        }
      }

      &.secondary {
        background: #f5f5f5;

        text {
          color: #666;
        }
      }
    }
  }
}
</style>

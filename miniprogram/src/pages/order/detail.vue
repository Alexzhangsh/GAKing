<!-- @ai-generated -->
<!--
  订单详情页
  - 商品信息区（图片+标题+支付金额）
  - 订单状态区（状态标签+订单号+支付时间+结算时间）
  - 佣金信息区（用户佣金/平台佣金/总佣金）
  - 佣金流水明细列表（commission_flows，含流水类型/金额/转账状态/时间）
  - 异常兜底（订单不存在/加载失败）
-->
<template>
  <view class="page-container">
    <!-- 加载中 -->
    <view v-if="loading && !order.id" class="loading-wrap">
      <text class="loading-text">订单加载中...</text>
    </view>

    <!-- 订单详情内容 -->
    <view v-else-if="order.id" class="detail-content">
      <!-- 商品信息 -->
      <view class="section goods-section">
        <view class="goods-main">
          <view class="goods-img">
            <image
              v-if="order.goods_img"
              :src="order.goods_img"
              mode="aspectFill"
              class="image"
            />
            <text v-else class="img-placeholder"><IconLine name="order" style="--size:52rpx;color:#bbb" /></text>
          </view>
          <view class="goods-info">
            <text class="goods-title">{{ order.goods_title || '商品信息同步中' }}</text>
            <view class="goods-price">
              <text class="symbol">¥</text>
              <text class="value">{{ formatPrice(order.pay_amount) }}</text>
              <text class="label">支付金额</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 订单状态 -->
      <view class="section status-section">
        <view class="status-header">
          <text class="status-tag" :class="getStatusClass(order.order_status)">
            {{ getStatusText(order.order_status) }}
          </text>
          <text class="status-desc">{{ getStatusDesc(order.order_status) }}</text>
        </view>
        <view class="status-list">
          <view class="status-item">
            <text class="item-label">订单编号</text>
            <text class="item-value">{{ order.out_order_no }}</text>
          </view>
          <view class="status-item">
            <text class="item-label">内部单号</text>
            <text class="item-value">{{ order.internal_order_no }}</text>
          </view>
          <view class="status-item">
            <text class="item-label">支付时间</text>
            <text class="item-value">{{ order.pay_time || '-' }}</text>
          </view>
          <view v-if="order.settle_time" class="status-item">
            <text class="item-label">结算时间</text>
            <text class="item-value">{{ order.settle_time }}</text>
          </view>
          <view class="status-item">
            <text class="item-label">下单时间</text>
            <text class="item-value">{{ order.create_time }}</text>
          </view>
        </view>
      </view>

      <!-- 佣金信息 -->
      <view class="section commission-section">
        <view class="section-title">
          <text>佣金信息</text>
        </view>
        <view class="commission-grid">
          <view class="commission-cell highlight">
            <text class="cell-value">¥{{ formatPrice(order.user_commission) }}</text>
            <text class="cell-label">我的返利</text>
          </view>
          <view class="commission-cell">
            <text class="cell-value">¥{{ formatPrice(order.platform_commission) }}</text>
            <text class="cell-label">平台佣金</text>
          </view>
          <view class="commission-cell">
            <text class="cell-value">¥{{ formatPrice(order.total_commission) }}</text>
            <text class="cell-label">总佣金</text>
          </view>
        </view>
      </view>

      <!-- 佣金流水明细 -->
      <view class="section flows-section">
        <view class="section-title">
          <text>佣金流水明细</text>
          <text v-if="flows.length > 0" class="flow-count">共{{ flows.length }}条</text>
        </view>

        <view v-if="flows.length > 0" class="flow-list">
          <view v-for="flow in flows" :key="flow.id" class="flow-item">
            <view class="flow-left">
              <text class="flow-type">{{ getFlowTypeText(flow.flow_type) }}</text>
              <text class="flow-time">{{ flow.create_time }}</text>
              <text v-if="flow.remark" class="flow-remark">{{ flow.remark }}</text>
            </view>
            <view class="flow-right">
              <text class="flow-amount" :class="{ deduct: flow.flow_type === 'DEDUCT' }">
                {{ flow.flow_type === 'DEDUCT' ? '-' : '+' }}¥{{ formatPrice(flow.amount) }}
              </text>
              <text class="flow-transfer" :class="getTransferClass(flow.transfer_status)">
                {{ getTransferText(flow.transfer_status) }}
              </text>
            </view>
          </view>
        </view>

        <view v-else class="flow-empty">
          <text class="empty-text">暂无佣金流水记录</text>
          <text class="empty-tip">订单结算后将生成佣金流水</text>
        </view>
      </view>
    </view>

    <!-- 异常兜底 -->
    <Empty
      v-else
      type="error"
      :text="errorText"
      action-text="返回订单列表"
      @action="goBack"
    />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import Empty from '@/components/Empty.vue'
import IconLine from '@/components/IconLine.vue'
import { getOrderDetail } from '@/api/order'
import { BizError } from '@/utils/request'
import {
  OrderStatus,
  ORDER_STATUS_TEXT,
  type CommissionFlow,
  type OrderDetailResponse
} from '@/api/types'
import { formatPrice } from '@/utils/format'

const orderId = ref(0)
const order = ref<OrderDetailResponse>({} as OrderDetailResponse)
const flows = ref<CommissionFlow[]>([])
const loading = ref(false)
const errorText = ref('订单信息加载失败')

/** 加载订单详情 */
const loadOrderDetail = async (id: number) => {
  loading.value = true
  try {
    const res = await getOrderDetail(id)
    if (res.data) {
      order.value = res.data
      flows.value = res.data.commission_flows || []
    } else {
      errorText.value = '订单不存在'
    }
  } catch (error) {
    if (error instanceof BizError) {
      errorText.value = error.message || '订单信息加载失败'
    } else {
      errorText.value = '网络连接失败，请检查网络设置'
    }
  } finally {
    loading.value = false
  }
}

/** 获取状态中文 */
const getStatusText = (status: number): string => {
  return ORDER_STATUS_TEXT[status] || '未知'
}

/** 获取状态描述 */
const getStatusDesc = (status: number): string => {
  const map: Record<number, string> = {
    [OrderStatus.PENDING]: '订单已创建，等待付款',
    [OrderStatus.FROZEN]: '订单异常冻结，请联系客服',
    [OrderStatus.SETTLABLE]: '订单已付款，佣金待结算',
    [OrderStatus.SETTLED]: '订单已结算，佣金已入账',
    [OrderStatus.INVALID]: '订单已失效',
    [OrderStatus.REFUNDED]: '订单已退款'
  }
  return map[status] || ''
}

/** 获取状态样式类 */
const getStatusClass = (status: number): string => {
  const map: Record<number, string> = {
    [OrderStatus.PENDING]: 'status-pending',
    [OrderStatus.FROZEN]: 'status-frozen',
    [OrderStatus.SETTLABLE]: 'status-settlable',
    [OrderStatus.SETTLED]: 'status-settled',
    [OrderStatus.INVALID]: 'status-invalid',
    [OrderStatus.REFUNDED]: 'status-refunded'
  }
  return map[status] || 'status-default'
}

/** 流水类型中文 */
const getFlowTypeText = (type: string): string => {
  const map: Record<string, string> = {
    ORDER: '订单佣金',
    SUPPLEMENT: '佣金补发',
    DEDUCT: '佣金扣减'
  }
  return map[type] || type
}

/** 转账状态中文 */
const getTransferText = (status: string): string => {
  const map: Record<string, string> = {
    PENDING: '待转账',
    PROCESSING: '转账中',
    SUCCESS: '已到账',
    FAILED: '转账失败'
  }
  return map[status] || status
}

/** 转账状态样式 */
const getTransferClass = (status: string): string => {
  const map: Record<string, string> = {
    PENDING: 'transfer-pending',
    PROCESSING: 'transfer-processing',
    SUCCESS: 'transfer-success',
    FAILED: 'transfer-failed'
  }
  return map[status] || ''
}

/** 返回订单列表 */
const goBack = () => {
  uni.navigateBack({ delta: 1 })
}

onLoad((options: any) => {
  const id = Number(options?.id || 0)
  if (id > 0) {
    orderId.value = id
    loadOrderDetail(id)
  } else {
    errorText.value = '订单参数缺失'
  }
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 40rpx;
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
  .section {
    background: #fff;
    margin-bottom: 20rpx;
    padding: 24rpx;
  }
}

.goods-section {
  .goods-main {
    display: flex;
    gap: 20rpx;

    .goods-img {
      width: 160rpx;
      height: 160rpx;
      border-radius: 12rpx;
      background: #f5f5f5;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      .image {
        width: 100%;
        height: 100%;
        border-radius: 12rpx;
      }

      .img-placeholder {
        font-size: 56rpx;
      }
    }

    .goods-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;

      .goods-title {
        font-size: 30rpx;
        color: #333;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
      }

      .goods-price {
        display: flex;
        align-items: baseline;
        gap: 8rpx;

        .symbol {
          font-size: 28rpx;
          color: var(--amber, #ff9500);
          font-weight: 600;
        }

        .value {
          font-size: 44rpx;
          color: var(--amber, #ff9500);
          font-weight: 700;
        }

        .label {
          font-size: 24rpx;
          color: #999;
          margin-left: 8rpx;
        }
      }
    }
  }
}

.status-section {
  .status-header {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin-bottom: 24rpx;

    .status-tag {
      font-size: 26rpx;
      padding: 8rpx 20rpx;
      border-radius: 8rpx;
      font-weight: 500;

      &.status-pending {
        color: #999;
        background: #f5f5f5;
      }
      &.status-frozen {
        color: #faad14;
        background: #fff7e6;
      }
      &.status-settlable {
        color: #1890ff;
        background: #e6f7ff;
      }
      &.status-settled {
        color: #52c41a;
        background: #f6ffed;
      }
      &.status-invalid {
        color: #999;
        background: #f5f5f5;
      }
      &.status-refunded {
        color: #ff4d4f;
        background: #fff1f0;
      }
    }

    .status-desc {
      font-size: 26rpx;
      color: #666;
    }
  }

  .status-list {
    .status-item {
      display: flex;
      justify-content: space-between;
      padding: 16rpx 0;

      .item-label {
        font-size: 26rpx;
        color: #999;
      }

      .item-value {
        font-size: 26rpx;
        color: #333;
      }
    }
  }
}

.commission-section {
  .section-title {
    font-size: 30rpx;
    font-weight: 600;
    color: #333;
    margin-bottom: 24rpx;
  }

  .commission-grid {
    display: flex;
    justify-content: space-around;

    .commission-cell {
      flex: 1;
      text-align: center;
      display: flex;
      flex-direction: column;
      gap: 8rpx;

      &.highlight {
        .cell-value {
          color: var(--amber, #ff9500);
        }
      }

      .cell-value {
        font-size: 36rpx;
        font-weight: 700;
        color: #333;
      }

      .cell-label {
        font-size: 24rpx;
        color: #999;
      }
    }
  }
}

.flows-section {
  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24rpx;

    text:first-child {
      font-size: 30rpx;
      font-weight: 600;
      color: #333;
    }

    .flow-count {
      font-size: 24rpx;
      color: #999;
    }
  }

  .flow-list {
    .flow-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20rpx 0;
      border-bottom: 2rpx solid #f5f5f5;

      &:last-child {
        border-bottom: none;
      }

      .flow-left {
        display: flex;
        flex-direction: column;
        gap: 6rpx;

        .flow-type {
          font-size: 28rpx;
          color: #333;
        }

        .flow-time {
          font-size: 22rpx;
          color: #bbb;
        }

        .flow-remark {
          font-size: 22rpx;
          color: #999;
        }
      }

      .flow-right {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 6rpx;

        .flow-amount {
          font-size: 30rpx;
          font-weight: 600;
          color: #52c41a;

          &.deduct {
            color: #ff4d4f;
          }
        }

        .flow-transfer {
          font-size: 22rpx;
          padding: 4rpx 12rpx;
          border-radius: 4rpx;

          &.transfer-pending {
            color: #999;
            background: #f5f5f5;
          }
          &.transfer-processing {
            color: #1890ff;
            background: #e6f7ff;
          }
          &.transfer-success {
            color: #52c41a;
            background: #f6ffed;
          }
          &.transfer-failed {
            color: #ff4d4f;
            background: #fff1f0;
          }
        }
      }
    }
  }

  .flow-empty {
    padding: 60rpx 0;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 12rpx;

    .empty-text {
      font-size: 28rpx;
      color: #999;
    }

    .empty-tip {
      font-size: 24rpx;
      color: #bbb;
    }
  }
}
</style>

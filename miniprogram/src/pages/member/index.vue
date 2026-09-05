<!-- @ai-generated -->
<!--
  会员中心页面
  - 会员状态展示
  - 会员权益说明
  - 续费入口
-->
<template>
  <view class="member-page">
    <view class="member-card">
      <view class="card-header">
        <text class="card-title">金角大王会员</text>
        <view v-if="isMember" class="member-badge">VIP</view>
      </view>
      <view class="card-body">
        <text class="member-status">{{ isMember ? '您已是尊贵会员' : '升级会员享受更多优惠' }}</text>
        <text v-if="isMember" class="member-expire">到期时间：{{ expireDate }}</text>
      </view>
      <view class="card-footer">
        <view class="renew-btn" @click="handleRenew">
          <text>{{ isMember ? '立即续费' : '立即开通' }}</text>
        </view>
      </view>
    </view>

    <view class="benefits-section">
      <text class="section-title">会员权益</text>
      <view class="benefits-list">
        <view class="benefit-item" v-for="(item, index) in benefits" :key="index">
          <view class="benefit-icon"><IconLine :name="item.icon" style="--size:40rpx;color:#1a1a1a" /></view>
          <view class="benefit-info">
            <text class="benefit-title">{{ item.title }}</text>
            <text class="benefit-desc">{{ item.desc }}</text>
          </view>
        </view>
      </view>
    </view>

    <view class="price-section">
      <text class="section-title">会员套餐</text>
      <view class="price-list">
        <view
          v-for="(item, index) in pricePlans"
          :key="index"
          class="price-item"
          :class="{ active: selectedPlan === index }"
          @click="selectPlan(index)"
        >
          <text class="price-period">{{ item.period }}</text>
          <text class="price-amount">¥{{ item.price }}</text>
          <text v-if="item.originalPrice" class="price-original">¥{{ item.originalPrice }}</text>
          <text v-if="item.tag" class="price-tag">{{ item.tag }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import IconLine from '@/components/IconLine.vue'

const isMember = ref(false)
const expireDate = ref('2026-12-31')
const selectedPlan = ref(0)

const benefits = ref([
  { icon: 'yuan', title: '最高返利', desc: '享受会员专属返利比例' },
  { icon: 'bolt', title: '优先发货', desc: '订单优先处理确认' },
  { icon: 'gift', title: '专属活动', desc: '会员专属优惠活动' },
  { icon: 'chart', title: '数据分析', desc: '消费数据分析报告' }
])

const pricePlans = ref([
  { period: '月卡', price: 29.9, originalPrice: 39.9, tag: '实惠' },
  { period: '季卡', price: 79.9, originalPrice: 119.7, tag: '推荐' },
  { period: '年卡', price: 259.9, originalPrice: 478.8, tag: '超值' }
])

const selectPlan = (index: number) => {
  selectedPlan.value = index
}

const handleRenew = () => {
  uni.showToast({ title: '会员功能开发中', icon: 'none' })
}
</script>

<style lang="scss" scoped>
.member-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 30rpx;
  padding-bottom: 60rpx;
}

.member-card {
  background: linear-gradient(135deg, #ffd400 0%, #ffb800 100%);
  border-radius: 24rpx;
  padding: 40rpx;
  color: #1a1a1a;
  margin-bottom: 30rpx;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;

  .card-title {
    font-size: 36rpx;
    font-weight: 700;
  }

  .member-badge {
    background: #1a1a1a;
    color: #ffd400;
    padding: 8rpx 20rpx;
    border-radius: 20rpx;
    font-size: 24rpx;
    font-weight: 600;
  }
}

.card-body {
  margin-bottom: 40rpx;

  .member-status {
    display: block;
    font-size: 32rpx;
    margin-bottom: 16rpx;
  }

  .member-expire {
    font-size: 26rpx;
    opacity: 0.8;
  }
}

.card-footer {
  .renew-btn {
    background: #1a1a1a;
    color: #ffd400;
    text-align: center;
    padding: 24rpx 0;
    border-radius: 40rpx;
    font-weight: 600;
    font-size: 30rpx;

    &:active {
      opacity: 0.9;
    }
  }
}

.benefits-section {
  background: #fff;
  border-radius: 24rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;

  .section-title {
    display: block;
    font-size: 32rpx;
    font-weight: 600;
    color: #333;
    margin-bottom: 30rpx;
  }
}

.benefits-list {
  .benefit-item {
    display: flex;
    align-items: center;
    padding: 24rpx 0;
    border-bottom: 1rpx solid #f5f5f5;

    &:last-child {
      border-bottom: none;
    }

    .benefit-icon {
      width: 80rpx;
      height: 80rpx;
      background: var(--yellow-soft, #fff0b0);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 40rpx;
      margin-right: 24rpx;
    }

    .benefit-info {
      flex: 1;

      .benefit-title {
        display: block;
        font-size: 28rpx;
        font-weight: 600;
        color: #333;
        margin-bottom: 8rpx;
      }

      .benefit-desc {
        font-size: 24rpx;
        color: #999;
      }
    }
  }
}

.price-section {
  background: #fff;
  border-radius: 24rpx;
  padding: 30rpx;

  .section-title {
    display: block;
    font-size: 32rpx;
    font-weight: 600;
    color: #333;
    margin-bottom: 30rpx;
  }
}

.price-list {
  display: flex;
  gap: 20rpx;

  .price-item {
    flex: 1;
    background: #f8f8f8;
    border-radius: 16rpx;
    padding: 30rpx 20rpx;
    text-align: center;
    border: 2rpx solid transparent;
    transition: all 0.2s;

    &.active {
      background: var(--yellow-soft, #fff0b0);
      border-color: var(--amber, #ff9500);
    }

    .price-period {
      display: block;
      font-size: 26rpx;
      color: #666;
      margin-bottom: 16rpx;
    }

    .price-amount {
      display: block;
      font-size: 40rpx;
      font-weight: 700;
      color: var(--amber, #ff9500);
      margin-bottom: 8rpx;
    }

    .price-original {
      display: block;
      font-size: 22rpx;
      color: #ccc;
      text-decoration: line-through;
      margin-bottom: 12rpx;
    }

    .price-tag {
      display: inline-block;
      background: #1a1a1a;
      color: #ffd400;
      font-size: 20rpx;
      padding: 4rpx 16rpx;
      border-radius: 20rpx;
    }
  }
}
</style>

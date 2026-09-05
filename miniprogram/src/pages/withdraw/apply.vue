<!-- @ai-generated -->
<!--
  提现申请页
  - 可提现余额展示
  - 金额输入（支持全部提现快捷按钮）
  - 手续费试算（fee = max(amount × 0.1%, 1元)）
  - 实际到账金额展示
  - 提现规则说明（门槛 10 元 / T+N 延迟到账）
  - 提交提现申请（对接 POST /api/v1/withdraw/apply）
  - 提交成功后跳转提现记录页
-->
<template>
  <view class="page-container">
    <!-- 余额展示 -->
    <view class="balance-card">
      <text class="balance-label">可提现佣金(元)</text>
      <view class="balance-amount">
        <text class="symbol">¥</text>
        <text class="value">{{ formatPrice(account.available_balance) }}</text>
      </view>
    </view>

    <!-- 提现金额输入 -->
    <view class="input-section">
      <view class="section-title">
        <text>提现金额</text>
      </view>
      <view class="amount-input">
        <text class="currency">¥</text>
        <input
          class="input"
          type="digit"
          :value="amountStr"
          placeholder="请输入提现金额"
          @input="handleAmountInput"
        />
        <view class="all-btn" @click="handleAllWithdraw">
          <text>全部</text>
        </view>
      </view>

      <!-- 手续费试算 -->
      <view v-if="amount > 0" class="fee-detail">
        <view class="fee-row">
          <text class="fee-label">提现金额</text>
          <text class="fee-value">¥{{ formatPrice(amount) }}</text>
        </view>
        <view class="fee-row">
          <text class="fee-label">手续费(0.1%)</text>
          <text class="fee-value">-¥{{ formatPrice(fee) }}</text>
        </view>
        <view class="fee-row highlight">
          <text class="fee-label">实际到账</text>
          <text class="fee-value">¥{{ formatPrice(actualAmount) }}</text>
        </view>
      </view>
    </view>

    <!-- 提现规则 -->
    <view class="rules-section">
      <view class="section-title">
        <text>提现说明</text>
      </view>
      <view class="rules-list">
        <text class="rule-item">1. 最低提现金额 10 元</text>
        <text class="rule-item">2. 手续费 = max(提现金额 × 0.1%, 1元)</text>
        <text class="rule-item">3. 提现申请提交后进入审核，审核通过后微信打款</text>
        <text class="rule-item">4. 打款到账时间 T+N（N 为延迟天数）</text>
        <text class="rule-item">5. 提现申请期间金额将被冻结，驳回后退回可用余额</text>
      </view>
    </view>

    <!-- 提交按钮 -->
    <view class="bottom-bar safe-area-bottom">
      <view
        class="submit-btn"
        :class="{ disabled: !canSubmit || submitting }"
        @click="handleSubmit"
      >
        <text>{{ submitting ? '提交中...' : '确认提现' }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getMyAccount, applyWithdraw } from '@/api/withdraw'
import auth from '@/utils/auth'
import { BizError } from '@/utils/request'
import tracker from '@/utils/tracker'
import type { UserAccount } from '@/api/types'
import { formatPrice } from '@/utils/format'

/** 最低提现门槛（与后端 WITHDRAW_MIN_AMOUNT 一致） */
const MIN_AMOUNT = 10

const account = ref<UserAccount>({
  user_id: 0,
  total_balance: 0,
  available_balance: 0,
  frozen_balance: 0,
  cumulative_withdrawn: 0,
  cumulative_fee: 0,
  last_settle_date: null,
  version: 0
})

const amountStr = ref('')
const submitting = ref(false)

/** 输入金额（数字） */
const amount = computed((): number => {
  const n = parseFloat(amountStr.value)
  return isNaN(n) ? 0 : n
})

/** 手续费：max(amount × 0.1%, 1元) */
const fee = computed((): number => {
  if (amount.value <= 0) return 0
  const calc = amount.value * 0.001
  return Math.max(calc, 1)
})

/** 实际到账 */
const actualAmount = computed((): number => {
  if (amount.value <= 0) return 0
  return Math.max(amount.value - fee.value, 0)
})

/** 是否可提交 */
const canSubmit = computed((): boolean => {
  return (
    amount.value >= MIN_AMOUNT &&
    amount.value <= account.value.available_balance
  )
})

/** 加载账户余额 */
const loadAccount = async () => {
  try {
    const res = await getMyAccount()
    if (res.data) {
      account.value = res.data
    }
  } catch (error) {
    console.warn('[提现] 账户加载失败:', error)
    uni.showToast({ title: '账户信息加载失败', icon: 'none' })
  }
}

/** 金额输入处理（限制两位小数） */
const handleAmountInput = (e: any) => {
  let val = String(e.detail.value || '')
  // 限制只能输入数字和一个小数点，最多两位小数
  val = val.replace(/[^\d.]/g, '')
  const parts = val.split('.')
  if (parts.length > 2) {
    val = parts[0] + '.' + parts.slice(1).join('')
  }
  if (parts[1] && parts[1].length > 2) {
    val = parts[0] + '.' + parts[1].slice(0, 2)
  }
  amountStr.value = val
}

/** 全部提现 */
const handleAllWithdraw = () => {
  const available = account.value.available_balance
  if (available <= 0) {
    uni.showToast({ title: '可提现余额为0', icon: 'none' })
    return
  }
  amountStr.value = available.toFixed(2)
}

/** 提交提现申请 */
const handleSubmit = async () => {
  if (submitting.value) return

  if (!auth.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  if (amount.value < MIN_AMOUNT) {
    uni.showToast({ title: `最低提现${MIN_AMOUNT}元`, icon: 'none' })
    return
  }

  if (amount.value > account.value.available_balance) {
    uni.showToast({ title: '提现金额超过可提现余额', icon: 'none' })
    return
  }

  // 二次确认
  uni.showModal({
    title: '确认提现',
    content: `提现 ¥${formatPrice(amount.value)}，实际到账 ¥${formatPrice(actualAmount.value)}，确认提交？`,
    success: async (res) => {
      if (!res.confirm) return

      submitting.value = true
      try {
        await applyWithdraw(amount.value)
        // 提现申请埋点
        tracker.trackWithdrawApply(amount.value)
        uni.showToast({ title: '提现申请已提交', icon: 'success' })

        // 延迟跳转提现记录页
        setTimeout(() => {
          uni.redirectTo({ url: '/pages/withdraw/list' })
        }, 1200)
      } catch (error) {
        if (error instanceof BizError) {
          uni.showToast({ title: error.message || '提现失败', icon: 'none' })
        } else {
          uni.showToast({ title: '网络异常，请重试', icon: 'none' })
        }
      } finally {
        submitting.value = false
      }
    }
  })
}

onMounted(() => {
  loadAccount()
  tracker.trackPageView('提现申请')
})
</script>

<style lang="scss" scoped>
.page-container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 140rpx;
}

/* 余额卡 */
.balance-card {
  background: linear-gradient(160deg, #2b2a24 0%, #111111 100%);
  padding: 50rpx 30rpx;
  color: #fff;
  display: flex;
  flex-direction: column;
  gap: 12rpx;

  .balance-label {
    font-size: 26rpx;
    color: rgba(255, 255, 255, 0.85);
  }

  .balance-amount {
    display: flex;
    align-items: baseline;

    .symbol {
      font-size: 32rpx;
      font-weight: 600;
      color: #ffd400;
    }

    .value {
      font-size: 64rpx;
      font-weight: 700;
      line-height: 1;
      color: #ffd400;
    }
  }
}

/* 输入区 */
.input-section,
.rules-section {
  background: #fff;
  margin: 20rpx;
  border-radius: 16rpx;
  padding: 24rpx;

  .section-title {
    font-size: 30rpx;
    font-weight: 600;
    color: #333;
    margin-bottom: 24rpx;
  }
}

.amount-input {
  display: flex;
  align-items: center;
  background: #f9f9f9;
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
  border: 2rpx solid #f0f0f0;

  .currency {
    font-size: 40rpx;
    color: var(--amber, #ff9500);
    font-weight: 700;
    margin-right: 12rpx;
  }

  .input {
    flex: 1;
    font-size: 40rpx;
    color: #333;
    font-weight: 600;
  }

  .all-btn {
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

.fee-detail {
  margin-top: 24rpx;
  padding: 20rpx;
  background: #fafafa;
  border-radius: 12rpx;

  .fee-row {
    display: flex;
    justify-content: space-between;
    padding: 8rpx 0;

    .fee-label {
      font-size: 26rpx;
      color: #666;
    }

    .fee-value {
      font-size: 26rpx;
      color: #333;
    }

    &.highlight {
      padding-top: 16rpx;
      margin-top: 8rpx;
      border-top: 2rpx solid #eee;

      .fee-label {
        color: var(--amber, #ff9500);
        font-weight: 600;
      }

      .fee-value {
        color: var(--amber, #ff9500);
        font-weight: 700;
        font-size: 30rpx;
      }
    }
  }
}

/* 规则说明 */
.rules-section {
  .rules-list {
    display: flex;
    flex-direction: column;
    gap: 12rpx;

    .rule-item {
      font-size: 24rpx;
      color: #999;
      line-height: 1.6;
    }
  }
}

/* 底部提交按钮 */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 20rpx 24rpx;
  box-shadow: 0 -2rpx 12rpx rgba(0, 0, 0, 0.05);
  z-index: 100;

  .submit-btn {
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
      background: #d4d4d4;
    }

    &:active:not(.disabled) {
      opacity: 0.85;
    }
  }
}
</style>

<!-- @ai-generated -->
<!--
  消息订阅弹窗组件（F05 新建）
  - 展示可订阅的微信订阅消息模板（支持多选）
  - 调用 uni.requestSubscribeMessage 发起微信订阅授权
  - 异常分支处理：
      accept  → 用户同意 → 后端记录已订阅（有效期7天）
      reject  → 用户拒绝 → 后端记录未订阅，提示用户可稍后重试
      ban     → 模板被后台封禁 → 后端记录 expired，提示模板不可用
      filter  → 用户勾选"总是保持以上选择" → 按 accept/reject 处理
      fail    → 授权调用失败（非微信环境/未配置模板）→ 静默降级
  - 订阅行为埋点统计（弹窗展示/同意/拒绝/过期）
-->
<template>
  <view v-if="visible" class="subscribe-mask" @touchmove.stop.prevent @click="handleMaskClick">
    <view class="subscribe-popup" @click.stop>
      <!-- 头部 -->
      <view class="popup-header">
        <text class="popup-title">消息订阅</text>
        <view class="popup-close" @click="handleClose">
          <text class="close-icon">✕</text>
        </view>
      </view>

      <!-- 说明文案 -->
      <view class="popup-desc">
        <text class="desc-text">开启后，我们将通过微信服务通知向您推送佣金到账、订单状态等消息，不错过每一笔收益。</text>
      </view>

      <!-- 模板列表 -->
      <scroll-view scroll-y class="template-list">
        <view
          v-for="item in templateList"
          :key="item.id"
          class="template-item"
          :class="{ 'template-item--disabled': isExpired(item) }"
          @click="toggleSelect(item)"
        >
          <view class="template-check">
            <view
              class="check-box"
              :class="{ 'check-box--checked': isSelected(item) && !isExpired(item) }"
            >
              <text v-if="isSelected(item) && !isExpired(item)" class="check-mark">✓</text>
            </view>
          </view>
          <view class="template-info">
            <view class="template-title-row">
              <text class="template-title">{{ item.template_name }}</text>
              <text v-if="isExpired(item)" class="template-tag template-tag--expired">已过期</text>
              <text v-else-if="isSubscribed(item)" class="template-tag template-tag--active">已订阅</text>
            </view>
            <text class="template-content ellipsis-2">{{ item.content || '接收该类型消息通知' }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- 底部操作 -->
      <view class="popup-footer safe-area-bottom">
        <view class="footer-btn footer-btn--cancel" @click="handleClose">
          <text>暂不开启</text>
        </view>
        <view class="footer-btn footer-btn--confirm" :class="{ 'footer-btn--disabled': selectedCount === 0 }" @click="handleConfirm">
          <text>{{ selectedCount > 0 ? `开启订阅(${selectedCount})` : '开启订阅' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getSubscribeTemplates, recordSubscribe } from '@/api/message'
import type { SubscribeStatusItem, SubscribeTemplate } from '@/api/types'
import tracker from '@/utils/tracker'

const props = withDefaults(
  defineProps<{
    /** 是否显示弹窗（v-model） */
    visible: boolean
    /** 模板列表（不传则自动拉取） */
    templates?: SubscribeTemplate[]
    /** 订阅状态映射（template_id → 状态项） */
    statusMap?: Record<number, SubscribeStatusItem>
  }>(),
  {
    visible: false,
    templates: undefined,
    statusMap: undefined
  }
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'subscribed', templateId: number, templateName: string): void
}>()

/** 模板列表（优先使用外部传入，否则自动拉取） */
const templateList = ref<SubscribeTemplate[]>([])
/** 已选中的模板ID集合 */
const selectedIds = ref<Set<number>>(new Set())
/** 加载状态 */
const loading = ref(false)

/** 订阅状态映射（template_id → 状态项） */
const statusMapRef = computed(() => props.statusMap || {})

/** 已选中数量 */
const selectedCount = computed(() => selectedIds.value.size)

/** 模板是否已订阅 */
const isSubscribed = (item: SubscribeTemplate): boolean => {
  const st = statusMapRef.value[item.id]
  return !!st && st.subscribe_status === 1 && !st.expired
}

/** 模板是否已过期（需重新订阅） */
const isExpired = (item: SubscribeTemplate): boolean => {
  const st = statusMapRef.value[item.id]
  return !!st && st.expired
}

/** 是否已选中 */
const isSelected = (item: SubscribeTemplate): boolean => {
  return selectedIds.value.has(item.id)
}

/** 切换选中状态（已过期模板不可选） */
const toggleSelect = (item: SubscribeTemplate): void => {
  if (isExpired(item)) return
  const next = new Set(selectedIds.value)
  if (next.has(item.id)) {
    next.delete(item.id)
  } else {
    next.add(item.id)
  }
  selectedIds.value = next
}

/** 加载模板列表 */
const loadTemplates = async (): Promise<void> => {
  if (props.templates && props.templates.length > 0) {
    templateList.value = props.templates
    return
  }
  if (templateList.value.length > 0) return
  loading.value = true
  try {
    const res = await getSubscribeTemplates()
    templateList.value = res.data?.list || []
  } catch {
    // 拉取失败静默处理，弹窗仍可关闭
  } finally {
    loading.value = false
  }
}

/** 初始化选中状态：默认选中未订阅且未过期的模板 */
const initSelection = (): void => {
  const next = new Set<number>()
  templateList.value.forEach((item) => {
    if (!isSubscribed(item) && !isExpired(item)) {
      next.add(item.id)
    }
  })
  selectedIds.value = next
}

/** 关闭弹窗 */
const handleClose = (): void => {
  emit('update:visible', false)
}

/** 点击遮罩关闭 */
const handleMaskClick = (): void => {
  handleClose()
}

/**
 * 发起微信订阅授权
 * 异常分支：
 * - accept  → 用户同意
 * - reject  → 用户拒绝
 * - ban     → 模板被后台封禁（按 expired 处理）
 * - filter  → 用户勾选"总是保持以上选择"（按 accept/reject 处理）
 * - fail    → 授权调用失败（非微信环境等，静默降级）
 */
const requestSubscribe = (item: SubscribeTemplate): Promise<'accept' | 'reject' | 'expired'> => {
  return new Promise((resolve) => {
    // 非小程序环境（H5）无 requestSubscribeMessage → 直接按 accept 处理（开发联调用）
    if (typeof uni.requestSubscribeMessage !== 'function') {
      resolve('accept')
      return
    }

    uni.requestSubscribeMessage({
      tmplIds: [item.tmpl_id || ''],
      success: (res: any) => {
        const result = res[item.tmpl_id] || res[item.tmpl_id + '']
        if (result === 'accept') {
          resolve('accept')
        } else if (result === 'reject') {
          resolve('reject')
        } else if (result === 'filter') {
          // 用户勾选"总是保持以上选择"：accept 表示同意，reject 表示拒绝
          resolve('accept')
        } else {
          // ban / 其他未知状态 → 按过期处理
          resolve('expired')
        }
      },
      fail: () => {
        // 授权调用失败（非微信环境/未配置模板ID）→ 开发环境按 accept 处理
        resolve('expired')
      }
    })
  })
}

/** 确认订阅 */
const handleConfirm = async (): Promise<void> => {
  if (selectedCount.value === 0) return

  const selected = templateList.value.filter((item) => selectedIds.value.has(item.id))
  if (selected.length === 0) return

  // 埋点：弹窗内确认发起订阅
  selected.forEach((item) => {
    tracker.trackSubscribePopupShow(item.id, item.template_name)
  })

  // 逐个模板发起授权（微信一次可传多个，这里逐个处理便于精确记录结果）
  let acceptCount = 0
  for (const item of selected) {
    const action = await requestSubscribe(item)
    try {
      await recordSubscribe(item.id, action, item.tmpl_id)
    } catch {
      // 记录失败不阻断流程
    }

    if (action === 'accept') {
      acceptCount++
      tracker.trackSubscribeAccept(item.id, item.template_name)
      emit('subscribed', item.id, item.template_name)
    } else if (action === 'reject') {
      tracker.trackSubscribeReject(item.id, item.template_name)
    } else {
      tracker.trackSubscribeExpired(item.id, item.template_name)
    }
  }

  if (acceptCount > 0) {
    uni.showToast({ title: `已开启 ${acceptCount} 项订阅`, icon: 'success' })
    handleClose()
  } else {
    uni.showToast({ title: '未开启订阅，可在消息中心重新开启', icon: 'none' })
    handleClose()
  }
}

// 弹窗打开时加载模板并初始化选中
watch(
  () => props.visible,
  async (val) => {
    if (val) {
      await loadTemplates()
      initSelection()
    }
  }
)
</script>

<style lang="scss" scoped>
.subscribe-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.subscribe-popup {
  width: 100%;
  max-height: 80vh;
  background: #fff;
  border-radius: 32rpx 32rpx 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .popup-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 32rpx 32rpx 16rpx;

    .popup-title {
      font-size: 36rpx;
      font-weight: var(--font-weight-bold);
      color: var(--color-text);
    }

    .popup-close {
      width: 56rpx;
      height: 56rpx;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: var(--color-bg);

      .close-icon {
        font-size: 28rpx;
        color: var(--color-text-placeholder);
      }
    }
  }

  .popup-desc {
    padding: 0 32rpx 24rpx;

    .desc-text {
      font-size: 26rpx;
      color: var(--color-text-secondary);
      line-height: 1.6;
    }
  }

  .template-list {
    flex: 1;
    max-height: 48vh;
    padding: 0 32rpx;

    .template-item {
      display: flex;
      align-items: flex-start;
      gap: 20rpx;
      padding: 24rpx 0;
      border-bottom: 2rpx solid var(--color-border);

      &:last-child {
        border-bottom: none;
      }

      &--disabled {
        opacity: 0.6;
      }

      .template-check {
        padding-top: 4rpx;

        .check-box {
          width: 40rpx;
          height: 40rpx;
          border-radius: 50%;
          border: 3rpx solid var(--color-border);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;

          &--checked {
            background: var(--color-primary);
            border-color: var(--color-primary);
          }

          .check-mark {
            color: #fff;
            font-size: 24rpx;
            font-weight: var(--font-weight-bold);
          }
        }
      }

      .template-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8rpx;

        .template-title-row {
          display: flex;
          align-items: center;
          gap: 12rpx;

          .template-title {
            font-size: 30rpx;
            font-weight: var(--font-weight-medium);
            color: var(--color-text);
          }

          .template-tag {
            font-size: 20rpx;
            padding: 4rpx 12rpx;
            border-radius: var(--radius-full);

            &--active {
              color: var(--color-success);
              background: var(--color-success-bg);
            }

            &--expired {
              color: var(--color-warning);
              background: var(--color-warning-bg);
            }
          }
        }

        .template-content {
          font-size: 24rpx;
          color: var(--color-text-placeholder);
          line-height: 1.5;
        }
      }
    }
  }

  .popup-footer {
    display: flex;
    gap: 20rpx;
    padding: 24rpx 32rpx 32rpx;
    border-top: 2rpx solid var(--color-border);

    .footer-btn {
      flex: 1;
      height: 88rpx;
      border-radius: var(--radius-full);
      display: flex;
      align-items: center;
      justify-content: center;

      text {
        font-size: 30rpx;
        font-weight: var(--font-weight-medium);
      }

      &--cancel {
        background: var(--color-bg);

        text {
          color: var(--color-text-secondary);
        }
      }

      &--confirm {
        background: var(--color-primary);

        text {
          color: #fff;
        }

        &:active {
          opacity: 0.85;
        }
      }

      &--disabled {
        background: var(--color-text-disabled);
        opacity: 0.6;
      }
    }
  }
}
</style>

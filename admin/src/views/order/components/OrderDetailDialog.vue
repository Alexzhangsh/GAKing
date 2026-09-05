<!-- @ai-generated -->
<!--
  订单详情弹窗（含佣金流水）
  对接：GET /api/v1/cps/order/:orderId
-->
<template>
  <el-dialog
    :model-value="visible"
    title="订单详情"
    width="880px"
    top="5vh"
    append-to-body
    destroy-on-close
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div v-loading="loading" class="order-detail">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="3" border size="small" class="base-desc">
          <el-descriptions-item label="订单ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="外部订单号">{{ detail.out_order_no }}</el-descriptions-item>
          <el-descriptions-item label="内部订单号">{{ detail.internal_order_no }}</el-descriptions-item>
          <el-descriptions-item label="用户ID">{{ detail.user_id }}</el-descriptions-item>
          <el-descriptions-item label="渠道">
            <el-tag v-if="ChannelMeta[detail.channel_code]" size="small" :type="ChannelMeta[detail.channel_code].type as any">
              {{ ChannelMeta[detail.channel_code].label }}
            </el-tag>
            <span v-else>{{ detail.channel_code }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <StatusTag :status="detail.order_status" :map="orderStatusMap" />
          </el-descriptions-item>
          <el-descriptions-item label="支付金额">¥{{ detail.pay_amount }}</el-descriptions-item>
          <el-descriptions-item label="总佣金">¥{{ detail.total_commission }}</el-descriptions-item>
          <el-descriptions-item label="用户/平台佣金">
            <span class="commission-split">
              用户 ¥{{ detail.user_commission }} / 平台 ¥{{ detail.platform_commission }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="付款时间">{{ detail.pay_time || '--' }}</el-descriptions-item>
          <el-descriptions-item label="结算时间">{{ detail.settle_time || '--' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.create_time || '--' }}</el-descriptions-item>
          <el-descriptions-item label="商品" :span="3">
            <div class="goods-cell">
              <el-image
                v-if="detail.goods_img"
                :src="detail.goods_img"
                fit="cover"
                style="width: 48px; height: 48px; border-radius: 4px"
                lazy
              />
              <span class="goods-title">{{ detail.goods_title }}</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 佣金流水 -->
        <el-divider content-position="left">佣金明细</el-divider>
        <el-table :data="detail.commission_flows" size="small" stripe>
          <el-table-column prop="id" label="流水ID" width="90" />
          <el-table-column prop="flow_type" label="类型" width="120" />
          <el-table-column prop="flow_amount" label="金额" width="110" align="right">
            <template #default="{ row }">¥{{ row.flow_amount }}</template>
          </el-table-column>
          <el-table-column prop="transfer_status" label="状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="transferStatusTag(row.transfer_status)" effect="plain">
                {{ row.transfer_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="settle_time" label="结算时间" width="170" />
          <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
          <el-table-column prop="create_time" label="创建时间" width="170" />
          <template #empty>
            <el-empty description="暂无佣金流水" :image-size="60" />
          </template>
        </el-table>
      </template>

      <el-empty v-else-if="!loading" description="暂无数据" :image-size="60" />
    </div>

    <template #footer>
      <el-button @click="emit('update:visible', false)">关闭</el-button>
      <el-button
        v-permission="'order:update'"
        type="primary"
        :disabled="!canManualSettle"
        :loading="settleLoading"
        @click="handleManualSettle"
      >
        手动结算
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, watch, computed } from 'vue'
import {
  ElDialog,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElTable,
  ElTableColumn,
  ElEmpty,
  ElButton,
  ElTag,
  ElMessage,
  ElMessageBox,
} from 'element-plus'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import {
  orderApi,
  type OrderDetail,
  OrderStatusMeta,
  ChannelMeta,
} from '@/api/order'

const props = defineProps<{
  visible: boolean
  orderId: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'manual-settle'): void
}>()

const loading = ref(false)
const settleLoading = ref(false)
const detail = ref<OrderDetail | null>(null)

const orderStatusMap: StatusMap = Object.fromEntries(
  Object.entries(OrderStatusMeta).map(([k, v]) => [k, { text: v.label, type: v.type }])
)

function transferStatusTag(status: string): 'info' | 'warning' | 'success' | 'danger' {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
    PENDING: 'warning',
    SETTLING: 'info',
    SUCCESS: 'success',
    FAILED: 'danger',
  }
  return map[status] || 'info'
}

const canManualSettle = computed(() => {
  const s = detail.value?.order_status
  return s === 30 // PAID 状态允许手动结算
})

async function loadDetail() {
  if (!props.orderId) return
  loading.value = true
  try {
    detail.value = await orderApi.getDetail(props.orderId)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) loadDetail()
    else detail.value = null
  }
)

watch(
  () => props.orderId,
  () => {
    if (props.visible) loadDetail()
  }
)

async function handleManualSettle() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `确认手动结算订单「${detail.value.out_order_no}」？`,
      '手动结算确认',
      { type: 'warning' }
    )
    settleLoading.value = true
    await orderApi.updateStatus({ order_id: detail.value!.id, target_status: 40 })
    ElMessage.success('结算成功')
    emit('manual-settle')
    loadDetail()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  } finally {
    settleLoading.value = false
  }
}
</script>

<style scoped>
.order-detail {
  min-height: 240px;
}

.base-desc :deep(.el-descriptions__label) {
  width: 110px;
}

.goods-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.goods-title {
  color: #303133;
  font-weight: 300;
}

.commission-split {
  color: #606266;
  font-weight: 300;
}
</style>

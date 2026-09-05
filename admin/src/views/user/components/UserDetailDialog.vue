<!-- @ai-generated -->
<!--
  用户详情弹窗（含金角币/佣金流水）
  对接：GET /api/v1/admin/user/:userId
-->
<template>
  <el-dialog
    :model-value="visible"
    title="用户详情"
    width="920px"
    top="5vh"
    append-to-body
    destroy-on-close
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div v-loading="loading" class="user-detail">
      <template v-if="detail">
        <!-- 基础信息 -->
        <el-descriptions :column="4" border size="small" class="base-desc">
          <el-descriptions-item label="用户ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.nickname }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="detail.user_type === 'VIP' ? 'warning' : 'info'" size="small" effect="plain">
              {{ detail.user_type === 'VIP' ? '付费会员' : '普通用户' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag
              :status="detail.status"
              :map="userStatusMap"
            />
          </el-descriptions-item>
          <el-descriptions-item label="金角币">
            <span class="coin">{{ detail.gold_coin_balance }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="佣金账户">
            <span class="commission">¥{{ detail.commission_balance }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="累计提现">¥{{ detail.total_withdrawn }}</el-descriptions-item>
          <el-descriptions-item label="订单数">{{ detail.order_count }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ detail.register_time || '--' }}</el-descriptions-item>
          <el-descriptions-item label="最近登录" :span="2">
            {{ detail.last_login_time || '--' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- Tab 切换流水 -->
        <el-tabs v-model="activeTab" class="flow-tabs" @tab-change="handleTabChange">
          <el-tab-pane label="金角币流水" name="gold">
            <el-table :data="detail.gold_coin_flows" size="small" stripe max-height="360">
              <el-table-column prop="id" label="流水ID" width="90" />
              <el-table-column prop="flow_type" label="类型" width="120" />
              <el-table-column prop="amount" label="变动" width="110" align="right">
                <template #default="{ row }">
                  <span :style="{ color: Number(row.amount) >= 0 ? '#67c23a' : '#f56c6c' }">
                    {{ Number(row.amount) >= 0 ? '+' : '' }}{{ row.amount }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="balance_after" label="变动后余额" width="120" align="right" />
              <el-table-column prop="related_order_id" label="关联订单" width="110" align="right" />
              <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
              <el-table-column prop="create_time" label="时间" width="170" />
              <template #empty>
                <el-empty description="暂无金角币流水" :image-size="60" />
              </template>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="佣金流水" name="commission">
            <el-table :data="detail.commission_flows" size="small" stripe max-height="360">
              <el-table-column prop="id" label="流水ID" width="90" />
              <el-table-column prop="flow_type" label="类型" width="140" />
              <el-table-column prop="amount" label="变动金额" width="120" align="right">
                <template #default="{ row }">
                  <span :style="{ color: Number(row.amount) >= 0 ? '#67c23a' : '#f56c6c' }">
                    {{ Number(row.amount) >= 0 ? '+' : '' }}{{ row.amount }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="settle_status" label="结算状态" width="110" align="center">
                <template #default="{ row }">
                  <el-tag
                    size="small"
                    :type="settleStatusTag(row.settle_status)"
                    effect="plain"
                  >
                    {{ row.settle_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="balance_after" label="变动后余额" width="120" align="right" />
              <el-table-column prop="related_order_id" label="关联订单" width="110" align="right" />
              <el-table-column prop="create_time" label="时间" width="170" />
              <template #empty>
                <el-empty description="暂无佣金流水" :image-size="60" />
              </template>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>

      <el-empty v-else-if="!loading" description="暂无数据" :image-size="60" />
    </div>

    <template #footer>
      <el-button @click="emit('update:visible', false)">关闭</el-button>
      <el-button :loading="refreshLoading" @click="loadDetail">刷新</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, watch } from 'vue'
import {
  ElDialog,
  ElDescriptions,
  ElDescriptionsItem,
  ElTabs,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElEmpty,
  ElButton,
  ElTag,
} from 'element-plus'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import { userApi, type UserDetail } from '@/api/user'

const props = defineProps<{
  visible: boolean
  userId: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'refresh'): void
}>()

const loading = ref(false)
const refreshLoading = ref(false)
const detail = ref<UserDetail | null>(null)
const activeTab = ref<'gold' | 'commission'>('gold')

const userStatusMap: StatusMap = {
  NORMAL: { text: '正常', type: 'success' },
  FROZEN: { text: '已冻结', type: 'danger' },
}

function settleStatusTag(status: string): 'info' | 'warning' | 'success' | 'danger' {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
    PENDING: 'warning',
    SETTLING: 'info',
    SUCCESS: 'success',
    FAILED: 'danger',
  }
  return map[status] || 'info'
}

async function loadDetail() {
  if (!props.userId) return
  loading.value = true
  try {
    detail.value = await userApi.getDetail(props.userId)
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
  () => props.userId,
  () => {
    if (props.visible) loadDetail()
  }
)

function handleTabChange() {
  // 预留：可按需懒加载
}
</script>

<style scoped>
.user-detail {
  min-height: 240px;
}

.base-desc :deep(.el-descriptions__label) {
  width: 110px;
}

.coin {
  color: #e6a23c;
  font-weight: 500;
}

.commission {
  color: #409eff;
  font-weight: 300;
}

.flow-tabs {
  margin-top: 16px;
}
</style>

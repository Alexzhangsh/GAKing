<!-- @ai-generated -->
<!--
  提现审核列表页
  对接：GET /api/v1/admin/withdraw/applies
  权限：withdraw:manage
  功能：提现列表、审核通过/驳回、打款完成、失败回滚
-->
<template>
  <div class="withdraw-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="用户ID">
          <el-input v-model="filter.user_id" placeholder="用户ID" clearable style="width: 160px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="提现状态">
          <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option v-for="(m, s) in WithdrawStatusMeta" :key="s" :label="m.label" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <ProTable
        :data="tableData"
        :columns="columns"
        :loading="loading"
        :pagination="{ page: filter.page, page_size: filter.page_size, total }"
        row-key="id"
        show-index
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
      >
        <template #col-status="{ row }">
          <StatusTag :status="row.status" :map="withdrawStatusMap" />
        </template>

        <template #col-apply_amount="{ row }">
          <span class="amount">¥{{ row.apply_amount }}</span>
        </template>
        <template #col-fee="{ row }">¥{{ row.fee }}</template>
        <template #col-actual_amount="{ row }">
          <span class="amount primary">¥{{ row.actual_amount }}</span>
        </template>

        <template #col-bank_name="{ row }">
          {{ row.bank_name }}
          <span v-if="row.bank_card_no" class="bank-card">
            · · · {{ row.bank_card_no.slice(-4) }}
          </span>
        </template>

        <template #col-action="{ row }">
          <template v-if="row.status === 'PENDING'">
            <el-button
              v-permission="'withdraw:review'"
              size="small"
              link
              type="success"
              @click="handleApprove(row)"
            >
              通过
            </el-button>
            <el-button
              v-permission="'withdraw:review'"
              size="small"
              link
              type="danger"
              @click="handleReject(row)"
            >
              驳回
            </el-button>
          </template>
          <template v-else-if="row.status === 'APPROVED' || row.status === 'PROCESSING'">
            <el-button
              v-permission="'withdraw:complete'"
              size="small"
              link
              type="primary"
              @click="handleComplete(row)"
            >
              标记打款
            </el-button>
            <el-button
              v-permission="'withdraw:fail'"
              size="small"
              link
              type="danger"
              @click="handleFail(row)"
            >
              打款失败
            </el-button>
          </template>
          <template v-else-if="row.status === 'SUCCESS'">
            <span class="text-success">已到账</span>
          </template>
          <template v-else>
            <span class="text-danger">已驳回</span>
          </template>
        </template>
      </ProTable>
    </el-card>

    <!-- 操作弹窗 -->
    <el-dialog
      v-model="opDialogVisible"
      :title="opDialogTitle"
      width="460px"
      append-to-body
      destroy-on-close
    >
      <el-form v-if="opType === 'approve'" :model="opForm" label-width="90px">
        <el-form-item label="审核备注">
          <el-input v-model="opForm.review_remark" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <el-form v-else-if="opType === 'reject'" :model="opForm" label-width="90px">
        <el-form-item label="驳回原因" required>
          <el-input v-model="opForm.reject_reason" type="textarea" :rows="3" placeholder="请填写驳回原因" />
        </el-form-item>
      </el-form>
      <el-form v-else-if="opType === 'complete'" :model="opForm" label-width="110px">
        <el-form-item label="打款批次号" required>
          <el-input v-model="opForm.transfer_batch_id" placeholder="请输入打款批次号" />
        </el-form-item>
      </el-form>
      <el-form v-else-if="opType === 'fail'" :model="opForm" label-width="90px">
        <el-form-item label="失败原因" required>
          <el-input v-model="opForm.reason" type="textarea" :rows="3" placeholder="请填写失败原因" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="opDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="opLoading" @click="submitOp">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, onMounted, computed } from 'vue'
import {
  ElCard,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElMessage,
  ElDialog,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import {
  withdrawApi,
  WithdrawStatusMeta,
  type WithdrawApplyItem,
  type WithdrawListParams,
  type WithdrawApproveRequest,
  type WithdrawRejectRequest,
  type WithdrawCompleteRequest,
  type WithdrawFailRequest,
} from '@/api/withdraw'

defineOptions({ name: 'WithdrawList' })

const filter = reactive<WithdrawListParams & { keyword?: string }>({
  page: 1,
  page_size: 20,
  user_id: undefined,
  status: undefined,
})

const tableData = ref<WithdrawApplyItem[]>([])
const total = ref(0)
const loading = ref(false)

const withdrawStatusMap: StatusMap = Object.fromEntries(
  Object.entries(WithdrawStatusMeta).map(([k, v]) => [k, { text: v.label, type: v.type }])
)

const columns: ProTableColumn[] = [
  { prop: 'id', label: '申请ID', width: 90 },
  { prop: 'user_id', label: '用户ID', width: 100, align: 'right' },
  { prop: 'apply_amount', label: '申请金额', width: 120, align: 'right' },
  { prop: 'fee', label: '手续费', width: 100, align: 'right' },
  { prop: 'actual_amount', label: '实际到账', width: 120, align: 'right' },
  { prop: 'status', label: '状态', width: 100, align: 'center' },
  { prop: 'bank_name', label: '收款账户', minWidth: 180 },
  { prop: 'apply_time', label: '申请时间', width: 170 },
  { prop: 'review_time', label: '审核时间', width: 170 },
  { prop: 'fail_time', label: '失败时间', width: 170 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await withdrawApi.list({
      user_id: filter.user_id ? Number(filter.user_id) : undefined,
      status: filter.status,
      page: filter.page,
      page_size: filter.page_size,
    })
    tableData.value = res.list || []
    total.value = res.total || 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filter.page = 1
  loadData()
}
function handleReset() {
  filter.user_id = undefined
  filter.status = undefined
  filter.page = 1
  loadData()
}
function handlePageChange(page: number) {
  filter.page = page
  loadData()
}
function handleSizeChange(size: number) {
  filter.page_size = size
  filter.page = 1
  loadData()
}

// ── 操作弹窗 ──────────────
type OpType = 'approve' | 'reject' | 'complete' | 'fail' | ''

const opDialogVisible = ref(false)
const opType = ref<OpType>('')
const opTarget = ref<WithdrawApplyItem | null>(null)
const opLoading = ref(false)

const opDialogTitle = computed(() => {
  const map: Record<string, string> = {
    approve: '审核通过',
    reject: '驳回申请',
    complete: '标记打款完成',
    fail: '打款失败回滚',
  }
  return opType.value ? map[opType.value] || '操作' : '操作'
})

const opForm = reactive<
  WithdrawApproveRequest &
    WithdrawRejectRequest &
    WithdrawCompleteRequest &
    WithdrawFailRequest
>({
  review_remark: '',
  reject_reason: '',
  transfer_batch_id: '',
  reason: '',
})

function openOp(type: OpType, row: WithdrawApplyItem) {
  opType.value = type
  opTarget.value = row
  // 重置表单
  opForm.review_remark = ''
  opForm.reject_reason = ''
  opForm.transfer_batch_id = ''
  opForm.reason = ''
  opDialogVisible.value = true
}

function handleApprove(row: WithdrawApplyItem) {
  openOp('approve', row)
}
function handleReject(row: WithdrawApplyItem) {
  openOp('reject', row)
}
function handleComplete(row: WithdrawApplyItem) {
  openOp('complete', row)
}
function handleFail(row: WithdrawApplyItem) {
  openOp('fail', row)
}

async function submitOp() {
  if (!opTarget.value || !opType.value) return
  const row = opTarget.value
  opLoading.value = true
  try {
    switch (opType.value) {
      case 'approve':
        await withdrawApi.approve(row.id, { review_remark: opForm.review_remark })
        ElMessage.success('审核通过')
        break
      case 'reject':
        if (!opForm.reject_reason) {
          ElMessage.warning('请填写驳回原因')
          opLoading.value = false
          return
        }
        await withdrawApi.reject(row.id, { reject_reason: opForm.reject_reason })
        ElMessage.success('已驳回')
        break
      case 'complete':
        if (!opForm.transfer_batch_id) {
          ElMessage.warning('请填写打款批次号')
          opLoading.value = false
          return
        }
        await withdrawApi.complete(row.id, {
          transfer_batch_id: opForm.transfer_batch_id,
        })
        ElMessage.success('已标记打款完成')
        break
      case 'fail':
        if (!opForm.reason) {
          ElMessage.warning('请填写失败原因')
          opLoading.value = false
          return
        }
        await withdrawApi.fail(row.id, { reason: opForm.reason })
        ElMessage.success('已标记打款失败并回滚')
        break
    }
    opDialogVisible.value = false
    loadData()
  } catch {
    // 拦截器已提示
  } finally {
    opLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.withdraw-list-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 12px;
}

.table-card :deep(.el-card__body) {
  padding: 16px;
}

.amount {
  color: #303133;
  font-weight: 300;
}

.amount.primary {
  color: #409eff;
  font-weight: 500;
}

.bank-card {
  color: #909399;
  font-weight: 300;
  font-size: 12px;
}

.text-success {
  color: #67c23a;
  font-weight: 300;
}

.text-danger {
  color: #f56c6c;
  font-weight: 300;
}
</style>

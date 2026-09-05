<!-- @ai-generated -->
<!--
  异常订单列表页
  对接 B05-4 异常订单接口：GET /api/v1/admin/abnormal-orders/list
  权限：order:manage
  功能：多条件筛选、复核状态标签、复核操作、统计概览
-->
<template>
  <div class="abnormal-order-page">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">异常订单总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-pending">
          <div class="stat-value">{{ stats.pending }}</div>
          <div class="stat-label">待审核</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-reviewed">
          <div class="stat-value">{{ stats.reviewed }}</div>
          <div class="stat-label">已复核</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-ignored">
          <div class="stat-value">{{ stats.ignored }}</div>
          <div class="stat-label">已忽略</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="filter.keyword"
            placeholder="订单号/商品标题"
            clearable
            style="width: 240px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="filter.channel_code" placeholder="全部渠道" clearable style="width: 140px">
            <el-option v-for="(m, c) in ChannelMeta" :key="c" :label="m.label" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="复核状态">
          <el-select v-model="filter.review_status" placeholder="全部状态" clearable style="width: 140px">
            <el-option
              v-for="(m, s) in ReviewStatusMeta"
              :key="s"
              :label="m.label"
              :value="s"
            />
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
        <template #col-channel_code="{ row }">
          <el-tag v-if="ChannelMeta[row.channel_code]" size="small" :type="ChannelMeta[row.channel_code].type as any" effect="plain">
            {{ ChannelMeta[row.channel_code].label }}
          </el-tag>
          <span v-else>{{ row.channel_code }}</span>
        </template>

        <template #col-review_status="{ row }">
          <StatusTag :status="row.review_status" :map="reviewStatusMap" />
        </template>

        <template #col-pay_amount="{ row }">¥{{ row.pay_amount }}</template>
        <template #col-total_commission="{ row }">¥{{ row.total_commission }}</template>

        <template #col-abnormal_reason="{ row }">
          <el-tooltip :content="row.abnormal_reason" placement="top" :show-after="300">
            <span class="reason-text">{{ row.abnormal_reason }}</span>
          </el-tooltip>
        </template>

        <template #col-action="{ row }">
          <el-button
            v-if="row.review_status === 'PENDING'"
            size="small"
            link
            type="primary"
            @click="handleReview(row)"
          >
            复核
          </el-button>
          <el-button
            v-else
            size="small"
            link
            type="warning"
            @click="handleEdit(row)"
          >
            编辑
          </el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 复核弹窗 -->
    <el-dialog
      v-model="reviewDialogVisible"
      title="异常订单复核"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="reviewFormRef" :model="reviewForm" :rules="reviewRules" label-width="80px">
        <el-form-item label="订单号">
          <el-input :model-value="currentRow?.out_order_no" disabled />
        </el-form-item>
        <el-form-item label="商品标题">
          <el-input :model-value="currentRow?.goods_title" disabled />
        </el-form-item>
        <el-form-item label="异常原因">
          <el-input :model-value="currentRow?.abnormal_reason" type="textarea" disabled :rows="2" />
        </el-form-item>
        <el-form-item label="匹配用户ID">
          <el-input :model-value="currentRow?.matched_user_id" disabled />
        </el-form-item>
        <el-form-item label="指定归属" prop="assigned_user_id">
          <el-input-number
            v-model="reviewForm.assigned_user_id"
            :min="0"
            :max="999999999"
            placeholder="输入归属用户ID，0=不指定"
            style="width: 100%"
          />
          <div class="form-tip">输入 >0 的用户ID将手动指定该订单归属</div>
        </el-form-item>
        <el-form-item label="复核结果" prop="review_status">
          <el-radio-group v-model="reviewForm.review_status">
            <el-radio value="REVIEWED">已复核（确认无法归属）</el-radio>
            <el-radio value="IGNORED">已忽略（无需关注）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="复核备注" prop="review_remark">
          <el-input
            v-model="reviewForm.review_remark"
            type="textarea"
            placeholder="请输入复核备注"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewLoading" @click="handleSubmitReview">
          确认提交
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗（复核后修改归属/备注） -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑异常订单归属"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="订单号">
          <el-input :model-value="editRow?.out_order_no" disabled />
        </el-form-item>
        <el-form-item label="商品标题">
          <el-input :model-value="editRow?.goods_title" disabled />
        </el-form-item>
        <el-form-item label="复核状态">
          <StatusTag :status="editRow?.review_status || ''" :map="reviewStatusMap" />
        </el-form-item>
        <el-form-item label="指定归属" prop="assigned_user_id">
          <el-input-number
            v-model="editForm.assigned_user_id"
            :min="0"
            :max="999999999"
            placeholder="输入归属用户ID"
            style="width: 100%"
          />
          <div class="form-tip">输入 >0 的用户ID将手动指定该订单归属</div>
        </el-form-item>
        <el-form-item label="复核备注" prop="review_remark">
          <el-input
            v-model="editForm.review_remark"
            type="textarea"
            placeholder="请输入复核备注"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleSubmitEdit">
          保存修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, onMounted } from 'vue'
import {
  ElCard,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElTag,
  ElTooltip,
  ElDialog,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElCol,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import {
  abnormalOrderApi,
  ReviewStatusMeta,
  ChannelMeta,
  type AbnormalOrderItem,
  type AbnormalOrderStats,
  type ReviewRequest,
  type EditRequest,
} from '@/api/abnormalOrder'

defineOptions({ name: 'AbnormalOrderList' })

// ── 筛选条件 ──────────────
const filter = reactive<{
  page: number
  page_size: number
  keyword: string
  channel_code: string
  review_status: string
}>({
  page: 1,
  page_size: 20,
  keyword: '',
  channel_code: '',
  review_status: '',
})

// ── 统计概览 ──────────────
const stats = reactive<AbnormalOrderStats>({
  total: 0,
  pending: 0,
  reviewed: 0,
  ignored: 0,
})

async function loadStats() {
  try {
    const res = await abnormalOrderApi.stats()
    Object.assign(stats, res)
  } catch {
    // 静默失败
  }
}

// ── 表格数据 ──────────────
const tableData = ref<AbnormalOrderItem[]>([])
const total = ref(0)
const loading = ref(false)

const reviewStatusMap: StatusMap = Object.fromEntries(
  Object.entries(ReviewStatusMeta).map(([k, v]) => [k, { text: v.label, type: v.type }])
)

const columns: ProTableColumn[] = [
  { prop: 'out_order_no', label: '渠道订单号', width: 190 },
  { prop: 'goods_title', label: '商品标题', minWidth: 200 },
  { prop: 'channel_code', label: '渠道', width: 90, align: 'center' },
  { prop: 'pay_amount', label: '支付金额', width: 110, align: 'right' },
  { prop: 'total_commission', label: '总佣金', width: 110, align: 'right' },
  { prop: 'order_status', label: '原始状态', width: 100, align: 'center' },
  { prop: 'abnormal_reason', label: '异常原因', minWidth: 200 },
  { prop: 'matched_user_id', label: '匹配用户ID', width: 110, align: 'center' },
  { prop: 'assigned_user_id', label: '归属用户ID', width: 110, align: 'center' },
  { prop: 'review_status', label: '复核状态', width: 90, align: 'center' },
  { prop: 'pay_time', label: '付款时间', width: 170 },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await abnormalOrderApi.list({
      page: filter.page,
      page_size: filter.page_size,
      review_status: filter.review_status || undefined,
      channel_code: filter.channel_code || undefined,
      keyword: filter.keyword || undefined,
    })
    tableData.value = res.items || []
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
  loadStats()
}

function handleReset() {
  filter.keyword = ''
  filter.channel_code = ''
  filter.review_status = ''
  filter.page = 1
  loadData()
  loadStats()
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

// ── 复核弹窗 ──────────────
const reviewDialogVisible = ref(false)
const reviewLoading = ref(false)
const currentRow = ref<AbnormalOrderItem | null>(null)
const reviewFormRef = ref<FormInstance>()

const reviewForm = reactive<ReviewRequest>({
  review_status: 'REVIEWED',
  review_remark: '',
  assigned_user_id: 0,
})

const reviewRules: FormRules = {
  review_status: [{ required: true, message: '请选择复核结果', trigger: 'change' }],
  assigned_user_id: [{ type: 'number', min: 0, message: '归属用户ID不能为负数', trigger: 'blur' }],
}

function handleReview(row: AbnormalOrderItem) {
  currentRow.value = row
  reviewForm.review_status = 'REVIEWED'
  reviewForm.review_remark = ''
  reviewForm.assigned_user_id = row.assigned_user_id || 0
  reviewDialogVisible.value = true
}

async function handleSubmitReview() {
  if (!currentRow.value) return

  const valid = await reviewFormRef.value?.validate().catch(() => false)
  if (!valid) return

  reviewLoading.value = true
  try {
    await abnormalOrderApi.review(currentRow.value.id, {
      review_status: reviewForm.review_status,
      review_remark: reviewForm.review_remark,
      assigned_user_id: reviewForm.assigned_user_id,
    })
    ElMessage.success('复核完成')
    reviewDialogVisible.value = false
    loadData()
    loadStats()
  } catch {
    // 拦截器已提示
  } finally {
    reviewLoading.value = false
  }
}

// ── 编辑弹窗（复核后修改归属/备注） ──────────
const editDialogVisible = ref(false)
const editLoading = ref(false)
const editRow = ref<AbnormalOrderItem | null>(null)
const editFormRef = ref<FormInstance>()

const editForm = reactive<EditRequest>({
  assigned_user_id: 0,
  review_remark: '',
})

const editRules: FormRules = {
  assigned_user_id: [{ type: 'number', min: 0, message: '归属用户ID不能为负数', trigger: 'blur' }],
}

function handleEdit(row: AbnormalOrderItem) {
  editRow.value = row
  editForm.assigned_user_id = row.assigned_user_id || 0
  editForm.review_remark = row.review_remark || ''
  editDialogVisible.value = true
}

async function handleSubmitEdit() {
  if (!editRow.value) return

  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  editLoading.value = true
  try {
    await abnormalOrderApi.edit(editRow.value.id, {
      assigned_user_id: editForm.assigned_user_id,
      review_remark: editForm.review_remark,
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    loadData()
    loadStats()
  } catch {
    // 拦截器已提示
  } finally {
    editLoading.value = false
  }
}

onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped>
.abnormal-order-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stats-row {
  margin-bottom: 0;
}

.stat-card {
  text-align: center;
  padding: 8px 0;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
  font-weight: 300;
}

.stat-pending .stat-value {
  color: #e6a23c;
}

.stat-reviewed .stat-value {
  color: #67c23a;
}

.stat-ignored .stat-value {
  color: #909399;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 12px;
}

.table-card :deep(.el-card__body) {
  padding: 16px;
}

.reason-text {
  display: inline-block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 300;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
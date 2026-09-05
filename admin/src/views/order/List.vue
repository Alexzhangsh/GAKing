<!-- @ai-generated -->
<!--
  订单列表页
  对接 B13 CPS 订单接口：GET /api/v1/cps/order
  权限：order:manage
  功能：多条件筛选、状态标签、详情弹窗、佣金明细、批量导出 Excel
-->
<template>
  <div class="order-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="订单号">
          <el-input
            v-model="filter.keyword"
            placeholder="订单号/商品标题/用户ID"
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
        <el-form-item label="订单状态">
          <el-select v-model="filter.order_status" placeholder="全部状态" clearable style="width: 140px">
            <el-option
              v-for="(m, s) in OrderStatusMeta"
              :key="s"
              :label="m.label"
              :value="Number(s)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input
            v-model="filter.user_id"
            placeholder="用户ID"
            clearable
            style="width: 140px"
            @keyup.enter="handleSearch"
          />
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
        selectable
        show-index
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
        @selection-change="handleSelectionChange"
      >
        <template #toolbar>
          <el-button v-permission="'order:export'" :loading="exportLoading" @click="handleExport">
            <el-icon><Download /></el-icon>批量导出 Excel
          </el-button>
          <span v-if="selection.length > 0" class="selection-tip">
            已选 {{ selection.length }} 项
          </span>
        </template>

        <template #col-goods_img="{ row }">
          <el-image
            v-if="row.goods_img"
            :src="row.goods_img"
            fit="cover"
            style="width: 60px; height: 60px; border-radius: 4px"
            lazy
          />
          <span v-else class="no-img">无图</span>
        </template>

        <template #col-goods_title="{ row }">
          <el-link type="primary" :underline="false" @click="handleDetail(row)">
            {{ row.goods_title || '(无标题)' }}
          </el-link>
        </template>

        <template #col-channel_code="{ row }">
          <el-tag v-if="ChannelMeta[row.channel_code]" size="small" :type="ChannelMeta[row.channel_code].type as any" effect="plain">
            {{ ChannelMeta[row.channel_code].label }}
          </el-tag>
          <span v-else>{{ row.channel_code }}</span>
        </template>

        <template #col-order_status="{ row }">
          <StatusTag :status="row.order_status" :map="orderStatusMap" />
        </template>

        <template #col-pay_amount="{ row }">¥{{ row.pay_amount }}</template>
        <template #col-total_commission="{ row }">¥{{ row.total_commission }}</template>
        <template #col-user_commission="{ row }">¥{{ row.user_commission }}</template>

        <template #col-action="{ row }">
          <el-button size="small" link type="primary" @click="handleDetail(row)">详情</el-button>
          <el-button
            v-permission="'order:update'"
            size="small"
            link
            type="warning"
            @click="handleManualSettle(row)"
          >
            手动结算
          </el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 详情弹窗 -->
    <OrderDetailDialog
      v-model:visible="detailVisible"
      :order-id="currentOrderId"
      @manual-settle="loadData"
    />
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
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElImage,
  ElLink,
  ElTag,
  ElMessage,
  ElMessageBox,
} from 'element-plus'
import { Download, Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import OrderDetailDialog from './components/OrderDetailDialog.vue'
import {
  orderApi,
  OrderStatusMeta,
  ChannelMeta,
  type OrderItem,
  type OrderListParams,
} from '@/api/order'
import { exportToExcel, type ExcelColumn } from '@/utils/excel'

defineOptions({ name: 'OrderList' })

// ── 筛选条件 ──────────────
const filter = reactive<OrderListParams & { keyword?: string }>({
  page: 1,
  page_size: 20,
  channel_code: undefined,
  order_status: undefined,
  user_id: undefined,
  keyword: '',
})

// ── 表格数据 ──────────────
const tableData = ref<OrderItem[]>([])
const total = ref(0)
const loading = ref(false)

const orderStatusMap: StatusMap = Object.fromEntries(
  Object.entries(OrderStatusMeta).map(([k, v]) => [k, { text: v.label, type: v.type }])
)

const columns: ProTableColumn[] = [
  { prop: 'goods_img', label: '主图', width: 80, align: 'center' },
  { prop: 'goods_title', label: '商品', minWidth: 220 },
  { prop: 'out_order_no', label: '外部订单号', width: 180 },
  { prop: 'user_id', label: '用户ID', width: 90, align: 'right' },
  { prop: 'channel_code', label: '渠道', width: 100, align: 'center' },
  { prop: 'order_status', label: '状态', width: 90, align: 'center' },
  { prop: 'pay_amount', label: '支付金额', width: 110, align: 'right' },
  { prop: 'total_commission', label: '总佣金', width: 110, align: 'right' },
  { prop: 'user_commission', label: '用户佣金', width: 110, align: 'right' },
  { prop: 'pay_time', label: '付款时间', width: 170 },
  { prop: 'settle_time', label: '结算时间', width: 170 },
]

const selection = ref<OrderItem[]>([])
function handleSelectionChange(sel: OrderItem[]) {
  selection.value = sel
}

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await orderApi.list({
      channel_code: filter.channel_code,
      order_status: filter.order_status,
      user_id: filter.user_id ? Number(filter.user_id) : undefined,
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
  // keyword 暂未对接后端，先清空其它参数
  filter.page = 1
  loadData()
}

function handleReset() {
  filter.keyword = ''
  filter.channel_code = undefined
  filter.order_status = undefined
  filter.user_id = undefined
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

// ── 详情弹窗 ──────────────
const detailVisible = ref(false)
const currentOrderId = ref<number>(0)

function handleDetail(row: OrderItem) {
  currentOrderId.value = row.id
  detailVisible.value = true
}

// ── 手动结算 ──────────────
async function handleManualSettle(row: OrderItem) {
  try {
    await ElMessageBox.confirm(
      `确认手动结算订单「${row.out_order_no}」？将强制推进到 SETTLED 状态。`,
      '手动结算确认',
      { type: 'warning' }
    )
    await orderApi.updateStatus({ order_id: row.id, target_status: 40 })
    ElMessage.success('结算成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

// ── Excel 导出 ──────────────
const exportLoading = ref(false)

async function handleExport() {
  exportLoading.value = true
  try {
    const res = await orderApi.list({
      channel_code: filter.channel_code,
      order_status: filter.order_status,
      user_id: filter.user_id ? Number(filter.user_id) : undefined,
      page: 1,
      page_size: 1000,
    })
    const data = res.list || []
    if (data.length === 0) {
      ElMessage.warning('当前筛选条件下无数据可导出')
      return
    }
    const cols: ExcelColumn[] = [
      { header: '订单ID', key: 'id', width: 10 },
      { header: '外部订单号', key: 'out_order_no', width: 22 },
      { header: '商品', key: 'goods_title', width: 36 },
      { header: '用户ID', key: 'user_id', width: 10 },
      {
        header: '渠道',
        key: 'channel_code',
        width: 12,
        formatter: (v) => (ChannelMeta[String(v)]?.label || String(v)),
      },
      {
        header: '状态',
        key: 'order_status',
        width: 10,
        formatter: (v) => (OrderStatusMeta[Number(v)]?.label || String(v)),
      },
      { header: '支付金额(元)', key: 'pay_amount', width: 14 },
      { header: '总佣金(元)', key: 'total_commission', width: 14 },
      { header: '用户佣金(元)', key: 'user_commission', width: 14 },
      { header: '平台佣金(元)', key: 'platform_commission', width: 14 },
      { header: '付款时间', key: 'pay_time', width: 20 },
      { header: '结算时间', key: 'settle_time', width: 20 },
    ]
    exportToExcel('订单列表', cols, data as unknown as Record<string, unknown>[])
    ElMessage.success(`已导出 ${data.length} 条数据`)
  } catch (e) {
    if (e instanceof Error) ElMessage.error(e.message)
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.order-list-page {
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

.selection-tip {
  margin-left: 12px;
  font-size: 13px;
  color: #e6a23c;
  font-weight: 300;
}

.no-img {
  display: inline-block;
  width: 60px;
  height: 60px;
  line-height: 60px;
  text-align: center;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 12px;
  border-radius: 4px;
  font-weight: 300;
}
</style>

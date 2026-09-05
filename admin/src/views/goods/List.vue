<!-- @ai-generated -->
<!--
  商品列表页（核心）
  对接 B13 接口：
  - GET    /api/v1/admin/goods          列表查询（分页+筛选）
  - PUT    /api/v1/admin/goods/batch/shelf   批量上下架
  - DELETE /api/v1/admin/goods/batch     批量删除
  权限：goods:manage
-->
<template>
  <div class="goods-list-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="12" class="stat-row">
      <el-col :span="8" v-for="stat in statCards" :key="stat.label">
        <el-card shadow="hover" :body-style="{ padding: '16px 20px' }">
          <div class="stat-mini">
            <span class="stat-mini__label">{{ stat.label }}</span>
            <span class="stat-mini__value" :style="{ color: stat.color }">{{ stat.value }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="filter.keyword"
            placeholder="商品标题搜索"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="来源渠道">
          <el-select v-model="filter.source_channel" placeholder="全部渠道" clearable style="width: 140px">
            <el-option label="喵有券 (myq)" value="myq" />
            <el-option label="订单侠 (orderx)" value="orderx" />
            <el-option label="大淘客 (dta)" value="dta" />
          </el-select>
        </el-form-item>
        <el-form-item label="上下架">
          <el-select v-model="filter.shelf_status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="上架" value="on_shelf" />
            <el-option label="下架" value="off_shelf" />
          </el-select>
        </el-form-item>
        <el-form-item label="类目">
          <el-input v-model="filter.category" placeholder="类目" clearable style="width: 140px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 + 工具栏 -->
    <el-card shadow="never" class="table-card">
      <ProTable
        :data="tableData"
        :columns="columns"
        :loading="loading"
        :pagination="{ page: filter.page, page_size: filter.page_size, total }"
        row-key="goods_id"
        selectable
        :action-width="220"
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
        @selection-change="handleSelectionChange"
      >
        <template #toolbar>
          <el-button type="primary" v-permission="'goods:manage'" @click="$router.push('/goods/edit')">
            <el-icon><Plus /></el-icon>新增商品
          </el-button>
          <el-button v-permission="'goods:manage'" @click="syncDialogVisible = true">
            <el-icon><Refresh /></el-icon>CPS 同步
          </el-button>
          <el-button
            v-permission="'goods:manage'"
            :disabled="selection.length === 0"
            @click="handleBatchShelf('on_shelf')"
          >
            批量上架
          </el-button>
          <el-button
            v-permission="'goods:manage'"
            :disabled="selection.length === 0"
            @click="handleBatchShelf('off_shelf')"
          >
            批量下架
          </el-button>
          <el-button
            v-permission="'goods:manage'"
            type="danger"
            :disabled="selection.length === 0"
            @click="handleBatchDelete"
          >
            <el-icon><Delete /></el-icon>批量删除
          </el-button>
          <el-button :loading="exportLoading" @click="handleExport">
            <el-icon><Download /></el-icon>导出 Excel
          </el-button>
          <span v-if="selection.length > 0" class="selection-tip">
            已选 {{ selection.length }} 项
          </span>
        </template>

        <template #col-goods_img="{ row }">
          <el-image
            v-if="row.goods_img"
            :src="row.goods_img"
            :preview-src-list="[row.goods_img]"
            preview-teleported
            fit="cover"
            style="width: 60px; height: 60px; border-radius: 4px"
            lazy
          />
          <span v-else class="no-img">无图</span>
        </template>

        <template #col-goods_title="{ row }">
          <el-link type="primary" underline="never" @click="handleDetail(row)">
            {{ row.goods_title || '(无标题)' }}
          </el-link>
        </template>

        <template #col-source_channel="{ row }">
          <el-tag size="small" :type="channelTagType(row.source_channel)" effect="plain">
            {{ channelLabel(row.source_channel) }}
          </el-tag>
        </template>

        <template #col-sale_price="{ row }">
          ¥{{ row.sale_price }}
        </template>

        <template #col-commission_rate="{ row }">
          {{ row.commission_rate }}%
        </template>

        <template #col-shelf_status="{ row }">
          <StatusTag :status="row.shelf_status" :map="shelfStatusMap" />
        </template>

        <template #col-action="{ row }">
          <div style="white-space: nowrap; display: flex; gap: 4px; justify-content: center;">
            <el-button size="small" link type="primary" @click="handleDetail(row)">详情</el-button>
            <el-button size="small" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button
              size="small"
              link
              :type="row.shelf_status === 'on_shelf' ? 'warning' : 'success'"
              @click="handleToggleShelf(row)"
            >
              {{ row.shelf_status === 'on_shelf' ? '下架' : '上架' }}
            </el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </div>
        </template>
      </ProTable>
    </el-card>

    <!-- CPS 同步弹窗 -->
    <SyncDialog v-model:visible="syncDialogVisible" @success="loadData" />
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElCard,
  ElRow,
  ElCol,
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
import { Plus, Refresh, Delete, Download, Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import SyncDialog from './components/SyncDialog.vue'
import { goodsApi, type GoodsItem, type GoodsListParams } from '@/api/goods'
import { exportToExcel, type ExcelColumn } from '@/utils/excel'

defineOptions({ name: 'GoodsList' })

const router = useRouter()

// ── 筛选条件 ──────────────
const filter = reactive<GoodsListParams>({
  keyword: '',
  source_channel: undefined,
  shelf_status: undefined,
  category: '',
  page: 1,
  page_size: 20,
})

// ── 表格数据 ──────────────
const tableData = ref<GoodsItem[]>([])
const total = ref(0)
const totalOnShelf = ref(0)
const totalOffShelf = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'goods_img', label: '主图', width: 80, align: 'center' },
  { prop: 'goods_title', label: '商品标题', minWidth: 220 },
  { prop: 'source_channel', label: '渠道', width: 100, align: 'center' },
  { prop: 'category', label: '类目', width: 120 },
  { prop: 'shop_name', label: '店铺', width: 140 },
  { prop: 'sale_price', label: '销售价', width: 100, align: 'right' },
  { prop: 'commission_rate', label: '佣金率', width: 90, align: 'right' },
  { prop: 'shelf_status', label: '状态', width: 80, align: 'center' },
  { prop: 'sort_order', label: '排序', width: 70, align: 'center' },
  { prop: 'update_time', label: '更新时间', width: 170 },
]

// ── 状态映射 ──────────────
const shelfStatusMap: StatusMap = {
  on_shelf: { text: '上架', type: 'success' },
  off_shelf: { text: '下架', type: 'info' },
}

function channelLabel(code: string): string {
  const map: Record<string, string> = { myq: '喵有券', orderx: '订单侠', dta: '大淘客' }
  return map[code] || code
}

function channelTagType(code: string): 'primary' | 'success' | 'warning' {
  const map: Record<string, 'primary' | 'success' | 'warning'> = {
    myq: 'primary',
    orderx: 'success',
    dta: 'warning',
  }
  return map[code] || 'primary'
}

// ── 顶部统计卡片（总数，非当前页） ──────────────
const statCards = computed(() => [
  { label: '总商品数', value: total.value, color: '#e6a23c' },
  { label: '上架数量', value: totalOnShelf.value, color: '#67c23a' },
  { label: '下架数量', value: totalOffShelf.value, color: '#909399' },
])

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await goodsApi.list({
      keyword: filter.keyword || undefined,
      source_channel: filter.source_channel || undefined,
      shelf_status: filter.shelf_status || undefined,
      category: filter.category || undefined,
      page: filter.page,
      page_size: filter.page_size,
    })
    tableData.value = res.items || []
    total.value = res.total || 0
    totalOnShelf.value = res.total_on_shelf ?? 0
    totalOffShelf.value = res.total_off_shelf ?? 0
  } catch {
    tableData.value = []
    total.value = 0
    totalOnShelf.value = 0
    totalOffShelf.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filter.page = 1
  loadData()
}

function handleReset() {
  filter.keyword = ''
  filter.source_channel = undefined
  filter.shelf_status = undefined
  filter.category = ''
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

// ── 选择与批量操作 ──────────────
const selection = ref<GoodsItem[]>([])

function handleSelectionChange(sel: GoodsItem[]) {
  selection.value = sel
}

/** 批量操作需要同渠道（后端要求 source_channel 必填） */
function checkSameChannel(rows: GoodsItem[]): string | null {
  if (rows.length === 0) {
    ElMessage.warning('请先选择要操作的商品')
    return null
  }
  const channels = new Set(rows.map((r) => r.source_channel))
  if (channels.size > 1) {
    ElMessage.warning('批量操作仅支持同一来源渠道的商品，请重新选择')
    return null
  }
  return rows[0].source_channel
}

async function handleBatchShelf(status: 'on_shelf' | 'off_shelf') {
  const channel = checkSameChannel(selection.value)
  if (!channel) return
  try {
    await ElMessageBox.confirm(
      `确认将选中的 ${selection.value.length} 个商品${status === 'on_shelf' ? '上架' : '下架'}？`,
      '批量操作确认',
      { type: 'warning' }
    )
    await goodsApi.batchShelf({
      goods_ids: selection.value.map((r) => r.goods_id),
      source_channel: channel,
      shelf_status: status,
    })
    ElMessage.success(`批量${status === 'on_shelf' ? '上架' : '下架'}成功`)
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleBatchDelete() {
  const channel = checkSameChannel(selection.value)
  if (!channel) return
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${selection.value.length} 个商品管理记录？删除后不可恢复！`,
      '危险操作确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await goodsApi.batchDelete({
      goods_ids: selection.value.map((r) => r.goods_id),
      source_channel: channel,
    })
    ElMessage.success('批量删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

// ── 单行操作 ──────────────
function handleDetail(row: GoodsItem) {
  router.push({
    path: `/goods/detail/${encodeURIComponent(row.goods_id)}`,
    query: { source_channel: row.source_channel },
  })
}

function handleEdit(row: GoodsItem) {
  router.push({
    path: `/goods/edit/${encodeURIComponent(row.goods_id)}`,
    query: { source_channel: row.source_channel },
  })
}

async function handleToggleShelf(row: GoodsItem) {
  const target = row.shelf_status === 'on_shelf' ? 'off_shelf' : 'on_shelf'
  try {
    await goodsApi.updateShelf(row.goods_id, row.source_channel, target)
    ElMessage.success(`${target === 'on_shelf' ? '上架' : '下架'}成功`)
    loadData()
  } catch {
    // 拦截器已提示
  }
}

async function handleDelete(row: GoodsItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除商品「${row.goods_title || row.goods_id}」？删除后不可恢复！`,
      '危险操作确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await goodsApi.batchDelete({
      goods_ids: [row.goods_id],
      source_channel: row.source_channel,
    })
    ElMessage.success('删除成功')
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
    // 按当前筛选条件拉取全量数据（最多 1000 条）
    const res = await goodsApi.list({
      keyword: filter.keyword || undefined,
      source_channel: filter.source_channel || undefined,
      shelf_status: filter.shelf_status || undefined,
      category: filter.category || undefined,
      page: 1,
      page_size: 1000,
    })
    const data = res.items || []
    if (data.length === 0) {
      ElMessage.warning('当前筛选条件下无数据可导出')
      return
    }
    const cols: ExcelColumn[] = [
      { header: '商品ID', key: 'goods_id', width: 24 },
      { header: '商品标题', key: 'goods_title', width: 40 },
      { header: '来源渠道', key: 'source_channel', width: 10, formatter: (v) => channelLabel(String(v)) },
      { header: '类目', key: 'category', width: 14 },
      { header: '店铺', key: 'shop_name', width: 16 },
      { header: '销售价(元)', key: 'sale_price', width: 12 },
      { header: '佣金率(%)', key: 'commission_rate', width: 10 },
      { header: '上下架', key: 'shelf_status', width: 8, formatter: (v) => (v === 'on_shelf' ? '上架' : '下架') },
      { header: '排序', key: 'sort_order', width: 8 },
      { header: '备注', key: 'admin_remark', width: 24 },
      { header: '更新时间', key: 'update_time', width: 20 },
    ]
    exportToExcel('商品列表', cols, data as unknown as Record<string, unknown>[])
    ElMessage.success(`已导出 ${data.length} 条数据`)
  } catch (e) {
    if (e instanceof Error) {
      ElMessage.error(e.message)
    }
  } finally {
    exportLoading.value = false
  }
}

// ── 同步弹窗 ──────────────
const syncDialogVisible = ref(false)

onActivated(() => {
  loadData()
})
</script>

<style scoped>
.goods-list-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-row {
  margin: 0 !important;
}

.stat-row .el-col {
  padding: 6px;
}

.stat-mini {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-mini__label {
  font-size: 13px;
  color: #909399;
  font-weight: 300;
}

.stat-mini__value {
  font-size: 24px;
  font-weight: 500;
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

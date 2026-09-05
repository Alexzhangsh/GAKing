<!-- @ai-generated -->
<!--
  会员记录查询页（X02-1）
  对接接口：
  - GET  /api/v1/admin/member-record/records   会员记录列表
  - GET  /api/v1/admin/member-record/stats     会员数据统计
  - POST /api/v1/admin/member-record/export    会员记录导出（Excel）
  权限：member:view（查询）/ member:export（导出）
-->
<template>
  <div class="member-record-page">
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
        <el-form-item label="用户ID">
          <el-input
            v-model.number="filter.user_id"
            placeholder="平台用户ID"
            clearable
            style="width: 140px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="会员状态">
          <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="生效中" value="active" />
            <el-option label="已到期" value="expired" />
            <el-option label="已撤销" value="revoked" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐">
          <el-select v-model="filter.package_id" placeholder="全部套餐" clearable filterable style="width: 160px">
            <el-option v-for="pkg in packageOptions" :key="pkg.id" :label="pkg.package_name" :value="pkg.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐名称">
          <el-input
            v-model="filter.keyword"
            placeholder="套餐名称关键字"
            clearable
            style="width: 140px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="开通时间">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="截止时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
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

    <!-- 表格 + 工具栏 -->
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
        <template #toolbar>
          <el-button v-permission="'member:export'" :loading="exportLoading" @click="handleExport">
            <el-icon><Download /></el-icon>导出 Excel
          </el-button>
        </template>

        <template #col-member_commission_rate="{ row }">
          {{ (row.member_commission_rate * 100).toFixed(2) }}%
        </template>

        <template #col-status="{ row }">
          <StatusTag :status="row.status" :map="statusMap" />
        </template>

        <template #col-order_id="{ row }">
          {{ row.order_id ?? '-' }}
        </template>
      </ProTable>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, onMounted } from 'vue'
import {
  ElCard,
  ElRow,
  ElCol,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElDatePicker,
  ElButton,
  ElIcon,
  ElMessage,
} from 'element-plus'
import { Download, Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import {
  memberPackageApi,
  memberRecordApi,
  type MemberPackage,
  type MemberRecord,
} from '@/api/member'

defineOptions({ name: 'MemberRecordList' })

// ── 筛选条件 ──────────────
const dateRange = ref<[string, string] | null>(null)

const filter = reactive<{
  user_id: number | undefined
  status: string | undefined
  package_id: number | undefined
  keyword: string
  page: number
  page_size: number
}>({
  user_id: undefined,
  status: undefined,
  package_id: undefined,
  keyword: '',
  page: 1,
  page_size: 20,
})

// ── 套餐下拉选项 ──────────────
const packageOptions = ref<MemberPackage[]>([])

async function loadPackages() {
  try {
    const res = await memberPackageApi.onShelf()
    packageOptions.value = res.items || []
  } catch {
    packageOptions.value = []
  }
}

// ── 表格数据 ──────────────
const tableData = ref<MemberRecord[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'user_id', label: '用户ID', width: 100, align: 'center' },
  { prop: 'package_name', label: '套餐名称', minWidth: 140 },
  { prop: 'member_commission_rate', label: '会员分佣比例', width: 120, align: 'right' },
  { prop: 'status', label: '会员状态', width: 90, align: 'center' },
  { prop: 'started_at', label: '开通时间', width: 170 },
  { prop: 'expire_at', label: '到期时间', width: 170 },
  { prop: 'order_id', label: '开通订单ID', width: 130, align: 'center' },
  { prop: 'create_time', label: '记录时间', width: 170 },
]

// ── 状态映射 ──────────────
const statusMap: StatusMap = {
  active: { text: '生效中', type: 'success' },
  expired: { text: '已到期', type: 'info' },
  revoked: { text: '已撤销', type: 'danger' },
}

// ── 顶部统计卡片（后端统计） ──────────────
const statCards = ref<{ label: string; value: number; color: string }[]>([
  { label: '生效中会员', value: 0, color: '#67c23a' },
  { label: '已到期会员', value: 0, color: '#909399' },
  { label: '会员记录总数', value: 0, color: '#409eff' },
])

async function loadStats() {
  try {
    const stats = await memberRecordApi.stats()
    statCards.value = [
      { label: '生效中会员', value: stats.active_count || 0, color: '#67c23a' },
      { label: '已到期会员', value: stats.expired_count || 0, color: '#909399' },
      { label: '会员记录总数', value: stats.total_count || 0, color: '#409eff' },
    ]
  } catch {
    // 统计失败不阻断列表
  }
}

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await memberRecordApi.list({
      user_id: filter.user_id || undefined,
      status: filter.status,
      package_id: filter.package_id,
      keyword: filter.keyword || undefined,
      start_time: dateRange.value?.[0],
      end_time: dateRange.value?.[1],
      page: filter.page,
      page_size: filter.page_size,
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
}

function handleReset() {
  filter.user_id = undefined
  filter.status = undefined
  filter.package_id = undefined
  filter.keyword = ''
  dateRange.value = null
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

// ── Excel 导出 ──────────────
const exportLoading = ref(false)

async function handleExport() {
  exportLoading.value = true
  try {
    const res = await memberRecordApi.export({
      user_id: filter.user_id || undefined,
      status: filter.status,
      package_id: filter.package_id,
      keyword: filter.keyword || undefined,
      start_time: dateRange.value?.[0],
      end_time: dateRange.value?.[1],
    })
    ElMessage.success(`导出成功，共 ${res.row_count} 条`)
  } catch (e) {
    if (e instanceof Error) {
      ElMessage.error(e.message)
    }
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  loadPackages()
  loadStats()
  loadData()
})
</script>

<style scoped>
.member-record-page {
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
</style>

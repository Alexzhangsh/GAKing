<!-- @ai-generated -->
<!--
  会员套餐管理页（X02-1）
  对接接口：
  - GET    /api/v1/admin/member-package/packages          套餐列表
  - POST   /api/v1/admin/member-package/packages          新增套餐
  - PUT    /api/v1/admin/member-package/packages/{id}     编辑套餐
  - PUT    /api/v1/admin/member-package/packages/{id}/status  上下架
  - DELETE /api/v1/admin/member-package/packages/{id}     删除套餐
  权限：member:manage
-->
<template>
  <div class="member-package-page">
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
            placeholder="套餐名称/编码搜索"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="上架" :value="1" />
            <el-option label="下架" :value="0" />
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
          <el-button type="primary" v-permission="'member:manage'" @click="openCreate">
            <el-icon><Plus /></el-icon>新增套餐
          </el-button>
        </template>

        <template #col-price="{ row }">
          ¥{{ row.price.toFixed(2) }}
        </template>

        <template #col-member_commission_rate="{ row }">
          {{ (row.member_commission_rate * 100).toFixed(2) }}%
        </template>

        <template #col-status="{ row }">
          <StatusTag :status="row.status" :map="statusMap" />
        </template>

        <template #col-action="{ row }">
          <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            link
            :type="row.status === 1 ? 'warning' : 'success'"
            @click="handleToggleStatus(row)"
          >
            {{ row.status === 1 ? '下架' : '上架' }}
          </el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑会员套餐' : '新增会员套餐'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="120px">
        <el-form-item label="套餐编码" prop="package_code">
          <el-input v-model="form.package_code" :disabled="!!editingId" placeholder="如 VIP_MONTH" maxlength="32" />
        </el-form-item>
        <el-form-item label="套餐名称" prop="package_name">
          <el-input v-model="form.package_name" placeholder="如 月度会员" maxlength="64" />
        </el-form-item>
        <el-form-item label="套餐价格(元)" prop="price">
          <el-input-number v-model="form.price" :min="0" :precision="2" :step="10" style="width: 200px" />
        </el-form-item>
        <el-form-item label="有效期(天)" prop="duration_days">
          <el-input-number v-model="form.duration_days" :min="1" :max="3650" :step="30" style="width: 200px" />
        </el-form-item>
        <el-form-item label="会员分佣比例" prop="member_commission_rate">
          <el-input-number
            v-model="form.member_commission_rate"
            :min="0"
            :max="1"
            :step="0.05"
            :precision="4"
            style="width: 200px"
          />
          <span class="form-tip">0~1，如 0.85 表示会员分佣 85%</span>
        </el-form-item>
        <el-form-item label="排序号" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :step="1" style="width: 200px" />
        </el-form-item>
        <el-form-item label="上架状态" prop="status">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="上架" inactive-text="下架" />
        </el-form-item>
        <el-form-item label="套餐描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="512" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, onMounted } from 'vue'
import {
  ElCard,
  ElRow,
  ElCol,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElSwitch,
  ElButton,
  ElIcon,
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import { memberPackageApi, type MemberPackage } from '@/api/member'

defineOptions({ name: 'MemberPackageList' })

// ── 筛选条件 ──────────────
const filter = reactive<{ keyword: string; status: number | undefined; page: number; page_size: number }>({
  keyword: '',
  status: undefined,
  page: 1,
  page_size: 20,
})

// ── 表格数据 ──────────────
const tableData = ref<MemberPackage[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'package_code', label: '套餐编码', width: 130 },
  { prop: 'package_name', label: '套餐名称', minWidth: 140 },
  { prop: 'price', label: '价格', width: 100, align: 'right' },
  { prop: 'duration_days', label: '有效期(天)', width: 100, align: 'center' },
  { prop: 'member_commission_rate', label: '会员分佣比例', width: 120, align: 'right' },
  { prop: 'status', label: '状态', width: 80, align: 'center' },
  { prop: 'sort_order', label: '排序', width: 70, align: 'center' },
  { prop: 'update_time', label: '更新时间', width: 170 },
]

// ── 状态映射 ──────────────
const statusMap: StatusMap = {
  1: { text: '上架', type: 'success' },
  0: { text: '下架', type: 'info' },
}

// ── 顶部统计卡片（前端聚合） ──────────────
const statCards = computed(() => {
  const all = tableData.value
  const onShelf = all.filter((i) => i.status === 1).length
  const offShelf = all.filter((i) => i.status === 0).length
  return [
    { label: '当前页套餐数', value: all.length, color: '#409eff' },
    { label: '上架（当前页）', value: onShelf, color: '#67c23a' },
    { label: '下架（当前页）', value: offShelf, color: '#909399' },
  ]
})

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await memberPackageApi.list({
      keyword: filter.keyword || undefined,
      status: filter.status,
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
  filter.keyword = ''
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

// ── 新增/编辑弹窗 ──────────────
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  package_code: '',
  package_name: '',
  price: 0,
  duration_days: 30,
  member_commission_rate: 0.8,
  status: 1,
  sort_order: 0,
  description: '',
})

const formRules: FormRules = {
  package_code: [{ required: true, message: '请输入套餐编码', trigger: 'blur' }],
  package_name: [{ required: true, message: '请输入套餐名称', trigger: 'blur' }],
  price: [{ required: true, message: '请输入套餐价格', trigger: 'blur' }],
  duration_days: [{ required: true, message: '请输入有效期', trigger: 'blur' }],
  member_commission_rate: [{ required: true, message: '请输入会员分佣比例', trigger: 'blur' }],
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    package_code: '',
    package_name: '',
    price: 0,
    duration_days: 30,
    member_commission_rate: 0.8,
    status: 1,
    sort_order: 0,
    description: '',
  })
  dialogVisible.value = true
}

function openEdit(row: MemberPackage) {
  editingId.value = row.id
  Object.assign(form, {
    package_code: row.package_code,
    package_name: row.package_name,
    price: row.price,
    duration_days: row.duration_days,
    member_commission_rate: row.member_commission_rate,
    status: row.status,
    sort_order: row.sort_order,
    description: row.description,
  })
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await memberPackageApi.update(editingId.value, {
        package_name: form.package_name,
        price: form.price,
        duration_days: form.duration_days,
        member_commission_rate: form.member_commission_rate,
        status: form.status,
        sort_order: form.sort_order,
        description: form.description,
      })
      ElMessage.success('套餐更新成功')
    } else {
      await memberPackageApi.create({
        package_code: form.package_code,
        package_name: form.package_name,
        price: form.price,
        duration_days: form.duration_days,
        member_commission_rate: form.member_commission_rate,
        status: form.status,
        sort_order: form.sort_order,
        description: form.description,
      })
      ElMessage.success('套餐创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

// ── 单行操作 ──────────────
async function handleToggleStatus(row: MemberPackage) {
  const target = row.status === 1 ? 0 : 1
  try {
    await memberPackageApi.updateStatus(row.id, target)
    ElMessage.success(target === 1 ? '套餐已上架' : '套餐已下架')
    loadData()
  } catch {
    // 拦截器已提示
  }
}

async function handleDelete(row: MemberPackage) {
  try {
    await ElMessageBox.confirm(
      `确认删除套餐「${row.package_name || row.package_code}」？删除后不可恢复！`,
      '危险操作确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await memberPackageApi.remove(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.member-package-page {
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

.form-tip {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
  font-weight: 300;
}
</style>

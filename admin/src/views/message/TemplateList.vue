<!-- @ai-generated -->
<!--
  消息模板管理页面
  对接 F04 接口：
  - GET    /api/v1/admin/message/templates          列表
  - POST   /api/v1/admin/message/templates          新增
  - PUT    /api/v1/admin/message/templates/{id}     更新
  - DELETE /api/v1/admin/message/templates/{id}     删除
  - PUT    /api/v1/admin/message/templates/{id}/toggle  启停
  权限：message:manage
-->
<template>
  <div class="template-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="模板类型">
          <el-select v-model="filter.template_type" placeholder="全部类型" clearable style="width: 140px">
            <el-option label="微信订阅消息" :value="1" />
            <el-option label="站内消息" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="停用" :value="0" />
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
        <template #toolbar>
          <el-button type="primary" v-permission="'message:manage'" @click="handleAdd">
            <el-icon><Plus /></el-icon>新增模板
          </el-button>
          <el-button :loading="exportLoading" @click="handleExport">
            <el-icon><Download /></el-icon>导出 Excel
          </el-button>
        </template>

        <template #col-template_type="{ row }">
          <el-tag :type="row.template_type === 1 ? 'primary' : 'success'" size="small">
            {{ row.template_type === 1 ? '微信订阅' : '站内消息' }}
          </el-tag>
        </template>

        <template #col-status="{ row }">
          <el-switch
            v-permission="'message:manage'"
            :model-value="row.status === 1"
            @change="handleToggleStatus(row)"
          />
          <el-tag v-if="!hasPermission(['message:manage'])" :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>

        <template #col-action="{ row }">
          <template v-if="hasPermission(['message:manage'])">
            <el-button size="small" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
          <el-button v-else size="small" link type="primary" @click="handleView(row)">查看</el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 编辑弹窗 -->
    <TemplateFormDialog
      v-model:visible="dialogVisible"
      :edit-data="editingRow"
      :readonly="viewOnly"
      @success="loadData"
    />
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, onMounted } from 'vue'
import {
  ElCard, ElForm, ElFormItem, ElSelect, ElOption, ElButton,
  ElIcon, ElTag, ElSwitch, ElMessage, ElMessageBox,
} from 'element-plus'
import { Plus, Download, Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import TemplateFormDialog from './components/TemplateFormDialog.vue'
import { messageTemplateApi, type MessageTemplate } from '@/api/message'
import { useUserStore } from '@/store/user'
import { exportToExcel, type ExcelColumn } from '@/utils/excel'

defineOptions({ name: 'MessageTemplateList' })

const userStore = useUserStore()
function hasPermission(codes: string[]): boolean {
  return userStore.hasPermission(codes)
}

// ── 筛选 ──────────────
const filter = reactive({
  template_type: undefined as number | undefined,
  status: undefined as number | undefined,
  page: 1,
  page_size: 20,
})

// ── 表格 ──────────────
const tableData = ref<MessageTemplate[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'template_name', label: '模板名称', minWidth: 180 },
  { prop: 'template_type', label: '类型', width: 110, align: 'center' },
  { prop: 'tmpl_id', label: 'tmpl_id', width: 160, showOverflowTooltip: true },
  { prop: 'title', label: '标题', minWidth: 160 },
  { prop: 'content', label: '内容', minWidth: 200, showOverflowTooltip: true },
  { prop: 'status', label: '状态', width: 90, align: 'center' },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await messageTemplateApi.list({
      page: filter.page,
      page_size: filter.page_size,
      template_type: filter.template_type,
      status: filter.status,
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
  filter.template_type = undefined
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

// ── CRUD ──────────────
const dialogVisible = ref(false)
const editingRow = ref<MessageTemplate | null>(null)
const viewOnly = ref(false)

function handleAdd() {
  editingRow.value = null
  viewOnly.value = false
  dialogVisible.value = true
}

function handleEdit(row: MessageTemplate) {
  editingRow.value = row
  viewOnly.value = false
  dialogVisible.value = true
}

function handleView(row: MessageTemplate) {
  editingRow.value = row
  viewOnly.value = true
  dialogVisible.value = true
}

async function handleToggleStatus(row: MessageTemplate) {
  try {
    await messageTemplateApi.toggle(row.id)
    ElMessage.success('状态切换成功')
    loadData()
  } catch {
    // 拦截器已提示
  }
}

async function handleDelete(row: MessageTemplate) {
  try {
    await ElMessageBox.confirm(
      `确认删除模板「${row.template_name}」？删除后不可恢复！`,
      '危险操作确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await messageTemplateApi.delete(row.id)
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
    const res = await messageTemplateApi.list({
      page: 1,
      page_size: 1000,
      template_type: filter.template_type,
      status: filter.status,
    })
    const data = res.items || []
    if (data.length === 0) {
      ElMessage.warning('当前筛选条件下无数据可导出')
      return
    }
    const cols: ExcelColumn[] = [
      { header: 'ID', key: 'id', width: 8 },
      { header: '模板名称', key: 'template_name', width: 24 },
      { header: '类型', key: 'template_type', width: 12, formatter: (v) => (Number(v) === 1 ? '微信订阅' : '站内消息') },
      { header: 'tmpl_id', key: 'tmpl_id', width: 24 },
      { header: '标题', key: 'title', width: 20 },
      { header: '内容', key: 'content', width: 40 },
      { header: '状态', key: 'status', width: 8, formatter: (v) => (Number(v) === 1 ? '启用' : '停用') },
      { header: '备注', key: 'remark', width: 24 },
      { header: '创建时间', key: 'create_time', width: 20 },
    ]
    exportToExcel('消息模板列表', cols, data as unknown as Record<string, unknown>[])
    ElMessage.success(`已导出 ${data.length} 条数据`)
  } catch (e) {
    if (e instanceof Error) {
      ElMessage.error(e.message)
    }
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.template-list-page {
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
</style>

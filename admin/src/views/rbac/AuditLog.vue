<!-- @ai-generated -->
<!--
  系统审计日志页
  权限：audit:view
  功能：全操作日志列表、操作人/IP/时间/行为多维度筛选、日志详情查看
-->
<template>
  <div class="audit-log-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="操作人ID">
          <el-input
            v-model="filter.user_id"
            placeholder="操作人ID"
            clearable
            style="width: 140px"
            type="number"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="filter.action" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="a in ActionOptions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标类型">
          <el-input v-model="filter.target_type" placeholder="目标类型" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="IP">
          <el-input v-model="filterUI.ip_address" placeholder="IP地址" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetime"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 340px"
            value-format="YYYY-MM-DD HH:mm:ss"
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
        show-index
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
      >
        <template #col-action="{ row }">
          <el-button size="small" link type="primary" @click="handleDetail(row)">详情</el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 日志详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="审计日志详情"
      width="780px"
      top="5vh"
      append-to-body
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="日志ID">{{ detail.id }}</el-descriptions-item>
            <el-descriptions-item label="操作时间">{{ detail.create_time }}</el-descriptions-item>
            <el-descriptions-item label="操作人">
              {{ detail.user_name }}（ID: {{ detail.user_id }}）
            </el-descriptions-item>
            <el-descriptions-item label="操作类型">
              <el-tag size="small" :type="actionTagType(detail.action)" effect="plain">
                {{ detail.action }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="操作目标">
              {{ detail.target_type }}
              <span v-if="detail.target_id"> #{{ detail.target_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="请求IP" :span="2">
              {{ detail.ip_address }}
              <span v-if="detail.user_agent" class="ua"> · {{ detail.user_agent }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">详细数据</el-divider>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="详情">
              <pre class="json-pre">{{ detail.details || '无' }}</pre>
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <el-empty v-else-if="!detailLoading" description="暂无数据" :image-size="60" />
      </div>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
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
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElDatePicker,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElEmpty,
  ElDialog,
  ElTag,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import {
  auditApi,
  type AuditLogItem,
  type AuditLogListParams,
} from '@/api/audit'

defineOptions({ name: 'AuditLog' })

const ActionOptions = [
  'LOGIN', 'LOGOUT', 'CREATE', 'UPDATE', 'DELETE',
  'EXPORT', 'ENABLE', 'DISABLE', 'FREEZE', 'UNFREEZE',
  'APPROVE', 'REJECT', 'TRANSFER', 'DASHBOARD_QUERY',
]

const filter = reactive<AuditLogListParams>({
  page: 1,
  page_size: 20,
  user_id: undefined,
  action: undefined,
  target_type: undefined,
  start_time: undefined,
  end_time: undefined,
})

// 前端临时字段，不直接传给后端
const filterUI = reactive({
  ip_address: undefined as string | undefined,
})

const dateRange = ref<[string, string] | null>(null)

const tableData = ref<AuditLogItem[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'user_name', label: '操作人', width: 120 },
  { prop: 'user_id', label: '操作人ID', width: 100 },
  { prop: 'action', label: '操作类型', width: 130, align: 'center' },
  { prop: 'target_type', label: '目标类型', width: 120 },
  { prop: 'target_id', label: '目标ID', width: 90 },
  { prop: 'ip_address', label: 'IP地址', width: 140 },
  { prop: 'user_agent', label: 'User-Agent', minWidth: 200 },
  { prop: 'create_time', label: '操作时间', width: 170 },
]

function actionTagType(action: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    LOGIN: 'primary',
    LOGOUT: 'info',
    CREATE: 'success',
    UPDATE: 'warning',
    DELETE: 'danger',
    EXPORT: 'info',
    DASHBOARD_QUERY: 'info',
  }
  return map[action] || 'info'
}

async function loadData() {
  loading.value = true
  try {
    const params: AuditLogListParams = {
      page: filter.page,
      page_size: filter.page_size,
    }
    if (filter.user_id) params.user_id = filter.user_id
    if (filter.action) params.action = filter.action
    if (filter.target_type) params.target_type = filter.target_type
    if (filter.start_time) params.start_time = filter.start_time
    if (filter.end_time) params.end_time = filter.end_time

    const res = await auditApi.list(params)
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
  if (dateRange.value) {
    filter.start_time = dateRange.value[0]
    filter.end_time = dateRange.value[1]
  } else {
    filter.start_time = undefined
    filter.end_time = undefined
  }
  filter.page = 1
  loadData()
}

function handleReset() {
  filter.user_id = undefined
  filter.action = undefined
  filter.target_type = undefined
  filterUI.ip_address = undefined
  filter.start_time = undefined
  filter.end_time = undefined
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

// ── 详情弹窗 ──────────────
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<AuditLogItem | null>(null)

async function handleDetail(row: AuditLogItem) {
  detailLoading.value = true
  detailVisible.value = true
  try {
    detail.value = await auditApi.getDetail(row.id)
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.audit-log-page {
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

.ua {
  color: #909399;
  font-size: 12px;
  font-weight: 300;
}

.json-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #606266;
  background: #f7f9fc;
  padding: 8px 12px;
  border-radius: 4px;
  max-height: 180px;
  overflow-y: auto;
}
</style>
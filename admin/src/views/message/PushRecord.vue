<!-- @ai-generated -->
<!--
  推送记录查询页面（只读）
  对接 F04 接口：GET /api/v1/admin/message/push-records
  权限：message:manage
-->
<template>
  <div class="push-record-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="模板ID">
          <el-input v-model="filter.template_id" placeholder="按模板ID筛选" clearable style="width: 140px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input v-model="filter.user_id" placeholder="按用户ID筛选" clearable style="width: 140px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="推送状态">
          <el-select v-model="filter.push_status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="成功" :value="1" />
            <el-option label="失败" :value="2" />
            <el-option label="待发送" :value="3" />
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
        <template #col-push_status="{ row }">
          <el-tag :type="pushStatusType(row.push_status)" size="small">
            {{ pushStatusLabel(row.push_status) }}
          </el-tag>
        </template>
      </ProTable>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, onMounted } from 'vue'
import { ElCard, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElButton, ElIcon, ElTag } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import { pushRecordApi, type PushRecord } from '@/api/message'

defineOptions({ name: 'PushRecord' })

const filter = reactive({
  template_id: '',
  user_id: '',
  push_status: undefined as number | undefined,
  page: 1,
  page_size: 20,
})

const tableData = ref<PushRecord[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'template_id', label: '模板ID', width: 100 },
  { prop: 'user_id', label: '用户ID', width: 120 },
  { prop: 'push_status', label: '推送状态', width: 100, align: 'center' },
  { prop: 'push_time', label: '推送时间', width: 170 },
  { prop: 'error_msg', label: '失败原因', minWidth: 200, showOverflowTooltip: true },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

function pushStatusLabel(status: number): string {
  return ({ 1: '成功', 2: '失败', 3: '待发送' } as Record<number, string>)[status] || '未知'
}

function pushStatusType(status: number): 'success' | 'danger' | 'warning' {
  return ({ 1: 'success', 2: 'danger', 3: 'warning' } as Record<number, 'success' | 'danger' | 'warning'>)[status] || 'warning'
}

async function loadData() {
  loading.value = true
  try {
    const res = await pushRecordApi.list({
      page: filter.page,
      page_size: filter.page_size,
      template_id: filter.template_id ? Number(filter.template_id) : undefined,
      user_id: filter.user_id ? Number(filter.user_id) : undefined,
      push_status: filter.push_status,
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
  filter.template_id = ''
  filter.user_id = ''
  filter.push_status = undefined
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

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.push-record-page {
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

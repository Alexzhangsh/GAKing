<!-- @ai-generated -->
<!--
  订阅消息绑定查询页面（只读）
  对接 F04 接口：GET /api/v1/admin/message/subscriptions
  权限：message:manage
-->
<template>
  <div class="subscribe-binding-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="用户ID">
          <el-input v-model="filter.user_id" placeholder="按用户ID筛选" clearable style="width: 140px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="模板ID">
          <el-input v-model="filter.template_id" placeholder="按模板ID筛选" clearable style="width: 140px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="订阅状态">
          <el-select v-model="filter.subscribe_status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="已订阅" :value="1" />
            <el-option label="已取消" :value="0" />
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
        <template #col-subscribe_status="{ row }">
          <el-tag :type="row.subscribe_status === 1 ? 'success' : 'info'" size="small">
            {{ row.subscribe_status === 1 ? '已订阅' : '已取消' }}
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
import { subscribeBindingApi, type SubscribeBinding } from '@/api/message'

defineOptions({ name: 'SubscribeBinding' })

const filter = reactive({
  user_id: '',
  template_id: '',
  subscribe_status: undefined as number | undefined,
  page: 1,
  page_size: 20,
})

const tableData = ref<SubscribeBinding[]>([])
const total = ref(0)
const loading = ref(false)

const columns: ProTableColumn[] = [
  { prop: 'user_id', label: '用户ID', width: 120 },
  { prop: 'template_id', label: '模板ID', width: 100 },
  { prop: 'subscribe_status', label: '订阅状态', width: 100, align: 'center' },
  { prop: 'subscribe_time', label: '订阅时间', width: 170 },
  { prop: 'expire_time', label: '过期时间', width: 170 },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await subscribeBindingApi.list({
      page: filter.page,
      page_size: filter.page_size,
      user_id: filter.user_id ? Number(filter.user_id) : undefined,
      template_id: filter.template_id ? Number(filter.template_id) : undefined,
      subscribe_status: filter.subscribe_status,
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
  filter.user_id = ''
  filter.template_id = ''
  filter.subscribe_status = undefined
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
.subscribe-binding-page {
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

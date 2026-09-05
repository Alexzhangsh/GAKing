<!-- @ai-generated -->
<!--
  角色列表页（RBAC）
  权限：rbac:manage
  功能：角色列表、状态标签、新增/编辑/删除/启用/禁用、权限码批量绑定
-->
<template>
  <div class="role-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="角色名">
          <el-input v-model="filter.keyword" placeholder="角色名搜索" clearable style="width: 180px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filter.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" value="ENABLED" />
            <el-option label="禁用" value="DISABLED" />
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
          <el-button v-permission="'rbac:create'" type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>新增角色
          </el-button>
        </template>

        <template #col-status="{ row }">
          <StatusTag :status="String(row.status)" :map="statusMap" />
        </template>

        <template #col-permissions="{ row }">
          <el-tag
            v-for="p in (row.permissions || []).slice(0, 3)"
            :key="p"
            size="small"
            effect="plain"
            style="margin-right: 4px"
          >
            {{ p }}
          </el-tag>
          <el-tooltip
            v-if="(row.permissions || []).length > 3"
            :content="(row.permissions || []).slice(3).join(', ')"
            placement="top"
          >
            <el-tag size="small" type="info" effect="plain">
              +{{ (row.permissions || []).length - 3 }}
            </el-tag>
          </el-tooltip>
          <span v-if="!row.permissions || row.permissions.length === 0" class="empty-perm">暂无</span>
        </template>

        <template #col-action="{ row }">
          <el-button size="small" link type="primary" @click="handleEdit(row)">编辑</el-button>
          <el-button
            v-if="row.status === true"
            v-permission="'rbac:disable'"
            size="small"
            link
            type="warning"
            @click="handleDisable(row)"
          >
            禁用
          </el-button>
          <el-button
            v-else
            v-permission="'rbac:enable'"
            size="small"
            link
            type="success"
            @click="handleEnable(row)"
          >
            启用
          </el-button>
          <el-button
            v-permission="'rbac:delete'"
            size="small"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 角色表单弹窗 -->
    <RoleFormDialog
      v-model:visible="formVisible"
      :role="currentRole"
      @success="loadData"
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
  ElTag,
  ElTooltip,
  ElMessage,
  ElMessageBox,
} from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import RoleFormDialog from './components/RoleFormDialog.vue'
import {
  rbacApi,
  type RoleItem,
  type RoleListParams,
} from '@/api/rbac'

defineOptions({ name: 'RoleList' })

const filter = reactive<RoleListParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  status: undefined,
})

const tableData = ref<RoleItem[]>([])
const total = ref(0)
const loading = ref(false)

const statusMap: StatusMap = {
  true: { text: '已启用', type: 'success' },
  false: { text: '已禁用', type: 'info' },
}

const columns: ProTableColumn[] = [
  { prop: 'role_name', label: '角色名', width: 160 },
  { prop: 'role_desc', label: '描述', minWidth: 180 },
  { prop: 'status', label: '状态', width: 100, align: 'center' },
  { prop: 'admin_user_count', label: '关联管理员', width: 110, align: 'right' },
  { prop: 'permissions', label: '权限码', minWidth: 240 },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await rbacApi.list({
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

// ── 表单弹窗 ──────────────
const formVisible = ref(false)
const currentRole = ref<RoleItem | null>(null)

function handleAdd() {
  currentRole.value = null
  formVisible.value = true
}

function handleEdit(row: RoleItem) {
  currentRole.value = row
  formVisible.value = true
}

// ── 启用/禁用/删除 ──────────────
async function handleEnable(row: RoleItem) {
  try {
    await ElMessageBox.confirm(
      `确认启用角色「${row.role_name}」？启用后该角色下的管理员将立即获得对应权限。`,
      '启用确认',
      { type: 'warning' }
    )
    await rbacApi.update(row.id, {
      role_name: row.role_name,
      role_desc: row.role_desc,
      permissions: row.permissions,
      status: true,
    })
    ElMessage.success('已启用')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleDisable(row: RoleItem) {
  try {
    await ElMessageBox.confirm(
      `确认禁用角色「${row.role_name}」？禁用后该角色下的管理员将立即失去对应权限。`,
      '禁用确认',
      { type: 'warning' }
    )
    await rbacApi.update(row.id, {
      role_name: row.role_name,
      role_desc: row.role_desc,
      permissions: row.permissions,
      status: false,
    })
    ElMessage.success('已禁用')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleDelete(row: RoleItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除角色「${row.role_name}」？删除操作不可恢复！${
        row.admin_user_count > 0 ? `（注意：该角色下仍有 ${row.admin_user_count} 个管理员，请先转移或删除关联账号）` : ''
      }`,
      '删除确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await rbacApi.remove(row.id)
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
.role-list-page {
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

.empty-perm {
  color: #c0c4cc;
  font-size: 12px;
  font-weight: 300;
}
</style>

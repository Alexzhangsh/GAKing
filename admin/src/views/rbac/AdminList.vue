<!-- @ai-generated -->
<!--
  管理员账号列表页
  权限：rbac:manage
  功能：管理员列表、筛选、新增/编辑/删除、分配角色、重置密码、冻结/解冻
-->
<template>
  <div class="admin-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="filter.keyword"
            placeholder="用户名/真实姓名/手机号"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filter.role_id" placeholder="全部角色" clearable style="width: 160px">
            <el-option v-for="r in roleOptions" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filter.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="正常" value="NORMAL" />
            <el-option label="冻结" value="FROZEN" />
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
        :action-width="240"
        row-key="id"
        show-index
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
      >
        <template #toolbar>
          <el-button v-permission="'rbac:create'" type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>新增管理员
          </el-button>
        </template>

        <template #col-status="{ row }">
          <StatusTag :status="String(row.status)" :map="statusMap" />
        </template>

        <template #col-role_name="{ row }">
          <el-tag size="small" type="primary" effect="plain">{{ row.role_name }}</el-tag>
        </template>

        <template #col-action="{ row }">
          <div class="action-btns">
            <el-button v-permission="'rbac:update'" size="small" link type="primary" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              v-permission="'rbac:update'"
              size="small"
              link
              type="warning"
              @click="handleResetPassword(row)"
            >
              重置密码
            </el-button>
            <el-button
              v-if="row.status === true"
              v-permission="'rbac:freeze'"
              size="small"
              link
              type="danger"
              @click="handleFreeze(row)"
            >
              冻结
            </el-button>
            <el-button
              v-else
              v-permission="'rbac:unfreeze'"
              size="small"
              link
              type="success"
              @click="handleUnfreeze(row)"
            >
              解冻
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
          </div>
        </template>
      </ProTable>
    </el-card>

    <!-- 表单弹窗 -->
    <AdminFormDialog
      v-model:visible="formVisible"
      :admin="currentAdmin"
      :roles="roleOptions"
      @success="loadData"
    />

    <!-- 重置密码弹窗 -->
    <el-dialog
      v-model="resetDialogVisible"
      title="重置密码"
      width="420px"
      append-to-body
      destroy-on-close
    >
      <el-form v-if="resetTarget" :model="resetForm" :rules="resetRules" ref="resetFormRef" label-width="90px">
        <el-form-item label="目标账号">
          <span class="reset-target">{{ resetTarget.username }}（{{ resetTarget.real_name }}）</span>
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="resetForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetLoading" @click="submitResetPassword">
          确认重置
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
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElTag,
  ElMessage,
  ElMessageBox,
  ElDialog,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import AdminFormDialog from './components/AdminFormDialog.vue'
import { adminApi, type AdminItem, type AdminListParams } from '@/api/admin'
import { rbacApi, type RoleItem } from '@/api/rbac'

defineOptions({ name: 'AdminList' })

const filter = reactive<AdminListParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  role_id: undefined,
  status: undefined,
})

const tableData = ref<AdminItem[]>([])
const total = ref(0)
const loading = ref(false)
const roleOptions = ref<RoleItem[]>([])

const statusMap: StatusMap = {
  true: { text: '正常', type: 'success' },
  false: { text: '已冻结', type: 'danger' },
}

const columns: ProTableColumn[] = [
  { prop: 'username', label: '用户名', minWidth: 140 },
  { prop: 'real_name', label: '真实姓名', width: 120 },
  { prop: 'role_name', label: '角色', width: 140 },
  { prop: 'status', label: '状态', width: 90, align: 'center' },
  { prop: 'phone', label: '手机号', width: 130 },
  { prop: 'email', label: '邮箱', width: 180 },
  { prop: 'create_time', label: '创建时间', width: 170 },
]

// ── 角色选项加载 ──────────────
async function loadRoleOptions() {
  try {
    const res = await rbacApi.list({ page: 1, page_size: 200 })
    roleOptions.value = res.items || []
  } catch {
    roleOptions.value = []
  }
}

// ── 数据加载 ──────────────
async function loadData() {
  loading.value = true
  try {
    const res = await adminApi.list({
      keyword: filter.keyword || undefined,
      role_id: filter.role_id,
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
  filter.role_id = undefined
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
const currentAdmin = ref<AdminItem | null>(null)

function handleAdd() {
  currentAdmin.value = null
  formVisible.value = true
}

function handleEdit(row: AdminItem) {
  currentAdmin.value = row
  formVisible.value = true
}

// ── 重置密码 ──────────────
const resetDialogVisible = ref(false)
const resetTarget = ref<AdminItem | null>(null)
const resetLoading = ref(false)
const resetFormRef = ref<FormInstance>()
const resetForm = reactive({
  new_password: '',
  confirm_password: '',
})
const resetRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== resetForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function handleResetPassword(row: AdminItem) {
  resetTarget.value = row
  resetForm.new_password = ''
  resetForm.confirm_password = ''
  resetDialogVisible.value = true
}

async function submitResetPassword() {
  if (!resetFormRef.value || !resetTarget.value) return
  await resetFormRef.value.validate(async (valid) => {
    if (!valid) return
    resetLoading.value = true
    try {
      await adminApi.resetPassword(resetTarget.value!.id, {
        new_password: resetForm.new_password,
      })
      ElMessage.success('密码重置成功')
      resetDialogVisible.value = false
    } catch {
      // 拦截器已提示
    } finally {
      resetLoading.value = false
    }
  })
}

// ── 冻结/解冻/删除 ──────────────
async function handleFreeze(row: AdminItem) {
  try {
    await ElMessageBox.prompt(
      `确认冻结账号「${row.username}」？冻结后该账号将无法登录。`,
      '冻结确认',
      {
        inputPattern: /.+/,
        inputErrorMessage: '请填写冻结原因',
        inputPlaceholder: '冻结原因（必填）',
        type: 'warning',
        confirmButtonText: '确认冻结',
      }
    )
    await adminApi.update(row.id, { status: false, role_id: row.role_id })
    ElMessage.success('已冻结')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleUnfreeze(row: AdminItem) {
  try {
    await ElMessageBox.confirm(
      `确认解冻账号「${row.username}」？`,
      '解冻确认',
      { type: 'success' }
    )
    await adminApi.update(row.id, { status: true, role_id: row.role_id })
    ElMessage.success('已解冻')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleDelete(row: AdminItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除管理员「${row.username}」？此操作不可恢复！`,
      '删除确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await adminApi.remove(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

onMounted(() => {
  loadRoleOptions()
  loadData()
})
</script>

<style scoped>
.admin-list-page {
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

.reset-target {
  color: #303133;
  font-weight: 500;
}

.action-btns {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
}
</style>

<!-- @ai-generated -->
<!--
  用户/会员 列表页
  对接：GET /api/v1/admin/user
  权限：user:manage
  功能：用户列表、筛选、详情弹窗（含金角币/佣金流水）、冻结/解冻
-->
<template>
  <div class="user-list-page">
    <!-- 筛选区 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filter" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="filter.keyword"
            placeholder="昵称/手机号/用户ID"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="用户类型">
          <el-select v-model="filter.user_type" placeholder="全部" clearable style="width: 140px">
            <el-option label="普通用户" value="NORMAL" />
            <el-option label="付费会员" value="VIP" />
          </el-select>
        </el-form-item>
        <el-form-item label="账户状态">
          <el-select v-model="filter.status" placeholder="全部" clearable style="width: 140px">
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
        row-key="id"
        show-index
        @page-change="handlePageChange"
        @size-change="handleSizeChange"
      >
        <template #col-avatar="{ row }">
          <el-avatar :size="40" :src="row.avatar">{{ (row.nickname || 'U').charAt(0) }}</el-avatar>
        </template>

        <template #col-user_type="{ row }">
          <el-tag
            :type="row.user_type === 'VIP' ? 'warning' : 'info'"
            size="small"
            effect="plain"
          >
            {{ row.user_type === 'VIP' ? '付费会员' : '普通用户' }}
          </el-tag>
        </template>

        <template #col-status="{ row }">
          <StatusTag
            :status="row.status"
            :map="userStatusMap"
          />
        </template>

        <template #col-gold_coin_balance="{ row }">
          <span class="coin">{{ row.gold_coin_balance }}</span>
        </template>
        <template #col-commission_balance="{ row }">
          <span class="commission">¥{{ row.commission_balance }}</span>
        </template>

        <template #col-action="{ row }">
          <el-button size="small" link type="primary" @click="handleDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'NORMAL'"
            v-permission="'user:freeze'"
            size="small"
            link
            type="danger"
            @click="handleFreeze(row)"
          >
            冻结
          </el-button>
          <el-button
            v-else
            v-permission="'user:unfreeze'"
            size="small"
            link
            type="success"
            @click="handleUnfreeze(row)"
          >
            解冻
          </el-button>
        </template>
      </ProTable>
    </el-card>

    <!-- 详情弹窗 -->
    <UserDetailDialog
      v-model:visible="detailVisible"
      :user-id="currentUserId"
      @refresh="loadData"
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
  ElAvatar,
  ElTag,
  ElMessage,
  ElMessageBox,
} from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import UserDetailDialog from './components/UserDetailDialog.vue'
import {
  userApi,
  UserStatus,
  type UserItem,
  type UserListParams,
} from '@/api/user'

defineOptions({ name: 'UserList' })

const filter = reactive<UserListParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  user_type: undefined,
  status: undefined,
})

const tableData = ref<UserItem[]>([])
const total = ref(0)
const loading = ref(false)

const userStatusMap: StatusMap = {
  NORMAL: { text: '正常', type: 'success' },
  FROZEN: { text: '已冻结', type: 'danger' },
}

const columns: ProTableColumn[] = [
  { prop: 'avatar', label: '头像', width: 80, align: 'center' },
  { prop: 'nickname', label: '昵称', width: 140 },
  { prop: 'phone', label: '手机号', width: 130 },
  { prop: 'user_type', label: '类型', width: 100, align: 'center' },
  { prop: 'status', label: '状态', width: 90, align: 'center' },
  { prop: 'gold_coin_balance', label: '金角币', width: 100, align: 'right' },
  { prop: 'commission_balance', label: '佣金账户', width: 120, align: 'right' },
  { prop: 'order_count', label: '订单数', width: 90, align: 'right' },
  { prop: 'total_withdrawn', label: '累计提现', width: 120, align: 'right' },
  { prop: 'register_time', label: '注册时间', width: 170 },
  { prop: 'last_login_time', label: '最近登录', width: 170 },
]

async function loadData() {
  loading.value = true
  try {
    const res = await userApi.list({
      keyword: filter.keyword || undefined,
      user_type: filter.user_type,
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
  filter.user_type = undefined
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

// ── 详情弹窗 ──────────────
const detailVisible = ref(false)
const currentUserId = ref<number>(0)
function handleDetail(row: UserItem) {
  currentUserId.value = row.id
  detailVisible.value = true
}

// ── 冻结/解冻 ──────────────
async function handleFreeze(row: UserItem) {
  try {
    const { value } = await ElMessageBox.prompt(
      `确认冻结用户「${row.nickname || row.id}」？冻结后该用户无法登录及发起订单。`,
      '冻结确认',
      {
        inputPattern: /.+/,
        inputErrorMessage: '请填写冻结原因',
        inputPlaceholder: '冻结原因（必填）',
        type: 'warning',
        confirmButtonText: '确认冻结',
      }
    )
    await userApi.freeze(row.id, {
      target_status: UserStatus.FROZEN,
      reason: value,
    })
    ElMessage.success('已冻结')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

async function handleUnfreeze(row: UserItem) {
  try {
    await ElMessageBox.confirm(
      `确认解冻用户「${row.nickname || row.id}」？`,
      '解冻确认',
      { type: 'success' }
    )
    await userApi.unfreeze(row.id, { target_status: UserStatus.NORMAL })
    ElMessage.success('已解冻')
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
.user-list-page {
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

.coin {
  color: #e6a23c;
  font-weight: 500;
}

.commission {
  color: #409eff;
  font-weight: 300;
}
</style>

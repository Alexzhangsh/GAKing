<!-- @ai-generated -->
<!--
  渠道配置页面（Tab：参数配置 + 数据看板）
  Tab1 参数配置：渠道CRUD（对接 /api/v1/admin/channel）
  Tab2 数据看板：渠道佣金统计 + 订单趋势（复用 dashboardApi）
  权限：config:manage
-->
<template>
  <div class="channel-config-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 参数配置 -->
      <el-tab-pane label="参数配置" name="params">
        <ProTable
          :data="channelList"
          :columns="channelColumns"
          :loading="channelLoading"
          :pagination="{ page: channelPage, page_size: channelPageSize, total: channelTotal }"
          row-key="id"
          show-index
          @page-change="(p) => { channelPage = p; loadChannels() }"
          @size-change="(s) => { channelPageSize = s; channelPage = 1; loadChannels() }"
        >
          <template #toolbar>
            <el-button type="primary" v-permission="'config:manage'" @click="handleAddChannel">
              <el-icon><Plus /></el-icon>新增渠道
            </el-button>
          </template>

          <template #col-channel_code="{ row }">
            <el-tag size="small">{{ channelLabel(row.channel_code) }}</el-tag>
          </template>

          <template #col-settle_rate="{ row }">
            {{ (row.settle_rate * 100).toFixed(1) }}%
          </template>

          <template #col-status="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>

          <template #col-action="{ row }">
            <el-button size="small" link type="primary" @click="handleEditChannel(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="handleDeleteChannel(row)">删除</el-button>
          </template>
        </ProTable>
      </el-tab-pane>

      <!-- Tab 2: 数据看板 -->
      <el-tab-pane label="数据看板" name="dashboard">
        <div class="dashboard-area">
          <!-- 日期范围选择 -->
          <el-form :inline="true" class="dashboard-filter">
            <el-form-item label="日期范围">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 280px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadDashboard">查询</el-button>
            </el-form-item>
          </el-form>

          <!-- 渠道佣金统计 -->
          <el-card shadow="never" class="stat-card">
            <template #header>按渠道佣金统计</template>
            <el-table :data="channelStats" border style="width: 100%" v-loading="dashboardLoading">
              <el-table-column prop="channel_code" label="渠道" width="120">
                <template #default="{ row }">
                  <el-tag size="small">{{ channelLabel(row.channel_code) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="total_commission" label="佣金总额" width="160" />
              <el-table-column prop="order_count" label="订单数" width="120" />
            </el-table>
            <el-empty v-if="!dashboardLoading && channelStats.length === 0" description="暂无数据" :image-size="60" />
          </el-card>

          <!-- 订单趋势 -->
          <el-card shadow="never" class="stat-card">
            <template #header>订单趋势</template>
            <el-table :data="orderTrend" border style="width: 100%" v-loading="dashboardLoading">
              <el-table-column prop="date" label="日期" width="140" />
              <el-table-column prop="order_count" label="订单数" width="120" />
              <el-table-column prop="total_commission" label="佣金总额" width="160" />
            </el-table>
            <el-empty v-if="!dashboardLoading && orderTrend.length === 0" description="暂无数据" :image-size="60" />
          </el-card>
        </div>
      </el-tab-pane>

      <!-- Tab 3: 佣金策略（F04-2） -->
      <el-tab-pane label="佣金策略" name="commission">
        <CommissionStrategyTab />
      </el-tab-pane>
    </el-tabs>

    <!-- 渠道编辑弹窗 -->
    <el-dialog v-model="channelDialogVisible" :title="channelDialogTitle" width="560px">
      <el-form ref="channelFormRef" :model="channelForm" :rules="channelRules" label-width="120px">
        <el-form-item label="渠道标识" prop="channel_code">
          <el-select v-model="channelForm.channel_code" placeholder="选择渠道" :disabled="isEditChannel" style="width: 100%">
            <el-option label="喵有券 (myq)" value="myq" />
            <el-option label="订单侠 (orderx)" value="orderx" />
          </el-select>
        </el-form-item>
        <el-form-item label="渠道名称">
          <el-input v-model="channelForm.channel_name" placeholder="渠道中文名称" />
        </el-form-item>
        <el-form-item label="API Token">
          <el-input v-model="channelForm.api_token" placeholder="渠道API Token" />
        </el-form-item>
        <el-form-item label="API Secret">
          <el-input v-model="channelForm.api_secret" placeholder="渠道API密钥" type="password" show-password />
        </el-form-item>
        <el-form-item label="推广位PID">
          <el-input v-model="channelForm.pid" placeholder="渠道推广位PID" />
        </el-form-item>
        <el-form-item label="结算比例">
          <el-input-number v-model="channelForm.settle_rate" :min="0" :max="1" :step="0.01" :precision="2" />
          <span class="rate-hint">{{ ((channelForm.settle_rate ?? 0) * 100).toFixed(1) }}%</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="channelForm.status" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="channelForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="channelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="channelSubmitting" @click="handleSubmitChannel">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, onMounted } from 'vue'
import {
  ElTabs, ElTabPane, ElCard, ElForm, ElFormItem, ElInput, ElInputNumber,
  ElSelect, ElOption, ElButton, ElIcon, ElTag, ElSwitch, ElTable, ElTableColumn,
  ElDatePicker, ElEmpty, ElDialog, ElMessage, ElMessageBox, type FormInstance,
} from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import { channelConfigApi, type ChannelConfig, type ChannelConfigCreate } from '@/api/channel'
import { dashboardApi, type CommissionStatsByChannelItem, type OrderTrendItem } from '@/api/dashboard'
import CommissionStrategyTab from './CommissionStrategyTab.vue'

defineOptions({ name: 'ChannelConfig' })

const activeTab = ref('params')

// ── 渠道名称映射 ──────────────
function channelLabel(code: string): string {
  const map: Record<string, string> = { myq: '喵有券', orderx: '订单侠', dta: '大淘客' }
  return map[code] || code
}

// ════════════════════════════════════════════════════════════
// Tab 1: 参数配置
// ════════════════════════════════════════════════════════════

const channelList = ref<ChannelConfig[]>([])
const channelLoading = ref(false)
const channelPage = ref(1)
const channelPageSize = ref(20)
const channelTotal = ref(0)

const channelColumns: ProTableColumn[] = [
  { prop: 'channel_code', label: '渠道标识', width: 100, align: 'center' },
  { prop: 'channel_name', label: '渠道名称', width: 120 },
  { prop: 'api_token', label: 'API Token', width: 200, showOverflowTooltip: true },
  { prop: 'pid', label: '推广位PID', width: 140 },
  { prop: 'settle_rate', label: '结算比例', width: 100, align: 'right' },
  { prop: 'status', label: '状态', width: 80, align: 'center' },
  { prop: 'remark', label: '备注', minWidth: 160, showOverflowTooltip: true },
  { prop: 'update_time', label: '更新时间', width: 170 },
]

async function loadChannels() {
  channelLoading.value = true
  try {
    const res = await channelConfigApi.list({ page: channelPage.value, page_size: channelPageSize.value })
    channelList.value = res.items || []
    channelTotal.value = res.total || 0
  } catch {
    channelList.value = []
    channelTotal.value = 0
  } finally {
    channelLoading.value = false
  }
}

// 渠道弹窗
const channelDialogVisible = ref(false)
const channelDialogTitle = ref('新增渠道')
const channelFormRef = ref<FormInstance>()
const channelSubmitting = ref(false)
const editingChannelCode = ref<string | null>(null)
const isEditChannel = computed(() => !!editingChannelCode.value)

const channelForm = reactive<ChannelConfigCreate>({
  channel_code: '',
  channel_name: '',
  api_token: '',
  api_secret: '',
  pid: '',
  settle_rate: 0.8,
  status: true,
  remark: '',
})

const channelRules = {
  channel_code: [{ required: true, message: '请选择渠道', trigger: 'change' }],
}

function handleAddChannel() {
  editingChannelCode.value = null
  channelDialogTitle.value = '新增渠道'
  Object.assign(channelForm, {
    channel_code: '', channel_name: '', api_token: '', api_secret: '',
    pid: '', settle_rate: 0.8, status: true, remark: '',
  })
  channelDialogVisible.value = true
}

function handleEditChannel(row: ChannelConfig) {
  editingChannelCode.value = row.channel_code
  channelDialogTitle.value = '编辑渠道'
  Object.assign(channelForm, {
    channel_code: row.channel_code,
    channel_name: row.channel_name,
    api_token: row.api_token,
    api_secret: '',  // 后端脱敏返回***，编辑时留空表示不修改
    pid: row.pid,
    settle_rate: row.settle_rate,
    status: row.status,
    remark: row.remark,
  })
  channelDialogVisible.value = true
}

async function handleSubmitChannel() {
  if (!channelFormRef.value) return
  await channelFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    channelSubmitting.value = true
    try {
      if (isEditChannel.value && editingChannelCode.value) {
        const data = { ...channelForm }
        // api_secret 为空时不传（不修改）
        if (!data.api_secret) delete data.api_secret
        if (!data.api_token) delete data.api_token
        await channelConfigApi.update(editingChannelCode.value, data)
        ElMessage.success('更新成功')
      } else {
        await channelConfigApi.create(channelForm)
        ElMessage.success('创建成功')
      }
      channelDialogVisible.value = false
      loadChannels()
    } catch {
      // 拦截器已提示
    } finally {
      channelSubmitting.value = false
    }
  })
}

async function handleDeleteChannel(row: ChannelConfig) {
  try {
    await ElMessageBox.confirm(
      `确认删除渠道「${channelLabel(row.channel_code)}」？`,
      '危险操作确认',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await channelConfigApi.delete(row.channel_code)
    ElMessage.success('删除成功')
    loadChannels()
  } catch (e) {
    if (e !== 'cancel') {
      // 拦截器已提示
    }
  }
}

// ════════════════════════════════════════════════════════════
// Tab 2: 数据看板
// ════════════════════════════════════════════════════════════

const dateRange = ref<[string, string] | null>(null)
const dashboardLoading = ref(false)
const channelStats = ref<CommissionStatsByChannelItem[]>([])
const orderTrend = ref<OrderTrendItem[]>([])

async function loadDashboard() {
  if (!dateRange.value || dateRange.value.length < 2) {
    ElMessage.warning('请选择日期范围')
    return
  }
  dashboardLoading.value = true
  try {
    const [startDate, endDate] = dateRange.value
    const [stats, trend] = await Promise.all([
      dashboardApi.getCommissionStats({ group_by: 'channel', start_date: startDate, end_date: endDate }),
      dashboardApi.getOrderTrend({ start_date: startDate, end_date: endDate }),
    ])
    channelStats.value = (stats as CommissionStatsByChannelItem[]) || []
    orderTrend.value = (trend as OrderTrendItem[]) || []
  } catch {
    channelStats.value = []
    orderTrend.value = []
  } finally {
    dashboardLoading.value = false
  }
}

onMounted(() => {
  loadChannels()
})
</script>

<style scoped>
.channel-config-page {
  display: flex;
  flex-direction: column;
}

.dashboard-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-filter {
  margin-bottom: 8px;
}

.stat-card {
  margin-bottom: 0;
}

.rate-hint {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}
</style>

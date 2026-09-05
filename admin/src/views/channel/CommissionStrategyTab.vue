<!-- @ai-generated -->
<!--
  渠道佣金策略 Tab（F04-2）
  - 佣金策略列表：渠道筛选 + 生效状态筛选 + 分页 + 导出
  - 策略编辑弹窗：策略名称、阶梯维度、生效开关、阶梯明细配置
  - 阶梯明细：按普通用户/付费会员分别配置 N 条阶梯，每条阶梯有双比例
  - 实时预览弹窗：输入金额/数量，查看命中的阶梯和分佣结果
  - 变更审计记录：切换 Tab 查看操作历史
  - 权限：config:manage
-->
<template>
  <div class="commission-strategy-tab">
    <!-- 子 Tab：策略列表 / 审计记录 -->
    <el-tabs v-model="subTab" type="card" class="sub-tabs">
      <!-- ─── Tab 1: 佣金策略列表 ──────────────────────── -->
      <el-tab-pane label="佣金策略" name="strategy">
        <ProTable
          :data="strategyList"
          :columns="strategyColumns"
          :loading="strategyLoading"
          :pagination="{ page: strategyPage, page_size: strategyPageSize, total: strategyTotal }"
          row-key="id"
          show-index
          @page-change="(p) => { strategyPage = p; loadStrategies() }"
          @size-change="(s) => { strategyPageSize = s; strategyPage = 1; loadStrategies() }"
        >
          <template #toolbar>
            <el-form :inline="true" class="filter-form">
              <el-form-item label="渠道">
                <el-select v-model="filterChannel" placeholder="全部渠道" clearable style="width: 140px" @change="onFilterChange">
                  <el-option label="喵有券" value="myq" />
                  <el-option label="订单侠" value="orderx" />
                  <el-option label="大淘客" value="dta" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="filterEnabled" placeholder="全部" clearable style="width: 120px" @change="onFilterChange">
                  <el-option label="生效" :value="true" />
                  <el-option label="停用" :value="false" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" v-permission="'config:manage'" @click="handleAddStrategy">
                  <el-icon><Plus /></el-icon>新增策略
                </el-button>
              </el-form-item>
              <el-form-item>
                <el-button :loading="exportLoading" @click="handleExport">
                  <el-icon><Download /></el-icon>导出
                </el-button>
              </el-form-item>
            </el-form>
          </template>

          <template #col-channel_code="{ row }">
            <el-tag size="small">{{ channelLabel(row.channel_code) }}</el-tag>
          </template>

          <template #col-enabled="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">
              {{ row.enabled ? '生效' : '停用' }}
            </el-tag>
          </template>

          <template #col-tier_dimension="{ row }">
            {{ row.tier_dimension_label }}
          </template>

          <template #col-action="{ row }">
            <el-button size="small" link type="primary" @click="handleEditStrategy(row)">编辑</el-button>
            <el-button size="small" link type="primary" @click="handlePreview(row)">预览</el-button>
            <el-button size="small" link :type="row.enabled ? 'warning' : 'success'" @click="handleToggle(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
          </template>
        </ProTable>
      </el-tab-pane>

      <!-- ─── Tab 2: 变更审计记录 ──────────────────────── -->
      <el-tab-pane label="变更审计记录" name="audit">
        <div class="audit-filter">
          <el-form :inline="true">
            <el-form-item label="渠道">
              <el-select v-model="auditFilterChannel" placeholder="全部渠道" clearable style="width: 140px" @change="loadAuditLogs">
                <el-option label="喵有券" value="myq" />
                <el-option label="订单侠" value="orderx" />
                <el-option label="大淘客" value="dta" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>
        <ProTable
          :data="auditLogList"
          :columns="auditColumns"
          :loading="auditLoading"
          :pagination="{ page: auditPage, page_size: auditPageSize, total: auditTotal }"
          row-key="id"
          show-index
          @page-change="(p) => { auditPage = p; loadAuditLogs() }"
          @size-change="(s) => { auditPageSize = s; auditPage = 1; loadAuditLogs() }"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- ─── 策略编辑弹窗（新增/编辑公用） ────────────────── -->
    <el-dialog
      v-model="strategyDialogVisible"
      :title="strategyDialogTitle"
      width="720px"
      top="5vh"
      @close="handleDialogClose"
    >
      <el-form ref="strategyFormRef" :model="strategyForm" :rules="strategyRules" label-width="140px">
        <el-form-item label="渠道" prop="channel_code">
          <el-select v-model="strategyForm.channel_code" placeholder="选择渠道" :disabled="isEditStrategy" style="width: 100%">
            <el-option label="喵有券 (myq)" value="myq" />
            <el-option label="订单侠 (orderx)" value="orderx" />
            <el-option label="大淘客 (dta)" value="dta" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略名称" prop="strategy_name">
          <el-input v-model="strategyForm.strategy_name" placeholder="如：2026年Q3阶梯佣金" maxlength="128" />
        </el-form-item>
        <el-form-item label="阶梯维度" prop="tier_dimension">
          <el-radio-group v-model="strategyForm.tier_dimension">
            <el-radio :value="1">按订单金额</el-radio>
            <el-radio :value="2">按订单数量</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="生效开关">
          <el-switch v-model="strategyForm.enabled" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="strategyForm.remark" type="textarea" :rows="2" maxlength="512" />
        </el-form-item>

        <!-- ─── 阶梯佣金配置 ────────────────────────────── -->
        <el-divider content-position="left">阶梯佣金配置</el-divider>

        <el-form-item label="普通用户阶梯">
          <div class="tier-list">
            <div
              v-for="(tier, idx) in normalTiers"
              :key="'normal-' + idx"
              class="tier-card"
            >
              <div class="tier-header">
                <span class="tier-label">阶梯 {{ idx + 1 }}</span>
                <el-button text type="danger" size="small" @click="removeNormalTier(idx)">删除</el-button>
              </div>
              <div class="tier-body">
                <el-form-item v-if="strategyForm.tier_dimension === 1" label="订单金额区间" class="tier-form-item">
                  <el-input-number v-model="tier.tier_min" :min="0" :precision="2" size="small" style="width: 120px" />
                  <span class="tier-sep">~</span>
                  <el-input-number v-model="tier.tier_max" :min="0" :precision="2" size="small" style="width: 120px" :disabled="tier.tier_max === 0" />
                  <el-checkbox v-model="tier._unlimited" size="small" style="margin-left: 8px" @change="onUnlimitedChange(tier)">无上限</el-checkbox>
                </el-form-item>
                <el-form-item v-else label="订单数量区间" class="tier-form-item">
                  <el-input-number v-model="tier.tier_min" :min="0" :step="1" size="small" style="width: 120px" />
                  <span class="tier-sep">~</span>
                  <el-input-number v-model="tier.tier_max" :min="0" :step="1" size="small" style="width: 120px" :disabled="tier.tier_max === 0" />
                  <el-checkbox v-model="tier._unlimited" size="small" style="margin-left: 8px" @change="onUnlimitedChange(tier)">无上限</el-checkbox>
                </el-form-item>
                <div class="tier-rates">
                  <el-form-item label="用户返利" class="rate-item">
                    <el-input-number v-model="tier.user_commission_rate" :min="0" :max="1" :step="0.01" :precision="4" size="small" style="width: 130px" />
                    <span class="rate-pct">{{ (tier.user_commission_rate * 100).toFixed(2) }}%</span>
                  </el-form-item>
                  <el-form-item label="平台留存" class="rate-item">
                    <el-input-number v-model="tier.platform_retention_rate" :min="0" :max="1" :step="0.01" :precision="4" size="small" style="width: 130px" />
                    <span class="rate-pct">{{ (tier.platform_retention_rate * 100).toFixed(2) }}%</span>
                  </el-form-item>
                  <el-button v-if="autoSyncRates" text size="small" type="info" @click="syncRates(tier)">补全</el-button>
                </div>
              </div>
            </div>
            <el-button size="small" @click="addNormalTier">+ 新增普通用户阶梯</el-button>
          </div>
        </el-form-item>

        <el-form-item label="付费会员阶梯">
          <div class="tier-list">
            <div
              v-for="(tier, idx) in vipTiers"
              :key="'vip-' + idx"
              class="tier-card"
            >
              <div class="tier-header">
                <span class="tier-label">阶梯 {{ idx + 1 }}</span>
                <el-button text type="danger" size="small" @click="removeVipTier(idx)">删除</el-button>
              </div>
              <div class="tier-body">
                <el-form-item v-if="strategyForm.tier_dimension === 1" label="订单金额区间" class="tier-form-item">
                  <el-input-number v-model="tier.tier_min" :min="0" :precision="2" size="small" style="width: 120px" />
                  <span class="tier-sep">~</span>
                  <el-input-number v-model="tier.tier_max" :min="0" :precision="2" size="small" style="width: 120px" :disabled="tier.tier_max === 0" />
                  <el-checkbox v-model="tier._unlimited" size="small" style="margin-left: 8px" @change="onUnlimitedChange(tier)">无上限</el-checkbox>
                </el-form-item>
                <el-form-item v-else label="订单数量区间" class="tier-form-item">
                  <el-input-number v-model="tier.tier_min" :min="0" :step="1" size="small" style="width: 120px" />
                  <span class="tier-sep">~</span>
                  <el-input-number v-model="tier.tier_max" :min="0" :step="1" size="small" style="width: 120px" :disabled="tier.tier_max === 0" />
                  <el-checkbox v-model="tier._unlimited" size="small" style="margin-left: 8px" @change="onUnlimitedChange(tier)">无上限</el-checkbox>
                </el-form-item>
                <div class="tier-rates">
                  <el-form-item label="用户返利" class="rate-item">
                    <el-input-number v-model="tier.user_commission_rate" :min="0" :max="1" :step="0.01" :precision="4" size="small" style="width: 130px" />
                    <span class="rate-pct">{{ (tier.user_commission_rate * 100).toFixed(2) }}%</span>
                  </el-form-item>
                  <el-form-item label="平台留存" class="rate-item">
                    <el-input-number v-model="tier.platform_retention_rate" :min="0" :max="1" :step="0.01" :precision="4" size="small" style="width: 130px" />
                    <span class="rate-pct">{{ (tier.platform_retention_rate * 100).toFixed(2) }}%</span>
                  </el-form-item>
                  <el-button v-if="autoSyncRates" text size="small" type="info" @click="syncRates(tier)">补全</el-button>
                </div>
              </div>
            </div>
            <el-button size="small" @click="addVipTier">+ 新增付费会员阶梯</el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="strategyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="strategySubmitting" @click="handleSubmitStrategy">确定</el-button>
      </template>
    </el-dialog>

    <!-- ─── 分佣预览弹窗 ──────────────────────────────── -->
    <el-dialog v-model="previewVisible" title="分佣预览" width="520px">
      <el-form ref="previewFormRef" :model="previewForm" :rules="previewRules" label-width="120px">
        <el-form-item label="用户类型">
          <el-radio-group v-model="previewForm.user_type">
            <el-radio :value="1">普通用户</el-radio>
            <el-radio :value="2">付费会员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="previewStrategy?.tier_dimension === 1" label="订单金额" prop="amount">
          <el-input-number v-model="previewForm.amount" :min="0" :precision="2" style="width: 200px" />
        </el-form-item>
        <el-form-item v-else label="订单数量" prop="order_count">
          <el-input-number v-model="previewForm.order_count" :min="0" :step="1" style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="previewLoading" @click="handleDoPreview">预览分佣</el-button>
        </el-form-item>
      </el-form>

      <el-divider v-if="previewResult" />
      <div v-if="previewResult" class="preview-result">
        <div v-if="!previewResult.enabled" class="preview-disabled">策略未生效，当前按默认比例结算</div>
        <template v-else-if="previewResult.matched_tier">
          <div class="preview-matched">
            <span class="preview-label">命中阶梯：</span>
            <span class="preview-value">{{ previewResult.matched_tier.tier_name || `用户${previewResult.matched_tier.user_type === 1 ? '普通' : '会员'}阶梯` }}</span>
          </div>
          <div class="preview-detail">
            <div class="preview-row">
              <span class="preview-label">用户返利比例：</span>
              <span class="preview-value">{{ (previewResult.matched_tier.user_commission_rate * 100).toFixed(2) }}%</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">平台留存比例：</span>
              <span class="preview-value">{{ (previewResult.matched_tier.platform_retention_rate * 100).toFixed(2) }}%</span>
            </div>
            <el-divider />
            <div class="preview-row">
              <span class="preview-label">总佣金：</span>
              <span class="preview-value">¥{{ previewResult.result?.total_commission ?? '-' }}</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">用户佣金：</span>
              <span class="preview-value highlight">¥{{ previewResult.result?.user_commission ?? '-' }}</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">平台佣金：</span>
              <span class="preview-value">¥{{ previewResult.result?.platform_commission ?? '-' }}</span>
            </div>
          </div>
        </template>
        <div v-else class="preview-disabled">未命中任何阶梯规则，请检查阶梯区间配置</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, onMounted } from 'vue'
import {
  ElTabs, ElTabPane, ElForm, ElFormItem, ElInput, ElInputNumber,
  ElSelect, ElOption, ElButton, ElIcon, ElTag, ElSwitch, ElRadioGroup, ElRadio,
  ElDivider, ElCheckbox, ElDialog, ElMessage, type FormInstance,
} from 'element-plus'
import { Plus, Download } from '@element-plus/icons-vue'
import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import {
  channelCommissionApi,
  type CommissionStrategy,
  type CommissionStrategyCreate,
  type CommissionStrategyUpdate,
  type CommissionTier,
  type CommissionPreviewResult,
  type StrategyAuditLog,
} from '@/api/channel'
import { exportToExcel, type ExcelColumn } from '@/utils/excel'

defineOptions({ name: 'CommissionStrategyTab' })

// ── 渠道名称映射 ──────────────
function channelLabel(code: string): string {
  const map: Record<string, string> = { myq: '喵有券', orderx: '订单侠', dta: '大淘客' }
  return map[code] || code
}

// ════════════════════════════════════════════════════════════
// 子 Tab
// ════════════════════════════════════════════════════════════
const subTab = ref('strategy')

// ════════════════════════════════════════════════════════════
// Tab 1: 策略列表
// ════════════════════════════════════════════════════════════

const strategyList = ref<CommissionStrategy[]>([])
const strategyLoading = ref(false)
const strategyPage = ref(1)
const strategyPageSize = ref(20)
const strategyTotal = ref(0)
const filterChannel = ref<string | undefined>(undefined)
const filterEnabled = ref<boolean | undefined>(undefined)

const strategyColumns: ProTableColumn[] = [
  { prop: 'channel_code', label: '渠道', width: 100, align: 'center' },
  { prop: 'strategy_name', label: '策略名称', width: 180 },
  { prop: 'enabled', label: '状态', width: 80, align: 'center' },
  { prop: 'tier_dimension_label', label: '阶梯维度', width: 120, align: 'center' },
  { prop: 'remark', label: '备注', minWidth: 180, showOverflowTooltip: true },
  { prop: 'update_time', label: '更新时间', width: 170 },
]

function onFilterChange() {
  strategyPage.value = 1
  loadStrategies()
}

async function loadStrategies() {
  strategyLoading.value = true
  try {
    const res = await channelCommissionApi.listStrategies({
      page: strategyPage.value,
      page_size: strategyPageSize.value,
      channel_code: filterChannel.value,
      enabled: filterEnabled.value,
    })
    strategyList.value = res.items || []
    strategyTotal.value = res.total || 0
  } catch {
    strategyList.value = []
    strategyTotal.value = 0
  } finally {
    strategyLoading.value = false
  }
}

// ── 策略编辑弹窗 ──────────────

interface TierFormItem extends CommissionTier {
  _unlimited: boolean
}

const strategyDialogVisible = ref(false)
const strategyDialogTitle = ref('新增策略')
const strategyFormRef = ref<FormInstance>()
const strategySubmitting = ref(false)
const editingChannelCode = ref<string | null>(null)
const isEditStrategy = computed(() => !!editingChannelCode.value)

const strategyForm = reactive<CommissionStrategyCreate>({
  channel_code: '',
  strategy_name: '',
  enabled: false,
  tier_dimension: 1,
  remark: '',
  tiers: [],
})

// 普通用户/付费会员阶梯分开管理（UI 展示方便）
const normalTiers = ref<TierFormItem[]>([])
const vipTiers = ref<TierFormItem[]>([])

const autoSyncRates = ref(true)

const strategyRules = {
  channel_code: [{ required: true, message: '请选择渠道', trigger: 'change' }],
  strategy_name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
}

function _makeTier(userType: number, min = 0, max = 0): TierFormItem {
  return {
    user_type: userType,
    tier_name: '',
    tier_min: min,
    tier_max: max,
    user_commission_rate: 0.8,
    platform_retention_rate: 0.2,
    sort_order: 0,
    _unlimited: max === 0,
  }
}

function _rebuildTiersArray() {
  // 合并 normalTiers + vipTiers 到 strategyForm.tiers（排序号 + user_type）
  const allTiers: TierFormItem[] = []
  normalTiers.value.forEach((t, i) => {
    t.user_type = 1
    t.sort_order = i
    allTiers.push(t)
  })
  vipTiers.value.forEach((t, i) => {
    t.user_type = 2
    t.sort_order = i
    allTiers.push(t)
  })
  strategyForm.tiers = allTiers as unknown as CommissionTier[]
}

function addNormalTier() {
  normalTiers.value.push(_makeTier(1, normalTiers.value.length > 0 ? 0 : 0))
  _rebuildTiersArray()
}

function removeNormalTier(idx: number) {
  normalTiers.value.splice(idx, 1)
  _rebuildTiersArray()
}

function addVipTier() {
  vipTiers.value.push(_makeTier(2, vipTiers.value.length > 0 ? 0 : 0))
  _rebuildTiersArray()
}

function removeVipTier(idx: number) {
  vipTiers.value.splice(idx, 1)
  _rebuildTiersArray()
}

function onUnlimitedChange(tier: TierFormItem) {
  if (tier._unlimited) {
    tier.tier_max = 0
  }
}

function syncRates(tier: TierFormItem) {
  // 补全：如果用户返利+平台留存 != 1，补全平台留存
  const total = tier.user_commission_rate + tier.platform_retention_rate
  if (Math.abs(total - 1.0) > 0.0001) {
    if (tier.platform_retention_rate === 0) {
      tier.platform_retention_rate = Math.round((1 - tier.user_commission_rate) * 10000) / 10000
    } else {
      tier.user_commission_rate = Math.round((1 - tier.platform_retention_rate) * 10000) / 10000
    }
  }
}

function handleAddStrategy() {
  editingChannelCode.value = null
  strategyDialogTitle.value = '新增策略'
  strategyForm.channel_code = ''
  strategyForm.strategy_name = ''
  strategyForm.enabled = false
  strategyForm.tier_dimension = 1
  strategyForm.remark = ''
  normalTiers.value = [_makeTier(1)]
  vipTiers.value = [_makeTier(2)]
  _rebuildTiersArray()
  strategyDialogVisible.value = true
}

async function handleEditStrategy(row: CommissionStrategy) {
  editingChannelCode.value = row.channel_code
  strategyDialogTitle.value = '编辑策略'
  strategyForm.channel_code = row.channel_code
  strategyForm.strategy_name = row.strategy_name
  strategyForm.enabled = row.enabled
  strategyForm.tier_dimension = row.tier_dimension
  strategyForm.remark = row.remark

  // 拆分阶梯
  normalTiers.value = row.tiers
    .filter((t) => t.user_type === 1)
    .map((t) => ({ ...t, _unlimited: t.tier_max === 0 }))
  vipTiers.value = row.tiers
    .filter((t) => t.user_type === 2)
    .map((t) => ({ ...t, _unlimited: t.tier_max === 0 }))

  if (normalTiers.value.length === 0) normalTiers.value = [_makeTier(1)]
  if (vipTiers.value.length === 0) vipTiers.value = [_makeTier(2)]

  _rebuildTiersArray()
  strategyDialogVisible.value = true
}

function handleDialogClose() {
  // 清理表单状态
  normalTiers.value = []
  vipTiers.value = []
}

async function handleSubmitStrategy() {
  if (!strategyFormRef.value) return
  await strategyFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    // 校验比例
    for (const tier of [...normalTiers.value, ...vipTiers.value]) {
      const total = tier.user_commission_rate + tier.platform_retention_rate
      if (Math.abs(total - 1.0) > 0.0001) {
        ElMessage.error(`用户返利比例(${tier.user_commission_rate}) + 平台留存比例(${tier.platform_retention_rate}) 必须等于 1 (100%)`)
        return
      }
    }

    _rebuildTiersArray()
    strategySubmitting.value = true
    try {
      if (isEditStrategy.value && editingChannelCode.value) {
        const data: CommissionStrategyUpdate = {
          strategy_name: strategyForm.strategy_name,
          enabled: strategyForm.enabled,
          tier_dimension: strategyForm.tier_dimension,
          remark: strategyForm.remark,
          tiers: strategyForm.tiers,
        }
        await channelCommissionApi.updateStrategy(editingChannelCode.value, data)
        ElMessage.success('更新成功')
      } else {
        await channelCommissionApi.createStrategy(strategyForm)
        ElMessage.success('创建成功')
      }
      strategyDialogVisible.value = false
      loadStrategies()
    } catch {
      // 拦截器已提示
    } finally {
      strategySubmitting.value = false
    }
  })
}

async function handleToggle(row: CommissionStrategy) {
  const newEnabled = !row.enabled
  try {
    await channelCommissionApi.toggleStrategy(row.channel_code, newEnabled)
    ElMessage.success(newEnabled ? '策略已启用' : '策略已停用')
    loadStrategies()
  } catch {
    // 拦截器已提示
  }
}

// ── 导出 ──────────────────────

const exportLoading = ref(false)

async function handleExport() {
  exportLoading.value = true
  try {
    const res = await channelCommissionApi.listStrategies({
      page: 1,
      page_size: 100,
      channel_code: filterChannel.value,
      enabled: filterEnabled.value,
    })
    const data = res.items || []
    if (data.length === 0) {
      ElMessage.warning('当前筛选条件下无数据可导出')
      return
    }
    const cols: ExcelColumn[] = [
      { header: '渠道', key: 'channel_code', width: 10, formatter: (v) => channelLabel(v as string) },
      { header: '策略名称', key: 'strategy_name', width: 24 },
      { header: '状态', key: 'enabled', width: 8, formatter: (v) => (v ? '生效' : '停用') },
      { header: '阶梯维度', key: 'tier_dimension_label', width: 12 },
      { header: '阶梯数', key: 'tiers', width: 8, formatter: (v) => String((v as unknown[] | undefined)?.length ?? 0) },
      { header: '备注', key: 'remark', width: 24 },
      { header: '更新时间', key: 'update_time', width: 20 },
    ]
    exportToExcel('渠道佣金策略', cols, data as unknown as Record<string, unknown>[])
    ElMessage.success(`已导出 ${data.length} 条数据`)
  } catch (e) {
    if (e instanceof Error) {
      ElMessage.error(e.message)
    }
  } finally {
    exportLoading.value = false
  }
}

// ════════════════════════════════════════════════════════════
// 分佣预览
// ════════════════════════════════════════════════════════════

const previewVisible = ref(false)
const previewStrategy = ref<CommissionStrategy | null>(null)
const previewFormRef = ref<FormInstance>()
const previewLoading = ref(false)
const previewResult = ref<CommissionPreviewResult | null>(null)

const previewForm = reactive({
  user_type: 1,
  amount: 100,
  order_count: 1,
})

const previewRules = {
  amount: [{ required: true, message: '请输入订单金额', trigger: 'blur' }],
  order_count: [{ required: true, message: '请输入订单数量', trigger: 'blur' }],
}

function handlePreview(row: CommissionStrategy) {
  previewStrategy.value = row
  previewForm.user_type = 1
  previewForm.amount = 100
  previewForm.order_count = 1
  previewResult.value = null
  previewVisible.value = true
}

async function handleDoPreview() {
  if (!previewFormRef.value || !previewStrategy.value) return
  await previewFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    previewLoading.value = true
    try {
      const res = await channelCommissionApi.preview({
        channel_code: previewStrategy.value!.channel_code,
        user_type: previewForm.user_type,
        amount: previewForm.amount,
        order_count: previewForm.order_count,
      })
      previewResult.value = res
    } catch {
      previewResult.value = null
    } finally {
      previewLoading.value = false
    }
  })
}

// ════════════════════════════════════════════════════════════
// Tab 2: 审计记录
// ════════════════════════════════════════════════════════════

const auditLogList = ref<StrategyAuditLog[]>([])
const auditLoading = ref(false)
const auditPage = ref(1)
const auditPageSize = ref(20)
const auditTotal = ref(0)
const auditFilterChannel = ref<string | undefined>(undefined)

const auditColumns: ProTableColumn[] = [
  { prop: 'user_name', label: '操作人', width: 120 },
  { prop: 'action', label: '操作类型', width: 180 },
  { prop: 'details', label: '变更详情', minWidth: 280, showOverflowTooltip: true },
  { prop: 'ip_address', label: 'IP地址', width: 140 },
  { prop: 'create_time', label: '操作时间', width: 170 },
]

async function loadAuditLogs() {
  auditLoading.value = true
  try {
    const res = await channelCommissionApi.listAuditLogs({
      page: auditPage.value,
      page_size: auditPageSize.value,
      channel_code: auditFilterChannel.value,
    })
    // 格式化 action 显示
    res.items = (res.items || []).map((item) => ({
      ...item,
      _actionLabel: actionLabel(item.action),
      _detailsText: formatDetails(item.details),
    }))
    auditLogList.value = res.items || []
    auditTotal.value = res.total || 0
  } catch {
    auditLogList.value = []
    auditTotal.value = 0
  } finally {
    auditLoading.value = false
  }
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    COMMISSION_STRATEGY_CREATE: '新增策略',
    COMMISSION_STRATEGY_UPDATE: '更新策略',
    COMMISSION_STRATEGY_TOGGLE: '启停策略',
  }
  return map[action] || action
}

function formatDetails(details: unknown): string {
  if (!details) return ''
  if (typeof details === 'string') {
    try {
      const obj = JSON.parse(details)
      return JSON.stringify(obj)
    } catch {
      return details
    }
  }
  if (typeof details === 'object') {
    return JSON.stringify(details)
  }
  return String(details)
}

// ════════════════════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════════════════════

onMounted(() => {
  loadStrategies()
})

// 监听子 Tab 切换，审计 Tab 切到时加载数据
import { watch } from 'vue'
watch(subTab, (val) => {
  if (val === 'audit') {
    loadAuditLogs()
  }
})
</script>

<style scoped>
.commission-strategy-tab {
  display: flex;
  flex-direction: column;
}

.sub-tabs {
  margin-bottom: 0;
}

.filter-form {
  margin-bottom: 0;
}

/* ── 阶梯配置 ────────────── */

.tier-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.tier-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  background: #fafafa;
}

.tier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tier-label {
  font-weight: 500;
  font-size: 13px;
}

.tier-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tier-form-item {
  margin-bottom: 0;
}

.tier-sep {
  margin: 0 8px;
  color: #909399;
}

.tier-rates {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.rate-item {
  margin-bottom: 0;
}

.rate-pct {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

/* ── 预览 ────────────── */

.preview-result {
  padding: 0 8px;
}

.preview-disabled {
  color: #909399;
  font-size: 14px;
  text-align: center;
  padding: 16px;
}

.preview-matched {
  margin-bottom: 12px;
}

.preview-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-label {
  color: #606266;
  font-size: 14px;
}

.preview-value {
  font-weight: 500;
  font-size: 14px;
}

.preview-value.highlight {
  color: #e6a23c;
  font-size: 16px;
}

/* ── 审计筛选 ────────────── */

.audit-filter {
  margin-bottom: 12px;
}
</style>
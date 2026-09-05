<!-- @ai-generated -->
<template>
  <div class="config-page">
    <el-card>
      <div class="card-header">
        <span>支付渠道配置</span>
        <el-button type="primary" @click="handleAdd">新增配置</el-button>
      </div>
      
      <el-table :data="tableData" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="pay_type" label="支付类型" width="100">
          <template #default="scope">
            <span>{{ scope.row.pay_type === 1 ? '微信支付' : '未知' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mch_id" label="商户号" />
        <el-table-column prop="notify_url" label="回调地址" show-overflow-tooltip />
        <el-table-column prop="withdraw_rate" label="提现费率" width="100" />
        <el-table-column prop="withdraw_min" label="最低提现" width="100" />
        <el-table-column prop="withdraw_fixed_fee" label="固定手续费" width="120" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.status ? 'success' : 'danger'">
              {{ scope.row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" show-overflow-tooltip />
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.row as unknown as PayConfig)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row as unknown as PayConfig)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" ref="formRef" label-width="120px">
        <el-form-item label="支付类型">
          <el-select v-model="form.pay_type" placeholder="请选择支付类型">
            <el-option label="微信支付" :value="1" />
          </el-select>
        </el-form-item>
        <el-form-item label="商户号">
          <el-input v-model="form.mch_id" placeholder="请输入商户号" />
        </el-form-item>
        <el-form-item label="API密钥">
          <el-input v-model="form.api_key" type="password" placeholder="请输入API密钥" />
        </el-form-item>
        <el-form-item label="证书路径">
          <el-input v-model="form.cert_path" placeholder="请输入证书路径" />
        </el-form-item>
        <el-form-item label="回调地址">
          <el-input v-model="form.notify_url" placeholder="请输入回调地址" />
        </el-form-item>
        <el-form-item label="提现费率">
          <el-input-number v-model="form.withdraw_rate" :precision="2" :min="0" :max="1" :step="0.01" />
        </el-form-item>
        <el-form-item label="最低提现金额">
          <el-input-number v-model="form.withdraw_min" :precision="2" :min="0" :step="0.01" />
        </el-form-item>
        <el-form-item label="固定手续费">
          <el-input-number v-model="form.withdraw_fixed_fee" :precision="2" :min="0" :step="0.01" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElCard, ElTable, ElTableColumn, ElButton, ElPagination, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElSelect, ElOption, ElSwitch, ElTag, ElMessage } from 'element-plus'
import { payConfigApi, type PayConfig, type PayConfigCreate } from '@/api/config'

const tableData = ref<PayConfig[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const formRef = ref()
const editingId = ref<number | null>(null)

const form = reactive({
  pay_type: 1,
  mch_id: '',
  api_key: '',
  cert_path: '',
  notify_url: '',
  withdraw_rate: 0,
  withdraw_min: 0,
  withdraw_fixed_fee: 0,
  status: true,
  remark: ''
})

const loadData = async () => {
  const res = await payConfigApi.list({ page: page.value, page_size: pageSize.value })
  tableData.value = res.data ?? []
  total.value = res.total
}

const handleAdd = () => {
  editingId.value = null
  dialogTitle.value = '新增配置'
  Object.assign(form, {
    pay_type: 1,
    mch_id: '',
    api_key: '',
    cert_path: '',
    notify_url: '',
    withdraw_rate: 0,
    withdraw_min: 0,
    withdraw_fixed_fee: 0,
    status: true,
    remark: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row: PayConfig) => {
  editingId.value = row.id
  dialogTitle.value = '编辑配置'
  Object.assign(form, {
    pay_type: row.pay_type,
    mch_id: row.mch_id,
    api_key: row.api_key,
    cert_path: row.cert_path,
    notify_url: row.notify_url,
    withdraw_rate: row.withdraw_rate,
    withdraw_min: row.withdraw_min,
    withdraw_fixed_fee: row.withdraw_fixed_fee,
    status: row.status,
    remark: row.remark
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    if (editingId.value) {
      await payConfigApi.update(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await payConfigApi.create(form as PayConfigCreate)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row: PayConfig) => {
  try {
    await payConfigApi.delete(row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  loadData()
}

const handleCurrentChange = (currentPage: number) => {
  page.value = currentPage
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.config-page {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  font-size: 18px;
  font-weight: 500;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
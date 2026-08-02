<!-- @ai-generated -->
<template>
  <div class="config-page">
    <el-card>
      <div class="card-header">
        <span>渠道字段映射</span>
        <el-button type="primary" @click="handleAdd">新增映射</el-button>
      </div>
      
      <div class="filter-bar">
        <el-select v-model="filterChannel" placeholder="选择渠道" style="width: 150px">
          <el-option label="全部" :value="''" />
          <el-option label="妙券" :value="'myq'" />
          <el-option label="大淘客" :value="'dta'" />
          <el-option label="OrderX" :value="'orderx'" />
        </el-select>
        <el-button @click="loadData">查询</el-button>
      </div>
      
      <el-table :data="tableData" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="channel_code" label="渠道标识" width="120">
          <template #default="scope">
            <el-tag>{{ scope.row.channel_code === 'myq' ? '妙券' : scope.row.channel_code === 'dta' ? '大淘客' : 'OrderX' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="third_field" label="第三方字段" />
        <el-table-column prop="system_field" label="系统字段" />
        <el-table-column prop="field_desc" label="字段说明" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.status ? 'success' : 'danger'">
              {{ scope.row.status ? '生效' : '失效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort_num" label="排序" width="80" />
        <el-table-column prop="remark" label="备注" show-overflow-tooltip />
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
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
        <el-form-item label="渠道标识" prop="channel_code">
          <el-select v-model="form.channel_code" placeholder="请选择渠道">
            <el-option label="妙券" :value="'myq'" />
            <el-option label="大淘客" :value="'dta'" />
            <el-option label="OrderX" :value="'orderx'" />
          </el-select>
        </el-form-item>
        <el-form-item label="第三方字段" prop="third_field">
          <el-input v-model="form.third_field" placeholder="请输入第三方字段名" />
        </el-form-item>
        <el-form-item label="系统字段" prop="system_field">
          <el-input v-model="form.system_field" placeholder="请输入系统字段名" />
        </el-form-item>
        <el-form-item label="字段说明">
          <el-input v-model="form.field_desc" placeholder="请输入字段说明" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_num" :min="0" />
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
import { channelMappingApi, type ChannelMapping, type ChannelMappingCreate } from '@/api/config'

const tableData = ref<ChannelMapping[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const dialogTitle = ref('新增映射')
const formRef = ref()
const editingId = ref<number | null>(null)
const filterChannel = ref('')

const form = reactive({
  channel_code: '',
  third_field: '',
  system_field: '',
  field_desc: '',
  status: true,
  sort_num: 0,
  remark: ''
})

const rules = {
  channel_code: [{ required: true, message: '请选择渠道', trigger: 'change' }],
  third_field: [{ required: true, message: '请输入第三方字段名', trigger: 'blur' }],
  system_field: [{ required: true, message: '请输入系统字段名', trigger: 'blur' }]
}

const loadData = async () => {
  const params: { page: number; page_size: number; channel_code?: string } = {
    page: page.value,
    page_size: pageSize.value
  }
  if (filterChannel.value) {
    params.channel_code = filterChannel.value
  }
  const res = await channelMappingApi.list(params)
  tableData.value = res.data
  total.value = res.total
}

const handleAdd = () => {
  editingId.value = null
  dialogTitle.value = '新增映射'
  Object.assign(form, {
    channel_code: '',
    third_field: '',
    system_field: '',
    field_desc: '',
    status: true,
    sort_num: 0,
    remark: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row: ChannelMapping) => {
  editingId.value = row.id
  dialogTitle.value = '编辑映射'
  Object.assign(form, {
    channel_code: row.channel_code,
    third_field: row.third_field,
    system_field: row.system_field,
    field_desc: row.field_desc,
    status: row.status,
    sort_num: row.sort_num,
    remark: row.remark
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        if (editingId.value) {
          await channelMappingApi.update(editingId.value, form)
          ElMessage.success('更新成功')
        } else {
          await channelMappingApi.create(form as ChannelMappingCreate)
          ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        await loadData()
      } catch (e) {
        ElMessage.error('操作失败')
      }
    }
  })
}

const handleDelete = async (row: ChannelMapping) => {
  try {
    await channelMappingApi.delete(row.id)
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

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
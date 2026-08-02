<!-- @ai-generated -->
<template>
  <div class="config-page">
    <el-card>
      <div class="card-header">
        <span>系统全局配置</span>
        <el-button type="primary" @click="handleAdd">新增配置</el-button>
      </div>
      
      <el-table :data="tableData" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="config_key" label="配置键名" />
        <el-table-column prop="config_name" label="配置名称" />
        <el-table-column prop="config_value" label="配置值" show-overflow-tooltip />
        <el-table-column prop="config_desc" label="配置说明" show-overflow-tooltip />
        <el-table-column prop="sort_num" label="排序" width="80" />
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column prop="update_time" label="更新时间" width="180" />
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
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" ref="formRef" label-width="100px">
        <el-form-item label="配置键名" prop="config_key">
          <el-input v-model="form.config_key" placeholder="请输入配置键名" />
        </el-form-item>
        <el-form-item label="配置名称" prop="config_name">
          <el-input v-model="form.config_name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="配置值" prop="config_value">
          <el-input v-model="form.config_value" type="textarea" :rows="4" placeholder="请输入配置值" />
        </el-form-item>
        <el-form-item label="配置说明">
          <el-input v-model="form.config_desc" type="textarea" :rows="2" placeholder="请输入配置说明" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_num" :min="0" />
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
import { ElCard, ElTable, ElTableColumn, ElButton, ElPagination, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage } from 'element-plus'
import { systemConfigApi, type SystemConfig, type SystemConfigCreate, type SystemConfigUpdate } from '@/api/config'

const tableData = ref<SystemConfig[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const formRef = ref()
const editingId = ref<number | null>(null)

const form = reactive({
  config_key: '',
  config_value: '',
  config_name: '',
  config_desc: '',
  sort_num: 0
})

const rules = {
  config_key: [{ required: true, message: '请输入配置键名', trigger: 'blur' }],
  config_name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }]
}

const loadData = async () => {
  const res = await systemConfigApi.list({ page: page.value, page_size: pageSize.value })
  tableData.value = res.data
  total.value = res.total
}

const handleAdd = () => {
  editingId.value = null
  dialogTitle.value = '新增配置'
  Object.assign(form, {
    config_key: '',
    config_value: '',
    config_name: '',
    config_desc: '',
    sort_num: 0
  })
  dialogVisible.value = true
}

const handleEdit = (row: SystemConfig) => {
  editingId.value = row.id
  dialogTitle.value = '编辑配置'
  Object.assign(form, {
    config_key: row.config_key,
    config_value: row.config_value,
    config_name: row.config_name,
    config_desc: row.config_desc,
    sort_num: row.sort_num
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        if (editingId.value) {
          await systemConfigApi.update(editingId.value, form)
          ElMessage.success('更新成功')
        } else {
          await systemConfigApi.create(form as SystemConfigCreate)
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

const handleDelete = async (row: SystemConfig) => {
  try {
    await systemConfigApi.delete(row.id)
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
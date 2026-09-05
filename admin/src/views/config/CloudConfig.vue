<!-- @ai-generated -->
<template>
  <div class="config-page">
    <el-card>
      <div class="card-header">
        <span>云资源配置</span>
        <el-button type="primary" @click="handleAdd">新增配置</el-button>
      </div>
      
      <el-table :data="tableData" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="config_name" label="配置名称" />
        <el-table-column prop="cdn_domain" label="CDN域名" show-overflow-tooltip />
        <el-table-column prop="obs_bucket" label="OBS桶名" />
        <el-table-column prop="obs_endpoint" label="OBS终端" show-overflow-tooltip />
        <el-table-column prop="access_key" label="AK" />
        <el-table-column prop="secret_key" label="SK" />
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
            <el-button size="small" @click="handleEdit(scope.row as unknown as CloudConfig)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row as unknown as CloudConfig)">删除</el-button>
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
      <el-form :model="form" ref="formRef" :rules="rules" label-width="120px">
        <el-form-item label="配置名称" prop="config_name">
          <el-input v-model="form.config_name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="CDN域名">
          <el-input v-model="form.cdn_domain" placeholder="请输入CDN域名" />
        </el-form-item>
        <el-form-item label="OBS桶名">
          <el-input v-model="form.obs_bucket" placeholder="请输入OBS桶名" />
        </el-form-item>
        <el-form-item label="OBS终端">
          <el-input v-model="form.obs_endpoint" placeholder="请输入OBS终端地址" />
        </el-form-item>
        <el-form-item label="AK">
          <el-input v-model="form.access_key" placeholder="请输入Access Key" />
        </el-form-item>
        <el-form-item label="SK">
          <el-input v-model="form.secret_key" type="password" placeholder="请输入Secret Key" />
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
import { ElCard, ElTable, ElTableColumn, ElButton, ElPagination, ElDialog, ElForm, ElFormItem, ElInput, ElSwitch, ElTag, ElMessage } from 'element-plus'
import { cloudConfigApi, type CloudConfig, type CloudConfigCreate } from '@/api/config'

const tableData = ref<CloudConfig[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const formRef = ref()
const editingId = ref<number | null>(null)

const form = reactive({
  config_name: '',
  cdn_domain: '',
  obs_bucket: '',
  obs_endpoint: '',
  access_key: '',
  secret_key: '',
  status: true,
  remark: ''
})

const rules = {
  config_name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }]
}

const loadData = async () => {
  const res = await cloudConfigApi.list({ page: page.value, page_size: pageSize.value })
  tableData.value = res.data ?? []
  total.value = res.total
}

const handleAdd = () => {
  editingId.value = null
  dialogTitle.value = '新增配置'
  Object.assign(form, {
    config_name: '',
    cdn_domain: '',
    obs_bucket: '',
    obs_endpoint: '',
    access_key: '',
    secret_key: '',
    status: true,
    remark: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row: CloudConfig) => {
  editingId.value = row.id
  dialogTitle.value = '编辑配置'
  Object.assign(form, {
    config_name: row.config_name,
    cdn_domain: row.cdn_domain,
    obs_bucket: row.obs_bucket,
    obs_endpoint: row.obs_endpoint,
    access_key: row.access_key,
    secret_key: row.secret_key,
    status: row.status,
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
          await cloudConfigApi.update(editingId.value, form)
          ElMessage.success('更新成功')
        } else {
          await cloudConfigApi.create(form as CloudConfigCreate)
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

const handleDelete = async (row: CloudConfig) => {
  try {
    await cloudConfigApi.delete(row.id)
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
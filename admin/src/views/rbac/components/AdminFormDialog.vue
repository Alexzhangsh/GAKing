<!-- @ai-generated -->
<!--
  管理员表单弹窗（新增/编辑/分配角色）
-->
<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑管理员' : '新增管理员'"
    width="520px"
    top="5vh"
    append-to-body
    destroy-on-close
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" :disabled="rolesLoading">
      <el-form-item label="用户名" prop="username" :disabled="isEdit">
        <el-input v-model="form.username" placeholder="登录用，创建后不可修改" />
      </el-form-item>
      <el-form-item v-if="!isEdit" label="初始密码" prop="password">
        <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" />
      </el-form-item>
      <el-form-item label="真实姓名" prop="real_name">
        <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.phone" placeholder="可选" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="可选" />
      </el-form-item>
      <el-form-item label="分配角色" prop="role_id">
        <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
          <el-option
            v-for="r in roles"
            :key="r.id"
            :label="`${r.role_name}（${r.role_desc || r.id}）`"
            :value="r.id"
            :disabled="r.status !== true"
          />
        </el-select>
        <div v-if="roles.length === 0 && !rolesLoading" class="no-roles">
          暂无可用角色，请先在「角色管理」中创建并启用角色
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存修改' : '创建账号' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, watch } from 'vue'
import {
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElButton,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { adminApi, type AdminItem, type AdminCreateRequest, type AdminUpdateRequest } from '@/api/admin'
import { type RoleItem } from '@/api/rbac'

const props = defineProps<{
  visible: boolean
  admin: AdminItem | null
  roles: RoleItem[]
  rolesLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'success'): void
}>()

const isEdit = computed(() => !!props.admin)
const roles = computed(() => props.roles)
const rolesLoading = computed(() => props.rolesLoading ?? false)

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive<{
  username: string
  password: string
  real_name: string
  phone: string
  email: string
  role_id: number | null
}>({
  username: '',
  password: '',
  real_name: '',
  phone: '',
  email: '',
  role_id: null,
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度 3-20 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请设置初始密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
  ],
  role_id: [
    { required: true, message: '请选择角色', trigger: 'change' },
  ],
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.real_name = ''
  form.phone = ''
  form.email = ''
  form.role_id = null
}

function fillForm(admin: AdminItem) {
  form.username = admin.username
  form.password = ''
  form.real_name = admin.real_name || ''
  form.phone = admin.phone || ''
  form.email = admin.email || ''
  form.role_id = admin.role_id
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      if (props.admin) {
        fillForm(props.admin)
      } else {
        resetForm()
      }
      formRef.value?.clearValidate()
    } else {
      resetForm()
    }
  }
)

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (props.admin) {
        const payload: AdminUpdateRequest = {
          real_name: form.real_name,
          phone: form.phone || undefined,
          email: form.email || undefined,
          role_id: form.role_id!,
        }
        await adminApi.update(props.admin.id, payload)
        ElMessage.success('更新成功')
      } else {
        const payload: AdminCreateRequest = {
          username: form.username,
          password: form.password,
          real_name: form.real_name,
          phone: form.phone || undefined,
          email: form.email || undefined,
          role_id: form.role_id!,
        }
        await adminApi.create(payload)
        ElMessage.success('账号创建成功')
      }
      emit('success')
      emit('update:visible', false)
    } catch {
      // 拦截器已提示
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.no-roles {
  font-size: 12px;
  color: #e6a23c;
  font-weight: 300;
  margin-top: 4px;
}
</style>

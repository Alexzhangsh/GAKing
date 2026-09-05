<!-- @ai-generated -->
<!--
  角色表单弹窗（含权限码勾选绑定）
  对接：RBAC 角色创建/更新接口 + 权限码目录接口
-->
<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑角色' : '新增角色'"
    width="720px"
    top="5vh"
    append-to-body
    destroy-on-close
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" v-loading="catalogLoading">
      <el-form-item label="角色名" prop="role_name">
        <el-input v-model="form.role_name" placeholder="请输入角色名称，如：运营审核员" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.role_desc" type="textarea" :rows="2" placeholder="可选，角色职责说明" />
      </el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="form.status" active-text="启用" inactive-text="禁用" />
      </el-form-item>
      <el-form-item label="权限码" prop="permissions">
        <div class="perm-tree">
          <!-- 全选/清空 -->
          <div class="perm-toolbar">
            <el-checkbox
              v-if="flatCatalog.length > 0"
              v-model="allChecked"
              :indeterminate="indeterminate"
              @change="(val: unknown) => handleCheckAll(Boolean(val))"
            >
              全选
            </el-checkbox>
            <span class="perm-count">
              已选 {{ form.permissions.length }} / {{ flatCatalog.length }}
            </span>
          </div>

          <!-- 按分组折叠展示 -->
          <el-collapse v-if="groupedCatalog.length > 0" v-model="activeGroups" class="perm-collapse">
            <el-collapse-item
              v-for="group in groupedCatalog"
              :key="group.name"
              :title="group.name"
              :name="group.name"
            >
              <el-checkbox-group v-model="form.permissions">
                <el-checkbox
                  v-for="item in group.items"
                  :key="item.code"
                  :value="item.code"
                  class="perm-checkbox"
                >
                  <div class="perm-item">
                    <span class="perm-label">{{ item.label }}</span>
                    <span class="perm-code">{{ item.code }}</span>
                  </div>
                </el-checkbox>
              </el-checkbox-group>
            </el-collapse-item>
          </el-collapse>

          <div v-else-if="!catalogLoading" class="empty-catalog">
            <el-empty description="暂无权限码目录" :image-size="60" />
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存修改' : '创建角色' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, watch, onMounted } from 'vue'
import {
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElCheckbox,
  ElCheckboxGroup,
  ElCollapse,
  ElCollapseItem,
  ElButton,
  ElEmpty,
  ElSwitch,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import {
  rbacApi,
  type RoleItem,
  type RoleCreateRequest,
  type PermissionCatalogItem,
} from '@/api/rbac'

const props = defineProps<{
  visible: boolean
  role: RoleItem | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'success'): void
}>()

const isEdit = computed(() => !!props.role)

const formRef = ref<FormInstance>()
const submitting = ref(false)
const catalogLoading = ref(false)

const form = reactive<{
  role_name: string
  role_desc: string
  permissions: string[]
  status: boolean
}>({
  role_name: '',
  role_desc: '',
  permissions: [],
  status: true,
})

const rules: FormRules = {
  role_name: [
    { required: true, message: '请输入角色名', trigger: 'blur' },
    { min: 2, max: 30, message: '角色名长度 2-30 位', trigger: 'blur' },
  ],
}

// ── 权限码目录 ──────────────
const catalog = ref<PermissionCatalogItem[]>([])
const flatCatalog = computed(() => catalog.value)

const groupedCatalog = computed(() => {
  const groups = new Map<string, PermissionCatalogItem[]>()
  for (const item of catalog.value) {
    const g = item.group || '其他'
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g)!.push(item)
  }
  return Array.from(groups.entries()).map(([name, items]) => ({ name, items }))
})

const activeGroups = ref<string[]>([])

// 全选状态
const allChecked = computed({
  get: () =>
    flatCatalog.value.length > 0 &&
    form.permissions.length === flatCatalog.value.length,
  set: (val: boolean) => {
    handleCheckAll(val)
  },
})

const indeterminate = computed(() => {
  const total = flatCatalog.value.length
  if (total === 0) return false
  return form.permissions.length > 0 && form.permissions.length < total
})

function handleCheckAll(val: boolean) {
  if (val) {
    form.permissions = flatCatalog.value.map((i) => i.code)
  } else {
    form.permissions = []
  }
}

// ── 数据加载 ──────────────
async function loadCatalog() {
  catalogLoading.value = true
  try {
    catalog.value = await rbacApi.getPermissionCatalog()
    // 默认展开第一个分组
    if (groupedCatalog.value.length > 0 && activeGroups.value.length === 0) {
      activeGroups.value = [groupedCatalog.value[0].name]
    }
  } catch {
    catalog.value = []
  } finally {
    catalogLoading.value = false
  }
}

function resetForm() {
  form.role_name = ''
  form.role_desc = ''
  form.permissions = []
  form.status = true
}

function fillForm(role: RoleItem) {
  form.role_name = role.role_name
  form.role_desc = role.role_desc || ''
  form.permissions = [...(role.permissions || [])]
  form.status = role.status
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      if (props.role) {
        fillForm(props.role)
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
      const payload: RoleCreateRequest = {
        role_name: form.role_name,
        role_desc: form.role_desc || undefined,
        permissions: form.permissions,
        status: form.status,
      }
      if (props.role) {
        await rbacApi.update(props.role.id, payload)
        ElMessage.success('更新成功')
      } else {
        await rbacApi.create(payload)
        ElMessage.success('创建成功')
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

onMounted(() => {
  loadCatalog()
})
</script>

<style scoped>
.perm-tree {
  width: 100%;
}

.perm-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f7f9fc;
  border-radius: 4px;
  margin-bottom: 8px;
}

.perm-count {
  font-size: 12px;
  color: #909399;
  font-weight: 300;
}

.perm-collapse :deep(.el-collapse-item__header) {
  font-weight: 500;
  color: #303133;
}

.perm-checkbox {
  margin-right: 0;
  display: block;
  margin-bottom: 4px;
}

.perm-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
}

.perm-label {
  font-size: 14px;
  color: #303133;
  font-weight: 300;
}

.perm-code {
  font-size: 12px;
  color: #909399;
  font-weight: 300;
  font-family: 'Courier New', monospace;
}

.empty-catalog {
  padding: 24px 0;
}
</style>

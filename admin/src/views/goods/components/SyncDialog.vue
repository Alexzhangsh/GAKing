<!-- @ai-generated -->
<!--
  CPS 渠道商品同步弹窗
  调用 POST /api/v1/admin/goods/sync 从 CPS 渠道拉取商品到本地管理表
-->
<template>
  <el-dialog
    :model-value="visible"
    title="CPS 渠道商品同步"
    width="480px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
  >
    <el-form :model="form" ref="formRef" :rules="rules" label-width="100px">
      <el-form-item label="来源渠道" prop="source_channel">
        <el-select v-model="form.source_channel" placeholder="请选择渠道" style="width: 100%">
          <el-option label="喵有券 (myq)" value="myq" />
          <el-option label="订单侠 (orderx)" value="orderx" />
          <el-option label="大淘客 (dta)" value="dta" />
        </el-select>
      </el-form-item>
      <el-form-item label="搜索关键词" prop="keyword">
        <el-input
          v-model="form.keyword"
          placeholder="选填，不填则同步渠道首页推荐"
          clearable
          maxlength="128"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="拉取页码" prop="page">
        <el-input-number v-model="form.page" :min="1" :max="100" />
      </el-form-item>
      <el-form-item label="每页数量" prop="page_size">
        <el-input-number v-model="form.page_size" :min="1" :max="100" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">开始同步</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, watch } from 'vue'
import {
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElInput,
  ElInputNumber,
  ElButton,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { goodsApi, type GoodsSyncRequest } from '@/api/goods'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'success'): void
}>()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive<GoodsSyncRequest>({
  source_channel: 'myq',
  keyword: '',
  page: 1,
  page_size: 20,
})

const rules: FormRules = {
  source_channel: [{ required: true, message: '请选择来源渠道', trigger: 'change' }],
}

// 弹窗打开时重置表单
watch(
  () => props.visible,
  (v) => {
    if (v) {
      Object.assign(form, { source_channel: 'myq', keyword: '', page: 1, page_size: 20 })
    }
  }
)

function handleClose() {
  emit('update:visible', false)
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await goodsApi.syncFromCps({
        source_channel: form.source_channel,
        keyword: form.keyword || undefined,
        page: form.page,
        page_size: form.page_size,
      })
      const synced = (res as { synced_count?: number })?.synced_count
      ElMessage.success(synced ? `同步成功，共 ${synced} 条商品` : '商品同步成功')
      emit('success')
      handleClose()
    } catch {
      // 拦截器已提示
    } finally {
      loading.value = false
    }
  })
}
</script>

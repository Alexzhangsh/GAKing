<!-- @ai-generated -->
<!--
  渠道密钥测试面板
  对接 F04 接口：POST /api/v1/admin/channel/test-key
  权限：channel:test
  生产环境前端禁用 + 后端 403 双重保障
-->
<template>
  <div class="key-test-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>渠道密钥测试</span>
          <el-tag v-if="isProduction" type="danger" size="small">生产环境已禁用</el-tag>
        </div>
      </template>

      <el-alert
        v-if="isProduction"
        title="生产环境禁止测试密钥"
        description="为保障生产安全，密钥测试功能仅在开发/测试环境可用。请在本地或测试环境操作。"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" style="max-width: 600px">
        <el-form-item label="渠道标识" prop="channel_code">
          <el-select v-model="form.channel_code" placeholder="选择渠道" style="width: 100%">
            <el-option label="喵有券 (myq)" value="myq" />
            <el-option label="订单侠 (orderx)" value="orderx" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Token" prop="api_token">
          <el-input
            v-model="form.api_token"
            placeholder="输入渠道API Token"
            type="password"
            show-password
            :disabled="isProduction"
          />
        </el-form-item>
        <el-form-item label="API Secret">
          <el-input
            v-model="form.api_secret"
            placeholder="输入渠道API密钥（选填）"
            type="password"
            show-password
            :disabled="isProduction"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="testing"
            :disabled="isProduction"
            @click="handleTest"
          >
            <el-icon><Key /></el-icon>测试密钥
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 测试结果 -->
      <el-result
        v-if="testResult"
        :icon="testResult.success ? 'success' : 'error'"
        :title="testResult.success ? '密钥测试通过' : '密钥测试失败'"
        :sub-title="testResult.message"
        style="margin-top: 20px"
      >
        <template #extra>
          <el-descriptions v-if="testResult.success" :column="2" border size="small" style="max-width: 500px">
            <el-descriptions-item label="渠道标识">{{ testResult.channel_code }}</el-descriptions-item>
            <el-descriptions-item label="Token长度">{{ testResult.token_length }}</el-descriptions-item>
            <el-descriptions-item label="Secret长度">{{ testResult.secret_length }}</el-descriptions-item>
            <el-descriptions-item label="测试时间">{{ testTime }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed } from 'vue'
import {
  ElCard, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElButton,
  ElIcon, ElTag, ElAlert, ElResult, ElDescriptions, ElDescriptionsItem,
  ElMessage, type FormInstance,
} from 'element-plus'
import { Key } from '@element-plus/icons-vue'
import { channelTestApi, type ChannelKeyTestResult } from '@/api/channel'

defineOptions({ name: 'ChannelKeyTest' })

const formRef = ref<FormInstance>()
const testing = ref(false)
const testResult = ref<ChannelKeyTestResult | null>(null)
const testTime = ref('')

// 生产环境判断（Vite 编译时常量）
const isProduction = computed(() => import.meta.env.PROD)

const form = reactive({
  channel_code: '',
  api_token: '',
  api_secret: '',
})

const rules = {
  channel_code: [{ required: true, message: '请选择渠道', trigger: 'change' }],
  api_token: [{ required: true, message: '请输入API Token', trigger: 'blur' }],
}

async function handleTest() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    testing.value = true
    testResult.value = null
    try {
      const result = await channelTestApi.testKey({
        channel_code: form.channel_code,
        api_token: form.api_token,
        api_secret: form.api_secret,
      })
      testResult.value = result
      testTime.value = new Date().toLocaleString('zh-CN')
      if (result.success) {
        ElMessage.success('密钥测试通过')
      } else {
        ElMessage.warning(result.message || '密钥测试失败')
      }
    } catch {
      // 拦截器已提示
      testResult.value = {
        success: false,
        message: '测试请求失败，请检查网络或后端服务',
        channel_code: form.channel_code,
      }
    } finally {
      testing.value = false
    }
  })
}

function handleReset() {
  form.channel_code = ''
  form.api_token = ''
  form.api_secret = ''
  testResult.value = null
  formRef.value?.resetFields()
}
</script>

<style scoped>
.key-test-page {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

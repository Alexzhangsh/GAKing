<!-- @ai-generated -->
<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <img src="@/assets/gak-logo.png" alt="金角大王" class="login-logo" />
        <h2>金角大王管理后台</h2>
        <p class="subtitle">CPS 返利小程序运营管理系统</p>
      </div>
      <el-form :model="form" ref="formRef" :rules="rules" label-width="0" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-tips">
        <span>忘记密码请联系超级管理员重置</span>
      </div>
    </div>

    <!-- 首次登录强制改密弹窗 -->
    <el-dialog
      v-model="pwdDialogVisible"
      title="首次登录请修改密码"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      width="420px"
    >
      <el-form :model="pwdForm" ref="pwdFormRef" :rules="pwdRules" label-width="100px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">提交并登录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElForm,
  ElFormItem,
  ElInput,
  ElButton,
  ElDialog,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { authApi } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

/** 获取 redirect 目标，默认 /dashboard */
function getRedirect(): string {
  const r = route.query.redirect
  return typeof r === 'string' && r ? r : '/dashboard'
}

const handleLogin = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await userStore.login({
        username: form.username,
        password: form.password,
      })
      // 首次登录强制改密
      if (res.must_change_password) {
        pwdForm.old_password = form.password
        pwdDialogVisible.value = true
        ElMessage.warning('首次登录请修改密码后继续')
        return
      }
      ElMessage.success('登录成功')
      router.push(getRedirect())
    } catch {
      // 拦截器已提示错误
    } finally {
      loading.value = false
    }
  })
}

// ── 改密弹窗 ──────────────
const pwdDialogVisible = ref(false)
const pwdLoading = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码至少 8 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const handleChangePassword = async () => {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    pwdLoading.value = true
    try {
      await authApi.changePassword({
        old_password: pwdForm.old_password,
        new_password: pwdForm.new_password,
      })
      ElMessage.success('密码修改成功')
      pwdDialogVisible.value = false
      router.push(getRedirect())
    } catch {
      // 拦截器已提示
    } finally {
      pwdLoading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #000;
  position: relative;
  overflow: hidden;
}

.login-container::before {
  content: '';
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(255, 215, 0, 0.15) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.login-box {
  width: 420px;
  padding: 48px 40px;
  background: rgba(20, 20, 20, 0.85);
  border: 1px solid rgba(255, 215, 0, 0.2);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(255, 215, 0, 0.1);
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 72px;
  height: 72px;
  margin-bottom: 16px;
  object-fit: contain;
}

.login-header h2 {
  margin: 0 0 8px;
  color: #ffd700;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 2px;
}

.login-header .subtitle {
  margin: 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  font-weight: 300;
}

.login-tips {
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  font-weight: 300;
}
</style>

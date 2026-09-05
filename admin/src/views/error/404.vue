<!-- @ai-generated -->
<template>
  <div class="error-page">
    <el-result icon="info" title="404" sub-title="抱歉，您访问的页面不存在">
      <template #extra>
        <el-button type="primary" @click="goHome">返回工作台</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { useRouter } from 'vue-router'
import { ElResult, ElButton } from 'element-plus'

const router = useRouter()
const goHome = () => router.push('/dashboard')
</script>

<style scoped>
.error-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>

<!-- @ai-generated -->
<template>
  <div class="layout-container">
    <aside class="sidebar">
      <div class="logo">金角大王</div>
      <el-menu :default-active="activeMenu" router class="sidebar-menu">
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/system-config">系统全局配置</el-menu-item>
          <el-menu-item index="/pay-config">支付渠道配置</el-menu-item>
          <el-menu-item index="/cloud-config">云资源配置</el-menu-item>
          <el-menu-item index="/channel-mapping">渠道字段映射</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </aside>
    <main class="main-content">
      <header class="header">
        <div class="header-left">
          <el-icon class="menu-toggle" @click="toggleSidebar"><Menu /></el-icon>
          <span class="title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-button text @click="handleLogout">退出登录</el-button>
        </div>
      </header>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMenu, ElSubMenu, ElMenu, ElMenuItem, ElIcon, ElButton, ElMessage } from 'element-plus'
import { Setting, Menu } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => route.path)
const sidebarCollapsed = ref(false)

const menuTitles: Record<string, string> = {
  '/system-config': '系统全局配置',
  '/pay-config': '支付渠道配置',
  '/cloud-config': '云资源配置',
  '/channel-mapping': '渠道字段映射'
}

const currentTitle = computed(() => menuTitles[route.path] || '')

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const handleLogout = () => {
  localStorage.removeItem('admin_token')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 220px;
  background: #2a2a3a;
  color: #fff;
  transition: width 0.3s;
}

.sidebar.collapsed {
  width: 60px;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  background: #1a1a2e;
}

.sidebar-menu {
  border-right: none;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: rgba(255, 255, 255, 0.8);
}

.sidebar-menu :deep(.el-menu-item.is-active),
.sidebar-menu :deep(.el-sub-menu__title.is-active) {
  color: #409eff;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-toggle {
  font-size: 20px;
  cursor: pointer;
}

.title {
  font-size: 16px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

main {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #f5f5f5;
}
</style>
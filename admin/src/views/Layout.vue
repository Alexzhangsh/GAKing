<!-- @ai-generated -->
<template>
  <div class="layout-container">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="logo">
        <img src="@/assets/gak-logo-sm.png" alt="logo" class="logo-icon" />
        <span v-if="!sidebarCollapsed">金角大王</span>
        <span v-else>金</span>
      </div>
      <el-scrollbar class="sidebar-scroll">
        <el-menu
          :default-active="activeMenu"
          :collapse="sidebarCollapsed"
          :collapse-transition="false"
          router
          class="sidebar-menu"
          background-color="#2a2a3a"
          text-color="rgba(255,255,255,0.85)"
          active-text-color="#409eff"
        >
          <template v-for="item in visibleMenus" :key="item.title">
            <!-- 有子菜单 -->
            <el-sub-menu v-if="item.children && item.children.length" :index="item.title">
              <template #title>
                <el-icon v-if="item.icon"><component :is="iconMap[item.icon as keyof typeof iconMap]" /></el-icon>
                <span>{{ item.title }}</span>
              </template>
              <template v-for="child in filterMenus(item.children)" :key="child.index">
                <el-menu-item :index="child.index || ''" :disabled="child.disabled">
                  <el-icon v-if="child.icon"><component :is="iconMap[child.icon as keyof typeof iconMap]" /></el-icon>
                  <template #title>
                    {{ child.title }}
                    <el-tag v-if="child.disabled" size="small" type="info" effect="plain" style="margin-left: 8px">待开放</el-tag>
                  </template>
                </el-menu-item>
              </template>
            </el-sub-menu>
            <!-- 无子菜单 -->
            <el-menu-item v-else :index="item.index || ''" :disabled="item.disabled">
              <el-icon v-if="item.icon"><component :is="iconMap[item.icon as keyof typeof iconMap]" /></el-icon>
              <template #title>
                {{ item.title }}
                <el-tag v-if="item.disabled" size="small" type="info" effect="plain" style="margin-left: 8px">待开放</el-tag>
              </template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
    </aside>

    <main class="main-content">
      <header class="header">
        <div class="header-left">
          <el-icon class="menu-toggle" @click="toggleSidebar"><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
          <span class="title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="28" class="user-avatar">{{ avatarText }}</el-avatar>
              <span class="user-name">{{ userStore.displayName }}</span>
              <el-tag size="small" type="primary" effect="plain">{{ userStore.roleName || '管理员' }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changePassword">
                  <el-icon><Lock /></el-icon>修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <section class="content-body">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['GoodsList']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </section>
    </main>

    <!-- 修改密码弹窗 -->
    <el-dialog v-model="pwdDialogVisible" title="修改密码" width="420px">
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
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMenu,
  ElMenuItem,
  ElSubMenu,
  ElIcon,
  ElScrollbar,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElAvatar,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElButton,
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import {
  Fold,
  Expand,
  ArrowDown,
  Lock,
  SwitchButton,
  Odometer,
  Goods,
  Setting,
  Wallet,
  Cloudy,
  Connection,
  List,
  Money,
  User,
  UserFilled,
  Avatar,
  Document,
  ChatDotRound,
  Promotion,
  Bell,
  Key,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { authApi } from '@/api/auth'

// 注册图标组件（template 中通过 :is 字符串名引用）
const iconMap = {
  Odometer, Goods, Setting, Wallet, Cloudy, Connection, List, Money, User, UserFilled,
  Avatar, Document, ChatDotRound, Promotion, Bell, Key,
}

interface MenuItem {
  title: string
  icon?: string
  index?: string
  permissions?: string[]
  children?: MenuItem[]
  disabled?: boolean
}

/** 完整菜单配置（含 F02/F03 已解锁项） */
const allMenus: MenuItem[] = [
  {
    title: '工作台',
    icon: 'Odometer',
    index: '/dashboard',
    permissions: ['dashboard:view'],
  },
  {
    title: '商品管理',
    icon: 'Goods',
    index: '/goods/list',
    permissions: ['goods:manage'],
  },
  {
    title: '订单管理',
    icon: 'List',
    index: '/order/list',
    permissions: ['order:manage'],
  },
  {
    title: '提现管理',
    icon: 'Money',
    index: '/withdraw/list',
    permissions: ['withdraw:manage'],
  },
  {
    title: '用户管理',
    icon: 'User',
    index: '/user/list',
    permissions: ['user:manage'],
  },
  // ── 营销消息（F04） ──
  {
    title: '营销消息',
    icon: 'ChatDotRound',
    permissions: ['message:manage'],
    children: [
      { title: '消息模板', icon: 'ChatDotRound', index: '/message/template', permissions: ['message:manage'] },
      { title: '推送记录', icon: 'Promotion', index: '/message/push-record', permissions: ['message:manage'] },
      { title: '订阅绑定', icon: 'Bell', index: '/message/subscribe', permissions: ['message:manage'] },
    ],
  },
  // ── 渠道配置（F04） ──
  {
    title: '渠道配置',
    icon: 'Connection',
    children: [
      { title: '参数配置', icon: 'Connection', index: '/channel/config', permissions: ['config:manage'] },
      { title: '密钥测试', icon: 'Key', index: '/channel/key-test', permissions: ['channel:test'] },
    ],
  },
  {
    title: '系统设置',
    icon: 'Setting',
    permissions: ['config:manage'],
    children: [
      { title: '系统全局配置', icon: 'Setting', index: '/system-config' },
      { title: '支付渠道配置', icon: 'Wallet', index: '/pay-config' },
      { title: '云资源配置', icon: 'Cloudy', index: '/cloud-config' },
      { title: '渠道字段映射', icon: 'Connection', index: '/channel-mapping' },
    ],
  },
  // ── 权限管理（F03） ──
  {
    title: '权限管理',
    icon: 'UserFilled',
    permissions: ['rbac:manage'],
    children: [
      { title: '角色管理', icon: 'UserFilled', index: '/rbac/role', permissions: ['rbac:manage'] },
      { title: '管理员账号', icon: 'Avatar', index: '/rbac/admin', permissions: ['rbac:manage'] },
      { title: '审计日志', icon: 'Document', index: '/rbac/audit', permissions: ['audit:view'] },
    ],
  },
]

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const sidebarCollapsed = ref(false)
const activeMenu = computed(() => route.path)

const avatarText = computed(() => {
  const name = userStore.displayName
  return name ? name.charAt(0).toUpperCase() : 'A'
})

/** 根据权限过滤菜单（含子菜单） */
function filterMenus(menus: MenuItem[]): MenuItem[] {
  return menus.filter((m) => {
    if (!m.permissions || m.permissions.length === 0) return true
    return userStore.hasPermission(m.permissions)
  })
}

const visibleMenus = computed(() => filterMenus(allMenus))

/** 当前页面标题 */
const currentTitle = computed(() => {
  const matched = route.matched.filter((r) => r.meta?.title)
  return matched.length > 0 ? matched[matched.length - 1].meta.title : ''
})

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

/** 下拉菜单命令处理 */
async function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确认退出登录吗？', '提示', {
        type: 'warning',
        confirmButtonText: '退出',
        cancelButtonText: '取消',
      })
      await userStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    } catch {
      // 取消
    }
  } else if (cmd === 'changePassword') {
    pwdDialogVisible.value = true
  }
}

// ── 修改密码弹窗 ──────────────
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
      ElMessage.success('密码修改成功，请重新登录')
      pwdDialogVisible.value = false
      await userStore.logout()
      router.push('/login')
    } catch {
      // 拦截器已提示
    } finally {
      pwdLoading.value = false
    }
  })
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
  transition: width 0.28s;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 64px;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 500;
  background: #1a1a2e;
  flex-shrink: 0;
}

.logo-icon {
  width: 28px;
  height: 28px;
  object-fit: contain;
  flex-shrink: 0;
}

.sidebar-scroll {
  flex: 1;
}

.sidebar-menu {
  border-right: none;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
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
  border-bottom: 1px solid #f0f0f0;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-toggle {
  font-size: 20px;
  cursor: pointer;
  color: #545454;
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 0 8px;
  height: 40px;
  border-radius: 4px;
  transition: background 0.2s;
}

.user-info:hover {
  background: #f5f5f5;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-size: 14px;
}

.user-name {
  font-size: 14px;
  color: #303133;
}

.content-body {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #f0f2f5;
}
</style>

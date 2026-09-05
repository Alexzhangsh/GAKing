// @ai-generated
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import permissionDirective from './directives/permission'
import '@/styles/global.css'

const app = createApp(App)

// 注册 Element Plus 全套图标（菜单/按钮图标按需使用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(pinia)
app.use(router)

// 注册 v-permission 权限指令
app.directive('permission', permissionDirective)

app.mount('#app')

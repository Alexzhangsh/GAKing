// @ai-generated
/**
 * v-permission 权限指令
 *
 * 用法：
 *   v-permission="'goods:manage'"            // 单权限码
 *   v-permission="['goods:manage','*']"      // 多权限码（或关系）
 *
 * 行为：无权限时直接移除 DOM 节点（非 display:none，防止 DOM 篡改绕过）
 * 注意：前端隐藏仅为体验优化，权限唯一可信来源为后端 RolesGuard
 */
import type { Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/store/user'

/** 解析 binding.value 为权限码数组 */
function parseCodes(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.filter((v) => typeof v === 'string')
  return []
}

export const permissionDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const codes = parseCodes(binding.value)
    if (codes.length === 0) return
    const userStore = useUserStore()
    if (!userStore.hasPermission(codes)) {
      // 直接移除节点，避免 display:none 被 devtools 篡改
      if (el.parentNode) {
        el.parentNode.removeChild(el)
      } else {
        // 无父节点时（极少见）隐藏，mounted 后期再移除
        el.style.display = 'none'
      }
    }
  },
  // 组件更新时重新校验（权限可能因 fetchUserInfo 异步刷新）
  updated(el: HTMLElement, binding: DirectiveBinding) {
    const codes = parseCodes(binding.value)
    if (codes.length === 0) return
    const userStore = useUserStore()
    if (!userStore.hasPermission(codes)) {
      if (el.parentNode) {
        el.parentNode.removeChild(el)
      }
    }
  },
}

export default permissionDirective

<!-- @ai-generated -->
<!--
  状态标签组件 StatusTag
  职责：统一渲染业务状态标签，颜色清晰区分
  复用：商品上下架、订单六态、提现五态、用户状态

  用法：
    <StatusTag status="on_shelf" :map="goodsShelfMap" />
    <StatusTag :status="row.shelf_status" :map="goodsShelfMap" />
-->
<template>
  <el-tag v-if="config" :type="config.type" :effect="effect" size="small" disable-transitions>
    {{ config.text }}
  </el-tag>
  <span v-else>{{ status }}</span>
</template>

<script setup lang="ts">
// @ai-generated
import { computed } from 'vue'
import { ElTag } from 'element-plus'

/** 状态映射项 */
export interface StatusMapItem {
  /** 显示文本 */
  text: string
  /** el-tag type */
  type: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}

/** 状态映射表：{ statusValue: { text, type } } */
export type StatusMap = Record<string, StatusMapItem>

const props = withDefaults(
  defineProps<{
    /** 状态值 */
    status: string | number
    /** 状态映射表 */
    map: StatusMap
    /** 标签主题（默认 light） */
    effect?: 'light' | 'dark' | 'plain'
  }>(),
  {
    effect: 'light',
  }
)

const config = computed<StatusMapItem | undefined>(() => {
  const key = String(props.status)
  return props.map[key]
})
</script>

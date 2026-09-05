<!-- @ai-generated -->
<!--
  公共表格组件 ProTable（泛型）
  职责：封装 el-table + el-pagination，统一 loading、空状态、分页、字体粗细 300
  复用：F01 商品列表、F02 订单/提现列表、F03 用户列表

  泛型参数 T 为行数据类型，从 :data 自动推断，slot row 即为 T，业务层无需手动转换。

  用法：
    <ProTable
      :data="tableData"
      :columns="columns"
      :loading="loading"
      :pagination="{ page, page_size, total }"
      row-key="id"
      selectable
      @page-change="onPageChange"
      @size-change="onSizeChange"
      @selection-change="onSelectionChange"
    >
      <template #toolbar>
        <el-button @click="handleAdd">新增</el-button>
      </template>
      <template #col-goods_title="{ row }">
        <span class="link" @click="handleDetail(row)">{{ row.goods_title }}</span>
      </template>
      <template #col-action="{ row }">
        <el-button size="small" @click="handleEdit(row)">编辑</el-button>
      </template>
    </ProTable>
-->
<template>
  <div class="pro-table">
    <!-- 工具栏插槽 -->
    <div v-if="$slots.toolbar" class="pro-table__toolbar">
      <slot name="toolbar" />
    </div>

    <el-table
      ref="tableRef"
      :data="data"
      :row-key="rowKey"
      :loading="loading"
      border
      stripe
      style="width: 100%"
      @selection-change="handleSelectionChange"
    >
      <!-- 多选列 -->
      <el-table-column
        v-if="selectable"
        type="selection"
        width="48"
        align="center"
        :reserve-selection="!!rowKey"
      />
      <!-- 序号列 -->
      <el-table-column
        v-if="showIndex"
        type="index"
        label="序号"
        width="64"
        align="center"
        :index="indexMethod"
      />

      <!-- 动态列 -->
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth || 120"
        :align="col.align || 'left'"
        :fixed="col.fixed"
        :show-overflow-tooltip="col.showOverflowTooltip !== false"
        :sortable="col.sortable"
      >
        <template #default="scope">
          <slot
            v-if="$slots[`col-${col.prop}`]"
            :name="`col-${col.prop}`"
            :row="scope.row as unknown as T"
            :index="scope.$index"
          />
          <template v-else>
            {{ col.formatter ? col.formatter(getCell(scope.row, col.prop), rowAsRecord(scope.row)) : getCell(scope.row, col.prop) }}
          </template>
        </template>
      </el-table-column>

      <!-- 操作列插槽 -->
      <el-table-column
        v-if="$slots['col-action']"
        label="操作"
        :width="actionWidth"
        :fixed="actionFixed ? 'right' : false"
        align="center"
      >
        <template #default="scope">
          <slot name="col-action" :row="scope.row as unknown as T" :index="scope.$index" />
        </template>
      </el-table-column>

      <!-- 空状态 -->
      <template #empty>
        <el-empty description="暂无数据" :image-size="80" />
      </template>
    </el-table>

    <!-- 分页器 -->
    <div v-if="pagination" class="pro-table__pagination">
      <el-pagination
        :current-page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="pageSizes"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="handleCurrentChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends object = Record<string, unknown>">
// @ai-generated
import { ref } from 'vue'
import { ElTable, ElTableColumn, ElPagination, ElEmpty, type TableInstance } from 'element-plus'

/** 列配置 */
export interface ProTableColumn {
  /** 字段名（对应 row 的 key） */
  prop: string
  /** 列标题 */
  label: string
  /** 列宽（px） */
  width?: number | string
  /** 最小列宽（默认 120） */
  minWidth?: number | string
  /** 对齐方式 */
  align?: 'left' | 'center' | 'right'
  /** 固定列 */
  fixed?: 'left' | 'right' | boolean
  /** 是否可排序 */
  sortable?: boolean | string
  /** 单元格内容超出是否隐藏（默认 true） */
  showOverflowTooltip?: boolean
  /** 自定义格式化函数（优先级低于 slot） */
  formatter?: (value: unknown, row: Record<string, unknown>) => string
}

/** 分页配置 */
export interface ProTablePagination {
  page: number
  page_size: number
  total: number
}

const props = withDefaults(
  defineProps<{
    /** 表格数据 */
    data: T[]
    /** 列配置 */
    columns: ProTableColumn[]
    /** 加载状态 */
    loading?: boolean
    /** 行 key（用于多选 reserve-selection） */
    rowKey?: string
    /** 是否显示多选列 */
    selectable?: boolean
    /** 是否显示序号列 */
    showIndex?: boolean
    /** 分页配置（不传则不显示分页器） */
    pagination?: ProTablePagination
    /** 可选每页条数 */
    pageSizes?: number[]
    /** 操作列宽度 */
    actionWidth?: number | string
    /** 操作列是否固定右侧 */
    actionFixed?: boolean
  }>(),
  {
    loading: false,
    selectable: false,
    showIndex: false,
    pageSizes: () => [10, 20, 50, 100],
    actionWidth: 160,
    actionFixed: true,
  }
)

const emit = defineEmits<{
  (e: 'page-change', page: number): void
  (e: 'size-change', size: number): void
  (e: 'selection-change', selection: T[]): void
}>()

const tableRef = ref<TableInstance>()

/** 序号方法（跨页连续） */
function indexMethod(index: number): number {
  if (!props.pagination) return index + 1
  return (props.pagination.page - 1) * props.pagination.page_size + index + 1
}

/** 安全读取行字段（统一转 Record 读取，兼容无索引签名的 interface） */
function getCell(row: T, prop: string): unknown {
  return (row as unknown as Record<string, unknown>)[prop]
}

/** 行数据转 Record（供 formatter 使用） */
function rowAsRecord(row: T): Record<string, unknown> {
  return row as unknown as Record<string, unknown>
}

function handleCurrentChange(page: number) {
  emit('page-change', page)
}

function handleSizeChange(size: number) {
  emit('size-change', size)
}

function handleSelectionChange(selection: T[]) {
  emit('selection-change', selection)
}

/** 暴露清空选中方法（批量操作后调用） */
defineExpose({
  clearSelection: () => tableRef.value?.clearSelection(),
  getSelection: () => tableRef.value?.getSelectionRows(),
})
</script>

<style scoped>
.pro-table {
  width: 100%;
}

.pro-table__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.pro-table__pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 表格字体粗细 300（用户 UI 偏好） */
.pro-table :deep(.el-table) {
  font-weight: 300;
}

.pro-table :deep(.el-table .el-table__cell) {
  font-weight: 300;
}

.pro-table :deep(.el-table th.el-table__cell) {
  font-weight: 400;
}
</style>

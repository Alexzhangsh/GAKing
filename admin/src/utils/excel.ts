// @ai-generated
/**
 * Excel 导出工具（基于 SheetJS / xlsx）
 *
 * 用法：
 *   import { exportToExcel } from '@/utils/excel'
 *   exportToExcel('商品列表', columns, data)
 *
 * 说明：
 * - 前端导出，不依赖后端接口
 * - 单次导出限制 1000 条，超出请提示用户分批
 * - 文件名自动追加时间戳，避免覆盖
 */
import * as XLSX from 'xlsx'

/** 导出列配置 */
export interface ExcelColumn {
  /** 列标题 */
  header: string
  /** 数据字段名 */
  key: string
  /** 自定义单元格格式化 */
  formatter?: (value: unknown, row: Record<string, unknown>) => string | number
  /** 列宽（字符数） */
  width?: number
}

/**
 * 导出数据到 Excel 文件
 * @param filename 文件名（不含扩展名）
 * @param columns 列配置
 * @param data 数据行
 */
export function exportToExcel(
  filename: string,
  columns: ExcelColumn[],
  data: Record<string, unknown>[]
): void {
  if (!data || data.length === 0) {
    throw new Error('导出数据为空')
  }
  if (data.length > 1000) {
    throw new Error('单次导出最多 1000 条，请缩小筛选范围后分批导出')
  }

  // 转换为带表头的二维数组
  const header = columns.map((c) => c.header)
  const rows = data.map((item) =>
    columns.map((col) => {
      const val = item[col.key]
      return col.formatter ? col.formatter(val, item) : (val ?? '') as string | number
    })
  )
  const aoa = [header, ...rows]

  const ws = XLSX.utils.aoa_to_sheet(aoa)

  // 设置列宽
  ws['!cols'] = columns.map((c) => ({ wch: c.width || 16 }))

  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')

  // 文件名追加时间戳
  const ts = formatTimestamp(new Date())
  XLSX.writeFile(wb, `${filename}_${ts}.xlsx`)
}

/** 时间戳格式化：YYYYMMDD_HHmmss */
function formatTimestamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  )
}

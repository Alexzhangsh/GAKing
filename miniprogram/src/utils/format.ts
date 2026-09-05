// @ai-generated
/**
 * 通用格式化工具（M05 抽取：消除 6 个页面的 formatPrice 重复代码）
 */

/**
 * 价格格式化（保留 2 位小数）
 * @param val 数值（可能为 null/undefined/NaN）
 * @returns 格式化后的字符串，如 "12.00"
 */
export function formatPrice(val: number | null | undefined | string): string {
  if (val === null || val === undefined || val === '') return '0.00'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return '0.00'
  return num.toFixed(2)
}

/**
 * 金额格式化（带 ¥ 前缀）
 */
export function formatCurrency(val: number | null | undefined | string): string {
  return `¥${formatPrice(val)}`
}

/**
 * 时间戳格式化为日期字符串
 * @param ts 时间戳（秒或毫秒）或日期字符串
 * @param format 格式（默认 YYYY-MM-DD HH:mm）
 */
export function formatDate(
  ts: number | string | null | undefined,
  format: string = 'YYYY-MM-DD HH:mm'
): string {
  if (!ts) return ''
  let date: Date
  if (typeof ts === 'number') {
    // 兼容秒级和毫秒级时间戳
    date = ts < 1e12 ? new Date(ts * 1000) : new Date(ts)
  } else {
    date = new Date(ts)
    if (isNaN(date.getTime())) return ''
  }

  const pad = (n: number) => n < 10 ? '0' + n : String(n)
  return format
    .replace('YYYY', String(date.getFullYear()))
    .replace('MM', pad(date.getMonth() + 1))
    .replace('DD', pad(date.getDate()))
    .replace('HH', pad(date.getHours()))
    .replace('mm', pad(date.getMinutes()))
    .replace('ss', pad(date.getSeconds()))
}

export default {
  formatPrice,
  formatCurrency,
  formatDate
}

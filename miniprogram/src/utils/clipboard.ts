// @ai-generated
/**
 * 剪贴板链接解析工具
 *
 * 职责：
 * 1. 识别剪贴板内容是否为电商商品链接（淘宝/天猫/京东/拼多多等）
 * 2. 从剪贴板文本中提取商品链接（含口令解析）
 * 3. 提供 getClipboardData 封装（兼容 H5 / 小程序）
 */

/**
 * 电商链接特征正则
 * 覆盖主流电商平台的完整链接 + 淘口令/京东口令
 */
const ECOMMERCE_URL_REGEX =
  /(https?:\/\/[^\s]*?(?:taobao|tmall|jd|pinduoduo|yangkeduo|vip|suning|jumei|kaola|douyin|kuaishou)\.[a-z.]+[^\s]*)/i

/** 淘口令特征（￥xxx￥ 或 ₴xxx₴ 或 €xxx€） */
const TAOBAO_PASSWORD_REGEX = /[￥₴€][A-Za-z0-9]{8,}[￥₴€]/

/** 通用 URL 正则 */
const URL_REGEX = /https?:\/\/[^\s]+/i

/**
 * 判断文本是否为电商商品链接
 * 支持：完整 URL、淘口令、京东短链等
 */
export function isEcommerceLink(text: string): boolean {
  if (!text || typeof text !== 'string') return false
  const trimmed = text.trim()
  if (!trimmed) return false
  return (
    ECOMMERCE_URL_REGEX.test(trimmed) ||
    TAOBAO_PASSWORD_REGEX.test(trimmed) ||
    /^https?:\/\/(m|item|detail|mobile)\.[a-z]+\.(taobao|tmall|jd|pinduoduo)\.com/i.test(trimmed)
  )
}

/**
 * 从文本中提取第一个商品链接
 * 优先匹配电商 URL，其次匹配通用 URL
 * @returns 提取到的链接，未匹配返回空串
 */
export function extractEcommerceLink(text: string): string {
  if (!text || typeof text !== 'string') return ''
  const trimmed = text.trim()

  // 1. 优先匹配电商完整链接
  const ecommerceMatch = trimmed.match(ECOMMERCE_URL_REGEX)
  if (ecommerceMatch && ecommerceMatch[1]) {
    return ecommerceMatch[1]
  }

  // 2. 匹配通用 URL
  const urlMatch = trimmed.match(URL_REGEX)
  if (urlMatch && urlMatch[0]) {
    return urlMatch[0]
  }

  // 3. 淘口令无法直接转链，需整段提交（返回原文）
  if (TAOBAO_PASSWORD_REGEX.test(trimmed)) {
    return trimmed
  }

  return ''
}

/**
 * 获取剪贴板内容（兼容 H5 / 微信小程序）
 * @returns 剪贴板文本，失败返回空串
 */
export function getClipboardData(): Promise<string> {
  return new Promise((resolve) => {
    uni.getClipboardData({
      success: (res) => {
        resolve(res.data || '')
      },
      fail: () => {
        resolve('')
      }
    })
  })
}

/**
 * 复制文本到剪贴板
 */
export function setClipboardData(text: string): Promise<boolean> {
  return new Promise((resolve) => {
    uni.setClipboardData({
      data: text,
      success: () => resolve(true),
      fail: () => resolve(false)
    })
  })
}

/**
 * 检测剪贴板是否包含可转链的电商链接
 * 用于 App.vue / 首页 onShow 时主动提示用户转链
 * @returns 电商链接（可转链），无可转链内容返回空串
 */
export async function checkClipboardLink(): Promise<string> {
  const clipText = await getClipboardData()
  if (!clipText) return ''
  return extractEcommerceLink(clipText)
}

export default {
  isEcommerceLink,
  extractEcommerceLink,
  getClipboardData,
  setClipboardData,
  checkClipboardLink
}

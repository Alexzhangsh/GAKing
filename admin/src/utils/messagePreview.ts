// @ai-generated
/**
 * 消息模板预览工具（F04）
 *
 * 后端无预览接口，由前端将模板内容中的 {{keywordN}} 占位符替换为示例值，
 * 实现"消息推送预览"能力。
 *
 * F04-1 增强：
 * - 支持 HTML 富文本内容（wangEditor 输出）
 * - 支持自定义示例值映射（实时调整关键词展示）
 * - 占位符提取 / HTML 转义 / 纯文本剥离
 */

/** 示例值映射（按占位符名称生成演示数据） */
export function sampleValue(keyword: string): string {
  const map: Record<string, string> = {
    keyword1: '示例内容',
    keyword2: '示例数据',
    keyword3: '示例说明',
    order_id: '202607011234567890',
    amount: '12.80',
    goods_name: '示例商品',
    remark: '请及时查看',
  }
  return map[keyword] ?? `${keyword}示例`
}

/** 占位符正则：{{ 任意名称 }} */
const PLACEHOLDER_RE = /\{\{\s*([\w\u4e00-\u9fa5]+)\s*\}\}/g

/** HTML 转义（预览时防止示例值破坏 HTML 结构） */
export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 去除 HTML 标签，返回纯文本（用于空内容校验） */
export function stripHtml(html: string): string {
  if (!html) return ''
  const div = document.createElement('div')
  div.innerHTML = html
  return (div.textContent || '').trim()
}

/** 轻量 HTML 消毒：移除危险标签与事件属性（预览渲染安全） */
export function sanitizeHtml(html: string): string {
  if (!html) return ''
  const div = document.createElement('div')
  div.innerHTML = html
  div
    .querySelectorAll('script,style,iframe,object,embed,link,meta,form')
    .forEach((el) => el.remove())
  div.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase()
      const val = attr.value.trim().toLowerCase()
      if (
        /^on/i.test(name) ||
        ((name === 'src' || name === 'href') &&
          (val.startsWith('javascript:') || val.startsWith('data:text/html')))
      ) {
        el.removeAttribute(attr.name)
      }
    }
  })
  return div.innerHTML
}

/**
 * 提取内容中的所有占位符名称（去重，保持出现顺序）。
 * 兼容纯文本与 HTML 内容。
 */
export function extractPlaceholders(content: string): string[] {
  if (!content) return []
  const names: string[] = []
  const seen = new Set<string>()
  PLACEHOLDER_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = PLACEHOLDER_RE.exec(content)) !== null) {
    const name = m[1]
    if (!seen.has(name)) {
      seen.add(name)
      names.push(name)
    }
  }
  return names
}

/**
 * 将模板内容中的 {{xxx}} 占位符替换为示例值，返回预览渲染结果。
 * @param content 模板内容（支持 HTML）
 * @param sampleMap 自定义示例值映射（覆盖默认值）
 */
export function renderTemplatePreview(
  content: string,
  sampleMap?: Record<string, string>,
): string {
  if (!content) return ''
  return content.replace(PLACEHOLDER_RE, (_m, kw: string) => {
    const val = sampleMap?.[kw] ?? sampleValue(kw)
    return escapeHtml(val)
  })
}

/**
 * 校验内容是否包含至少一个占位符。
 * 用于提示用户占位符将展示为示例数据。
 */
export function hasPlaceholder(content: string): boolean {
  if (!content) return false
  PLACEHOLDER_RE.lastIndex = 0
  return PLACEHOLDER_RE.test(content)
}

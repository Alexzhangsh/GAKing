// @ai-generated
/**
 * F04 消息模板预览工具函数单元测试
 *
 * 覆盖：
 * 1. renderTemplatePreview 占位符替换（keywordN / 业务字段 / 未知字段 / 多占位符）
 * 2. hasPlaceholder 占位符存在性校验
 * 3. sampleValue 示例值映射
 *
 * 运行：npx vitest run src/__tests__/messagePreview.test.ts
 */
import { describe, it, expect } from 'vitest'
import { renderTemplatePreview, hasPlaceholder, sampleValue } from '@/utils/messagePreview'

describe('renderTemplatePreview', () => {
  it('should replace {{keywordN}} placeholder with sample value', () => {
    const result = renderTemplatePreview('您的订单 {{keyword1}} 已发货')
    expect(result).toBe('您的订单 示例内容 已发货')
  })

  it('should replace business keyword placeholders with sample data', () => {
    const result = renderTemplatePreview('订单 {{order_id}} 金额 {{amount}}')
    expect(result).toBe('订单 202607011234567890 金额 12.80')
  })

  it('should replace unknown keyword with keyword+示例', () => {
    const result = renderTemplatePreview('内容 {{custom_field}}')
    expect(result).toBe('内容 custom_field示例')
  })

  it('should replace multiple placeholders in one content', () => {
    const result = renderTemplatePreview('{{keyword1}} 与 {{keyword2}} 与 {{keyword3}}')
    expect(result).toBe('示例内容 与 示例数据 与 示例说明')
  })

  it('should keep placeholder spacing normalized', () => {
    const result = renderTemplatePreview('{{ keyword1 }}')
    expect(result).toBe('示例内容')
  })

  it('should return empty string for empty content', () => {
    expect(renderTemplatePreview('')).toBe('')
    expect(renderTemplatePreview(null as unknown as string)).toBe('')
  })

  it('should keep content without placeholder unchanged', () => {
    const content = '这是一条普通消息，没有变量'
    expect(renderTemplatePreview(content)).toBe(content)
  })
})

describe('hasPlaceholder', () => {
  it('should return true when content contains placeholder', () => {
    expect(hasPlaceholder('订单 {{order_id}} 已到账')).toBe(true)
  })

  it('should return false when content has no placeholder', () => {
    expect(hasPlaceholder('普通消息内容')).toBe(false)
  })

  it('should return false for empty content', () => {
    expect(hasPlaceholder('')).toBe(false)
  })
})

describe('sampleValue', () => {
  it('should return mapped value for known keyword', () => {
    expect(sampleValue('order_id')).toBe('202607011234567890')
    expect(sampleValue('amount')).toBe('12.80')
    expect(sampleValue('goods_name')).toBe('示例商品')
  })

  it('should return keyword+示例 for unknown keyword', () => {
    expect(sampleValue('unknown_thing')).toBe('unknown_thing示例')
  })
})

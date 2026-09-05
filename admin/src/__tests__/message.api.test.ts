// @ai-generated
/**
 * F04 营销消息 API 单元测试
 *
 * 覆盖：
 * 1. messageTemplateApi 所有方法（list/get/create/update/delete/toggle）
 * 2. pushRecordApi 列表查询
 * 3. subscribeBindingApi 列表查询
 *
 * 运行：npx vitest run src/__tests__/message.api.test.ts
 */
import { describe, it, expect, vi } from 'vitest'
import { messageTemplateApi, pushRecordApi, subscribeBindingApi } from '@/api/message'
import request from '@/utils/request'

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('messageTemplateApi', () => {
  const mockTemplate = {
    id: 1,
    template_name: '订单提醒',
    template_type: 1,
    tmpl_id: 'wx_template_123',
    title: '您有新的订单',
    content: '订单编号：{{order_id}}，金额：{{amount}}',
    keywords: ['order_id', 'amount'],
    status: 1,
    remark: '订单通知模板',
    create_time: '2026-07-01 10:00:00',
    update_time: '2026-07-15 10:00:00',
  }

  describe('list', () => {
    it('should call GET /v1/admin/message/templates with params', async () => {
      const mockResponse = { total: 1, page: 1, page_size: 20, items: [mockTemplate] }
      vi.mocked(request.get).mockResolvedValue(mockResponse)

      const result = await messageTemplateApi.list({ page: 1, page_size: 20, template_type: 1 })

      expect(request.get).toHaveBeenCalledWith('/v1/admin/message/templates', {
        params: { page: 1, page_size: 20, template_type: 1 },
      })
      expect(result.items).toHaveLength(1)
    })
  })

  describe('get', () => {
    it('should call GET /v1/admin/message/templates/{id}', async () => {
      vi.mocked(request.get).mockResolvedValue(mockTemplate)

      const result = await messageTemplateApi.get(1)

      expect(request.get).toHaveBeenCalledWith('/v1/admin/message/templates/1')
      expect(result.template_name).toBe('订单提醒')
    })
  })

  describe('create', () => {
    it('should call POST /v1/admin/message/templates', async () => {
      const createData = {
        template_name: '新模板',
        template_type: 2,
        content: '测试内容',
      }
      vi.mocked(request.post).mockResolvedValue({ id: 2, ...createData, status: 1, create_time: null, update_time: null })

      const result = await messageTemplateApi.create(createData)

      expect(request.post).toHaveBeenCalledWith('/v1/admin/message/templates', createData)
      expect(result.template_name).toBe('新模板')
    })
  })

  describe('update', () => {
    it('should call PUT /v1/admin/message/templates/{id}', async () => {
      const updateData = { template_name: '更新后的模板' }
      vi.mocked(request.put).mockResolvedValue({ ...mockTemplate, ...updateData })

      const result = await messageTemplateApi.update(1, updateData)

      expect(request.put).toHaveBeenCalledWith('/v1/admin/message/templates/1', updateData)
      expect(result.template_name).toBe('更新后的模板')
    })
  })

  describe('delete', () => {
    it('should call DELETE /v1/admin/message/templates/{id}', async () => {
      vi.mocked(request.delete).mockResolvedValue(undefined)

      await messageTemplateApi.delete(1)

      expect(request.delete).toHaveBeenCalledWith('/v1/admin/message/templates/1')
    })
  })

  describe('toggle', () => {
    it('should call PUT /v1/admin/message/templates/{id}/toggle', async () => {
      const updated = { ...mockTemplate, status: 0 }
      vi.mocked(request.put).mockResolvedValue(updated)

      const result = await messageTemplateApi.toggle(1)

      expect(request.put).toHaveBeenCalledWith('/v1/admin/message/templates/1/toggle')
      expect(result.status).toBe(0)
    })
  })
})

describe('pushRecordApi', () => {
  describe('list', () => {
    it('should call GET /v1/admin/message/push-records with params', async () => {
      const mockResponse = { total: 1, page: 1, page_size: 20, items: [{ id: 1, template_id: '1', user_id: '100', push_status: 1, push_time: '2026-07-01 10:00:00', error_msg: '', create_time: '2026-07-01 10:00:00' }] }
      vi.mocked(request.get).mockResolvedValue(mockResponse)

      const result = await pushRecordApi.list({ page: 1, page_size: 20, push_status: 1 })

      expect(request.get).toHaveBeenCalledWith('/v1/admin/message/push-records', {
        params: { page: 1, page_size: 20, push_status: 1 },
      })
      expect(result.items).toHaveLength(1)
    })
  })
})

describe('subscribeBindingApi', () => {
  describe('list', () => {
    it('should call GET /v1/admin/message/subscriptions with params', async () => {
      const mockResponse = { total: 1, page: 1, page_size: 20, items: [{ id: 1, user_id: '100', template_id: '1', subscribe_status: 1, subscribe_time: '2026-07-01 10:00:00', expire_time: null, create_time: '2026-07-01 10:00:00' }] }
      vi.mocked(request.get).mockResolvedValue(mockResponse)

      const result = await subscribeBindingApi.list({ page: 1, page_size: 20, subscribe_status: 1 })

      expect(request.get).toHaveBeenCalledWith('/v1/admin/message/subscriptions', {
        params: { page: 1, page_size: 20, subscribe_status: 1 },
      })
      expect(result.items).toHaveLength(1)
    })
  })
})
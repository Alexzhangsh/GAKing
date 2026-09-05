// @ai-generated
/**
 * F04 渠道配置 API 单元测试
 *
 * 覆盖：
 * 1. channelConfigApi 所有方法（list/get/create/update/delete）
 * 2. channelTestApi.testKey 方法
 * 3. 请求参数构造、路径拼接、返回类型
 *
 * 运行：npx vitest run src/__tests__/channel.api.test.ts
 */
import { describe, it, expect, vi } from 'vitest'
import { channelConfigApi, channelTestApi } from '@/api/channel'
import request from '@/utils/request'

// Mock request 模块
vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('channelConfigApi', () => {
  const mockChannel = {
    id: 1,
    channel_code: 'myq',
    channel_name: '喵有券',
    api_token: 'test_token_123',
    api_secret: '***',
    pid: 'mm_123_456',
    settle_rate: 0.85,
    status: true,
    remark: '测试渠道',
    create_time: '2026-07-01 10:00:00',
    update_time: '2026-07-15 10:00:00',
  }

  describe('list', () => {
    it('should call GET /v1/admin/channel/list with params', async () => {
      const mockResponse = { total: 1, page: 1, page_size: 20, items: [mockChannel] }
      vi.mocked(request.get).mockResolvedValue(mockResponse)

      const result = await channelConfigApi.list({ page: 1, page_size: 20 })

      expect(request.get).toHaveBeenCalledWith('/v1/admin/channel/list', { params: { page: 1, page_size: 20 } })
      expect(result).toEqual(mockResponse)
    })

    it('should handle empty list', async () => {
      const mockResponse = { total: 0, page: 1, page_size: 20, items: [] }
      vi.mocked(request.get).mockResolvedValue(mockResponse)

      const result = await channelConfigApi.list({ page: 1, page_size: 20 })

      expect(result.items).toHaveLength(0)
      expect(result.total).toBe(0)
    })
  })

  describe('get', () => {
    it('should call GET /v1/admin/channel/{channelCode}', async () => {
      vi.mocked(request.get).mockResolvedValue(mockChannel)

      const result = await channelConfigApi.get('myq')

      expect(request.get).toHaveBeenCalledWith('/v1/admin/channel/myq')
      expect(result.channel_code).toBe('myq')
    })
  })

  describe('create', () => {
    it('should call POST /v1/admin/channel with data', async () => {
      const createData = {
        channel_code: 'orderx',
        channel_name: '订单侠',
        api_token: 'orderx_token',
        settle_rate: 0.8,
      }
      const created = { id: 2, ...createData, api_secret: '', pid: '', status: true, remark: '', create_time: null, update_time: null }
      vi.mocked(request.post).mockResolvedValue(created)

      const result = await channelConfigApi.create(createData)

      expect(request.post).toHaveBeenCalledWith('/v1/admin/channel', createData)
      expect(result.channel_code).toBe('orderx')
    })
  })

  describe('update', () => {
    it('should call PUT /v1/admin/channel/{channelCode} with data', async () => {
      const updateData = { channel_name: '新喵有券', settle_rate: 0.9 }
      vi.mocked(request.put).mockResolvedValue({ ...mockChannel, ...updateData })

      const result = await channelConfigApi.update('myq', updateData)

      expect(request.put).toHaveBeenCalledWith('/v1/admin/channel/myq', updateData)
      expect(result.channel_name).toBe('新喵有券')
    })
  })

  describe('delete', () => {
    it('should call DELETE /v1/admin/channel/{channelCode}', async () => {
      vi.mocked(request.delete).mockResolvedValue(undefined)

      await channelConfigApi.delete('myq')

      expect(request.delete).toHaveBeenCalledWith('/v1/admin/channel/myq')
    })
  })
})

describe('channelTestApi', () => {
  describe('testKey', () => {
    it('should call POST /v1/admin/channel/test-key with data', async () => {
      const testData = {
        channel_code: 'myq',
        api_token: 'test_token_123456',
        api_secret: 'test_secret',
      }
      const mockResult = {
        success: true,
        message: '密钥格式校验通过',
        channel_code: 'myq',
        token_length: 18,
        secret_length: 10,
      }
      vi.mocked(request.post).mockResolvedValue(mockResult)

      const result = await channelTestApi.testKey(testData)

      expect(request.post).toHaveBeenCalledWith('/v1/admin/channel/test-key', testData)
      expect(result.success).toBe(true)
    })

    it('should handle test failure', async () => {
      const testData = {
        channel_code: 'myq',
        api_token: 'invalid',
      }
      const mockResult = {
        success: false,
        message: '密钥验证失败',
        channel_code: 'myq',
      }
      vi.mocked(request.post).mockResolvedValue(mockResult)

      const result = await channelTestApi.testKey(testData)

      expect(result.success).toBe(false)
    })
  })
})
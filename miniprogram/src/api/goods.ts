// @ai-generated
/**
 * CPS 商品 API（对接 B01-B02 后端接口）
 *
 * 接口清单：
 * 1. GET  /api/public/goods/search        商品搜索（搜索桶限流）
 * 2. POST /api/public/goods/convert-link  链接转链（转链桶限流）
 *
 * 后端文件：src/api/public/cps_goods.py
 */
import http from '@/utils/request'
import type {
  ApiResponse,
  ChannelCode,
  ConvertLinkRequest,
  ConvertLinkResponse,
  GoodsSearchResponse
} from './types'

/**
 * 商品搜索
 * @param keyword 搜索关键词
 * @param page 页码（从1开始）
 * @param size 每页条数
 * @param channel_code 渠道标识 myq/orderx/dta
 */
export function searchGoods(
  keyword: string,
  page: number = 1,
  size: number = 20,
  channel_code: ChannelCode = 'myq'
): Promise<ApiResponse<GoodsSearchResponse>> {
  return http.get<GoodsSearchResponse>('/api/public/goods/search', {
    keyword,
    page,
    size,
    channel_code
  })
}

/**
 * 链接转链
 * @param original_url 原始商品链接
 * @param user_channel_id 用户渠道溯源标识(relation_id)
 * @param channel_code 渠道标识
 */
export function convertLink(
  original_url: string,
  user_channel_id: string,
  channel_code: ChannelCode = 'myq'
): Promise<ApiResponse<ConvertLinkResponse>> {
  const body: ConvertLinkRequest = {
    original_url,
    user_channel_id,
    channel_code
  }
  return http.post<ConvertLinkResponse>('/api/public/goods/convert-link', body)
}

export default {
  searchGoods,
  convertLink
}

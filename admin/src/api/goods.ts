// @ai-generated
/**
 * 商品管理后台 API
 * 对接后端路由：/api/v1/admin/goods（权限码：goods:manage）
 * 字段与 src/schemas/b13_goods_admin.py 严格对齐（snake_case）
 *
 * 注意：后端 Decimal 字段在列表响应中序列化为 string，
 * 在 upsert 请求体中接受 number 或 string（Pydantic Decimal 自动转换）。
 */
import request, { PageResponse } from '@/utils/request'

/** 商品管理列表项响应 */
export interface GoodsItem {
  id: number
  goods_id: string
  source_channel: string
  goods_title: string
  goods_img: string
  /** 销售价（元，后端 Decimal 序列化为 string） */
  sale_price: string
  /** 商品原价（元） */
  original_price: string
  /** 佣金比例（%，后端 Decimal 序列化为 string） */
  commission_rate: string
  /** 普通会员奖金（元） */
  bonus_price_normal: string
  /** 普通会员奖金比例（%） */
  bonus_rate_normal: string
  /** VIP会员奖金（元） */
  bonus_price_vip: string
  /** VIP会员奖金比例（%） */
  bonus_rate_vip: string
  category: string
  shop_name: string
  /** 上下架状态：on_shelf=上架 / off_shelf=下架 */
  shelf_status: 'on_shelf' | 'off_shelf'
  sort_order: number
  admin_remark: string
  create_time: string | null
  update_time: string | null
}

/** 商品详情响应（继承列表项，扩展最后操作管理员ID） */
export interface GoodsDetail extends GoodsItem {
  last_admin_id: number
}

/** 商品列表查询参数 */
export interface GoodsListParams {
  keyword?: string
  source_channel?: string
  shelf_status?: 'on_shelf' | 'off_shelf'
  category?: string
  page: number
  page_size: number
}

/** 商品创建/更新请求（upsert by goods_id + source_channel） */
export interface GoodsUpsertRequest {
  goods_id: string
  source_channel: string
  goods_title?: string
  goods_img?: string
  /** 销售价（元），前端传 number 或 string 均可 */
  sale_price?: number | string
  /** 商品原价（元） */
  original_price?: number | string
  /** 佣金比例（%），前端传 number 或 string 均可 */
  commission_rate?: number | string
  /** 普通会员奖金（元） */
  bonus_price_normal?: number | string
  /** 普通会员奖金比例（%） */
  bonus_rate_normal?: number | string
  /** VIP会员奖金（元） */
  bonus_price_vip?: number | string
  /** VIP会员奖金比例（%） */
  bonus_rate_vip?: number | string
  category?: string
  shop_name?: string
  sort_order?: number
  admin_remark?: string
}

/** 商品上下架请求 */
export interface GoodsShelfRequest {
  shelf_status: 'on_shelf' | 'off_shelf'
}

/** 商品批量上下架请求 */
export interface GoodsBatchShelfRequest {
  goods_ids: string[]
  source_channel: string
  shelf_status: 'on_shelf' | 'off_shelf'
}

/** 商品批量删除请求 */
export interface GoodsBatchDeleteRequest {
  goods_ids: string[]
  source_channel: string
}

/** 商品 CPS 同步请求 */
export interface GoodsSyncRequest {
  source_channel: string
  keyword?: string
  page?: number
  page_size?: number
}

/** CPS 同步响应（后端返回同步数量等） */
export interface GoodsSyncResult {
  synced_count?: number
  [key: string]: unknown
}

/** 上下架/批量操作响应 */
export interface GoodsOpResult {
  affected?: number
  [key: string]: unknown
}

/** 商品列表响应（分页 + 上下架总数统计） */
export interface GoodsListResponse extends PageResponse<GoodsItem> {
  /** 总上架商品数（与列表共用非 shelf_status 过滤条件） */
  total_on_shelf: number
  /** 总下架商品数（与列表共用非 shelf_status 过滤条件） */
  total_off_shelf: number
}

export const goodsApi = {
  /** 商品列表筛选查询 */
  list(params: GoodsListParams) {
    return request.get<GoodsListResponse>('/v1/admin/goods', { params })
  },

  /** 商品详情（注意 source_channel 作为 query 必传） */
  getDetail(goodsId: string, sourceChannel: string) {
    return request.get<GoodsDetail | null>(`/v1/admin/goods/${goodsId}`, {
      params: { source_channel: sourceChannel },
    })
  },

  /** 创建/更新商品（upsert by goods_id + channel） */
  upsert(data: GoodsUpsertRequest) {
    return request.post<GoodsDetail>('/v1/admin/goods', data)
  },

  /** 单个商品上下架 */
  updateShelf(goodsId: string, sourceChannel: string, shelfStatus: 'on_shelf' | 'off_shelf') {
    return request.put<GoodsOpResult>(
      `/v1/admin/goods/${goodsId}/shelf`,
      { shelf_status: shelfStatus },
      { params: { source_channel: sourceChannel } }
    )
  },

  /** 批量上下架 */
  batchShelf(data: GoodsBatchShelfRequest) {
    return request.put<GoodsOpResult>('/v1/admin/goods/batch/shelf', data)
  },

  /** 批量删除商品管理记录 */
  batchDelete(data: GoodsBatchDeleteRequest) {
    return request.delete<GoodsOpResult>('/v1/admin/goods/batch', { data })
  },

  /** 从 CPS 渠道同步商品到本地管理表 */
  syncFromCps(data: GoodsSyncRequest) {
    return request.post<GoodsSyncResult>('/v1/admin/goods/sync', data)
  },
}

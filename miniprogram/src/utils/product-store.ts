// @ai-generated
/**
 * 商品数据页面间传递工具
 *
 * 由于 uni-app 子包页面间无法通过路由传递复杂对象，
 * 使用模块级变量暂存商品数据，避免详情页通过 searchGoods 重新搜索（hash ID 搜索不到）
 */
import type { GoodsItem } from '@/api/types'

let _pendingProduct: GoodsItem | null = null

/** 存入待传递的商品数据（列表页点击时调用） */
export function setPendingProduct(item: GoodsItem) {
  _pendingProduct = item
}

/** 取出并清除待传递的商品数据（详情页 onLoad 时调用） */
export function takePendingProduct(): GoodsItem | null {
  const data = _pendingProduct
  _pendingProduct = null
  return data
}
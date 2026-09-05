// @ai-generated
/**
 * 商品收藏夹本地缓存工具
 *
 * 职责：
 * 1. 基于 uni.setStorageSync 实现收藏夹本地持久化
 * 2. 支持收藏 / 取消收藏 / 查询是否已收藏
 * 3. 支持分类筛选 / 清理失效商品
 * 4. 收藏时保存商品快照，商品下架后用户仍可查看一次
 *
 * 数据结构：FavoriteItem[] 存储于本地 key = FAVORITE_KEY
 */
import type { FavoriteItem, GoodsItem } from '@/api/types'

const FAVORITE_KEY = 'favorites'
/** 收藏夹最大容量（防止本地存储溢出） */
const MAX_FAVORITE_COUNT = 500

/**
 * 读取全部收藏列表
 */
export function getFavorites(): FavoriteItem[] {
  const str = uni.getStorageSync(FAVORITE_KEY)
  if (!str) return []
  try {
    const list = JSON.parse(str) as FavoriteItem[]
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

/**
 * 持久化收藏列表
 */
function saveFavorites(list: FavoriteItem[]): void {
  uni.setStorageSync(FAVORITE_KEY, JSON.stringify(list))
}

/**
 * 判断是否已收藏（按 goods_id 去重）
 */
export function isFavorited(goods_id: string): boolean {
  const list = getFavorites()
  return list.some((item) => item.goods_id === goods_id)
}

/**
 * 收藏商品（保存快照）
 * @returns true=新增收藏，false=已存在
 */
export function addFavorite(goods: GoodsItem): boolean {
  const list = getFavorites()
  if (list.some((item) => item.goods_id === goods.goods_id)) {
    return false
  }

  // 构造收藏快照（基于 GoodsItem 扩展收藏时间）
  const favorite: FavoriteItem = {
    ...goods,
    favorite_time: Date.now(),
    invalid: false
  }

  // 超过容量上限时移除最早的收藏
  if (list.length >= MAX_FAVORITE_COUNT) {
    list.sort((a, b) => a.favorite_time - b.favorite_time)
    list.shift()
  }

  list.unshift(favorite)
  saveFavorites(list)
  return true
}

/**
 * 取消收藏
 * @returns true=移除成功，false=未收藏
 */
export function removeFavorite(goods_id: string): boolean {
  const list = getFavorites()
  const idx = list.findIndex((item) => item.goods_id === goods_id)
  if (idx === -1) return false
  list.splice(idx, 1)
  saveFavorites(list)
  return true
}

/**
 * 切换收藏状态
 * @returns 当前是否收藏
 */
export function toggleFavorite(goods: GoodsItem): boolean {
  if (isFavorited(goods.goods_id)) {
    removeFavorite(goods.goods_id)
    return false
  }
  addFavorite(goods)
  return true
}

/**
 * 标记商品为已失效
 */
export function markInvalid(goods_id: string): void {
  const list = getFavorites()
  const item = list.find((i) => i.goods_id === goods_id)
  if (item) {
    item.invalid = true
    saveFavorites(list)
  }
}

/**
 * 清理所有已失效商品
 * @returns 清理的商品数量
 */
export function clearInvalidFavorites(): number {
  const list = getFavorites()
  const before = list.length
  const valid = list.filter((item) => !item.invalid)
  saveFavorites(valid)
  return before - valid.length
}

/**
 * 按类目筛选收藏
 * @param category 类目名，传空串表示不筛选
 */
export function getFavoritesByCategory(category: string): FavoriteItem[] {
  const list = getFavorites()
  if (!category) return list
  return list.filter((item) => item.category === category)
}

/**
 * 获取所有收藏商品的类目列表（去重）
 */
export function getFavoriteCategories(): string[] {
  const list = getFavorites()
  const categories = list
    .map((item) => item.category)
    .filter((cat) => !!cat)
  return Array.from(new Set(categories))
}

/**
 * 收藏总数
 */
export function getFavoriteCount(): number {
  return getFavorites().length
}

export default {
  getFavorites,
  isFavorited,
  addFavorite,
  removeFavorite,
  toggleFavorite,
  markInvalid,
  clearInvalidFavorites,
  getFavoritesByCategory,
  getFavoriteCategories,
  getFavoriteCount
}

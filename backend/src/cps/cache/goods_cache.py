# @ai-generated
"""
CPS 商品双层缓存管理器

设计要点：
1. 冷热双层结构
   - L1 热层（TTL=CacheTTL.HOT_GOODS_SEARCH=30min）：高频访问商品/热门搜索结果
   - L2 冷层（TTL=CacheTTL.COLD_GOODS_SEARCH=10min）：兜底层，所有回源数据都写入
   - 差异化 TTL：按商品销量判定热度（>=HOT_THRESHOLD 走 L1，>=NORMAL_THRESHOLD 走 L2 长TTL）

2. 三大防护
   - 防穿透：布隆过滤器（goods_id 不存在直接返回）+ 空值兜底（空结果写 __EMPTY__，TTL=60s）
   - 防击穿：互斥锁（LockUtil.acquire_with_wait）+ 双重检查（DCL）
   - 防雪崩：复用 RedisClient._jitter_ttl 内置 ±20% 随机抖动

3. 对接 B01 适配器
   - 自动调 adapter.search_goods 拉取并回写缓存
   - 支持注入自定义 fetcher（便于 B04 单测 mock）
"""
import logging
from typing import Awaitable, Callable, List, Optional

from src.common.lock_util import LockUtil
from src.common.redis_client import RedisClient
from src.config.constants import CacheTTL
from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.dto import GoodsDTO, GoodsSearchResult
from src.cps.cache.bloom_filter import GoodsBloomFilter

logger = logging.getLogger("cps.cache.goods")

# ── 缓存键前缀（裸 key，RedisClient.add_prefix 会补 REDIS_PREFIX）──────────
# 实际 Redis key 形如 gaking:prod:goods:l1:{goods_id}
CACHE_KEY_GOODS_L1 = "goods:l1:"  # 单商品热层
CACHE_KEY_GOODS_L2 = "goods:l2:"  # 单商品冷层
CACHE_KEY_SEARCH_L1 = "goods:search:l1:"  # 搜索结果热层
CACHE_KEY_SEARCH_L2 = "goods:search:l2:"  # 搜索结果冷层

# ── 互斥锁（传裸 key 给 LockUtil，由其补 LOCK_PREFIX）──────────────────────
# 实际 Redis key：gaking:prod:lock:goods:lock:goods:{goods_id}
LOCK_KEY_GOODS = "goods:lock:goods:"
LOCK_KEY_SEARCH = "goods:lock:search:"

# ── 锁超时配置（秒）────────────────────────────────────────────────────────
GOODS_LOCK_TIMEOUT = 10  # 单商品回源锁持有上限
GOODS_LOCK_WAIT = 3  # 单商品锁等待上限（防击穿排队）
SEARCH_LOCK_TIMEOUT = 15  # 搜索回源锁持有上限
SEARCH_LOCK_WAIT = 5  # 搜索锁等待上限

# ── 商品热度阈值（销量判定，差异化 TTL 依据）──────────────────────────────
GOODS_HOT_SALES_THRESHOLD = 10_000  # 热门：销量 >= 1万 → 写 L1（30min）
GOODS_NORMAL_SALES_THRESHOLD = (
    1_000  # 普通：销量 >= 1千 → L2 用 COLD_GOODS_SEARCH(10min)
)
# 冷门：销量 < 1千 → L2 用 NORMAL_GOODS_SEARCH(5min)

# 类型别名：单商品回源函数
GoodsFetcher = Callable[[str], Awaitable[Optional[GoodsDTO]]]
# 搜索回源函数
SearchFetcher = Callable[[str, int, int], Awaitable[GoodsSearchResult]]


class GoodsCacheManager:
    """商品双层缓存管理器

    对外统一入口：
    - get_goods(goods_id): 单商品获取（双层 + 布隆 + 空值兜底 + 互斥锁）
    - search_goods(keyword, page, size): 搜索结果获取（双层 + 空值兜底 + 互斥锁）

    Args:
        adapter: CPS 适配器（B01），用于默认回源实现
        bloom_filter: 布隆过滤器实例（默认单例即可）
    """

    def __init__(
        self,
        adapter: Optional[BaseCpsAdapter] = None,
        bloom_filter: Optional[GoodsBloomFilter] = None,
    ) -> None:
        self._adapter: Optional[BaseCpsAdapter] = adapter
        self._bloom: GoodsBloomFilter = bloom_filter or GoodsBloomFilter()

    def set_adapter(self, adapter: BaseCpsAdapter) -> None:
        """注入适配器（支持延迟绑定）"""
        self._adapter = adapter

    # ════════════════════════════════════════════════════
    # 单商品获取（双层缓存）
    # ════════════════════════════════════════════════════

    async def get_goods(
        self,
        goods_id: str,
        fetcher: Optional[GoodsFetcher] = None,
    ) -> Optional[GoodsDTO]:
        """获取单个商品（L1→L2→回源，含防穿透/击穿）

        Args:
            goods_id: 商品唯一ID
            fetcher: 自定义回源函数（默认调适配器 search_goods 兜底）
        Returns:
            商品 DTO / None（不存在或回源失败）
        """
        if not goods_id:
            return None

        # 1. 布隆过滤器预检（防穿透第一道）
        #    不存在 → 直接返回 None，不查缓存不回源
        #    异常时降级为"可能存在"，继续走缓存
        bloom_exists = await self._bloom.exists(goods_id)
        if not bloom_exists:
            logger.debug(f"bloom miss, skip cache: goods_id={goods_id}")
            return None

        # 2. 查 L1 热层
        l1_key = f"{CACHE_KEY_GOODS_L1}{goods_id}"
        goods = await self._get_goods_from_cache(l1_key)
        if goods is not None:
            logger.debug(f"L1 hit: goods_id={goods_id}")
            return goods

        # 3. 查 L2 冷层
        l2_key = f"{CACHE_KEY_GOODS_L2}{goods_id}"
        # 空值标记检查（防穿透：上次回源无数据，TTL 内不再回源）
        if await RedisClient.is_empty_cache(l2_key):
            logger.debug(f"empty marker hit, skip backfill: goods_id={goods_id}")
            return None
        goods = await self._get_goods_from_cache(l2_key)
        if goods is not None:
            logger.debug(f"L2 hit, backfill L1: goods_id={goods_id}")
            # 回写 L1（按热度决定 TTL）
            await self._write_goods_to_l1(l1_key, goods)
            return goods

        # 4. L1/L2 都未命中，加互斥锁防击穿
        lock_key = f"{LOCK_KEY_GOODS}{goods_id}"
        owner = await LockUtil.acquire_with_wait(
            lock_key, timeout=GOODS_LOCK_TIMEOUT, wait_timeout=GOODS_LOCK_WAIT
        )
        if owner is None:
            # 锁等待超时（可能并发回源压力大），降级返回 None
            logger.warning(f"lock wait timeout: goods_id={goods_id}")
            return None

        try:
            # 5. 双重检查（DCL）：锁竞争期间可能已被其他线程回源填充
            if await RedisClient.is_empty_cache(l2_key):
                logger.debug(f"DCL empty marker hit: goods_id={goods_id}")
                return None
            goods = await self._get_goods_from_cache(l2_key)
            if goods is not None:
                logger.debug(f"DCL L2 hit after lock: goods_id={goods_id}")
                await self._write_goods_to_l1(l1_key, goods)
                return goods

            # 6. 回源拉取
            goods = await self._fetch_goods(goods_id, fetcher)
            if goods is None:
                # 7a. 回源无数据 → 写空值标记（防穿透第二道）
                await RedisClient.set_empty_cache(l2_key)
                logger.info(f"backfill empty marker: goods_id={goods_id}")
                return None

            # 7b. 回写 L2（冷层）
            await self._write_goods_to_l2(l2_key, goods)
            # 回写 L1（按热度判定）
            await self._write_goods_to_l1(l1_key, goods)
            # 加入布隆过滤器
            await self._bloom.add(goods_id)
            logger.info(
                f"backfill cache done: goods_id={goods_id} "
                f"sales={goods.sales_volume}"
            )
            return goods
        finally:
            await LockUtil.release_lock(lock_key, owner)

    # ════════════════════════════════════════════════════
    # 搜索结果获取（双层缓存）
    # ════════════════════════════════════════════════════

    async def search_goods(
        self,
        keyword: str,
        page: int = 1,
        size: int = 20,
        fetcher: Optional[SearchFetcher] = None,
    ) -> GoodsSearchResult:
        """搜索商品（L1→L2→回源，含空值兜底/互斥锁）

        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）
            size: 每页条数
            fetcher: 自定义回源函数（默认调适配器 search_goods）
        Returns:
            搜索结果（可能为空列表，但非 None）
        """
        if not keyword:
            return GoodsSearchResult(page=page, size=size)

        cache_suffix = f"{keyword}:{page}:{size}"

        # 1. 查 L1 热层
        l1_key = f"{CACHE_KEY_SEARCH_L1}{cache_suffix}"
        result = await self._get_search_from_cache(l1_key)
        if result is not None:
            logger.debug(f"search L1 hit: keyword={keyword} page={page}")
            return result

        # 2. 查 L2 冷层
        l2_key = f"{CACHE_KEY_SEARCH_L2}{cache_suffix}"
        result = await self._get_search_from_cache(l2_key)
        if result is not None:
            logger.debug(f"search L2 hit, backfill L1: keyword={keyword}")
            # 回写 L1（按结果热度判定）
            await self._write_search_to_l1(l1_key, result)
            return result

        # 3. 空值标记检查（防穿透）
        if await RedisClient.is_empty_cache(l2_key):
            logger.debug(f"search empty marker hit: keyword={keyword}")
            return GoodsSearchResult(page=page, size=size)

        # 4. 加互斥锁防击穿
        lock_key = f"{LOCK_KEY_SEARCH}{cache_suffix}"
        owner = await LockUtil.acquire_with_wait(
            lock_key, timeout=SEARCH_LOCK_TIMEOUT, wait_timeout=SEARCH_LOCK_WAIT
        )
        if owner is None:
            logger.warning(f"search lock wait timeout: keyword={keyword}")
            return GoodsSearchResult(page=page, size=size)

        try:
            # 5. 双重检查
            result = await self._get_search_from_cache(l2_key)
            if result is not None:
                logger.debug(f"search DCL L2 hit: keyword={keyword}")
                await self._write_search_to_l1(l1_key, result)
                return result

            if await RedisClient.is_empty_cache(l2_key):
                logger.debug(f"search DCL empty marker hit: keyword={keyword}")
                return GoodsSearchResult(page=page, size=size)

            # 6. 回源拉取
            result = await self._fetch_search(keyword, page, size, fetcher)

            # 7a. 空结果 → 写空值标记（TTL=60s，防穿透）
            if not result.items:
                await RedisClient.set_empty_cache(l2_key)
                logger.info(f"search backfill empty marker: keyword={keyword}")
                return result

            # 7b. 回写 L2 + 按热度回写 L1 + 布隆过滤器
            await self._write_search_to_l2(l2_key, result)
            await self._write_search_to_l1(l1_key, result)
            # 把搜索到的 goods_id 批量加入布隆过滤器
            goods_ids: List[str] = [g.goods_id for g in result.items if g.goods_id]
            if goods_ids:
                await self._bloom.add_batch(goods_ids)
            logger.info(
                f"search backfill done: keyword={keyword} "
                f"items={len(result.items)} total={result.total}"
            )
            return result
        finally:
            await LockUtil.release_lock(lock_key, owner)

    # ════════════════════════════════════════════════════
    # 缓存读写原语
    # ════════════════════════════════════════════════════

    @staticmethod
    async def _get_goods_from_cache(key: str) -> Optional[GoodsDTO]:
        """从缓存读取单商品（空值标记返回 None）"""
        if await RedisClient.is_empty_cache(key):
            return None
        data = await RedisClient.get_json(key)
        if data is None:
            return None
        try:
            return GoodsDTO.model_validate(data)
        except Exception as e:
            logger.warning(f"deserialize GoodsDTO failed for key={key}: {e}")
            return None

    @staticmethod
    async def _get_search_from_cache(key: str) -> Optional[GoodsSearchResult]:
        """从缓存读取搜索结果（空值标记返回 None）"""
        if await RedisClient.is_empty_cache(key):
            return None
        data = await RedisClient.get_json(key)
        if data is None:
            return None
        try:
            return GoodsSearchResult.model_validate(data)
        except Exception as e:
            logger.warning(f"deserialize GoodsSearchResult failed for key={key}: {e}")
            return None

    @staticmethod
    async def _write_goods_to_l2(key: str, goods: GoodsDTO) -> None:
        """写 L2 冷层（按销量差异化 TTL）"""
        ttl = GoodsCacheManager._calc_l2_ttl(goods.sales_volume)
        await RedisClient.set_json(key, goods.model_dump(), expire=ttl)

    @staticmethod
    async def _write_goods_to_l1(key: str, goods: GoodsDTO) -> None:
        """写 L1 热层（仅热门商品写入，非热门跳过）"""
        if goods.sales_volume < GOODS_HOT_SALES_THRESHOLD:
            return
        await RedisClient.set_json(
            key, goods.model_dump(), expire=int(CacheTTL.HOT_GOODS_SEARCH)
        )

    @staticmethod
    async def _write_search_to_l2(key: str, result: GoodsSearchResult) -> None:
        """写搜索结果 L2 冷层（按结果中最高销量差异化 TTL）"""
        max_sales = max((g.sales_volume for g in result.items), default=0)
        ttl = GoodsCacheManager._calc_l2_ttl(max_sales)
        await RedisClient.set_json(key, result.model_dump(), expire=ttl)

    @staticmethod
    async def _write_search_to_l1(key: str, result: GoodsSearchResult) -> None:
        """写搜索结果 L1 热层（仅热门搜索结果写入）"""
        max_sales = max((g.sales_volume for g in result.items), default=0)
        if max_sales < GOODS_HOT_SALES_THRESHOLD:
            return
        await RedisClient.set_json(
            key, result.model_dump(), expire=int(CacheTTL.HOT_GOODS_SEARCH)
        )

    @staticmethod
    def _calc_l2_ttl(max_sales: int) -> int:
        """根据销量计算 L2 TTL（差异化策略）

        - 销量 >= HOT_THRESHOLD: COLD_GOODS_SEARCH(10min) —— 已达热门但 L1 已覆盖，L2 用中等 TTL
        - 销量 >= NORMAL_THRESHOLD: COLD_GOODS_SEARCH(10min)
        - 销量 < NORMAL_THRESHOLD: NORMAL_GOODS_SEARCH(5min) —— 冷门商品短 TTL，避免低质数据占空间
        """
        if max_sales >= GOODS_NORMAL_SALES_THRESHOLD:
            return int(CacheTTL.COLD_GOODS_SEARCH)
        return int(CacheTTL.NORMAL_GOODS_SEARCH)

    # ════════════════════════════════════════════════════
    # 回源实现
    # ════════════════════════════════════════════════════

    async def _fetch_goods(
        self, goods_id: str, fetcher: Optional[GoodsFetcher]
    ) -> Optional[GoodsDTO]:
        """回源拉取单个商品

        优先级：自定义 fetcher > 适配器 get_goods_by_id > 适配器 search_goods 兜底
        """
        if fetcher is not None:
            try:
                return await fetcher(goods_id)
            except Exception as e:
                logger.error(
                    f"custom goods fetcher failed: goods_id={goods_id} err={e}"
                )
                return None

        if self._adapter is None:
            logger.warning("no adapter bound, cannot fetch goods")
            return None

        try:
            # B01 基类提供 get_goods_by_id，默认返回 None；子类可覆写
            goods = self._adapter.get_goods_by_id(goods_id)
            if goods is not None:
                return goods
            # 兜底：用 goods_id 作为关键词搜索，取首条
            result = await self._adapter.search_goods(keyword=goods_id, page=1, size=1)
            if result.items:
                return result.items[0]
            return None
        except Exception as e:
            logger.error(
                f"adapter fetch goods failed: goods_id={goods_id} err={e}",
                exc_info=True,
            )
            return None

    async def _fetch_search(
        self,
        keyword: str,
        page: int,
        size: int,
        fetcher: Optional[SearchFetcher],
    ) -> GoodsSearchResult:
        """回源拉取搜索结果"""
        if fetcher is not None:
            try:
                return await fetcher(keyword, page, size)
            except Exception as e:
                logger.error(f"custom search fetcher failed: keyword={keyword} err={e}")
                return GoodsSearchResult(page=page, size=size)

        if self._adapter is None:
            logger.warning("no adapter bound, cannot fetch search")
            return GoodsSearchResult(page=page, size=size)

        try:
            return await self._adapter.search_goods(
                keyword=keyword, page=page, size=size
            )
        except Exception as e:
            logger.error(
                f"adapter search failed: keyword={keyword} err={e}", exc_info=True
            )
            return GoodsSearchResult(page=page, size=size)

    # ════════════════════════════════════════════════════
    # 缓存管理（主动失效）
    # ════════════════════════════════════════════════════

    async def invalidate_goods(self, goods_id: str) -> int:
        """主动失效单商品缓存（L1+L2）"""
        count = 0
        count += await RedisClient.delete(f"{CACHE_KEY_GOODS_L1}{goods_id}")
        count += await RedisClient.delete(f"{CACHE_KEY_GOODS_L2}{goods_id}")
        if count:
            logger.info(f"invalidated goods cache: goods_id={goods_id} keys={count}")
        return count

    async def invalidate_search(
        self, keyword: str, page: int = 1, size: int = 20
    ) -> int:
        """主动失效搜索缓存（L1+L2）"""
        suffix = f"{keyword}:{page}:{size}"
        count = 0
        count += await RedisClient.delete(f"{CACHE_KEY_SEARCH_L1}{suffix}")
        count += await RedisClient.delete(f"{CACHE_KEY_SEARCH_L2}{suffix}")
        if count:
            logger.info(
                f"invalidated search cache: keyword={keyword} page={page} keys={count}"
            )
        return count

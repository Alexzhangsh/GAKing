# @ai-generated
"""
B16 商品预热定时任务作业定义

六项定时任务：
1. 喵有券渠道预热（cron: 0 0 1,13 * *）
   按类目轮换拉取高佣商品，佣金≥15%、售价 9.9-99 元，禁止固定搜索关键词
2. 订单侠渠道预热（cron: 30 0 1,13 * *）
   轮询食品/家居/服饰/美妆类目，佣金≥12%、月销量≥100
3. 热门商品刷新（cron: 0 0 */6 * *）
   存量热门商品（popularity>0）每 6 小时刷新一次
4. 普通商品刷新（cron: 0 2 * * *）
   存量普通商品（popularity=0）每日 02:00 刷新一次
5. 冷品过期标记（cron: 0 10 2 * *）
   连续 30 天无浏览商品标记为 expired
6. 冷品软删除（cron: 0 10 2 * *，与过期标记同 cron 分步执行）
   过期满 7 天宽限期的商品执行软删除

设计约定（硬性规范）：
1. 定时预热任务不得传入搜索关键词；关键词检索仅用于前端手动同步、用户搜索兜底；
2. 沿用现有适配器 MiaoyouquanAdapter、DingdanxiaAdapter；
3. 独立开关、gak 前缀 Redis 分布式锁、接口异常捕获、日志记录；
4. upsert 更新：静态资料非必要不覆盖，只刷新价格、优惠券、佣金、上下架状态；
5. 单渠道/单批次失败不阻断整体执行。

手动调用验证：
    from src.scheduler.goods_warming_jobs import warming_myq, warming_orderx, ...
    await warming_myq()           # 喵有券预热
    await warming_orderx()        # 订单侠预热
    await refresh_hot_goods()     # 热门商品刷新
    await refresh_normal_goods()  # 普通商品刷新
    await cleanup_expired_goods() # 冷品清理
"""
import logging
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_GOODS_WARMING_CURSOR,
    CACHE_TTL_GOODS_WARMING_CURSOR,
    TASK_CLEANUP_BATCH_SIZE,
    TASK_CLEANUP_EXPIRY_DAYS,
    TASK_CLEANUP_GRACE_DAYS,
    TASK_GOODS_CLEANUP_ENABLE,
    TASK_GOODS_REFRESH_ENABLE,
    TASK_GOODS_WARMING_ENABLE,
    TASK_WARMING_MYQ_CATEGORIES,
    TASK_WARMING_MYQ_ENABLE,
    TASK_WARMING_MYQ_MAX_PRICE,
    TASK_WARMING_MYQ_MIN_COMMISSION_RATE,
    TASK_WARMING_MYQ_MIN_PRICE,
    TASK_WARMING_ORDERX_CATEGORIES,
    TASK_WARMING_ORDERX_ENABLE,
    TASK_WARMING_ORDERX_MIN_COMMISSION_RATE,
    TASK_WARMING_ORDERX_MIN_SALES,
    TASK_WARMING_MAX_PAGES,
    TASK_WARMING_PAGE_SIZE,
)
from src.cps.adapter.dto import GoodsDTO
from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter
from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter
from src.dao.goods_management_dao import GoodsManagementDAO
from src.db.init_db import DatabaseManager
from src.config.env_config import EnvConfig

logger = logging.getLogger("scheduler.goods_warming")


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════


def _get_dynamic_upsert_data(goods: GoodsDTO) -> Dict[str, Any]:
    """构建 upsert 动态字段数据

    约束：静态资料（标题、主图、店铺名、类目）非必要不覆盖，
    仅刷新价格、优惠券信息、佣金比例、上下架状态。
    """
    now = datetime.now()
    data = {
        "sale_price": goods.sale_price,
        "commission_rate": goods.commission_rate,
        "shelf_status": "on_shelf",  # 预热拉取到的商品默认上架
        "last_sync_time": now,
        "sync_status": "normal",
    }
    # 新品创建时补充静态资料
    # （upsert 内部通过 get_by_goods_id_channel 判断，存在则不覆盖，
    #   但 DAO 的 update_by_id 会覆盖传入字段，故此处仅传动态字段）
    return data


def _get_create_data(goods: GoodsDTO) -> Dict[str, Any]:
    """构建新建商品完整数据"""
    now = datetime.now()
    return {
        "goods_title": goods.goods_title,
        "goods_img": goods.goods_img,
        "sale_price": goods.sale_price,
        "commission_rate": goods.commission_rate,
        "category": goods.category,
        "shop_name": goods.shop_name,
        "shelf_status": "on_shelf",
        "last_sync_time": now,
        "popularity": 0,
        "sync_status": "normal",
    }


async def _get_category_cursor(channel_code: str, categories: List[str]) -> int:
    """从 Redis 获取当前预热类目游标，按天轮换

    Returns:
        当前应使用的类目索引
    """
    redis_key = f"{CACHE_KEY_GOODS_WARMING_CURSOR}{channel_code}"
    cursor_str = await RedisClient.get(redis_key)
    if cursor_str is not None:
        try:
            return int(cursor_str) % len(categories)
        except (ValueError, TypeError):
            pass
    # 默认从 0 开始
    return 0


async def _update_category_cursor(channel_code: str, categories: List[str]) -> int:
    """更新预热类目游标到下一个类目

    Returns:
        下一个类目索引
    """
    redis_key = f"{CACHE_KEY_GOODS_WARMING_CURSOR}{channel_code}"
    current = await _get_category_cursor(channel_code, categories)
    next_cursor = (current + 1) % len(categories)
    await RedisClient.setex(redis_key, CACHE_TTL_GOODS_WARMING_CURSOR, str(next_cursor))
    return next_cursor


async def _warming_channel_goods(
    channel_code: str,
    categories: List[str],
    adapter,
    min_commission_rate: Decimal,
    extra_filter_func,
    task_name: str,
) -> Dict[str, Any]:
    """渠道预热通用逻辑

    Args:
        channel_code: 渠道码（myq / orderx）
        categories: 类目列表
        adapter: 渠道适配器实例
        min_commission_rate: 最低佣金比例
        extra_filter_func: 额外筛选函数，接收 GoodsDTO 返回 bool
        task_name: 任务名称（日志用）

    Returns:
        执行结果 dict
    """
    if not TASK_GOODS_WARMING_ENABLE:
        logger.info("[%s] 预热总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "预热总开关关闭"}

    # 渠道级开关检查
    channel_enable_map = {
        "myq": TASK_WARMING_MYQ_ENABLE,
        "orderx": TASK_WARMING_ORDERX_ENABLE,
    }
    if not channel_enable_map.get(channel_code, True):
        logger.info("[%s] 渠道开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": f"{channel_code} 渠道预热开关关闭"}

    # 获取当前轮换类目
    category_idx = await _get_category_cursor(channel_code, categories)
    category = categories[category_idx]
    logger.info(
        "[%s] 任务开始执行 category=%s (idx=%s/%s)",
        task_name,
        category,
        category_idx + 1,
        len(categories),
    )

    pulled_count = 0
    upserted_count = 0
    skipped_count = 0
    errors: List[str] = []

    try:
        async with DatabaseManager.get_session() as db:
            dao = GoodsManagementDAO(db)

            # 多页拉取
            for page in range(1, TASK_WARMING_MAX_PAGES + 1):
                try:
                    # 使用类目名称作为搜索关键词（非固定关键词，按天轮换）
                    result = await adapter.search_goods(
                        keyword=category,
                        page=page,
                        size=TASK_WARMING_PAGE_SIZE,
                    )
                except Exception as e:
                    err_msg = f"第{page}页拉取失败: {e}"
                    logger.error("[%s] %s", task_name, err_msg)
                    errors.append(err_msg)
                    continue

                items: List[GoodsDTO] = result.items
                if not items:
                    logger.info("[%s] 第%s页无更多商品，停止拉取", task_name, page)
                    break

                for goods in items:
                    pulled_count += 1

                    # 佣金比例筛选
                    if goods.commission_rate < min_commission_rate:
                        skipped_count += 1
                        continue

                    # 额外筛选条件
                    if extra_filter_func and not extra_filter_func(goods):
                        skipped_count += 1
                        continue

                    # upsert 到 goods_management
                    try:
                        # 先检查是否存在
                        existing = await dao.get_by_goods_id_channel(
                            goods.goods_id, channel_code
                        )
                        if existing:
                            # 更新：仅刷新动态字段
                            update_data = _get_dynamic_upsert_data(goods)
                            await dao.update_by_id(existing.id, update_data)
                        else:
                            # 新建：补充 goods_id 和 source_channel（模型 nullable=False 约束）
                            create_data = _get_create_data(goods)
                            create_data["goods_id"] = goods.goods_id
                            create_data["source_channel"] = channel_code
                            await dao.create(create_data)
                        upserted_count += 1
                    except Exception as e:
                        err_msg = f"商品 upsert 失败 goods_id={goods.goods_id}: {e}"
                        logger.warning("[%s] %s", task_name, err_msg)
                        errors.append(err_msg)

                logger.info(
                    "[%s] 第%s页完成 本页商品=%s 累计拉取=%s upsert=%s 跳过=%s",
                    task_name,
                    page,
                    len(items),
                    pulled_count,
                    upserted_count,
                    skipped_count,
                )

        # 更新类目游标到下一个
        next_idx = await _update_category_cursor(channel_code, categories)
        logger.info(
            "[%s] 任务完成 类目=%s→下一轮类目=%s 拉取=%s upsert=%s 跳过=%s 错误=%s",
            task_name,
            category,
            categories[next_idx],
            pulled_count,
            upserted_count,
            skipped_count,
            len(errors),
        )

        return {
            "status": "success" if not errors else "partial",
            "message": (
                f"预热完成: 类目={category}, 拉取={pulled_count}, "
                f"upsert={upserted_count}, 跳过={skipped_count}, 错误={len(errors)}"
            ),
            "category": category,
            "pulled_count": pulled_count,
            "upserted_count": upserted_count,
            "skipped_count": skipped_count,
            "error_count": len(errors),
            "errors": errors[:10],  # 最多返回 10 条错误
        }

    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "pulled_count": pulled_count,
            "upserted_count": upserted_count,
            "skipped_count": skipped_count,
            "error_count": len(errors),
        }


# ═══════════════════════════════════════════════════════════════════
# 任务1：喵有券渠道预热
# ═══════════════════════════════════════════════════════════════════


def _myq_extra_filter(goods: GoodsDTO) -> bool:
    """喵有券额外筛选条件：售价 9.9-99 元"""
    return TASK_WARMING_MYQ_MIN_PRICE <= goods.sale_price <= TASK_WARMING_MYQ_MAX_PRICE


async def warming_myq() -> Dict[str, Any]:
    """喵有券渠道预热任务

    cron: 0 0 1,13 * *（每日 01:00 和 13:00）
    筛选：佣金≥15%，售价 9.9-99 元，优先热销榜单，每日轮换抓取类目
    """
    adapter = MiaoyouquanAdapter()
    return await _warming_channel_goods(
        channel_code="myq",
        categories=TASK_WARMING_MYQ_CATEGORIES,
        adapter=adapter,
        min_commission_rate=TASK_WARMING_MYQ_MIN_COMMISSION_RATE,
        extra_filter_func=_myq_extra_filter,
        task_name="goods_warming_myq",
    )


# ═══════════════════════════════════════════════════════════════════
# 任务2：订单侠渠道预热
# ═══════════════════════════════════════════════════════════════════


def _orderx_extra_filter(goods: GoodsDTO) -> bool:
    """订单侠额外筛选条件：月销量≥100"""
    return goods.sales_volume >= TASK_WARMING_ORDERX_MIN_SALES


async def warming_orderx() -> Dict[str, Any]:
    """订单侠渠道预热任务

    cron: 30 0 1,13 * *（每日 01:30 和 13:30，错峰 30 分钟）
    筛选：佣金≥12%，月销量≥100，轮询食品/家居/服饰/美妆类目
    """
    # 订单侠暂未对接，token 为空时跳过
    if not EnvConfig.ORDERX_TOKEN:
        logger.info("[goods_warming_orderx] ORDERX_TOKEN 为空，跳过执行（渠道暂未对接）")
        return {"status": "skipped", "message": "ORDERX_TOKEN 为空，渠道暂未对接"}

    adapter = DingdanxiaAdapter()
    return await _warming_channel_goods(
        channel_code="orderx",
        categories=TASK_WARMING_ORDERX_CATEGORIES,
        adapter=adapter,
        min_commission_rate=TASK_WARMING_ORDERX_MIN_COMMISSION_RATE,
        extra_filter_func=_orderx_extra_filter,
        task_name="goods_warming_orderx",
    )


# ═══════════════════════════════════════════════════════════════════
# 任务3：热门商品刷新（每 6 小时）
# ═══════════════════════════════════════════════════════════════════


async def _refresh_products_by_list(
    products_list,
    adapter,
    channel_code: str,
    dao: GoodsManagementDAO,
    task_name: str,
) -> Dict[str, int]:
    """按商品列表逐条刷新（通过类目重新搜索匹配）

    由于适配器不支持按商品 ID 查详情，采用按类目重新搜索的方式，
    匹配已有的 goods_id 进行更新。
    """
    refreshed = 0
    skipped = 0
    errors = 0

    # 按类目分组，批量刷新
    category_groups: Dict[str, List[str]] = {}
    for p in products_list:
        cat = p.category or "其他"
        if cat not in category_groups:
            category_groups[cat] = []
        category_groups[cat].append(p.goods_id)

    for cat, goods_ids in category_groups.items():
        try:
            result = await adapter.search_goods(keyword=cat, page=1, size=100)
            now = datetime.now()
            remaining_ids = list(goods_ids)
            for goods in result.items:
                if goods.goods_id in remaining_ids:
                    existing = await dao.get_by_goods_id_channel(
                        goods.goods_id, channel_code
                    )
                    if existing:
                        await dao.update_by_id(
                            existing.id,
                            {
                                "sale_price": goods.sale_price,
                                "commission_rate": goods.commission_rate,
                                "last_sync_time": now,
                                "shelf_status": "on_shelf",
                            },
                        )
                        refreshed += 1
                    remaining_ids.remove(goods.goods_id)
            skipped += len(remaining_ids)
        except Exception as e:
            logger.warning("[%s] 类目 %s 刷新失败: %s", task_name, cat, e)
            errors += 1

    return {"refreshed": refreshed, "skipped": skipped, "errors": errors}


async def _refresh_by_channel(
    source_channel: str,
    is_hot: bool,
    task_name: str,
) -> Dict[str, Any]:
    """按渠道刷新存量商品

    Args:
        source_channel: 渠道码
        is_hot: True=热门商品刷新，False=普通商品刷新
        task_name: 任务名称
    """
    if not TASK_GOODS_REFRESH_ENABLE:
        logger.info("[%s] 刷新总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "刷新总开关关闭"}

    logger.info("[%s] 任务开始执行 channel=%s is_hot=%s", task_name, source_channel, is_hot)

    try:
        async with DatabaseManager.get_session() as db:
            dao = GoodsManagementDAO(db)

            if is_hot:
                products = await dao.list_hot_products(source_channel=source_channel)
            else:
                products = await dao.list_normal_products(source_channel=source_channel)

            if not products:
                logger.info("[%s] 无待刷新商品，跳过", task_name)
                return {
                    "status": "success",
                    "message": "无待刷新商品",
                    "total": 0,
                    "refreshed": 0,
                }

            adapter = _create_adapter(source_channel)
            if adapter is None:
                return {
                    "status": "failed",
                    "message": f"不支持的渠道: {source_channel}",
                    "total": 0,
                    "refreshed": 0,
                }

            result = await _refresh_products_by_list(
                products, adapter, source_channel, dao, task_name
            )

            logger.info(
                "[%s] 任务完成 total=%s refreshed=%s skipped=%s errors=%s",
                task_name,
                len(products),
                result["refreshed"],
                result["skipped"],
                result["errors"],
            )

            return {
                "status": "success",
                "message": (
                    f"刷新完成: 待刷={len(products)}, "
                    f"已刷={result['refreshed']}, "
                    f"跳过={result['skipped']}, "
                    f"错误={result['errors']}"
                ),
                "total": len(products),
                "refreshed": result["refreshed"],
                "skipped": result["skipped"],
                "errors": result["errors"],
            }

    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {"status": "failed", "message": str(e)}


def _create_adapter(channel_code: str):
    """创建渠道适配器实例"""
    if channel_code == "myq":
        return MiaoyouquanAdapter()
    elif channel_code == "orderx":
        return DingdanxiaAdapter()
    return None


async def refresh_hot_myq() -> Dict[str, Any]:
    """喵有券热门商品刷新（每 6 小时）"""
    return await _refresh_by_channel("myq", is_hot=True, task_name="refresh_hot_myq")


async def refresh_hot_orderx() -> Dict[str, Any]:
    """订单侠热门商品刷新（每 6 小时）"""
    return await _refresh_by_channel("orderx", is_hot=True, task_name="refresh_hot_orderx")


async def refresh_normal_myq() -> Dict[str, Any]:
    """喵有券普通商品刷新（每日 02:00）"""
    return await _refresh_by_channel("myq", is_hot=False, task_name="refresh_normal_myq")


async def refresh_normal_orderx() -> Dict[str, Any]:
    """订单侠普通商品刷新（每日 02:00）"""
    return await _refresh_by_channel("orderx", is_hot=False, task_name="refresh_normal_orderx")


# ═══════════════════════════════════════════════════════════════════
# 任务5+6：冷品清理（过期标记 + 软删除）
# ═══════════════════════════════════════════════════════════════════


async def cleanup_expired_goods() -> Dict[str, Any]:
    """冷品清理任务

    cron: 0 10 2 * *（每日 02:10）
    两步操作：
    1. 连续 TASK_CLEANUP_EXPIRY_DAYS 天无浏览 → sync_status=expired
    2. expired 状态超过 TASK_CLEANUP_GRACE_DAYS 天 → is_delete=True（软删除）
    """
    task_name = "cleanup_expired_goods"

    if not TASK_GOODS_CLEANUP_ENABLE:
        logger.info("[%s] 清理总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "清理总开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)

    marked_expired = 0
    soft_deleted = 0

    try:
        async with DatabaseManager.get_session() as db:
            dao = GoodsManagementDAO(db)

            # 第一步：标记过期商品（连续 30 天无浏览）
            expired_products = await dao.list_expired_products(
                expiry_days=TASK_CLEANUP_EXPIRY_DAYS
            )
            if expired_products:
                expired_ids = [p.id for p in expired_products]
                # 分批处理
                for i in range(0, len(expired_ids), TASK_CLEANUP_BATCH_SIZE):
                    batch = expired_ids[i : i + TASK_CLEANUP_BATCH_SIZE]
                    affected = await dao.batch_update_sync_status(batch, "expired")
                    marked_expired += affected

                logger.info(
                    "[%s] 过期标记完成 candidates=%s actual=%s",
                    task_name,
                    len(expired_products),
                    marked_expired,
                )
            else:
                logger.info("[%s] 无连续30天无浏览商品需要标记过期", task_name)

            # 第二步：软删除过期宽限期已满的商品
            delete_candidates = await dao.list_soft_delete_candidates(
                grace_days=TASK_CLEANUP_GRACE_DAYS
            )
            if delete_candidates:
                delete_ids = [p.id for p in delete_candidates]
                for i in range(0, len(delete_ids), TASK_CLEANUP_BATCH_SIZE):
                    batch = delete_ids[i : i + TASK_CLEANUP_BATCH_SIZE]
                    affected = await dao.batch_soft_delete(batch)
                    soft_deleted += affected

                logger.info(
                    "[%s] 软删除完成 candidates=%s actual=%s",
                    task_name,
                    len(delete_candidates),
                    soft_deleted,
                )
            else:
                logger.info("[%s] 无过期商品需要软删除", task_name)

        logger.info(
            "[%s] 任务完成 标记过期=%s 软删除=%s",
            task_name,
            marked_expired,
            soft_deleted,
        )

        return {
            "status": "success",
            "message": f"清理完成: 标记过期={marked_expired}, 软删除={soft_deleted}",
            "marked_expired": marked_expired,
            "soft_deleted": soft_deleted,
        }

    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "marked_expired": marked_expired,
            "soft_deleted": soft_deleted,
        }


# ═══════════════════════════════════════════════════════════════════
# 任务注册（由 scheduler_jobs.py 调用）
# ═══════════════════════════════════════════════════════════════════

from src.config.constants import (
    TASK_CRON_WARMING_MYQ,
    TASK_CRON_WARMING_ORDERX,
    TASK_CRON_REFRESH_HOT,
    TASK_CRON_REFRESH_NORMAL,
    TASK_CRON_CLEANUP_EXPIRED,
    TASK_GOODS_WARMING_LOCK_TIMEOUT,
    TASK_GOODS_REFRESH_LOCK_TIMEOUT,
    TASK_GOODS_CLEANUP_LOCK_TIMEOUT,
)
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import _run_with_lock


def register_goods_warming_jobs() -> None:
    """注册商品预热/刷新/清理定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 调用。
    定时频率 / 开关 / 锁超时均来自 constants.py，禁止硬编码。
    """
    # 任务1：喵有券渠道预热 —— 每日 01:00 和 13:00
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="goods_warming_myq",
        cron_expr=TASK_CRON_WARMING_MYQ,
        args=("goods_warming_myq", warming_myq, TASK_GOODS_WARMING_LOCK_TIMEOUT),
    )

    # 任务2：订单侠渠道预热 —— 每日 01:30 和 13:30（错峰 30 分钟）
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="goods_warming_orderx",
        cron_expr=TASK_CRON_WARMING_ORDERX,
        args=("goods_warming_orderx", warming_orderx, TASK_GOODS_WARMING_LOCK_TIMEOUT),
    )

    # 任务3：喵有券热门商品刷新 —— 每 6 小时
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="refresh_hot_myq",
        cron_expr=TASK_CRON_REFRESH_HOT,
        args=("refresh_hot_myq", refresh_hot_myq, TASK_GOODS_REFRESH_LOCK_TIMEOUT),
    )

    # 任务4：订单侠热门商品刷新 —— 每 6 小时
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="refresh_hot_orderx",
        cron_expr=TASK_CRON_REFRESH_HOT,
        args=("refresh_hot_orderx", refresh_hot_orderx, TASK_GOODS_REFRESH_LOCK_TIMEOUT),
    )

    # 任务5：普通商品刷新（喵有券+订单侠合并）—— 每日 02:00
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="refresh_normal_myq",
        cron_expr=TASK_CRON_REFRESH_NORMAL,
        args=("refresh_normal_myq", refresh_normal_myq, TASK_GOODS_REFRESH_LOCK_TIMEOUT),
    )

    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="refresh_normal_orderx",
        cron_expr=TASK_CRON_REFRESH_NORMAL,
        args=("refresh_normal_orderx", refresh_normal_orderx, TASK_GOODS_REFRESH_LOCK_TIMEOUT),
    )

    # 任务6：冷品清理 —— 每日 02:10
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="cleanup_expired_goods",
        cron_expr=TASK_CRON_CLEANUP_EXPIRED,
        args=("cleanup_expired_goods", cleanup_expired_goods, TASK_GOODS_CLEANUP_LOCK_TIMEOUT),
    )

    logger.info(
        "Goods warming jobs registered: myq(%s), orderx(%s), "
        "refresh_hot(%s), refresh_normal(%s), cleanup(%s)",
        TASK_CRON_WARMING_MYQ,
        TASK_CRON_WARMING_ORDERX,
        TASK_CRON_REFRESH_HOT,
        TASK_CRON_REFRESH_NORMAL,
        TASK_CRON_CLEANUP_EXPIRED,
    )
# @ai-generated
"""
B05 订单同步定时任务作业定义

三渠道错峰轮询拉取第三方 CPS 订单：
- 任务3：喵有券订单同步（cron */10 * * * *，每10分钟，0/10/20/30/40/50 分）
- 任务4：订单侠订单同步（cron 3-59/10 * * * *，每10分钟偏移3分）
- 任务5：大淘客订单同步（cron 6-59/10 * * * *，每10分钟偏移6分）

三渠道错峰 3 分钟，避免同时调用渠道 API 触发限流。

设计约定（硬性规范）：
1. 复用 scheduler_jobs._run_with_lock 分布式锁模式（防集群并发）；
2. 任务开关/锁超时/cron 全部来自 constants.py，禁止硬编码；
3. 单渠道任务失败不影响其他渠道执行（独立 try/except）；
4. 任务函数自带 try/except + 日志，单窗口失败不阻断整体；
5. 手动可调用验证（可直接 await sync_myq_orders()）。

手动调用验证：
    from src.scheduler.order_sync_jobs import sync_myq_orders, sync_orderx_orders, sync_dta_orders
    await sync_myq_orders()      # 喵有券同步
    await sync_orderx_orders()   # 订单侠同步
    await sync_dta_orders()      # 大淘客同步
"""
import logging
import traceback
from typing import Any, Dict

from src.common.lock_util import LockUtil
from src.config.constants import (
    LOCK_KEY_ORDER_SYNC,
    TASK_ORDER_SYNC_DTA_ENABLE,
    TASK_ORDER_SYNC_ENABLE,
    TASK_ORDER_SYNC_LOCK_TIMEOUT,
    TASK_ORDER_SYNC_MYQ_ENABLE,
    TASK_ORDER_SYNC_ORDERX_ENABLE,
    TASK_CRON_ORDER_SYNC_DTA,
    TASK_CRON_ORDER_SYNC_MYQ,
    TASK_CRON_ORDER_SYNC_ORDERX,
)
from src.dao.order_sync_dao import OrderSyncDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import _run_with_lock
from src.services.order_sync_service import OrderSyncService

logger = logging.getLogger("scheduler.order_sync_jobs")


# ── 任务3：喵有券订单同步 ─────────────────────────────────────────


async def sync_myq_orders() -> Dict[str, Any]:
    """喵有券订单同步任务

    流程：检查开关 → 获取 DB 会话 → 调用 OrderSyncService.pull_channel_orders
    单渠道独立 try/except，失败返回 failed 状态，不阻断其他渠道。
    """
    task_name = "order_sync_myq"

    if not TASK_ORDER_SYNC_ENABLE:
        logger.info("[%s] 总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "订单同步总开关关闭"}

    if not TASK_ORDER_SYNC_MYQ_ENABLE:
        logger.info("[%s] 渠道开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "喵有券渠道开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)
    try:
        async with DatabaseManager.get_session() as db:
            sync_dao = OrderSyncDAO(db)
            service = OrderSyncService(sync_dao)
            result = await service.pull_channel_orders("myq")
        logger.info(
            "[%s] 任务完成 status=%s pulled=%s inserted=%s updated=%s",
            task_name,
            result.get("status"),
            result.get("pulled_count"),
            result.get("inserted_count"),
            result.get("updated_count"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 任务执行失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e), "channel_code": "myq"}


# ── 任务4：订单侠订单同步 ─────────────────────────────────────────


async def sync_orderx_orders() -> Dict[str, Any]:
    """订单侠订单同步任务"""
    task_name = "order_sync_orderx"

    if not TASK_ORDER_SYNC_ENABLE:
        logger.info("[%s] 总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "订单同步总开关关闭"}

    if not TASK_ORDER_SYNC_ORDERX_ENABLE:
        logger.info("[%s] 渠道开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "订单侠渠道开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)
    try:
        async with DatabaseManager.get_session() as db:
            sync_dao = OrderSyncDAO(db)
            service = OrderSyncService(sync_dao)
            result = await service.pull_channel_orders("orderx")
        logger.info(
            "[%s] 任务完成 status=%s pulled=%s inserted=%s updated=%s",
            task_name,
            result.get("status"),
            result.get("pulled_count"),
            result.get("inserted_count"),
            result.get("updated_count"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 任务执行失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e), "channel_code": "orderx"}


# ── 任务5：大淘客订单同步 ─────────────────────────────────────────


async def sync_dta_orders() -> Dict[str, Any]:
    """大淘客订单同步任务"""
    task_name = "order_sync_dta"

    if not TASK_ORDER_SYNC_ENABLE:
        logger.info("[%s] 总开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "订单同步总开关关闭"}

    if not TASK_ORDER_SYNC_DTA_ENABLE:
        logger.info("[%s] 渠道开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "大淘客渠道开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)
    try:
        async with DatabaseManager.get_session() as db:
            sync_dao = OrderSyncDAO(db)
            service = OrderSyncService(sync_dao)
            result = await service.pull_channel_orders("dta")
        logger.info(
            "[%s] 任务完成 status=%s pulled=%s inserted=%s updated=%s",
            task_name,
            result.get("status"),
            result.get("pulled_count"),
            result.get("inserted_count"),
            result.get("updated_count"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 任务执行失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e), "channel_code": "dta"}


# ── 任务注册 ───────────────────────────────────────────────────────


def _make_lock_args(channel_code: str) -> tuple:
    """构造 _run_with_lock 的 args 参数（task_name, func, lock_timeout）"""
    channel_lock_map = {
        "myq": ("order_sync_myq", sync_myq_orders),
        "orderx": ("order_sync_orderx", sync_orderx_orders),
        "dta": ("order_sync_dta", sync_dta_orders),
    }
    task_name, func = channel_lock_map[channel_code]
    return (task_name, func, TASK_ORDER_SYNC_LOCK_TIMEOUT)


def register_order_sync_jobs() -> None:
    """注册三渠道订单同步定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 调用。
    三渠道使用不同 cron 表达式错峰执行，避免并发限流。
    定时频率 / 开关 / 锁超时均来自 constants.py，禁止硬编码。
    """
    # 任务3：喵有券订单同步 —— 每10分钟（0/10/20/30/40/50 分）
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="order_sync_myq",
        cron_expr=TASK_CRON_ORDER_SYNC_MYQ,
        args=_make_lock_args("myq"),
    )

    # 任务4：订单侠订单同步 —— 每10分钟偏移3分（3/13/23/33/43/53 分）
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="order_sync_orderx",
        cron_expr=TASK_CRON_ORDER_SYNC_ORDERX,
        args=_make_lock_args("orderx"),
    )

    # 任务5：大淘客订单同步 —— 每10分钟偏移6分（6/16/26/36/46/56 分）
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="order_sync_dta",
        cron_expr=TASK_CRON_ORDER_SYNC_DTA,
        args=_make_lock_args("dta"),
    )

    logger.info(
        "Order sync jobs registered: myq(%s), orderx(%s), dta(%s)",
        TASK_CRON_ORDER_SYNC_MYQ,
        TASK_CRON_ORDER_SYNC_ORDERX,
        TASK_CRON_ORDER_SYNC_DTA,
    )

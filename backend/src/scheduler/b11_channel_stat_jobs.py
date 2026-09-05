# @ai-generated
"""
B11-1 渠道每日统计定时任务

任务说明：
每日 01:00 统计前一日各渠道的订单数据，写入 gaking_channel_daily_stat 表
支持按渠道维度聚合：订单数、支付金额、佣金、退款等

设计约定：
1. 使用分布式锁防止集群并发执行
2. 单条渠道统计失败不阻断整体流程
3. 统计日期范围为前一日 [昨天 00:00, 今天 00:00)
"""
import logging
import traceback
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import and_, func, select

from src.common.lock_util import LockUtil
from src.config.b11_constants import (
    TASK_CHANNEL_DAILY_STAT_ENABLE,
    TASK_CHANNEL_DAILY_STAT_LOCK_TIMEOUT,
    TASK_CRON_CHANNEL_DAILY_STAT,
)
from src.dao.b11_channel_dao import ChannelDailyStatDAO
from src.db.init_db import DatabaseManager
from src.models.business.order_model import Order
from src.scheduler.scheduler import TaskScheduler

logger = logging.getLogger("scheduler.b11_channel_stat")


# ── 统计逻辑 ───────────────────────────────────────────────


async def channel_daily_stat() -> Dict[str, Any]:
    """渠道每日订单统计

    统计前一日（[昨天 00:00, 今天 00:00)）各渠道的订单数据：
    - 总订单数、支付总金额、总佣金
    - 用户佣金、平台佣金
    - 已结算订单数
    - 退款订单数、退款金额

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "stat_date": str, "channels": List[str], "stat_count": int}
    """
    task_name = "channel_daily_stat"

    if not TASK_CHANNEL_DAILY_STAT_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "任务开关关闭"}

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    start_time = datetime.combine(yesterday, datetime.min.time())
    end_time = datetime.combine(today, datetime.min.time())

    stat_date = yesterday
    logger.info(
        "[%s] 任务开始执行 统计日期=%s 区间=[%s, %s)",
        task_name, stat_date, start_time, end_time,
    )

    try:
        async with DatabaseManager.get_session() as db:
            # 1. 按渠道聚合前一日订单数据
            stmt = (
                select(
                    Order.channel_code,
                    func.count(Order.id).label("order_count"),
                    func.coalesce(func.sum(Order.pay_amount), 0).label("total_pay_amount"),
                    func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                    func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
                    func.coalesce(func.sum(Order.platform_commission), 0).label("platform_commission"),
                    func.coalesce(
                        func.sum(
                            func.if_(Order.order_status == 40, 1, 0)
                        ), 0
                    ).label("settled_count"),
                    func.coalesce(
                        func.sum(
                            func.if_(Order.order_status == 50, 1, 0)
                        ), 0
                    ).label("refund_count"),
                    func.coalesce(
                        func.sum(
                            func.if_(Order.order_status == 50, Order.pay_amount, 0)
                        ), 0
                    ).label("refund_amount"),
                )
                .where(
                    and_(
                        Order.is_delete == False,  # noqa: E712
                        Order.create_time >= start_time,
                        Order.create_time < end_time,
                    )
                )
                .group_by(Order.channel_code)
            )
            result = await db.execute(stmt)
            rows = result.all()

            if not rows:
                logger.info("[%s] 统计日期 %s 无订单数据", task_name, stat_date)
                return {
                    "status": "success",
                    "message": "无订单数据",
                    "stat_date": stat_date.isoformat(),
                    "channels": [],
                    "stat_count": 0,
                }

            # 2. 写入每日统计表
            dao = ChannelDailyStatDAO(db)
            channels = []
            for row in rows:
                channel_code = row.channel_code or "unknown"
                try:
                    await dao.upsert_stat(
                        stat_date=stat_date,
                        channel_code=channel_code,
                        order_count=int(row.order_count or 0),
                        total_pay_amount=float(row.total_pay_amount or 0),
                        total_commission=float(row.total_commission or 0),
                        user_commission=float(row.user_commission or 0),
                        platform_commission=float(row.platform_commission or 0),
                        settled_count=int(row.settled_count or 0),
                        refund_count=int(row.refund_count or 0),
                        refund_amount=float(row.refund_amount or 0),
                    )
                    channels.append(channel_code)
                    logger.info(
                        "[%s] 写入统计 channel=%s date=%s order_count=%s",
                        task_name, channel_code, stat_date, row.order_count,
                    )
                except Exception as e:
                    logger.error(
                        "[%s] 写入渠道统计失败 channel=%s error=%s",
                        task_name, channel_code, e,
                    )

            logger.info(
                "[%s] 统计完成 date=%s 渠道数=%s",
                task_name, stat_date, len(channels),
            )
            return {
                "status": "success",
                "message": f"统计完成: {len(channels)} 个渠道",
                "stat_date": stat_date.isoformat(),
                "channels": channels,
                "stat_count": len(channels),
            }

    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "stat_date": stat_date.isoformat(),
            "channels": [],
            "stat_count": 0,
        }


# ── 分布式锁包装 ───────────────────────────────────────────


async def _run_with_lock() -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底

    S04 P2-1：锁冲突时先短等待重试（5s），降低任务跳过概率；
    仍失败则记录锁冲突计数并跳过。
    """
    lock_owner = None
    task_name = "channel_daily_stat"
    try:
        lock_owner = await LockUtil.acquire_with_wait(
            f"scheduler:{task_name}",
            timeout=TASK_CHANNEL_DAILY_STAT_LOCK_TIMEOUT,
            wait_timeout=5,
            poll_interval=0.5,
        )
        if lock_owner is None:
            await LockUtil.record_lock_conflict(task_name)
            logger.warning("[channel_daily_stat] 等待5s后仍未获取到分布式锁，跳过本次执行")
            return {"status": "skipped", "message": "未获取到分布式锁，跳过"}
        return await channel_daily_stat()
    except Exception as e:
        logger.error("[channel_daily_stat] 任务执行异常: %s\n%s", e, traceback.format_exc())
        return {"status": "failed", "message": str(e)}
    finally:
        if lock_owner is not None:
            await LockUtil.release_lock(f"scheduler:{task_name}", lock_owner)


# ── 注册 ───────────────────────────────────────────────────


def register_b11_channel_stat_jobs() -> None:
    """注册渠道每日统计定时任务"""
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="channel_daily_stat",
        cron_expr=TASK_CRON_CHANNEL_DAILY_STAT,
        args=(),
    )
    logger.info(
        "B11 channel daily stat job registered: %s",
        TASK_CRON_CHANNEL_DAILY_STAT,
    )
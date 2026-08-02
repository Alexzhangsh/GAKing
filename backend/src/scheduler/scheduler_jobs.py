# @ai-generated
"""
APScheduler 定时任务作业定义

任务1：超时未支付订单自动关闭（cron */5 * * * *，每5分钟）
    条件：order_status=PENDING 且 create_time 早于 (now - TASK_ORDER_EXPIRE_MINUTES)
    动作：批量更新为 INVALID，写操作自动 commit，commit 后失效订单详情缓存

任务2：每日佣金对账统计（cron 10 0 * * *，每日 00:10）
    统计前一日 transfer_status=SUCCESS 的佣金流水，按推广员(user_id)汇总总额与订单量
    日志输出对账结果，并失效涉及的 commission_sum / order 详情缓存
    ⚠️ B07 整改：余额入账已下沉至 B07 的 batch_settle_commissions 定时任务
    （settle_order_commission_atomic 在结算时直接 FOR UPDATE 更新余额），
    本任务仅做对账核查与缓存失效，不再做余额写入，避免双重入账。

设计约定（硬性规范）：
1. 所有 DB 操作调用现有 DAO（OrderDAO / CommissionFlowDAO），写操作由 DAO 自动 commit；
2. 状态变更后由 DAO 内置缓存失效逻辑处理，本层不直接操作 Redis 业务缓存；
3. 完整 try/except + 日志；批量任务单条失败不阻断整体执行；
4. 定时频率、超时分钟数、任务开关全部来自 constants.py，禁止硬编码；
5. 每个任务通过分布式锁（gaking:prod:lock:scheduler:{name}）防止集群并发重复执行。

手动调用验证：
    from src.scheduler.scheduler_jobs import close_expired_unpaid_orders, daily_commission_reconciliation
    await close_expired_unpaid_orders()        # 任务1
    await daily_commission_reconciliation()    # 任务2
"""
import logging
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from src.common.lock_util import LockUtil
from src.config.constants import (
    TASK_CLOSE_EXPIRED_ORDERS_ENABLE,
    TASK_CLOSE_EXPIRED_ORDERS_LOCK_TIMEOUT,
    TASK_CRON_CLOSE_EXPIRED_ORDERS,
    TASK_CRON_DAILY_COMMISSION_RECONCILIATION,
    TASK_DAILY_COMMISSION_RECONCILIATION_ENABLE,
    TASK_DAILY_COMMISSION_RECONCILIATION_LOCK_TIMEOUT,
    TASK_ORDER_EXPIRE_MINUTES,
    TransferStatus,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler

logger = logging.getLogger("scheduler.jobs")


# ── 任务1：超时未支付订单自动关闭 ─────────────────────────────────────


async def close_expired_unpaid_orders() -> Dict[str, Any]:
    """关闭超时未支付订单

    条件：order_status == PENDING 且 create_time < (now - TASK_ORDER_EXPIRE_MINUTES)
    动作：调用 OrderDAO.close_expired_unpaid_orders 批量置为 INVALID（自动 commit + 失效缓存）

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "closed_count": int, "order_ids": List[int]}
    """
    task_name = "close_expired_unpaid_orders"

    if not TASK_CLOSE_EXPIRED_ORDERS_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "任务开关关闭",
            "closed_count": 0,
            "order_ids": [],
        }

    cutoff = datetime.now() - timedelta(minutes=TASK_ORDER_EXPIRE_MINUTES)
    logger.info("[%s] 任务开始执行 cutoff=%s", task_name, cutoff)

    try:
        async with DatabaseManager.get_session() as db:
            order_dao = OrderDAO(db)
            order_ids, affected = await order_dao.close_expired_unpaid_orders(cutoff)

        if not order_ids:
            logger.info("[%s] 无超时未支付订单需要关闭", task_name)
            return {
                "status": "success",
                "message": "无超时未支付订单",
                "closed_count": 0,
                "order_ids": [],
            }

        logger.info(
            "[%s] 关闭超时未支付订单成功 count=%s affected=%s order_ids=%s",
            task_name,
            len(order_ids),
            affected,
            order_ids,
        )
        return {
            "status": "success",
            "message": f"关闭 {affected} 笔超时未支付订单",
            "closed_count": affected,
            "order_ids": order_ids,
        }
    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "closed_count": 0,
            "order_ids": [],
        }


# ── 任务2：每日佣金对账统计 ───────────────────────────────────────────


async def daily_commission_reconciliation() -> Dict[str, Any]:
    """每日佣金对账统计（只读核查，不写余额）

    统计前一日（[昨天 00:00, 今天 00:00)）transfer_status=SUCCESS 的佣金流水：
    - 按平台用户(user_id)汇总佣金总额(SUM amount)与订单量(COUNT DISTINCT order_id)
    - 日志输出对账结果
    - 失效涉及的 commission_sum:{order_id} / order:{order_id} 缓存

    ⚠️ B07 整改说明（2026-08-02）：
    - 历史版本会将各用户当日已结算佣金幂等计入可用余额（credit_on_reconciliation），
      但 B07 的 batch_settle_commissions 定时任务已在结算时通过
      settle_order_commission_atomic（FOR UPDATE + 流水 + 余额更新）直接入账，
      本任务若再做余额写入会导致双重入账。
    - 现已移除余额写入逻辑，本任务仅保留对账核查 + 缓存失效职责。

    说明：
    - 「已结算」判定：CommissionFlow.transfer_status == TransferStatus.SUCCESS（转账成功）。
    - 时间维度以流水 create_time 落在前一日为准（流水无独立结算时间字段，用 create_time 近似）。

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "date": str, "promoter_count": int, "total_amount": str,
         "total_orders": int, "details": List[dict], "invalidated_order_ids": List[int]}
    """
    task_name = "daily_commission_reconciliation"

    if not TASK_DAILY_COMMISSION_RECONCILIATION_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "任务开关关闭",
            "date": "",
            "promoter_count": 0,
            "total_amount": "0",
            "total_orders": 0,
            "details": [],
            "invalidated_order_ids": [],
        }

    today = datetime.now().date()
    start_time = datetime.combine(today - timedelta(days=1), datetime.min.time())
    end_time = datetime.combine(today, datetime.min.time())
    reconcile_date = start_time.date().isoformat()

    logger.info(
        "[%s] 任务开始执行 区间=[%s, %s) status=%s",
        task_name,
        start_time,
        end_time,
        TransferStatus.SUCCESS.value,
    )

    try:
        async with DatabaseManager.get_session() as db:
            flow_dao = CommissionFlowDAO(db)
            details: List[Dict[str, Any]] = (
                await flow_dao.aggregate_settled_by_date_range(
                    start_time, end_time, TransferStatus.SUCCESS.value
                )
            )
            order_ids: List[int] = await flow_dao.list_settled_order_ids_by_date_range(
                start_time, end_time, TransferStatus.SUCCESS.value
            )
            # 失效涉及的佣金汇总 / 订单详情缓存（只读任务，缓存失效在查询后执行）
            await flow_dao.batch_invalidate_commission_cache(order_ids)

        total_amount = sum((d["total_amount"] for d in details), Decimal("0"))
        total_orders = sum(d["order_count"] for d in details)

        logger.info(
            "[%s] 对账完成 date=%s 平台用户数=%s 已结算佣金总额=%s 涉及订单数=%s",
            task_name,
            reconcile_date,
            len(details),
            total_amount,
            total_orders,
        )
        for d in details:
            logger.info(
                "[%s] 平台用户明细 user_id=%s 佣金总额=%s 订单数=%s",
                task_name,
                d["user_id"],
                d["total_amount"],
                d["order_count"],
            )

        return {
            "status": "success",
            "message": f"对账完成: {len(details)} 名平台用户, 总额 {total_amount}",
            "date": reconcile_date,
            "promoter_count": len(details),
            "total_amount": str(total_amount),
            "total_orders": total_orders,
            "details": [
                {
                    "user_id": d["user_id"],
                    "total_amount": str(d["total_amount"]),
                    "order_count": d["order_count"],
                }
                for d in details
            ],
            "invalidated_order_ids": order_ids,
        }
    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "date": reconcile_date,
            "promoter_count": 0,
            "total_amount": "0",
            "total_orders": 0,
            "details": [],
            "invalidated_order_ids": [],
        }


# ── 分布式锁包装 + 注册 ───────────────────────────────────────────────


async def _run_with_lock(
    task_name: str,
    func,
    lock_timeout: int,
) -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底

    - 锁获取失败（集群已有实例在跑）：记日志并跳过，不报错；
    - func 内部已自带 try/except，单条失败不阻断；此处兜底未捕获异常。
    """
    lock_owner = None
    try:
        lock_owner = await LockUtil.acquire_lock(
            f"scheduler:{task_name}", timeout=lock_timeout
        )
        if lock_owner is None:
            logger.warning("[%s] 未获取到分布式锁，跳过本次执行", task_name)
            return {"status": "skipped", "message": "未获取到分布式锁，跳过"}
        return await func()
    except Exception as e:
        logger.error("[%s] 任务执行异常: %s\n%s", task_name, e, traceback.format_exc())
        return {"status": "failed", "message": str(e)}
    finally:
        if lock_owner is not None:
            await LockUtil.release_lock(f"scheduler:{task_name}", lock_owner)


def register_scheduler_jobs() -> None:
    """注册定时任务作业到 TaskScheduler

    由 src/scheduler/tasks.py 的 register_tasks() 调用。
    定时频率 / 开关 / 锁超时均来自 constants.py，禁止在此硬编码。
    """
    # 任务1：超时未支付订单自动关闭 —— 每5分钟
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="close_expired_unpaid_orders",
        cron_expr=TASK_CRON_CLOSE_EXPIRED_ORDERS,
        args=(
            "close_expired_unpaid_orders",
            close_expired_unpaid_orders,
            TASK_CLOSE_EXPIRED_ORDERS_LOCK_TIMEOUT,
        ),
    )

    # 任务2：每日佣金对账统计 —— 每日 00:10
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="daily_commission_reconciliation",
        cron_expr=TASK_CRON_DAILY_COMMISSION_RECONCILIATION,
        args=(
            "daily_commission_reconciliation",
            daily_commission_reconciliation,
            TASK_DAILY_COMMISSION_RECONCILIATION_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "Scheduler jobs registered: close_expired_unpaid_orders(%s), daily_commission_reconciliation(%s)",
        TASK_CRON_CLOSE_EXPIRED_ORDERS,
        TASK_CRON_DAILY_COMMISSION_RECONCILIATION,
    )

    # B05 订单同步任务（三渠道错峰）：注册逻辑见 order_sync_jobs.py
    # 追加注册，不改动上方现有两个任务的注册逻辑
    from src.scheduler.order_sync_jobs import register_order_sync_jobs

    register_order_sync_jobs()

    # B07 佣金结算任务（批量结算 + 退款扣减）：注册逻辑见 commission_settlement_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.commission_settlement_jobs import (
        register_commission_settlement_jobs,
    )

    register_commission_settlement_jobs()

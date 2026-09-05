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

from sqlalchemy import and_, func, select

from src.common.lock_util import LockUtil
from src.config.b05_4_constants import (
    TASK_ABNORMAL_WATCHDOG_ENABLE,
    TASK_ABNORMAL_WATCHDOG_LOCK_TIMEOUT,
    TASK_ABNORMAL_WATCHDOG_WARN_THRESHOLD,
    TASK_CRON_ABNORMAL_WATCHDOG,
)
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
from src.dao.abnormal_order_dao import AbnormalOrderDAO
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.models.business.abnormal_order_model import AbnormalOrder
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


# ── 任务3：异常订单定时巡检 ───────────────────────────────────────────


async def abnormal_order_watchdog() -> Dict[str, Any]:
    """异常订单定时巡检

    统计当日新增的异常订单，按异常原因分组输出日志告警。
    当日新增超过阈值（TASK_ABNORMAL_WATCHDOG_WARN_THRESHOLD）时输出 WARNING 级别日志。

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "today_new_count": int, "pending_count": int,
         "reasons": Dict[str, int]}
    """
    task_name = "abnormal_order_watchdog"

    if not TASK_ABNORMAL_WATCHDOG_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "任务开关关闭"}

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info("[%s] 任务开始执行 today_start=%s", task_name, today_start)

    try:
        async with DatabaseManager.get_session() as db:
            dao = AbnormalOrderDAO(db)

            # 统计当日新增异常订单总数
            today_new = await dao.count_by_create_time(today_start)
            # 统计待审核数量
            pending_count = await dao.count_by_review_status_simple("PENDING")

            # 按异常原因分组统计
            stmt = (
                select(AbnormalOrder.abnormal_reason, func.count())
                .where(
                    and_(
                        AbnormalOrder.is_delete == False,  # noqa: E712
                        AbnormalOrder.create_time >= today_start,
                    )
                )
                .group_by(AbnormalOrder.abnormal_reason)
            )
            result = await db.execute(stmt)
            reasons: Dict[str, int] = {}
            for row in result.all():
                reason = str(row[0]) if row[0] else "unknown"
                reasons[reason] = int(row[1])

        # 输出日志告警
        if today_new > 0:
            log_level = (
                logging.WARNING
                if today_new >= TASK_ABNORMAL_WATCHDOG_WARN_THRESHOLD
                else logging.INFO
            )
            logger.log(
                log_level,
                "[%s] 巡检结果: 当日新增异常订单=%s 待审核=%s 阈值=%s "
                "原因分布=%s",
                task_name,
                today_new,
                pending_count,
                TASK_ABNORMAL_WATCHDOG_WARN_THRESHOLD,
                reasons,
            )
        else:
            logger.info("[%s] 巡检结果: 当日无新增异常订单", task_name)

        return {
            "status": "success",
            "message": f"当日新增异常订单 {today_new} 笔，待审核 {pending_count} 笔",
            "today_new_count": today_new,
            "pending_count": pending_count,
            "reasons": reasons,
        }
    except Exception as e:
        logger.error(
            "[%s] 巡检任务执行失败: %s\n%s",
            task_name, e, traceback.format_exc(),
        )
        return {
            "status": "failed",
            "message": str(e),
            "today_new_count": 0,
            "pending_count": 0,
            "reasons": {},
        }


# ── 分布式锁包装 + 注册 ───────────────────────────────────────────────


async def _run_with_lock(
    task_name: str,
    func,
    lock_timeout: int,
    lock_wait_seconds: int = 5,
) -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底

    S04 P2-1 优化：
    - 锁获取失败时先短等待重试（默认 5s），吸收部署重启/多实例同时启动时的
      瞬时锁冲突，显著降低任务跳过概率；
    - 等待后仍失败（集群实例正在长任务执行）才跳过，并记录锁冲突计数；
    - func 内部已自带 try/except，单条失败不阻断；此处兜底未捕获异常。
    """
    lock_owner = None
    try:
        lock_owner = await LockUtil.acquire_with_wait(
            f"scheduler:{task_name}",
            timeout=lock_timeout,
            wait_timeout=lock_wait_seconds,
            poll_interval=0.5,
        )
        if lock_owner is None:
            await LockUtil.record_lock_conflict(task_name)
            logger.warning(
                "[%s] 等待 %ss 后仍未获取到分布式锁，跳过本次执行",
                task_name,
                lock_wait_seconds,
            )
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

    # 任务3：异常订单定时巡检 —— 每 2 小时
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="abnormal_order_watchdog",
        cron_expr=TASK_CRON_ABNORMAL_WATCHDOG,
        args=(
            "abnormal_order_watchdog",
            abnormal_order_watchdog,
            TASK_ABNORMAL_WATCHDOG_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "Scheduler jobs registered: close_expired_unpaid_orders(%s), daily_commission_reconciliation(%s), abnormal_order_watchdog(%s)",
        TASK_CRON_CLOSE_EXPIRED_ORDERS,
        TASK_CRON_DAILY_COMMISSION_RECONCILIATION,
        TASK_CRON_ABNORMAL_WATCHDOG,
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

    # B12 佣金结算状态机任务（SETTLABLE 冻结 + SETTLED 解冻）：注册逻辑见 settlement_b12_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.settlement_b12_jobs import register_settlement_b12_jobs

    register_settlement_b12_jobs()

    # B13 全链路数据对账任务（每日凌晨 02:00 四方核对）：注册逻辑见 reconciliation_b13_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.reconciliation_b13_jobs import (
        register_reconciliation_b13_jobs,
    )

    register_reconciliation_b13_jobs()

    # B10 消息推送巡检定时任务（每5分钟）：注册逻辑见 b10_message_push_jobs.py
    from src.scheduler.b10_message_push_jobs import (
        register_b10_message_push_jobs,
    )

    register_b10_message_push_jobs()

    # B16 商品预热定时任务（渠道预热 + 存量刷新 + 冷品清理）：注册逻辑见 goods_warming_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.goods_warming_jobs import (
        register_goods_warming_jobs,
    )

    register_goods_warming_jobs()

    # B05-7 批量订单结算定时任务（运行日志 + 异常标记）：注册逻辑见 batch_settlement_task.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.batch_settlement_task import (
        register_batch_settlement_task,
        register_cleanup_task,
    )

    register_batch_settlement_task()
    register_cleanup_task()

    # B07-1 逆向佣金冲减定时任务（每30分钟）：注册逻辑见 b07_1_reverse_commission_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.b07_1_reverse_commission_jobs import (
        register_reverse_commission_jobs,
    )

    register_reverse_commission_jobs()

    # B11-1 渠道每日统计定时任务（每日 01:00）：注册逻辑见 b11_channel_stat_jobs.py
    from src.scheduler.b11_channel_stat_jobs import (
        register_b11_channel_stat_jobs,
    )

    register_b11_channel_stat_jobs()

    # B12-1 订单异常巡检定时任务（每30分钟）：注册逻辑见 b12_order_anomaly_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.b12_order_anomaly_jobs import (
        register_b12_order_anomaly_jobs,
    )

    register_b12_order_anomaly_jobs()

    # B14-1 数据大盘预计算定时任务（每30分钟）：注册逻辑见 b14_1_dashboard_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.b14_1_dashboard_jobs import (
        register_b14_1_dashboard_jobs,
    )

    register_b14_1_dashboard_jobs()

    # B17 多渠道对账定时任务（每日 02:30）：注册逻辑见 b17_channel_reconciliation_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.b17_channel_reconciliation_jobs import (
        register_b17_channel_reconciliation_jobs,
    )

    register_b17_channel_reconciliation_jobs()

    # X02-1 会员状态定时刷新任务（每30分钟）：注册逻辑见 member_status_jobs.py
    # 追加注册，不改动上方现有任务的注册逻辑
    from src.scheduler.member_status_jobs import register_member_status_jobs

    register_member_status_jobs()

    logger.info("All scheduler jobs registered successfully")

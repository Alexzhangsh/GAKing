# @ai-generated
"""
B17 多渠道对账定时任务（独立新建，不修改 B01-B16 基线）
每日 02:30 执行渠道维度对账（错峰：B13 每日 02:00 全链路对账之后）
"""
import logging
import traceback
from typing import Any, Dict

from src.common.lock_util import LockUtil
from src.config.b17_constants import (
    TASK_CHANNEL_RECONCILIATION_ENABLE,
    TASK_CHANNEL_RECONCILIATION_LOCK_TIMEOUT,
)
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
from src.dao.reconciliation_record_dao import ReconciliationRecordDAO
from src.db.init_db import DatabaseManager
from src.services.b17_channel_reconciliation_service import (
    B17ChannelReconciliationService,
)

logger = logging.getLogger("scheduler.b17_channel_reconciliation")

# 渠道对账分布式锁 key
LOCK_KEY_CHANNEL_RECONCILIATION_JOB = "channel_reconciliation_job"


async def channel_reconciliation_job() -> Dict[str, Any]:
    """每日渠道对账定时任务入口

    执行多渠道（myq/orderx）订单佣金 ↔ 结算入账核对，
    差异落库 + CRITICAL 告警。
    """
    if not TASK_CHANNEL_RECONCILIATION_ENABLE:
        return {"status": "skipped", "message": "渠道对账任务开关关闭"}

    # 分布式锁（防多实例并发）
    lock_owner = await LockUtil.acquire_lock(
        LOCK_KEY_CHANNEL_RECONCILIATION_JOB,
        timeout=TASK_CHANNEL_RECONCILIATION_LOCK_TIMEOUT,
    )
    if lock_owner is None:
        return {"status": "skipped", "message": "渠道对账任务正在执行中"}

    try:
        async with DatabaseManager.get_session() as session:
            service = B17ChannelReconciliationService(
                record_dao=ReconciliationRecordDAO(session),
                diff_dao=ReconciliationDiffDAO(session),
                session=session,
                circuit_breaker=CircuitBreaker(),
            )
            result = await service.run_channel_reconciliation(
                reconcile_type="DAILY",
            )
            logger.info(
                "[channel_reconciliation_job] 完成 status=%s diff=%s",
                result["status"], result["diff_count"],
            )
            return {
                "status": "success",
                "reconciliation_no": result["reconciliation_no"],
                "diff_count": result["diff_count"],
                "channel_stats": result["channel_stats"],
            }
    except Exception as e:
        logger.error(
            "[channel_reconciliation_job] 执行失败: %s\n%s",
            e, traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e)[:500]}
    finally:
        await LockUtil.release_lock(LOCK_KEY_CHANNEL_RECONCILIATION_JOB, lock_owner)


def register_b17_channel_reconciliation_jobs() -> None:
    """注册 B17 渠道对账定时任务（由 scheduler_jobs.py 调用）"""
    from src.scheduler.scheduler import TaskScheduler

    TaskScheduler.add_cron_task(
        func=channel_reconciliation_job,
        name="channel_reconciliation",
        cron_expr="30 2 * * *",
        description="B17 多渠道对账（每日02:30）",
    )
# @ai-generated
"""
B13 全链路数据对账定时任务作业定义（独立新建，不修改 B01-B12 基线）

定时任务：
- 任务10：每日全链路对账（cron 0 2 * * *，每日凌晨 02:00）
    对账前一日 [昨天 00:00, 今天 00:00) 的四方数据一致性

设计约定（硬性规范）：
1. 复用 scheduler_jobs._run_with_lock 分布式锁模式（防集群并发）；
2. 任务开关/锁超时/cron 全部来自 b13_constants.py，禁止硬编码；
3. 凌晨 02:00 执行，B07/B12 当日结算已完成，数据处于稳定状态；
4. Service 层自带幂等锁（防同日重复对账）；
5. 手动可调用验证（可直接 await daily_reconciliation_job()）。

手动调用验证：
    from src.scheduler.reconciliation_b13_jobs import (
        daily_reconciliation_job,
        manual_reconciliation_job,
    )
    await daily_reconciliation_job()                    # 每日自动对账（默认昨天）
    await manual_reconciliation_job(date(2026,8,1))     # 手动对账指定日期
"""
import logging
import traceback
from datetime import date
from typing import Any, Dict, Optional

from src.common.redis_client import RedisClient
from src.config.b13_constants import (
    CACHE_KEY_RECONCILIATION_DATE,
    CACHE_TTL_RECONCILIATION_DATE,
    RECONCILIATION_BREAKER_CHANNEL,
    TASK_CRON_DAILY_RECONCILIATION,
    TASK_DAILY_RECONCILIATION_ENABLE,
    TASK_DAILY_RECONCILIATION_LOCK_TIMEOUT,
    ReconciliationType,
)
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
from src.dao.reconciliation_query_dao import ReconciliationQueryDAO
from src.dao.reconciliation_record_dao import ReconciliationRecordDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import _run_with_lock
from src.services.reconciliation_b13_service import ReconciliationB13Service

logger = logging.getLogger("scheduler.reconciliation_b13_jobs")


# ── Service 构造工具 ───────────────────────────────────────────────


async def _build_service(db_session) -> ReconciliationB13Service:
    """根据 db session 构造 ReconciliationB13Service 实例

    注入 3 个 DAO（RecordDAO / DiffDAO / QueryDAO），共享同一 session。
    熔断器注入 CircuitBreaker 实例（channel_code=reconciliation）。
    """
    record_dao = ReconciliationRecordDAO(db_session)
    diff_dao = ReconciliationDiffDAO(db_session)
    query_dao = ReconciliationQueryDAO(db_session)
    circuit_breaker = CircuitBreaker()
    return ReconciliationB13Service(
        record_dao=record_dao,
        diff_dao=diff_dao,
        query_dao=query_dao,
        circuit_breaker=circuit_breaker,
    )


# ── 任务10：每日全链路对账 ──────────────────────────────────────────


async def daily_reconciliation_job() -> Dict[str, Any]:
    """每日自动对账任务（定时任务入口）

    流程：检查开关 → 获取 DB 会话 → 调用 Service.run_reconciliation
    默认对账昨天数据，幂等锁防重复执行。

    Returns:
        {status, reconciliation_id, reconciliation_no, matched_count, diff_count, ...}
    """
    task_name = "daily_reconciliation"

    if not TASK_DAILY_RECONCILIATION_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "每日对账任务开关关闭",
        }

    logger.info("[%s] 任务开始执行", task_name)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.run_reconciliation(
                reconcile_type=ReconciliationType.DAILY.value,
            )
        logger.info(
            "[%s] 任务完成 status=%s no=%s matched=%s diff=%s",
            task_name,
            result.get("status"),
            result.get("reconciliation_no"),
            result.get("matched_count"),
            result.get("diff_count"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 任务执行失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {
            "status": "failed",
            "message": str(e),
        }


async def manual_reconciliation_job(
    reconcile_date: Optional[date] = None,
    operator_id: Optional[int] = None,
) -> Dict[str, Any]:
    """手动触发对账任务（指定日期/默认昨天）

    适用于：运营发现历史数据异常时手动触发对账核查。
    幂等：Service 层幂等锁防同日重复对账。

    Args:
        reconcile_date: 对账日期（None 时默认昨天）
        operator_id: 操作人ID
    Returns:
        {status, reconciliation_id, reconciliation_no, ...}
    """
    task_name = "manual_reconciliation"
    logger.info(
        "[%s] 手动触发对账 date=%s operator=%s",
        task_name,
        reconcile_date,
        operator_id,
    )
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.run_reconciliation(
                reconcile_date=reconcile_date,
                reconcile_type=ReconciliationType.MANUAL.value,
                operator_id=operator_id,
            )
        logger.info(
            "[%s] 完成 no=%s status=%s",
            task_name,
            result.get("reconciliation_no"),
            result.get("status"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 手动对账失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {
            "status": "failed",
            "message": str(e),
        }


# ── 任务注册 ───────────────────────────────────────────────────────


def register_reconciliation_b13_jobs() -> None:
    """注册 B13 全链路对账定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 追加调用（不改动现有任务）。
    cron 表达式：每日凌晨 02:00（B07/B12 当日结算已完成）
    定时频率 / 开关 / 锁超时均来自 b13_constants.py，禁止硬编码。
    """
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="daily_reconciliation",
        cron_expr=TASK_CRON_DAILY_RECONCILIATION,
        args=(
            "daily_reconciliation",
            daily_reconciliation_job,
            TASK_DAILY_RECONCILIATION_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "B13 reconciliation job registered: daily_reconciliation(%s)",
        TASK_CRON_DAILY_RECONCILIATION,
    )

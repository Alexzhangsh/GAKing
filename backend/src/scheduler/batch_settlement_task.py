# @ai-generated
"""
B05-7 批量订单结算定时任务

职责：
1. 复用 CommissionSettlementService.batch_settle_orders() 批量结算核心逻辑
2. 记录每次任务运行日志（scheduled_task_run_log 表）
3. 异常订单标记失败，单条失败不阻断整体
4. 分布式锁防止集群并发

设计约定（硬性规范）：
1. 复用 scheduler_jobs._run_with_lock 分布式锁模式（防集群并发）；
2. 任务开关/锁超时/cron/batch_size 全部来自 b05_7_constants.py，禁止硬编码；
3. 使用 CommissionSettlementService 处理结算，复用 B07 的规则引擎和原子入账；
4. 每次运行在 scheduled_task_run_log 表记录完整运行状态，支持审计追溯；
5. 手动可调用验证（可直接 await batch_settlement_task()）。

手动调用验证：
    from src.scheduler.batch_settlement_task import batch_settlement_task
    await batch_settlement_task()              # 批量结算
    await batch_settlement_task(limit=50)      # 指定批次大小
"""
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from src.config.b05_7_constants import (
    TASK_BATCH_SETTLE_BATCH_SIZE,
    TASK_BATCH_SETTLE_ENABLE,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.dao.scheduled_task_run_log_dao import ScheduledTaskRunLogDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler_jobs import _run_with_lock
from src.services.commission_rule_engine import CommissionRuleEngine
from src.services.commission_settlement_service import CommissionSettlementService

logger = logging.getLogger("scheduler.batch_settlement_task")


# ── 运行批次ID生成 ───────────────────────────────────────────────


def _make_run_id(task_name: str) -> str:
    """生成运行批次ID

    Format: {task_name}_{YYYYMMDDHHMMSS}_{3位随机数}
    """
    import random
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = random.randint(100, 999)
    return f"{task_name}_{ts}_{rand}"


# ── Service 构造工具 ───────────────────────────────────────────


async def _build_service(db_session) -> CommissionSettlementService:
    """根据 db session 构造 CommissionSettlementService 实例

    统一注入 4 个依赖：OrderDAO / CommissionFlowDAO / CommissionSettlementDAO / CommissionRuleEngine
    所有 DAO 共享同一 session（保证单事务原子性）
    """
    from src.scheduler.commission_settlement_jobs import _make_config_loader

    order_dao = OrderDAO(db_session)
    flow_dao = CommissionFlowDAO(db_session)
    settlement_dao = CommissionSettlementDAO(db_session)
    config_loader = await _make_config_loader(db_session)
    rule_engine = CommissionRuleEngine(config_loader=config_loader)
    return CommissionSettlementService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        settlement_dao=settlement_dao,
        rule_engine=rule_engine,
    )


# ── 核心任务函数 ────────────────────────────────────────────────


async def batch_settlement_task(
    limit: int = TASK_BATCH_SETTLE_BATCH_SIZE,
) -> Dict[str, Any]:
    """批量订单结算定时任务

    流程：
    1. 检查任务开关 → 关闭则跳过
    2. 创建运行日志（status=running）
    3. 调用 CommissionSettlementService.batch_settle_orders() 批量结算
    4. 更新运行日志（status=success/partial/failed）
    5. 返回处理结果

    Args:
        limit: 单轮处理订单上限（默认 200）
    Returns:
        {status, message, total, success_count, failed_count, skipped_count,
         run_log_id, duration_seconds}
    """
    task_name = "batch_settlement_task"
    run_id = _make_run_id(task_name)
    started_at = datetime.now()

    # 开关检查
    if not TASK_BATCH_SETTLE_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "批量结算任务开关关闭",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "run_log_id": None,
            "duration_seconds": 0,
        }

    logger.info(
        "[%s] 任务开始执行 run_id=%s limit=%s", task_name, run_id, limit
    )

    run_log_id = None
    try:
        # 1. 创建运行日志
        async with DatabaseManager.get_session() as db:
            log_dao = ScheduledTaskRunLogDAO(db)
            run_log = await log_dao.create_run_log(
                task_name=task_name,
                run_id=run_id,
                status="running",
                started_at=started_at,
                total_orders=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
            )
            run_log_id = run_log.id

        # 2. 执行批量结算
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.batch_settle_orders(limit=limit)

        # 3. 计算统计数据
        total = result.get("total", 0)
        success_count = result.get("success_count", 0)
        failed_count = result.get("failed_count", 0)
        skipped_count = result.get("skipped_count", 0)

        # 提取失败订单摘要
        details = result.get("details", [])
        failed_details = [d for d in details if d.get("status") == "failed"]
        error_summary = ""
        if failed_details:
            error_summary = (
                f"失败订单数: {len(failed_details)}; "
                f"失败原因示例: {failed_details[0].get('message', '未知')[:200]}"
            )

        # 4. 更新运行日志
        finished_at = datetime.now()
        duration_seconds = int((finished_at - started_at).total_seconds())
        overall_status = result.get("status", "success")  # success/partial

        async with DatabaseManager.get_session() as db:
            log_dao = ScheduledTaskRunLogDAO(db)
            await log_dao.update_run_log(
                log_id=run_log_id,
                status=overall_status,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                total_orders=total,
                success_count=success_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                error_message=error_summary,
                detail_json=json.dumps(
                    [
                        {
                            "order_id": d.get("order_id"),
                            "status": d.get("status"),
                            "message": str(d.get("message", ""))[:100],
                        }
                        for d in details
                    ],
                    ensure_ascii=False,
                ),
            )

        logger.info(
            "[%s] 任务完成 run_id=%s status=%s total=%s success=%s failed=%s skipped=%s duration=%ss",
            task_name,
            run_id,
            overall_status,
            total,
            success_count,
            failed_count,
            skipped_count,
            duration_seconds,
        )

        return {
            "status": overall_status,
            "message": result.get("message", ""),
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "run_log_id": run_log_id,
            "duration_seconds": duration_seconds,
        }

    except Exception as e:
        # 5. 异常处理：标记失败
        finished_at = datetime.now()
        duration_seconds = int((finished_at - started_at).total_seconds())
        error_stack = traceback.format_exc()

        logger.error(
            "[%s] 任务执行失败: %s\n%s",
            task_name,
            e,
            error_stack,
        )

        if run_log_id is not None:
            try:
                async with DatabaseManager.get_session() as db:
                    log_dao = ScheduledTaskRunLogDAO(db)
                    await log_dao.update_run_log(
                        log_id=run_log_id,
                        status="failed",
                        finished_at=finished_at,
                        duration_seconds=duration_seconds,
                        error_message=f"任务执行异常: {str(e)}",
                    )
            except Exception as log_err:
                logger.error(
                    "[%s] 更新运行日志失败: %s", task_name, log_err
                )

        return {
            "status": "failed",
            "message": str(e),
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "run_log_id": run_log_id,
            "duration_seconds": duration_seconds,
        }


# ── 手动结算接口（后台补发用） ──────────────────────────────────


async def settle_single_order_job(order_id: int) -> Dict[str, Any]:
    """单订单结算任务（手动补发用）

    复用 CommissionSettlementService.settle_single_order()
    用于后台手动触发单笔补结算。

    Args:
        order_id: 订单 ID
    Returns:
        {status, order_id, flow_id, amount, transfer_batch_id}
    """
    task_name = "settle_single_order_b05_7"
    logger.info("[%s] 手动触发单笔结算 order_id=%s", task_name, order_id)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.settle_single_order(order_id)
        logger.info(
            "[%s] 完成 order_id=%s status=%s flow_id=%s",
            task_name,
            order_id,
            result.get("status"),
            result.get("flow_id"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 单笔结算失败 order_id=%s: %s\n%s",
            task_name,
            order_id,
            e,
            traceback.format_exc(),
        )
        return {
            "status": "failed",
            "order_id": order_id,
            "message": str(e),
        }


# ── 任务注册 ───────────────────────────────────────────────────


def register_batch_settlement_task() -> None:
    """注册 B05-7 批量订单结算定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 调用（追加注册，不改动现有任务）。
    定时频率 / 开关 / 锁超时均来自 b05_7_constants.py，禁止硬编码。
    """
    from src.config.b05_7_constants import (
        TASK_BATCH_SETTLE_LOCK_TIMEOUT,
        TASK_CRON_BATCH_SETTLE,
    )
    from src.scheduler.scheduler import TaskScheduler

    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="batch_settlement_task",
        cron_expr=TASK_CRON_BATCH_SETTLE,
        args=(
            "batch_settlement_task",
            batch_settlement_task,
            TASK_BATCH_SETTLE_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "B05-7 batch settlement task registered: cron=%s",
        TASK_CRON_BATCH_SETTLE,
    )


# ── 清理过期日志任务 ──────────────────────────────────────────


async def cleanup_task_run_logs() -> Dict[str, Any]:
    """清理过期运行日志（保留最近 N 天）

    由 scheduler_jobs.register_scheduler_jobs() 注册的定时任务调用。
    """
    from src.config.b05_7_constants import TASK_RUN_LOG_RETENTION_DAYS

    task_name = "cleanup_task_run_logs"
    logger.info(
        "[%s] 开始清理 retention_days=%s",
        task_name,
        TASK_RUN_LOG_RETENTION_DAYS,
    )
    try:
        async with DatabaseManager.get_session() as db:
            log_dao = ScheduledTaskRunLogDAO(db)
            deleted = await log_dao.delete_expired_logs(
                retention_days=TASK_RUN_LOG_RETENTION_DAYS
            )
        logger.info("[%s] 清理完成 count=%s", task_name, deleted)
        return {
            "status": "success",
            "message": f"清理 {deleted} 条过期运行日志",
            "deleted_count": deleted,
        }
    except Exception as e:
        logger.error(
            "[%s] 清理失败: %s\n%s",
            task_name,
            e,
            traceback.format_exc(),
        )
        return {
            "status": "failed",
            "message": str(e),
            "deleted_count": 0,
        }


def register_cleanup_task() -> None:
    """注册清理过期日志任务（每日凌晨 03:00）"""
    from src.config.b05_7_constants import TASK_BATCH_SETTLE_LOCK_TIMEOUT
    from src.scheduler.scheduler import TaskScheduler

    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="cleanup_task_run_logs",
        cron_expr="0 3 * * *",
        args=(
            "cleanup_task_run_logs",
            cleanup_task_run_logs,
            TASK_BATCH_SETTLE_LOCK_TIMEOUT,
        ),
    )

    logger.info("Cleanup task run logs task registered: cron=0 3 * * *")
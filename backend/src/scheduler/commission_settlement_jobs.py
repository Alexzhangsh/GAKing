# @ai-generated
"""
B07 佣金结算定时任务作业定义

两个定时任务：
- 任务6：批量佣金结算（cron */15 * * * *，每15分钟）
    拉取 SETTLED 状态无 ORDER 流水的订单 → 规则引擎算佣金 → 原子入账（FOR UPDATE + 流水 + 余额）
- 任务7：退款佣金扣减（cron */10 * * * *，每10分钟）
    拉取 REFUNDED 状态无 DEDUCT 流水的订单 → 逆向冲减（PENDING→FAILED / SUCCESS→扣余额）

设计约定（硬性规范）：
1. 复用 scheduler_jobs._run_with_lock 分布式锁模式（防集群并发）；
2. 任务开关/锁超时/cron/batch_size 全部来自 b07_constants.py，禁止硬编码；
3. 两个任务错峰：结算每 15 分钟，退款扣减每 10 分钟（与订单同步 */10 错开实例）；
4. Service 层自带 try/except + 日志，单条失败不阻断整体；
5. 手动可调用验证（可直接 await batch_settle_commissions() / process_refund_deductions_job()）。

手动调用验证：
    from src.scheduler.commission_settlement_jobs import (
        batch_settle_commissions,
        process_refund_deductions_job,
        settle_single_order_job,
        deduct_single_order_job,
    )
    await batch_settle_commissions()           # 批量结算
    await process_refund_deductions_job()      # 批量退款扣减
    await settle_single_order_job(order_id=1)  # 单笔结算（手动补发）
    await deduct_single_order_job(order_id=1)  # 单笔退款扣减（手动补发）
"""
import logging
import traceback
from typing import Any, Dict, Optional

from sqlalchemy import select

from src.common.redis_client import RedisClient
from src.config.b07_constants import (
    CACHE_TTL_COMMISSION_RULE,
    TASK_BATCH_SETTLE_BATCH_SIZE,
    TASK_BATCH_SETTLE_ENABLE,
    TASK_BATCH_SETTLE_LOCK_TIMEOUT,
    TASK_CRON_BATCH_SETTLE_COMMISSION,
    TASK_CRON_REFUND_DEDUCT,
    TASK_REFUND_DEDUCT_BATCH_SIZE,
    TASK_REFUND_DEDUCT_ENABLE,
    TASK_REFUND_DEDUCT_LOCK_TIMEOUT,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import _run_with_lock
from src.services.commission_rule_engine import CommissionRuleEngine
from src.services.commission_settlement_service import CommissionSettlementService

logger = logging.getLogger("scheduler.commission_settlement_jobs")


# ── 配置加载器（SystemConfig 表 + Redis 缓存） ─────────────────────


async def _make_config_loader(db_session):
    """构造规则引擎配置加载器

    返回一个异步函数 (config_key: str) -> Optional[str]：
    1. 先查 Redis 缓存（key=gaking:prod:{config_key}，TTL=5min）
    2. 未命中查 gaking_system_config 表 config_value
    3. 回填 Redis 缓存（含空值防穿透）

    Args:
        db_session: 异步数据库会话
    Returns:
        config_loader 异步函数
    """

    async def loader(config_key: str) -> Optional[str]:
        # 1. Redis 缓存优先
        cached = await RedisClient.get(config_key)
        if cached is not None:
            if cached == "__EMPTY__":
                return None
            return cached

        # 2. 查库
        try:
            stmt = select(SystemConfig.config_value).where(
                SystemConfig.config_key == config_key,
                SystemConfig.is_delete == False,  # noqa: E712
            )
            result = await db_session.execute(stmt)
            row = result.first()
            if row is None:
                # 空值防穿透（60s）
                await RedisClient.set_empty_cache(config_key)
                return None
            value = row[0]
            # 回填缓存（5min，b07_constants 配置）
            await RedisClient.set(config_key, value, expire=CACHE_TTL_COMMISSION_RULE)
            return value
        except Exception as e:
            logger.warning(
                "[config_loader] 读取 SystemConfig 失败 key=%s error=%s",
                config_key,
                e,
            )
            return None

    return loader


# ── Service 构造工具 ───────────────────────────────────────────────


async def _build_service(db_session) -> CommissionSettlementService:
    """根据 db session 构造 CommissionSettlementService 实例

    统一注入 4 个依赖：OrderDAO / CommissionFlowDAO / CommissionSettlementDAO / CommissionRuleEngine
    所有 DAO 共享同一 session（保证单事务原子性）
    规则引擎注入 config_loader（读 SystemConfig 表 + Redis 缓存）
    """
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


# ── 任务6：批量佣金结算 ────────────────────────────────────────────


async def batch_settle_commissions(
    limit: int = TASK_BATCH_SETTLE_BATCH_SIZE,
) -> Dict[str, Any]:
    """批量佣金结算任务

    流程：检查开关 → 获取 DB 会话 → 调用 CommissionSettlementService.batch_settle_orders
    Service 内部逐单 try/except，单条失败不阻断整体，返回 partial 状态。

    Args:
        limit: 单轮处理订单上限（默认 200，最大由 schema 控制）
    Returns:
        {status, total, success_count, failed_count, skipped_count, details}
    """
    task_name = "batch_settle_commissions"

    if not TASK_BATCH_SETTLE_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "批量结算任务开关关闭",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }

    logger.info("[%s] 任务开始执行 limit=%s", task_name, limit)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.batch_settle_orders(limit=limit)
        logger.info(
            "[%s] 任务完成 status=%s total=%s success=%s failed=%s skipped=%s",
            task_name,
            result.get("status"),
            result.get("total"),
            result.get("success_count"),
            result.get("failed_count"),
            result.get("skipped_count"),
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
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }


async def settle_single_order_job(order_id: int) -> Dict[str, Any]:
    """单订单结算任务（手动补发用）

    适用于：定时任务因异常漏单时，后台手动触发单笔补结算。
    幂等：已有 SUCCESS 状态的 ORDER 流水自动跳过。

    Args:
        order_id: 订单 ID
    Returns:
        {status, order_id, flow_id, amount, transfer_batch_id}
    """
    task_name = "settle_single_order"
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


# ── 任务7：退款佣金扣减 ────────────────────────────────────────────


async def process_refund_deductions_job(
    limit: int = TASK_REFUND_DEDUCT_BATCH_SIZE,
) -> Dict[str, Any]:
    """批量退款佣金扣减任务

    流程：检查开关 → 获取 DB 会话 → 调用 CommissionSettlementService.process_refund_deductions
    分支处理：
    - 无 ORDER 流水 → 跳过（佣金从未发放）
    - 已有 DEDUCT 流水 → 幂等跳过
    - ORDER 流水 PENDING → 标记 FAILED（在途扣减，不动余额）
    - ORDER 流水 SUCCESS → 扣减余额 + 生成 DEDUCT 流水

    Args:
        limit: 单轮处理订单上限（默认 100）
    Returns:
        {status, total, success_count, failed_count, skipped_count, details}
    """
    task_name = "process_refund_deductions"

    if not TASK_REFUND_DEDUCT_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "退款扣减任务开关关闭",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }

    logger.info("[%s] 任务开始执行 limit=%s", task_name, limit)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.process_refund_deductions(limit=limit)
        logger.info(
            "[%s] 任务完成 status=%s total=%s success=%s failed=%s skipped=%s",
            task_name,
            result.get("status"),
            result.get("total"),
            result.get("success_count"),
            result.get("failed_count"),
            result.get("skipped_count"),
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
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
        }


async def deduct_single_order_job(order_id: int) -> Dict[str, Any]:
    """单订单退款扣减任务（手动补发用）

    适用于：定时任务因异常漏单时，后台手动触发单笔退款扣减。
    幂等：已有 DEDUCT 流水自动跳过。

    Args:
        order_id: 订单 ID
    Returns:
        {status, order_id, deduct_flow_id, deduct_amount}
    """
    task_name = "deduct_single_order"
    logger.info("[%s] 手动触发单笔退款扣减 order_id=%s", task_name, order_id)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.process_single_refund(order_id)
        logger.info(
            "[%s] 完成 order_id=%s status=%s deduct_flow_id=%s",
            task_name,
            order_id,
            result.get("status"),
            result.get("deduct_flow_id"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 单笔退款扣减失败 order_id=%s: %s\n%s",
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


# ── 任务注册 ───────────────────────────────────────────────────────


def register_commission_settlement_jobs() -> None:
    """注册 B07 佣金结算定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 调用（追加注册，不改动现有任务）。
    两个任务使用不同 cron 表达式错峰执行：
    - 批量结算：每 15 分钟（与订单同步 */10 错开实例）
    - 退款扣减：每 10 分钟（与订单同步同频，但锁独立）
    定时频率 / 开关 / 锁超时均来自 b07_constants.py，禁止硬编码。
    """
    # 任务6：批量佣金结算 —— 每15分钟
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="batch_settle_commissions",
        cron_expr=TASK_CRON_BATCH_SETTLE_COMMISSION,
        args=(
            "batch_settle_commissions",
            batch_settle_commissions,
            TASK_BATCH_SETTLE_LOCK_TIMEOUT,
        ),
    )

    # 任务7：退款佣金扣减 —— 每10分钟
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="process_refund_deductions",
        cron_expr=TASK_CRON_REFUND_DEDUCT,
        args=(
            "process_refund_deductions",
            process_refund_deductions_job,
            TASK_REFUND_DEDUCT_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "Commission settlement jobs registered: batch_settle(%s), refund_deduct(%s)",
        TASK_CRON_BATCH_SETTLE_COMMISSION,
        TASK_CRON_REFUND_DEDUCT,
    )

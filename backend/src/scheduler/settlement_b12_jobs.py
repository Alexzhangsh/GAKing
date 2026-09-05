# @ai-generated
"""
B12 佣金结算状态机定时任务作业定义（独立新建，不修改 B01-B11 基线）

两个定时任务：
- 任务8：SETTLABLE 订单冻结入账（cron */12 * * * *，每12分钟）
    扫描 OrderStatus.SETTLABLE(30) 且无结算单的订单 → 创建结算单 + PENDING 流水 + frozen += amount
- 任务9：SETTLED 订单解冻转可用（cron */8 * * * *，每8分钟）
    扫描 OrderStatus.SETTLED(40) 且结算单为 SETTLABLE 态 → 解冻 frozen → available + PENDING→SUCCESS 流水

设计约定（硬性规范）：
1. 复用 scheduler_jobs._run_with_lock 分布式锁模式（防集群并发）；
2. 任务开关/锁超时/cron/batch_size 全部来自 b12_constants.py，禁止硬编码；
3. 两个任务错峰：冻结每 12 分钟（与 B07 的 */15 错开），解冻每 8 分钟（与 B07 的 */10 错开）；
4. Service 层自带 try/except + 日志，单条失败不阻断整体；
5. 延迟天数 delay_days 从 gaking_system_config 表动态读取（settlement_delay_days 键），
   缺失时兜底 SETTLEMENT_DELAY_DAYS_DEFAULT=30，仅用于超期预警与结算单快照，不强行解冻；
6. 手动可调用验证（可直接 await batch_freeze_settlable_job() / freeze_single_order_job(order_id=1)）。

手动调用验证：
    from src.scheduler.settlement_b12_jobs import (
        batch_freeze_settlable_job,
        batch_unfreeze_settled_job,
        freeze_single_order_job,
        unfreeze_single_order_job,
    )
    await batch_freeze_settlable_job()           # 批量冻结入账
    await batch_unfreeze_settled_job()           # 批量解冻转可用
    await freeze_single_order_job(order_id=1)    # 单笔冻结（手动补发）
    await unfreeze_single_order_job(order_id=1)  # 单笔解冻（手动补发）
"""
import logging
import traceback
from typing import Any, Dict, Optional

from sqlalchemy import select

from src.common.redis_client import RedisClient
from src.config.b12_constants import (
    CONFIG_KEY_SETTLEMENT_DELAY_DAYS,
    SETTLEMENT_DELAY_DAYS_CACHE_TTL,
    SETTLEMENT_DELAY_DAYS_DEFAULT,
    TASK_CRON_SETTLEMENT_FREEZE,
    TASK_CRON_SETTLEMENT_UNFREEZE,
    TASK_SETTLEMENT_FREEZE_BATCH_SIZE,
    TASK_SETTLEMENT_FREEZE_ENABLE,
    TASK_SETTLEMENT_FREEZE_LOCK_TIMEOUT,
    TASK_SETTLEMENT_UNFREEZE_BATCH_SIZE,
    TASK_SETTLEMENT_UNFREEZE_ENABLE,
    TASK_SETTLEMENT_UNFREEZE_LOCK_TIMEOUT,
)
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.order_dao import OrderDAO
from src.dao.settlement_atomic_dao import SettlementAtomicDAO
from src.dao.settlement_operation_log_dao import SettlementOperationLogDAO
from src.dao.settlement_record_dao import SettlementRecordDAO
from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig
from src.scheduler.scheduler import TaskScheduler
from src.scheduler.scheduler_jobs import _run_with_lock
from src.services.commission_settlement_b12_service import (
    CommissionSettlementB12Service,
)

logger = logging.getLogger("scheduler.settlement_b12_jobs")


# ── 配置加载器（SystemConfig 表 + Redis 缓存） ─────────────────────


async def _load_settlement_delay_days(db_session) -> int:
    """读取延迟结算天数配置

    读取顺序：
    1. Redis 缓存（key=gaking:prod:settlement_delay_days，TTL=5min）
    2. 未命中查 gaking_system_config 表 config_value
    3. 缺失兜底 SETTLEMENT_DELAY_DAYS_DEFAULT=30

    Args:
        db_session: 异步数据库会话
    Returns:
        延迟天数（int）
    """
    config_key = CONFIG_KEY_SETTLEMENT_DELAY_DAYS

    # 1. Redis 缓存优先
    cached = await RedisClient.get(config_key)
    if cached is not None:
        if cached == "__EMPTY__":
            return SETTLEMENT_DELAY_DAYS_DEFAULT
        try:
            return int(cached)
        except (ValueError, TypeError):
            logger.warning(
                "[config_loader] 延迟天数缓存值非法 key=%s value=%s，回退默认",
                config_key,
                cached,
            )
            return SETTLEMENT_DELAY_DAYS_DEFAULT

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
            return SETTLEMENT_DELAY_DAYS_DEFAULT
        value = row[0]
        # 回填缓存（5min）
        await RedisClient.set(config_key, value, expire=SETTLEMENT_DELAY_DAYS_CACHE_TTL)
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(
                "[config_loader] 延迟天数配置值非法 key=%s value=%s，回退默认",
                config_key,
                value,
            )
            return SETTLEMENT_DELAY_DAYS_DEFAULT
    except Exception as e:
        logger.warning(
            "[config_loader] 读取 SystemConfig 失败 key=%s error=%s",
            config_key,
            e,
        )
        return SETTLEMENT_DELAY_DAYS_DEFAULT


# ── Service 构造工具 ───────────────────────────────────────────────


async def _build_service(db_session) -> CommissionSettlementB12Service:
    """根据 db session 构造 CommissionSettlementB12Service 实例

    统一注入 4 个依赖：OrderDAO / SettlementRecordDAO / SettlementAtomicDAO /
    SettlementOperationLogDAO，所有 DAO 共享同一 session（保证单事务原子性）。
    熔断器注入 CircuitBreaker 实例（channel_code=settlement）。
    """
    order_dao = OrderDAO(db_session)
    settlement_dao = SettlementRecordDAO(db_session)
    atomic_dao = SettlementAtomicDAO(db_session)
    log_dao = SettlementOperationLogDAO(db_session)
    circuit_breaker = CircuitBreaker()
    return CommissionSettlementB12Service(
        order_dao=order_dao,
        settlement_dao=settlement_dao,
        atomic_dao=atomic_dao,
        log_dao=log_dao,
        circuit_breaker=circuit_breaker,
    )


# ── 任务8：SETTLABLE 订单批量冻结入账 ──────────────────────────────


async def batch_freeze_settlable_job(
    limit: int = TASK_SETTLEMENT_FREEZE_BATCH_SIZE,
) -> Dict[str, Any]:
    """批量冻结 SETTLABLE 订单（定时任务入口）

    流程：检查开关 → 获取 DB 会话 → 读取延迟天数配置 →
    调用 CommissionSettlementB12Service.batch_freeze_settlable
    Service 内部逐单 try/except，单条失败不阻断整体，返回 partial 状态。

    Args:
        limit: 单轮处理订单上限（默认 200，最大由 schema 控制）
    Returns:
        {status, total, success_count, failed_count, skipped_count, details, delay_days}
    """
    task_name = "batch_freeze_settlable"

    if not TASK_SETTLEMENT_FREEZE_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "批量冻结任务开关关闭",
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": [],
            "delay_days": SETTLEMENT_DELAY_DAYS_DEFAULT,
        }

    logger.info("[%s] 任务开始执行 limit=%s", task_name, limit)
    try:
        async with DatabaseManager.get_session() as db:
            delay_days = await _load_settlement_delay_days(db)
            service = await _build_service(db)
            result = await service.batch_freeze_settlable(
                limit=limit,
                delay_days=delay_days,
            )
            result["delay_days"] = delay_days
        logger.info(
            "[%s] 任务完成 status=%s total=%s success=%s failed=%s skipped=%s delay_days=%s",
            task_name,
            result.get("status"),
            result.get("total"),
            result.get("success_count"),
            result.get("failed_count"),
            result.get("skipped_count"),
            delay_days,
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
            "delay_days": SETTLEMENT_DELAY_DAYS_DEFAULT,
        }


async def freeze_single_order_job(
    order_id: int,
    delay_days: Optional[int] = None,
) -> Dict[str, Any]:
    """单订单冻结入账任务（手动补发用）

    适用于：定时任务因异常漏单时，后台手动触发单笔补冻结。
    幂等：已存在结算单自动跳过（Service 层 freeze_on_settlable 内置幂等校验）。

    Args:
        order_id: 订单 ID
        delay_days: 延迟天数（None 时从配置读取）
    Returns:
        {status, order_id, settlement_id, settlement_no, amount}
    """
    task_name = "freeze_single_order"
    logger.info("[%s] 手动触发单笔冻结 order_id=%s", task_name, order_id)
    try:
        async with DatabaseManager.get_session() as db:
            actual_delay_days = (
                delay_days
                if delay_days is not None
                else await _load_settlement_delay_days(db)
            )
            service = await _build_service(db)
            result = await service.freeze_on_settlable(
                order_id=order_id,
                delay_days=actual_delay_days,
            )
        logger.info(
            "[%s] 完成 order_id=%s status=%s settlement_id=%s",
            task_name,
            order_id,
            result.get("status"),
            result.get("settlement_id"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 单笔冻结失败 order_id=%s: %s\n%s",
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


# ── 任务9：SETTLED 订单批量解冻转可用 ──────────────────────────────


async def batch_unfreeze_settled_job(
    limit: int = TASK_SETTLEMENT_UNFREEZE_BATCH_SIZE,
) -> Dict[str, Any]:
    """批量解冻 SETTLED 订单（定时任务入口）

    流程：检查开关 → 获取 DB 会话 →
    调用 CommissionSettlementB12Service.batch_unfreeze_settled
    Service 内部逐单 try/except，单条失败不阻断整体，返回 partial 状态。

    Args:
        limit: 单轮处理订单上限（默认 200）
    Returns:
        {status, total, success_count, failed_count, skipped_count, details}
    """
    task_name = "batch_unfreeze_settled"

    if not TASK_SETTLEMENT_UNFREEZE_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {
            "status": "skipped",
            "message": "批量解冻任务开关关闭",
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
            result = await service.batch_unfreeze_settled(limit=limit)
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


async def unfreeze_single_order_job(order_id: int) -> Dict[str, Any]:
    """单订单解冻转可用任务（手动补发用）

    适用于：定时任务因异常漏单时，后台手动触发单笔补解冻。
    幂等：结算单状态机守护，非 SETTLABLE 态抛 ValueError 拦截。

    Args:
        order_id: 订单 ID
    Returns:
        {status, order_id, settlement_id, settlement_no, amount}
    """
    task_name = "unfreeze_single_order"
    logger.info("[%s] 手动触发单笔解冻 order_id=%s", task_name, order_id)
    try:
        async with DatabaseManager.get_session() as db:
            service = await _build_service(db)
            result = await service.unfreeze_on_settled(order_id=order_id)
        logger.info(
            "[%s] 完成 order_id=%s status=%s settlement_id=%s",
            task_name,
            order_id,
            result.get("status"),
            result.get("settlement_id"),
        )
        return result
    except Exception as e:
        logger.error(
            "[%s] 单笔解冻失败 order_id=%s: %s\n%s",
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


def register_settlement_b12_jobs() -> None:
    """注册 B12 佣金结算状态机定时任务到 TaskScheduler

    由 scheduler_jobs.register_scheduler_jobs() 追加调用（不改动现有任务）。
    两个任务使用不同 cron 表达式错峰执行：
    - 批量冻结：每 12 分钟（与 B07 结算 */15 错开实例）
    - 批量解冻：每 8 分钟（与 B07 退款扣减 */10 错开实例，锁独立）
    定时频率 / 开关 / 锁超时均来自 b12_constants.py，禁止硬编码。
    """
    # 任务8：SETTLABLE 订单冻结入账 —— 每12分钟
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="batch_freeze_settlable",
        cron_expr=TASK_CRON_SETTLEMENT_FREEZE,
        args=(
            "batch_freeze_settlable",
            batch_freeze_settlable_job,
            TASK_SETTLEMENT_FREEZE_LOCK_TIMEOUT,
        ),
    )

    # 任务9：SETTLED 订单解冻转可用 —— 每8分钟
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="batch_unfreeze_settled",
        cron_expr=TASK_CRON_SETTLEMENT_UNFREEZE,
        args=(
            "batch_unfreeze_settled",
            batch_unfreeze_settled_job,
            TASK_SETTLEMENT_UNFREEZE_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "B12 settlement jobs registered: batch_freeze(%s), batch_unfreeze(%s)",
        TASK_CRON_SETTLEMENT_FREEZE,
        TASK_CRON_SETTLEMENT_UNFREEZE,
    )

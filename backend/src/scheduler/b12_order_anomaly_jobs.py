# @ai-generated
"""
B12-1 订单异常巡检定时任务

任务说明：
每 30 分钟巡检一次订单状态，统计异常订单并输出告警日志

巡检项：
1. 当日新增的异常状态订单（INVALID/REFUNDED）
2. 超时未流转的冻结订单（FROZEN > 3天）
3. 超时未结算的订单（SETTLABLE > 7天）
"""
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import and_, func, select

from src.common.lock_util import LockUtil
from src.config.b12_constants import (
    TASK_CRON_ORDER_ANOMALY_PATROL,
    TASK_ORDER_ANOMALY_PATROL_ENABLE,
    TASK_ORDER_ANOMALY_PATROL_LOCK_TIMEOUT,
    TASK_ORDER_ANOMALY_WARN_THRESHOLD,
)
from src.config.constants import OrderStatus
from src.dao.b12_order_operation_log_dao import OrderOperationLogDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.models.business.order_model import Order
from src.scheduler.scheduler import TaskScheduler
from src.services.b12_order_state_machine_service import B12OrderStateMachineService

logger = logging.getLogger("scheduler.b12_order_anomaly")


async def order_anomaly_patrol() -> Dict[str, Any]:
    """订单异常巡检

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "today_anomaly_count": int, "pending_frozen_count": int,
         "pending_settled_count": int, "details": dict}
    """
    task_name = "order_anomaly_patrol"

    if not TASK_ORDER_ANOMALY_PATROL_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "任务开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)

    try:
        async with DatabaseManager.get_session() as db:
            order_dao = OrderDAO(db)
            log_dao = OrderOperationLogDAO(db)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            result = await svc.patrol_anomaly_orders()

            # 异常告警
            today_anomaly = result.get("today_anomaly_count", 0)
            if today_anomaly >= TASK_ORDER_ANOMALY_WARN_THRESHOLD:
                logger.warning(
                    "[%s] 异常告警: 当日新增异常订单=%s, 阈值=%s",
                    task_name, today_anomaly, TASK_ORDER_ANOMALY_WARN_THRESHOLD,
                )
            else:
                logger.info(
                    "[%s] 巡检完成: 当日新增异常=%s, 超时冻结=%s, 超时可结算=%s",
                    task_name,
                    result.get("today_anomaly_count", 0),
                    result.get("pending_frozen_count", 0),
                    result.get("pending_settled_count", 0),
                )

            result["status"] = "success"
            return result

    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc())
        return {
            "status": "failed",
            "message": str(e),
            "today_anomaly_count": 0,
            "pending_frozen_count": 0,
            "pending_settled_count": 0,
            "details": {},
        }


# ── 分布式锁包装 ───────────────────────────────────────────


async def _run_with_lock() -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底

    S04 P2-1：锁冲突时先短等待重试（5s），降低任务跳过概率；
    仍失败则记录锁冲突计数并跳过。
    """
    lock_owner = None
    task_name = "order_anomaly_patrol"
    try:
        lock_owner = await LockUtil.acquire_with_wait(
            f"scheduler:{task_name}",
            timeout=TASK_ORDER_ANOMALY_PATROL_LOCK_TIMEOUT,
            wait_timeout=5,
            poll_interval=0.5,
        )
        if lock_owner is None:
            await LockUtil.record_lock_conflict(task_name)
            logger.warning("[order_anomaly_patrol] 等待5s后仍未获取到分布式锁，跳过本次执行")
            return {"status": "skipped", "message": "未获取到分布式锁，跳过"}
        return await order_anomaly_patrol()
    except Exception as e:
        logger.error("[order_anomaly_patrol] 任务执行异常: %s\n%s", e, traceback.format_exc())
        return {"status": "failed", "message": str(e)}
    finally:
        if lock_owner is not None:
            await LockUtil.release_lock(f"scheduler:{task_name}", lock_owner)


# ── 注册 ───────────────────────────────────────────────────


def register_b12_order_anomaly_jobs() -> None:
    """注册订单异常巡检定时任务"""
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="order_anomaly_patrol",
        cron_expr=TASK_CRON_ORDER_ANOMALY_PATROL,
        args=(),
    )
    logger.info(
        "B12 order anomaly patrol job registered: %s",
        TASK_CRON_ORDER_ANOMALY_PATROL,
    )
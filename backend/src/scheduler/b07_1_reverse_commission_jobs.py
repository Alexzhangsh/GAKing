# @ai-generated
"""
B07-1 逆向佣金冲减定时任务

任务：reverse_commission_auto_process
    定时扫描退款订单，自动执行逆向佣金冲减。
    频率：每30分钟（cron */30 * * * *）
    流程：识别退款订单 → 批量执行冲减 → 输出日志

设计约定：
1. 使用分布式锁（gaking:prod:lock:scheduler:reverse_commission_auto_process）
2. 完整 try/except + 日志
3. 定时频率、开关均来自 constants.py，禁止硬编码
"""
import logging
import traceback
from typing import Any, Dict

from src.common.lock_util import LockUtil
from src.config.b07_1_constants import (
    TASK_CRON_REVERSE_COMMISSION,
    TASK_REVERSE_COMMISSION_BATCH_SIZE,
    TASK_REVERSE_COMMISSION_ENABLE,
    TASK_REVERSE_COMMISSION_LOCK_TIMEOUT,
)
from src.dao.b07_1_reverse_commission_dao import (
    ReverseCommissionQueryDAO,
    ReverseCommissionRecordDAO,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.dao.order_refund_operation_log_dao import OrderRefundOperationLogDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler
from src.services.b07_1_reverse_commission_service import ReverseCommissionService
from src.services.commission_flow_validation_service import (
    CommissionFlowValidationService,
)
from src.services.refund_deduction_service import RefundDeductionService

logger = logging.getLogger("scheduler.b07_1_reverse_commission")


async def reverse_commission_auto_process() -> Dict[str, Any]:
    """逆向佣金冲减自动处理定时任务

    每30分钟执行一次：
    1. 识别新的退款订单（REFUNDED 状态）
    2. 批量执行 IDENTIFIED 和可重试的冲减记录

    Returns:
        {"status": "success"|"skipped"|"failed"|"partial", "message": str,
         "identify_result": dict, "execute_result": dict}
    """
    task_name = "reverse_commission_auto_process"

    if not TASK_REVERSE_COMMISSION_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {"status": "skipped", "message": "任务开关关闭"}

    logger.info("[%s] 任务开始执行", task_name)

    try:
        async with DatabaseManager.get_session() as db:
            # 构造服务依赖
            record_dao = ReverseCommissionRecordDAO(db)
            query_dao = ReverseCommissionQueryDAO(db)
            order_dao = OrderDAO(db)
            flow_dao = CommissionFlowDAO(db)
            account_dao = UserCommissionAccountDAO(db)
            settlement_dao = CommissionSettlementDAO(db)
            log_dao = OrderRefundOperationLogDAO(db)
            validation_log_dao = CommissionFlowValidationLogDAO(db)
            validation_service = CommissionFlowValidationService(
                order_dao=order_dao,
                flow_dao=flow_dao,
                validation_log_dao=validation_log_dao,
            )
            deduction_service = RefundDeductionService(
                order_dao=order_dao,
                flow_dao=flow_dao,
                settlement_dao=settlement_dao,
                account_dao=account_dao,
                log_dao=log_dao,
                validation_service=validation_service,
            )
            service = ReverseCommissionService(
                record_dao=record_dao,
                query_dao=query_dao,
                order_dao=order_dao,
                flow_dao=flow_dao,
                deduction_service=deduction_service,
            )

            # 执行完整流程
            result = await service.scheduled_reverse_commission()

        logger.info("[%s] 任务完成: %s", task_name, result.get("message", ""))
        return result

    except Exception as e:
        logger.error(
            "[%s] 任务执行异常: %s\n%s",
            task_name, e, traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e)}


async def _run_with_lock() -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底

    S04 P2-1：锁冲突时先短等待重试（5s），降低任务跳过概率；
    仍失败则记录锁冲突计数并跳过。
    """
    lock_owner = None
    task_name = "reverse_commission_auto_process"
    try:
        lock_owner = await LockUtil.acquire_with_wait(
            f"scheduler:{task_name}",
            timeout=TASK_REVERSE_COMMISSION_LOCK_TIMEOUT,
            wait_timeout=5,
            poll_interval=0.5,
        )
        if lock_owner is None:
            await LockUtil.record_lock_conflict(task_name)
            logger.warning("[reverse_commission] 等待5s后仍未获取到分布式锁，跳过本次执行")
            return {"status": "skipped", "message": "未获取到分布式锁，跳过"}
        return await reverse_commission_auto_process()
    except Exception as e:
        logger.error(
            "[reverse_commission] 任务执行异常: %s\n%s",
            e, traceback.format_exc(),
        )
        return {"status": "failed", "message": str(e)}
    finally:
        if lock_owner is not None:
            await LockUtil.release_lock(
                f"scheduler:{task_name}", lock_owner
            )


def register_reverse_commission_jobs() -> None:
    """注册逆向佣金冲减定时任务"""
    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="reverse_commission_auto_process",
        cron_expr=TASK_CRON_REVERSE_COMMISSION,
    )

    logger.info(
        "Reverse commission job registered: %s",
        TASK_CRON_REVERSE_COMMISSION,
    )
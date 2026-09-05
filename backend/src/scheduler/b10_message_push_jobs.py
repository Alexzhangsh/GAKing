# @ai-generated
"""
B10 消息推送定时任务

职责：
1. 每5分钟巡检待推送消息（push_status=0），尝试推送
2. 分布式锁防止集群并发
3. 单条推送失败不阻断整体，记日志后继续
4. 接入微信订阅消息后实现实际推送，当前阶段仅标记已推送

注册方式：由 scheduler_jobs.py 的 register_scheduler_jobs 追加注册
"""
import logging
import traceback
from datetime import datetime
from typing import Any, Dict

from src.common.lock_util import LockUtil
from src.config.b10_constants import (
    TASK_CRON_MESSAGE_PUSH_PATROL,
    TASK_MESSAGE_PUSH_PATROL_BATCH_SIZE,
    TASK_MESSAGE_PUSH_PATROL_ENABLE,
    TASK_MESSAGE_PUSH_PATROL_LOCK_TIMEOUT,
)
from src.dao.b10_user_message_dao import UserMessageDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler
from src.services.b10_message_service import B10MessageService

logger = logging.getLogger("scheduler.b10_message_push")


async def message_push_patrol() -> Dict[str, Any]:
    """消息推送巡检任务

    每5分钟扫描 push_status=0 的待推送消息，逐个尝试推送。
    推送失败记日志并标记 push_status=2（推送失败），不阻断整体流程。

    Returns:
        {"status": "success"|"skipped"|"failed", "processed": int, "success": int, "failed": int}
    """
    task_name = "b10_message_push_patrol"

    if not TASK_MESSAGE_PUSH_PATROL_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", task_name)
        return {"status": "skipped", "processed": 0, "success": 0, "failed": 0}

    logger.info("[%s] 任务开始执行", task_name)

    try:
        async with DatabaseManager.get_session() as db:
            dao = UserMessageDAO(db)
            svc = B10MessageService(dao)
            result = await svc.process_pending_push(
                limit=TASK_MESSAGE_PUSH_PATROL_BATCH_SIZE
            )

        logger.info(
            "[%s] 巡检完成 processed=%s success=%s failed=%s",
            task_name,
            result["processed"],
            result["success"],
            result["failed"],
        )
        return {
            "status": "success",
            "processed": result["processed"],
            "success": result["success"],
            "failed": result["failed"],
        }
    except Exception as e:
        logger.error(
            "[%s] 任务执行失败: %s\n%s", task_name, e, traceback.format_exc()
        )
        return {"status": "failed", "processed": 0, "success": 0, "failed": 0, "error": str(e)}


def register_b10_message_push_jobs() -> None:
    """注册B10消息推送定时任务

    由 scheduler_jobs.py 的 register_scheduler_jobs 调用追加注册。
    """
    from src.scheduler.scheduler_jobs import _run_with_lock

    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name="b10_message_push_patrol",
        cron_expr=TASK_CRON_MESSAGE_PUSH_PATROL,
        args=(
            "b10_message_push_patrol",
            message_push_patrol,
            TASK_MESSAGE_PUSH_PATROL_LOCK_TIMEOUT,
        ),
    )

    logger.info(
        "B10 message push job registered: %s (cron=%s)",
        "b10_message_push_patrol",
        TASK_CRON_MESSAGE_PUSH_PATROL,
    )
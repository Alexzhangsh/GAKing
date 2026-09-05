# @ai-generated
"""
X02-1 会员状态定时刷新任务

职责：
1. 将已到期的 active 会员记录批量标记为 expired（user_member_record 表）
2. 每次运行在 scheduled_task_run_log 表记录完整运行状态，支持 M07-2 运维监控追溯
3. 分布式锁防止集群并发

手动调用验证：
    from src.scheduler.member_status_jobs import member_status_refresh
    await member_status_refresh()
"""
import json
import logging
import random
import traceback
from datetime import datetime
from typing import Any, Dict

from src.common.lock_util import LockUtil
from src.config.x02_1_constants import (
    TASK_MEMBER_STATUS_REFRESH_ENABLE,
    TASK_MEMBER_STATUS_REFRESH_LOCK_TIMEOUT,
)
from src.dao.scheduled_task_run_log_dao import ScheduledTaskRunLogDAO
from src.dao.user_member_record_dao import UserMemberRecordDAO
from src.db.init_db import DatabaseManager
from src.scheduler.scheduler import TaskScheduler

logger = logging.getLogger("scheduler.member_status")

TASK_NAME = "member_status_refresh"


def _make_run_id() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = random.randint(100, 999)
    return f"{TASK_NAME}_{ts}_{rand}"


async def member_status_refresh() -> Dict[str, Any]:
    """会员状态定时刷新

    将已到期的 active 会员记录标记为 expired。

    Returns:
        {"status": "success"|"skipped"|"failed", "message": str,
         "expired_count": int}
    """
    if not TASK_MEMBER_STATUS_REFRESH_ENABLE:
        logger.info("[%s] 任务开关关闭，跳过执行", TASK_NAME)
        return {"status": "skipped", "message": "任务开关关闭", "expired_count": 0}

    started_at = datetime.now()
    run_id = _make_run_id()
    logger.info("[%s] 任务开始执行 run_id=%s", TASK_NAME, run_id)

    async with DatabaseManager.get_session() as db:
        log_dao = ScheduledTaskRunLogDAO(db)
        log = await log_dao.create_run_log(
            task_name=TASK_NAME,
            run_id=run_id,
            status="running",
            started_at=started_at,
            total_orders=0,
        )

    try:
        async with DatabaseManager.get_session() as db:
            dao = UserMemberRecordDAO(db)
            expired_count = await dao.mark_expired_before(datetime.now())

        finished_at = datetime.now()
        duration = int((finished_at - started_at).total_seconds())
        detail = {"expired_count": expired_count}

        async with DatabaseManager.get_session() as db:
            log_dao = ScheduledTaskRunLogDAO(db)
            await log_dao.update_run_log(
                log.id,
                status="success",
                finished_at=finished_at,
                duration_seconds=duration,
                total_orders=expired_count,
                success_count=expired_count,
                detail_json=json.dumps(detail, ensure_ascii=False),
            )

        logger.info(
            "[%s] 会员状态刷新完成 expired_count=%s duration=%ss",
            TASK_NAME, expired_count, duration,
        )
        return {
            "status": "success",
            "message": f"会员状态刷新完成，到期标记 {expired_count} 条",
            "expired_count": expired_count,
        }
    except Exception as e:
        logger.error("[%s] 任务执行失败: %s\n%s", TASK_NAME, e, traceback.format_exc())
        finished_at = datetime.now()
        duration = int((finished_at - started_at).total_seconds())
        try:
            async with DatabaseManager.get_session() as db:
                log_dao = ScheduledTaskRunLogDAO(db)
                await log_dao.update_run_log(
                    log.id,
                    status="failed",
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error_message=str(e)[:500],
                )
        except Exception:
            pass
        return {"status": "failed", "message": str(e), "expired_count": 0}


# ── 分布式锁包装 ───────────────────────────────────────────


async def _run_with_lock() -> Dict[str, Any]:
    """任务执行包装：分布式锁 + 调用 + 异常兜底"""
    lock_owner = None
    try:
        lock_owner = await LockUtil.acquire_with_wait(
            f"scheduler:{TASK_NAME}",
            timeout=TASK_MEMBER_STATUS_REFRESH_LOCK_TIMEOUT,
            wait_timeout=5,
            poll_interval=0.5,
        )
        if lock_owner is None:
            await LockUtil.record_lock_conflict(TASK_NAME)
            logger.warning("[%s] 等待5s后仍未获取到分布式锁，跳过本次执行", TASK_NAME)
            return {"status": "skipped", "message": "未获取到分布式锁，跳过", "expired_count": 0}
        return await member_status_refresh()
    except Exception as e:
        logger.error("[%s] 任务执行异常: %s\n%s", TASK_NAME, e, traceback.format_exc())
        return {"status": "failed", "message": str(e), "expired_count": 0}
    finally:
        if lock_owner is not None:
            await LockUtil.release_lock(f"scheduler:{TASK_NAME}", lock_owner)


# ── 注册 ───────────────────────────────────────────────────


def register_member_status_jobs() -> None:
    """注册会员状态定时刷新任务"""
    from src.config.x02_1_constants import TASK_CRON_MEMBER_STATUS_REFRESH

    TaskScheduler.add_cron_task(
        func=_run_with_lock,
        name=TASK_NAME,
        cron_expr=TASK_CRON_MEMBER_STATUS_REFRESH,
        args=(),
    )
    logger.info(
        "X02-1 member status refresh job registered: %s",
        TASK_CRON_MEMBER_STATUS_REFRESH,
    )

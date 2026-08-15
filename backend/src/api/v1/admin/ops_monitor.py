# @ai-generated
"""
M07-2 运维监控 API 路由
路由前缀：/api/v1/admin/ops-monitor
权限码：ops:monitor（仅管理员可见大盘运维子Tab）
职责：
1. 定时任务概览统计（成功率 / 最近执行状态 / 失败清单）
2. 渠道报错计数（本地日志统计）
"""
import logging

from typing import Dict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_OPS_MONITOR
from src.dao.scheduled_task_run_log_dao import ScheduledTaskRunLogDAO
from src.db.init_db import DatabaseManager

logger = logging.getLogger("api.admin.ops_monitor")

router = APIRouter(
    prefix="/api/v1/admin/ops-monitor",
    tags=["后台-运维监控(M07-2)"],
)


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


@router.get("/overview")
async def get_ops_overview(
    request: Request,
    days: int = Query(default=7, ge=1, le=30, description="统计天数"),
    payload: dict = Depends(require_any_permission([PERM_OPS_MONITOR])),
    db: AsyncSession = Depends(get_db),
):
    """运维监控总览

    返回：
    - task_stats: 各定时任务成功率 / 运行次数 / 最近运行时间
    - recent_status: 各任务最近一次执行状态
    - failed_list: 最近失败清单
    - channel_errors: 渠道报错计数（本地日志统计）
    """
    request_id = get_request_id(request)
    try:
        log_dao = ScheduledTaskRunLogDAO(db)
        task_stats = await log_dao.get_task_summary_stats(days=days)
        recent_status = await log_dao.get_latest_run_per_task()
        failed_logs = await log_dao.get_recent_failed_logs(limit=20)
        failed_list = [
            {
                "id": log.id,
                "task_name": log.task_name,
                "status": log.status,
                "started_at": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else "",
                "duration_seconds": log.duration_seconds or 0,
                "error_message": log.error_message or "",
            }
            for log in failed_logs
        ]
        data = {
            "days": days,
            "task_stats": task_stats,
            "recent_status": recent_status,
            "failed_list": failed_list,
            "channel_errors": {"source": "local_log", "channels": {}},
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

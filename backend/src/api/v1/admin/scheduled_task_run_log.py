# @ai-generated
"""
后台定时任务运行日志管理接口（B05-7 新增）
路由前缀：/api/v1/admin/scheduled-task-run-logs
职责：管理员身份识别 → 参数校验 → 调用 DAO 查询 → 统一响应封装
"""
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.dao.scheduled_task_run_log_dao import ScheduledTaskRunLogDAO
from src.db.init_db import DatabaseManager
from src.schemas.scheduled_task_run_log import (
    ScheduledTaskRunLogDetailResponse,
    ScheduledTaskRunLogItem,
    ScheduledTaskRunLogListResponse,
)

logger = logging.getLogger("api.admin.scheduled_task_run_log")

router = APIRouter(
    prefix="/api/v1/admin/scheduled-task-run-logs",
    tags=["后台-定时任务运行日志"],
)


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["commission:settle"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC commission:settle 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


# ══════════════════════════════════════════════════════
# 1. 多条件查询运行日志
# ══════════════════════════════════════════════════════


@router.get("")
async def list_task_run_logs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    task_name: str = Query(default=None, description="任务名称筛选"),
    status: str = Query(default=None, description="运行状态筛选：success/failed/partial"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """1. 多条件查询定时任务运行日志

    支持按任务名称、运行状态筛选，按开始时间降序排列。
    """
    request_id = get_request_id(request)
    try:
        log_dao = ScheduledTaskRunLogDAO(db)
        items, total = await log_dao.list_with_filters(
            task_name=task_name or None,
            status=status or None,
            page=page,
            page_size=page_size,
        )
        log_items = [
            ScheduledTaskRunLogItem(
                id=item.id,
                task_name=item.task_name,
                run_id=item.run_id,
                status=item.status,
                started_at=item.started_at.strftime("%Y-%m-%d %H:%M:%S") if item.started_at else "",
                finished_at=item.finished_at.strftime("%Y-%m-%d %H:%M:%S") if item.finished_at else None,
                duration_seconds=item.duration_seconds or 0,
                total_orders=item.total_orders or 0,
                success_count=item.success_count or 0,
                failed_count=item.failed_count or 0,
                skipped_count=item.skipped_count or 0,
                error_message=item.error_message or "",
            )
            for item in items
        ]
        resp = ScheduledTaskRunLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 查询运行日志详情
# ══════════════════════════════════════════════════════


@router.get("/{log_id}")
async def get_task_run_log_detail(
    log_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
):
    """2. 查询单条运行日志详情（含详细结果JSON）

    用于后台审计查看单次任务运行的完整结果。
    """
    request_id = get_request_id(request)
    try:
        log_dao = ScheduledTaskRunLogDAO(db)
        log = await log_dao.get_by_id(log_id)
        if log is None:
            return error_response(
                code=404,
                msg=f"运行日志不存在: log_id={log_id}",
                request_id=request_id,
            )

        # 解析 detail_json
        detail_data = None
        if log.detail_json:
            try:
                detail_data = json.loads(log.detail_json)
            except (json.JSONDecodeError, TypeError):
                detail_data = log.detail_json

        resp = ScheduledTaskRunLogDetailResponse(
            id=log.id,
            task_name=log.task_name,
            run_id=log.run_id,
            status=log.status,
            started_at=log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else "",
            finished_at=log.finished_at.strftime("%Y-%m-%d %H:%M:%S") if log.finished_at else None,
            duration_seconds=log.duration_seconds or 0,
            total_orders=log.total_orders or 0,
            success_count=log.success_count or 0,
            failed_count=log.failed_count or 0,
            skipped_count=log.skipped_count or 0,
            error_message=log.error_message or "",
            detail_json=detail_data,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
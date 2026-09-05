# @ai-generated
"""
B14 审计日志查询 API（列表 / 详情 / 统计）
路由前缀：/api/v1/admin/audit
新建独立文件，不修改 B01-B13 任何基线 API

接口清单：
1. GET /api/v1/admin/audit/logs         分页查询审计日志（多条件筛选）
2. GET /api/v1/admin/audit/logs/{log_id} 审计日志详情
3. GET /api/v1/admin/audit/stats         审计日志统计（按 action/target_type/user 聚合）

权限设计：
- 全部接口需要 audit:view 权限（超管 * 通配符自动放行）
- 审计日志只读不写（写入由 AuditLogger / B14AuditMiddleware 自动完成）
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b14_constants import PERM_AUDIT_VIEW
from src.services.b14_audit_service import B14AuditService

logger = logging.getLogger("api.admin.b14_audit")

router = APIRouter(prefix="/api/v1/admin/audit", tags=["后台-审计日志(B14)"])


# ── 依赖注入 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_AUDIT_VIEW])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC audit:view 权限）"""
    return int(payload["user_id"])


def _serialize_log(log) -> dict:
    """序列化 AuditLogs 实例为字典（datetime 转字符串）"""
    create_time = log.create_time
    if isinstance(create_time, datetime):
        create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")
    
    details = log.details
    if details and not isinstance(details, str):
        import json
        details = json.dumps(details, ensure_ascii=False)
    
    return {
        "id": log.id,
        "user_id": log.user_id,
        "user_name": log.user_name,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": details,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "create_time": create_time,
    }


# ════════════════════════════════════════════════════════════
# 静态路径（必须在 /logs/{log_id} 之前）
# ════════════════════════════════════════════════════════════


@router.get("/stats")
async def get_audit_stats(
    request: Request,
    start_time: Optional[datetime] = Query(None, description="起始时间（含，ISO 8601）"),
    end_time: Optional[datetime] = Query(None, description="截止时间（不含，ISO 8601）"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """审计日志统计（按 action / target_type / user 聚合）"""
    request_id = get_request_id(request)
    try:
        stats = await B14AuditService.get_audit_stats(
            start_time=start_time, end_time=end_time
        )
        return success_response(data=stats, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 列表 & 动态路径
# ════════════════════════════════════════════════════════════


@router.get("/logs")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user_id: Optional[int] = Query(None, gt=0, description="操作人ID筛选"),
    action: Optional[str] = Query(None, description="动作类型筛选"),
    target_type: Optional[str] = Query(None, description="目标类型筛选"),
    start_time: Optional[datetime] = Query(None, description="起始时间（含）"),
    end_time: Optional[datetime] = Query(None, description="截止时间（不含）"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """分页查询审计日志（多条件筛选，按创建时间降序）"""
    request_id = get_request_id(request)
    try:
        items, total = await B14AuditService.list_audit_logs(
            user_id=user_id,
            action=action,
            target_type=target_type,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_log(log) for log in items],
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/logs/{log_id}")
async def get_audit_log(
    request: Request,
    log_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """获取审计日志详情"""
    request_id = get_request_id(request)
    try:
        log = await B14AuditService.get_audit_log(log_id)
        if log is None:
            return handle_service_exception(
                ValueError(f"审计日志ID {log_id} 不存在"), request_id
            )
        return success_response(data=_serialize_log(log), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

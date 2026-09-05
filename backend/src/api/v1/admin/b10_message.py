# @ai-generated
"""
B10 后台消息管理接口
路由前缀：/api/v1/admin/message
权限码：message:manage
职责：管理员身份识别 → 参数校验 → 调用 B10MessageService → 统一响应封装

接口清单：
1. GET    /api/v1/admin/message/list      后台消息管理列表（多条件分页查询）
2. GET    /api/v1/admin/message/unread-stat 未读消息统计（按用户/类型汇总）
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.dao.b10_user_message_dao import UserMessageDAO
from src.db.init_db import DatabaseManager
from src.services.b10_message_service import B10MessageService

logger = logging.getLogger("api.admin.b10_message")

router = APIRouter(prefix="/api/v1/admin/message", tags=["后台-消息管理(B10)"])


# ── 依赖注入 ──────────────────────────────────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["message:manage"])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC message:manage 权限）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_message_service(db: AsyncSession = Depends(get_db)) -> B10MessageService:
    """构造 B10MessageService 实例"""
    return B10MessageService(UserMessageDAO(db))


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.get("/list")
async def list_messages(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user_id: Optional[int] = Query(None, gt=0, description="用户ID筛选"),
    message_type: Optional[str] = Query(
        None, description="消息类型：commission/withdraw/order/refund"
    ),
    is_read: Optional[int] = Query(None, ge=0, le=1, description="已读状态：0=未读 1=已读"),
    push_status: Optional[int] = Query(None, ge=0, le=2, description="推送状态：0=待推送 1=已推送 2=推送失败"),
    start_time: Optional[str] = Query(None, description="创建时间起始（YYYY-MM-DD HH:mm:ss）"),
    end_time: Optional[str] = Query(None, description="创建时间截止（YYYY-MM-DD HH:mm:ss）"),
    admin_user_id: int = Depends(get_admin_user_id),
    svc: B10MessageService = Depends(get_message_service),
):
    """1. 后台消息管理列表（多条件分页查询）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 后台消息列表 admin=%s user_id=%s type=%s is_read=%s push_status=%s",
        request_id, admin_user_id, user_id, message_type, is_read, push_status,
    )
    try:
        result = await svc.list_messages_for_admin(
            user_id=user_id,
            message_type=message_type,
            is_read=is_read,
            push_status=push_status,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
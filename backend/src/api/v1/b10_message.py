# @ai-generated
"""
B10 用户端站内消息接口
路由前缀：/api/v1/message
职责：用户身份识别 → 参数校验 → 调用 B10MessageService → 统一响应封装
不包含任何业务逻辑

接口清单：
1. GET    /api/v1/message/list         查询我的消息列表（分页，支持按类型筛选）
2. GET    /api/v1/message/unread-count  查询未读消息数
3. PUT    /api/v1/message/read         标记消息已读（单条或全部）
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import JwtAuthGuard
from src.dao.b10_user_message_dao import UserMessageDAO
from src.db.init_db import DatabaseManager
from src.schemas.b10_message import MarkReadRequest
from src.services.b10_message_service import B10MessageService

logger = logging.getLogger("api.b10_message")

router = APIRouter(prefix="/api/v1/message", tags=["用户-站内消息(B10)"])


# ── 依赖注入：身份识别 + 数据库会话 + Service 实例 ──────────────


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> int:
    """获取当前平台用户ID（与 withdraw.py 身份识别逻辑一致）"""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        payload = JwtAuthGuard.verify_token(token)
        if payload and "user_id" in payload:
            return int(payload["user_id"])
        raise HTTPException(status_code=401, detail="无效或过期的 token")

    if x_user_id:
        try:
            uid = int(x_user_id)
            logger.warning("[auth] 开发模式回退：使用 X-User-Id=%s（未走 JWT）", uid)
            return uid
        except ValueError:
            raise HTTPException(status_code=400, detail="X-User-Id 必须为整数")

    raise HTTPException(
        status_code=401, detail="未提供身份凭证（Authorization 或 X-User-Id）"
    )


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
    message_type: Optional[str] = Query(
        None, description="消息类型：commission/withdraw/order/refund"
    ),
    user_id: int = Depends(get_current_user_id),
    svc: B10MessageService = Depends(get_message_service),
):
    """1. 查询我的消息列表（分页，按创建时间倒序）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询消息列表 user_id=%s type=%s page=%s size=%s",
        request_id, user_id, message_type, page, page_size,
    )
    try:
        result = await svc.list_user_messages(
            user_id=user_id, message_type=message_type, page=page, page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/unread-count")
async def get_unread_count(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    svc: B10MessageService = Depends(get_message_service),
):
    """2. 查询未读消息数（读穿缓存）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询未读消息数 user_id=%s", request_id, user_id,
    )
    try:
        count = await svc.get_unread_count(user_id)
        return success_response(data={"unread_count": count}, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/read")
async def mark_read(
    body: MarkReadRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    svc: B10MessageService = Depends(get_message_service),
):
    """3. 标记消息已读（单条或全部已读）

    - message_id 有值：标记单条已读
    - message_id 为空：标记全部已读
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 标记已读 user_id=%s message_id=%s",
        request_id, user_id, body.message_id,
    )
    try:
        updated = await svc.mark_as_read(user_id, message_id=body.message_id)
        return success_response(
            data={"updated": updated, "message_id": body.message_id},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)
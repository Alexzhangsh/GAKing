# @ai-generated
"""
F05 营销消息用户端 API
路由前缀：/api/v1/message/subscribe
职责：用户身份识别 → 参数校验 → 调用 B15MessageUserService → 统一响应封装

接口清单：
1. GET  /api/v1/message/subscribe/templates   可订阅模板列表（启用中的微信订阅模板）
2. GET  /api/v1/message/subscribe/status      我的订阅状态（含过期标记）
3. POST /api/v1/message/subscribe             记录订阅授权结果（accept/reject/expired）
4. POST /api/v1/message/unsubscribe           取消订阅
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import JwtAuthGuard
from src.schemas.b15_message_user import (
    SubscribeRequest,
    UnsubscribeRequest,
)
from src.services.b15_message_user_service import B15MessageUserService

logger = logging.getLogger("api.b15_message_user")

router = APIRouter(prefix="/api/v1/message", tags=["用户-营销消息订阅(F05)"])


# ── 依赖注入：C端用户身份识别（与 b10_message.py 一致） ──────────


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> int:
    """获取当前平台用户ID"""
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


# ════════════════════════════════════════════════════════════
# 接口实现
# ════════════════════════════════════════════════════════════


@router.get("/subscribe/templates")
async def list_subscribe_templates(
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """1. 可订阅模板列表（启用中的微信订阅消息模板）"""
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 查询可订阅模板 user_id=%s", request_id, user_id)
    try:
        data = await B15MessageUserService.list_subscribe_templates()
        return success_response(data={"list": data}, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/subscribe/status")
async def get_subscribe_status(
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """2. 我的订阅状态（含过期标记，供弹窗/消息中心渲染）"""
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 查询订阅状态 user_id=%s", request_id, user_id)
    try:
        data = await B15MessageUserService.get_user_subscribe_status(user_id)
        return success_response(data={"list": data}, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/subscribe")
async def record_subscribe(
    body: SubscribeRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """3. 记录订阅授权结果

    - action=accept：标记已订阅，有效期 7 天
    - action=reject：用户拒绝授权，标记未订阅
    - action=expired：授权过期/模板不可用，标记未订阅
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 记录订阅授权 user_id=%s template_id=%s action=%s",
        request_id, user_id, body.template_id, body.action,
    )
    try:
        data = await B15MessageUserService.record_subscribe(
            user_id=user_id,
            template_id=body.template_id,
            action=body.action,
            tmpl_id=body.tmpl_id,
        )
        return success_response(data=data, msg="订阅状态已更新", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/unsubscribe")
async def unsubscribe(
    body: UnsubscribeRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """4. 取消订阅"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 取消订阅 user_id=%s template_id=%s",
        request_id, user_id, body.template_id,
    )
    try:
        data = await B15MessageUserService.unsubscribe(user_id, body.template_id)
        return success_response(data=data, msg="已取消订阅", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

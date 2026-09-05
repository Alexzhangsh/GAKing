# @ai-generated
"""
B11-1 用户端渠道信息接口
路由前缀：/api/v1/b11/channel

功能范围：
1. 查询渠道黑名单状态（用户端校验）
2. 查询渠道统计信息（用户端展示）
"""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import JwtAuthGuard
from src.dao.b11_channel_dao import ChannelBlacklistDAO, ChannelDailyStatDAO
from src.db.base import DatabaseManager
from src.services.b11_channel_service import (
    B11ChannelBlacklistService,
    B11ChannelStatisticsService,
)

logger = logging.getLogger("api.b11_channel")

router = APIRouter(prefix="/api/v1/b11/channel", tags=["B11-渠道信息"])


# ── 依赖注入 ──────────────────────────────────────────────


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
        return int(x_user_id)
    raise HTTPException(status_code=401, detail="未提供认证信息")


# ════════════════════════════════════════════════════════════
# 1. 黑名单校验接口
# ════════════════════════════════════════════════════════════


@router.get("/blacklist/check")
async def check_blacklist(
    request: Request,
    channel_code: str = Query(..., description="渠道标识"),
    blacklist_type: str = Query(..., description="黑名单类型：user/ip/order"),
    blacklist_value: str = Query(..., description="待校验的值（用户ID/IP/订单号）"),
    user_id: int = Depends(get_current_user_id),
):
    """校验指定值是否在渠道黑名单中"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelBlacklistDAO(session)
            svc = B11ChannelBlacklistService(dao)
            is_blacklisted = await svc.check_blacklisted(
                channel_code=channel_code,
                blacklist_type=blacklist_type,
                blacklist_value=blacklist_value,
            )
            return success_response(
                data={
                    "channel_code": channel_code,
                    "blacklist_type": blacklist_type,
                    "blacklist_value": blacklist_value,
                    "is_blacklisted": is_blacklisted,
                },
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 渠道统计信息
# ════════════════════════════════════════════════════════════


@router.get("/stat/summary")
async def get_channel_stat_summary(
    request: Request,
    start_date: str = Query(..., description="起始日期(YYYY-MM-DD)"),
    end_date: str = Query(..., description="截止日期(YYYY-MM-DD)"),
    channel_code: Optional[str] = Query(None, description="渠道标识，为空时查询全部"),
    user_id: int = Depends(get_current_user_id),
):
    """获取渠道统计汇总信息"""
    request_id = get_request_id(request)
    try:
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)

        async with DatabaseManager.get_session() as session:
            dao = ChannelDailyStatDAO(session)
            svc = B11ChannelStatisticsService(dao)
            data = await svc.get_summary(
                start_date=start_dt,
                end_date=end_dt,
                channel_code=channel_code,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
# @ai-generated
"""
前端行为埋点 & 错误日志上报 API（M04 新建）
路由前缀：/api/v1/track

接口清单：
1. POST /api/v1/track/event   批量行为埋点上报（防抖合并）
2. POST /api/v1/track/error   批量错误日志上报（JS异常/接口报错/Promise拒绝）

设计要点：
1. 公开接口，无需 JwtAuthGuard（埋点需支持匿名用户）
2. 支持批量写入（前端防抖合并 30 条或 5s 上报一次）
3. 尝试从 Bearer Token 提取 user_id，匿名用户 user_id=0
4. 写入失败仅记录日志，不阻断前端（埋点不能影响业务）
5. params / device_info 为 JSON 字符串，前端序列化后传入
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from src.api.v1.response_util import (
    get_request_id,
    success_response,
)
from src.common.auth_util import JwtAuthGuard
from src.db.init_db import DatabaseManager
from src.models.business.track_event_model import TrackEvent

logger = logging.getLogger("api.track")

router = APIRouter(prefix="/api/v1/track", tags=["前端埋点&错误上报"])

# 单次批量上报上限（防止恶意大包）
MAX_BATCH_SIZE = 50


class TrackEventItem(BaseModel):
    """单条埋点/错误事件"""

    event_type: str = Field(
        ...,
        max_length=32,
        description="事件类型：page_view/goods_click/share/order_create/withdraw_apply/js_error/api_error/promise_reject",
    )
    event_name: str = Field(default="", max_length=128, description="事件名称")
    page_path: str = Field(default="", max_length=256, description="页面路径")
    params: Optional[dict] = Field(default=None, description="事件参数(对象，后端序列化存储)")
    device_info: Optional[dict] = Field(default=None, description="设备信息(对象)")
    session_id: str = Field(default="", max_length=64, description="会话ID")
    client_timestamp: int = Field(default=0, description="客户端事件时间戳(ms)")


class TrackBatchRequest(BaseModel):
    """批量埋点/错误上报请求"""

    events: List[TrackEventItem] = Field(..., max_length=MAX_BATCH_SIZE, description="事件列表(最多50条)")


class TrackBatchResponse(BaseModel):
    """批量上报响应"""

    received: int
    saved: int


def _extract_user_id(authorization: Optional[str]) -> int:
    """从 Bearer Token 提取 user_id，失败返回 0（匿名）"""
    if not authorization:
        return 0
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return 0
    payload = JwtAuthGuard.verify_token(token)
    if not payload:
        return 0
    try:
        return int(payload.get("user_id", 0))
    except (ValueError, TypeError):
        return 0


@router.post("/event")
async def track_event(
    body: TrackBatchRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """批量行为埋点上报

    前端防抖合并后批量上报，单次最多 50 条。
    user_id 从 Bearer Token 提取（匿名用户 user_id=0）。
    写入失败仅记录日志，不阻断前端。
    """
    request_id = get_request_id(request)
    user_id = _extract_user_id(authorization)

    if not body.events:
        return success_response(
            data=TrackBatchResponse(received=0, saved=0).model_dump(),
            request_id=request_id,
        )

    saved_count = 0
    try:
        async with DatabaseManager.get_session() as session:
            for item in body.events:
                event = TrackEvent(
                    user_id=user_id,
                    event_type=item.event_type,
                    event_name=item.event_name or "",
                    page_path=item.page_path or "",
                    params=json.dumps(item.params, ensure_ascii=False) if item.params else "",
                    device_info=json.dumps(item.device_info, ensure_ascii=False) if item.device_info else "",
                    session_id=item.session_id or "",
                    client_timestamp=item.client_timestamp or 0,
                )
                session.add(event)
                saved_count += 1
            await session.commit()

        logger.info(
            "[request_id=%s] 埋点批量写入成功 user_id=%s count=%s",
            request_id,
            user_id,
            saved_count,
        )
        return success_response(
            data=TrackBatchResponse(received=len(body.events), saved=saved_count).model_dump(),
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "[request_id=%s] 埋点批量写入失败 user_id=%s count=%s: %s",
            request_id,
            user_id,
            len(body.events),
            str(exc),
            exc_info=True,
        )
        # 埋点写入失败不阻断前端，返回成功（received=saved=0）
        return success_response(
            data=TrackBatchResponse(received=len(body.events), saved=0).model_dump(),
            msg="上报已接收",
            request_id=request_id,
        )


@router.post("/error")
async def track_error(
    body: TrackBatchRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """批量错误日志上报

    前端收集 JS 异常 / 接口报错 / Promise 拒绝后批量上报。
    与 /event 共用 track_event 表，通过 event_type 区分：
    - js_error: JS 运行时异常
    - api_error: 接口报错
    - promise_reject: 未处理的 Promise 拒绝
    """
    request_id = get_request_id(request)
    user_id = _extract_user_id(authorization)

    if not body.events:
        return success_response(
            data=TrackBatchResponse(received=0, saved=0).model_dump(),
            request_id=request_id,
        )

    saved_count = 0
    try:
        async with DatabaseManager.get_session() as session:
            for item in body.events:
                event = TrackEvent(
                    user_id=user_id,
                    event_type=item.event_type,
                    event_name=item.event_name or "",
                    page_path=item.page_path or "",
                    params=json.dumps(item.params, ensure_ascii=False) if item.params else "",
                    device_info=json.dumps(item.device_info, ensure_ascii=False) if item.device_info else "",
                    session_id=item.session_id or "",
                    client_timestamp=item.client_timestamp or 0,
                )
                session.add(event)
                saved_count += 1
            await session.commit()

        logger.info(
            "[request_id=%s] 错误日志批量写入成功 user_id=%s count=%s",
            request_id,
            user_id,
            saved_count,
        )
        return success_response(
            data=TrackBatchResponse(received=len(body.events), saved=saved_count).model_dump(),
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "[request_id=%s] 错误日志批量写入失败 user_id=%s count=%s: %s",
            request_id,
            user_id,
            len(body.events),
            str(exc),
            exc_info=True,
        )
        return success_response(
            data=TrackBatchResponse(received=len(body.events), saved=0).model_dump(),
            msg="上报已接收",
            request_id=request_id,
        )

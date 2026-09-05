# @ai-generated
"""
短链服务 API 接口
路由前缀：/s（公开重定向）/api/v1/short-link（内部创建）
"""
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.db.init_db import DatabaseManager
from src.schemas.short_link import ShortLinkCreateRequest, ShortLinkResponse
from src.services.short_link_service import ShortLinkService

logger = logging.getLogger("api.short_link")

# 公开短链重定向路由（无前缀，直接挂载到 /s/{short_key}）
public_router = APIRouter(tags=["短链重定向"])

# 内部短链管理路由（带 /api/v1/short-link 前缀）
router = APIRouter(prefix="/api/v1/short-link", tags=["短链管理"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


async def get_short_link_service(
    db: AsyncSession = Depends(get_db),
) -> ShortLinkService:
    return ShortLinkService(db)


# ══════════════════════════════════════════════════════
# 公开接口：短链重定向（无认证）
# ══════════════════════════════════════════════════════


@public_router.get("/s/{short_key}")
async def redirect_short_link(
    short_key: str,
    request: Request,
    svc: ShortLinkService = Depends(get_short_link_service),
):
    """短链重定向 + 点击记录

    流程：
    1. 查询短链映射
    2. 记录点击日志（UA, IP, Referer）
    3. 302 重定向到原始 CPS 推广链接
    """
    try:
        # 获取原始链接
        source_url = await svc.get_source_url_by_key(short_key)
        if source_url is None:
            return error_response(code=404, msg="短链不存在或已过期", request_id=get_request_id(request))

        # 记录点击
        ua = request.headers.get("User-Agent", "")
        ip = request.client.host if request.client else ""
        referer = request.headers.get("Referer", "")
        await svc.record_click(
            short_key=short_key,
            user_agent=ua,
            ip_address=ip,
            referer_url=referer,
        )

        # 302 重定向
        return RedirectResponse(url=source_url, status_code=302)
    except Exception as exc:
        return handle_service_exception(exc, get_request_id(request))


# ══════════════════════════════════════════════════════
# 管理接口：创建短链（需认证）
# ══════════════════════════════════════════════════════


@router.post("/create")
async def create_short_link(
    body: ShortLinkCreateRequest,
    request: Request,
    svc: ShortLinkService = Depends(get_short_link_service),
):
    """创建短链（内部调用）

    一般由商品推广流程调用，记录用户点击商品时的归属信息。
    """
    request_id = get_request_id(request)
    try:
        link = await svc.create_short_link(
            user_id=body.user_id,
            goods_id=body.goods_id,
            goods_title=body.goods_title,
            channel_code=body.channel_code,
            source_url=body.source_url,
        )
        # 构造短链完整 URL（从请求中提取 host）
        host = request.base_url
        short_url = f"{host}s/{link.short_key}"

        resp = ShortLinkResponse(
            short_key=link.short_key,
            short_url=short_url,
            user_id=link.user_id,
            goods_id=link.goods_id,
            goods_title=link.goods_title or "",
            channel_code=link.channel_code or "",
            expire_at=link.expire_at.strftime("%Y-%m-%d %H:%M:%S") if link.expire_at else "",
            click_count=link.click_count or 0,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
# @ai-generated
"""
CPS 商品对外公开接口层
路由前缀：/api/public/goods
职责：身份识别(限流key) → 双桶限流 → 参数校验 → 调用 CpsGoodsService → 统一响应封装

接口清单：
1. GET  /api/public/goods/search        商品搜索（搜索桶限流）
2. POST /api/public/goods/convert-link  链接转链（转链桶限流）

限流策略：
- 搜索桶：RateLimitType.SEARCH，20次/分钟/用户（按 user_id 或 IP 隔离）
- 转链桶：RateLimitType.TRANSFORM，100次/分钟/用户
- 超限抛 BizException(429)，接口层捕获返回 HTTP 429
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import ValidationError

from src.api.v1.response_util import (
    error_response,
    get_request_id,
    success_response,
)
from src.common.rate_limit_util import RateLimitUtil
from src.config.constants import RateLimitType
from src.schemas.cps_goods import (
    BizException,
    ConvertLinkRequest,
    ConvertLinkResponse,
    GoodsSearchRequest,
    GoodsSearchResponse,
)
from src.services.cps_goods_service import CpsGoodsService

logger = logging.getLogger("api.public.cps_goods")

router = APIRouter(prefix="/api/public/goods", tags=["C端商品搜索/转链"])


# ── 依赖注入 ──────────────────────────────────────────


def get_cps_goods_service() -> CpsGoodsService:
    """构造 CpsGoodsService 实例"""
    return CpsGoodsService()


def _get_limit_key(
    x_user_id: Optional[str],
    request: Request,
) -> str:
    """获取限流 key

    优先 X-User-Id 头；缺失时回退客户端 IP
    """
    if x_user_id:
        return f"uid:{x_user_id}"
    # 回退 IP（匿名访问）
    client = request.client
    if client and client.host:
        return f"ip:{client.host}"
    return "ip:unknown"


def _handle_biz_exception(exc: BizException, request_id: str):
    """统一业务异常 → HTTP 响应"""
    logger.warning(
        "[request_id=%s] 业务异常: code=%s msg=%s",
        request_id,
        exc.code,
        exc.msg,
    )
    # HTTP 状态码对齐业务 code（4xx → 200 返回业务码，5xx → 500）
    http_status = 200 if exc.code < 500 else 500
    return error_response(
        code=exc.code,
        msg=exc.msg,
        data=exc.data,
        request_id=request_id,
        http_status=http_status,
    )


# ════════════════════════════════════════════════════
# 接口实现
# ════════════════════════════════════════════════════


@router.get("/search")
async def search_goods(
    request: Request,
    keyword: str = Query(..., min_length=1, max_length=64, description="搜索关键词"),
    page: int = Query(1, ge=1, le=100, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    channel_code: str = Query("myq", description="渠道: myq/orderx/dta"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    svc: CpsGoodsService = Depends(get_cps_goods_service),
):
    """1. 商品搜索接口（搜索桶限流 + B02 双层缓存）

    - 按 user_id/IP 独立限流（20次/分钟）
    - 走 B02 双层缓存，未命中走 B01 适配器回源
    - 渠道异常自动降级为业务异常
    """
    request_id = get_request_id(request)
    limit_key = _get_limit_key(x_user_id, request)

    logger.info(
        "[request_id=%s] 商品搜索: keyword=%s page=%s size=%s channel=%s limit_key=%s",
        request_id,
        keyword,
        page,
        size,
        channel_code,
        limit_key,
    )

    try:
        # 1. 搜索桶限流检查
        allowed, info = await RateLimitUtil.check_by_type(
            RateLimitType.SEARCH, limit_key
        )
        if not allowed:
            logger.warning(
                "[request_id=%s] 搜索限流触发: limit_key=%s info=%s",
                request_id,
                limit_key,
                info,
            )
            raise BizException(code=429, msg="搜索接口访问过于频繁，请稍后重试")

        # 2. 构造请求参数（Pydantic 自动校验）
        search_request = GoodsSearchRequest(
            keyword=keyword,
            page=page,
            size=size,
            channel_code=channel_code,
        )

        # 3. 调用服务层（走 B02 缓存 → B01 适配器）
        result: GoodsSearchResponse = await svc.search_goods(search_request)

        return success_response(data=result.model_dump(), request_id=request_id)

    except BizException as exc:
        return _handle_biz_exception(exc, request_id)
    except ValidationError as exc:
        # Pydantic 校验异常（参数错误）
        logger.warning("[request_id=%s] 参数校验失败: %s", request_id, exc)
        return error_response(
            code=422, msg=f"参数校验失败: {exc}", request_id=request_id
        )
    except ValueError as exc:
        # 业务参数错误
        logger.warning("[request_id=%s] 参数错误: %s", request_id, exc)
        return error_response(code=400, msg=str(exc), request_id=request_id)
    except Exception as exc:
        logger.error("[request_id=%s] 搜索接口异常: %s", request_id, exc, exc_info=True)
        return error_response(code=500, msg="商品搜索服务异常", request_id=request_id)


@router.post("/convert-link")
async def convert_link(
    body: ConvertLinkRequest,
    request: Request,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    svc: CpsGoodsService = Depends(get_cps_goods_service),
):
    """2. 链接转链接口（转链桶限流 + B01 适配器直调）

    - 按 user_id/IP 独立限流（100次/分钟）
    - 转链结果不缓存（因 user_channel_id 差异）
    - 直调 B01 适配器 convert_link
    """
    request_id = get_request_id(request)
    limit_key = _get_limit_key(x_user_id, request)

    logger.info(
        "[request_id=%s] 链接转链: url=%s channel=%s limit_key=%s",
        request_id,
        body.original_url,
        body.channel_code,
        limit_key,
    )

    try:
        # 1. 转链桶限流检查
        allowed, info = await RateLimitUtil.check_by_type(
            RateLimitType.TRANSFORM, limit_key
        )
        if not allowed:
            logger.warning(
                "[request_id=%s] 转链限流触发: limit_key=%s info=%s",
                request_id,
                limit_key,
                info,
            )
            raise BizException(code=429, msg="转链接口访问过于频繁，请稍后重试")

        # 2. 调用服务层（走 B01 适配器）
        result: ConvertLinkResponse = await svc.convert_link(body)

        return success_response(data=result.model_dump(), request_id=request_id)

    except BizException as exc:
        return _handle_biz_exception(exc, request_id)
    except Exception as exc:
        logger.error("[request_id=%s] 转链接口异常: %s", request_id, exc, exc_info=True)
        return error_response(code=500, msg="链接转链服务异常", request_id=request_id)

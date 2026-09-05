# @ai-generated
"""
后台限流中间件（B14 新建，不修改 B01-B13 基线）
拦截 /api/v1/admin/* 路由，基于 Redis 滑动窗口限流（gaking:prod:rate: 前缀）
阈值动态读取 B14ConfigUtil（admin_rate_limit_per_minute），降级 EnvConfig.RATE_LIMIT_NORMAL
超限返回 429 标准 ApiResponse 格式
跳过 /healthz /readyz /metrics /api/v1/admin/auth/login

复用既有 RateLimitUtil.check_sliding_window，不重复造轮子
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.v1.response_util import get_request_id
from src.common.b14_config_util import B14ConfigUtil
from src.common.rate_limit_util import RateLimitUtil
from src.config.b14_constants import (
    ADMIN_PATH_PREFIX,
    RATE_LIMIT_ADMIN_KEY_PREFIX,
    RATE_LIMIT_SKIP_PATHS,
)
from src.config.env_config import EnvConfig
from src.schemas.cps import ApiResponse

logger = logging.getLogger("common.b14_rate_limit")


class B14RateLimitMiddleware(BaseHTTPMiddleware):
    """后台 admin 接口限流中间件

    - 仅拦截 /api/v1/admin/ 前缀路径
    - 跳过健康检查与登录接口
    - 单 IP 滑动窗口 60s，阈值动态读取配置
    - 超限返回 429 + ApiResponse 标准格式
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 仅拦截 admin 路径
        if not path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)

        # 跳过白名单路径
        if path in RATE_LIMIT_SKIP_PATHS:
            return await call_next(request)

        # 提取客户端 IP
        ip = self._get_client_ip(request)

        # 动态读取限流阈值（降级 EnvConfig）
        try:
            limit = await B14ConfigUtil.get_int(
                "admin_rate_limit_per_minute",
                default=EnvConfig.RATE_LIMIT_NORMAL,
            )
        except Exception as e:
            logger.warning("[rate_limit] 读取限流配置失败，降级默认值: %s", e)
            limit = EnvConfig.RATE_LIMIT_NORMAL

        if limit <= 0:
            # 限流关闭，直接放行
            return await call_next(request)

        # 滑动窗口限流检查
        rate_key = f"{RATE_LIMIT_ADMIN_KEY_PREFIX}{ip}"
        try:
            allowed, current_count = await RateLimitUtil.check_sliding_window(
                key=rate_key, limit=limit, window_seconds=60
            )
        except Exception as e:
            # Redis 异常时放行（限流降级，不阻塞业务）
            logger.warning("[rate_limit] Redis 限流检查异常，放行: %s", e)
            return await call_next(request)

        if not allowed:
            # 超限返回 429
            request_id = get_request_id(request)
            body = ApiResponse(
                code=429,
                msg="请求过于频繁，请稍后重试",
                data={"retry_after_seconds": 60, "current_count": current_count},
                request_id=request_id,
            )
            logger.info(
                "[rate_limit] IP=%s path=%s 触发限流 count=%s limit=%s",
                ip,
                path,
                current_count,
                limit,
            )
            return JSONResponse(
                status_code=429, content=body.model_dump()
            )

        # 设置响应头（剩余次数）
        response = await call_next(request)
        try:
            remaining = max(0, limit - current_count)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        except Exception:
            pass
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """提取客户端 IP（X-Forwarded-For 首段优先，降级 request.client.host）"""
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            if ip:
                return ip
        if request.client:
            return request.client.host or "unknown"
        return "unknown"

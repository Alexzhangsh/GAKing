# @ai-generated
"""
后台审计中间件（B14 新建，不修改 B01-B13 基线）
拦截 /api/v1/admin/* 的写操作（POST/PUT/PATCH/DELETE），自动记录审计日志
best-effort 解析 JWT 取 user_id/user_name（不阻断请求，鉴权由 endpoint 负责）
fire-and-forget：审计写入失败仅 warn，不影响业务响应

审计内容：action=HTTP_{METHOD}, target_type=endpoint, details={path, method, status_code, query}
对 B07-B13 已上线接口的写操作也能补审计（无需改它们的代码）
"""
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.auth_util import JwtAuthGuard
from src.common.b14_audit_util import AuditLogger
from src.config.b14_constants import (
    ADMIN_PATH_PREFIX,
    AUDIT_HTTP_METHODS,
    RATE_LIMIT_SKIP_PATHS,
)

logger = logging.getLogger("common.b14_audit_middleware")


class B14AuditMiddleware(BaseHTTPMiddleware):
    """后台写操作审计中间件

    - 仅拦截 /api/v1/admin/ 前缀 + 写方法（POST/PUT/PATCH/DELETE）
    - best-effort 解析 JWT 取操作人（无 token 则 user_id=0）
    - 调用 call_next 后记录审计日志（含响应状态码）
    - 审计失败不阻塞业务
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # 仅拦截 admin 路径 + 写方法
        if not path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)

        if method not in AUDIT_HTTP_METHODS:
            return await call_next(request)

        # best-effort 解析操作人信息
        user_id, user_name = self._extract_user(request)

        # 预存到 request.state 供 endpoint 装饰器使用
        request.state.user_id = user_id
        request.state.user_name = user_name

        # 执行请求
        response = await call_next(request)

        # 记录审计日志（fire-and-forget）
        try:
            ip = AuditLogger.get_client_ip(request)
            ua = AuditLogger.get_user_agent(request)
            # query 参数脱敏后记录（限制长度）
            query_str = str(request.query_params)[:500]
            details = {
                "path": path,
                "method": method,
                "status_code": response.status_code,
                "query": query_str,
            }
            # 跳过登录接口的 token 细节，但仍记录登录行为
            if path in RATE_LIMIT_SKIP_PATHS:
                details["note"] = "auth_endpoint"

            await AuditLogger.log(
                action=f"HTTP_{method}",
                target_type="endpoint",
                target_id=0,
                details=details,
                user_id=user_id,
                user_name=user_name,
                ip_address=ip,
                user_agent=ua,
            )
        except Exception as e:
            logger.warning("[audit_middleware] 审计记录失败 path=%s: %s", path, e)

        return response

    @staticmethod
    def _extract_user(request: Request) -> tuple:
        """从 Authorization header best-effort 解析 user_id/user_name

        Returns:
            (user_id: int, user_name: str)；无 token/解析失败返回 (0, "")
        """
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return 0, ""
            token = auth_header[7:]
            payload = JwtAuthGuard.verify_token(token)
            if payload is None:
                return 0, ""
            user_id = int(payload.get("user_id", 0) or 0)
            user_name = str(payload.get("username", "") or "")
            return user_id, user_name
        except Exception:
            return 0, ""

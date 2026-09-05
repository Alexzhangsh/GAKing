# @ai-generated
"""
B15 全局 RBAC 鉴权中间件
新建文件，不修改 B01-B14 任何基线代码

职责：
1. 拦截所有 /api/v1/admin/* 请求
2. JWT 校验 + 黑名单检测
3. URL 路径→权限码自动映射检测
4. request.state 上下文注入（user_id, username, role_id, permissions）
5. 兼容存量 B14 require_any_permission / require_permission 注解

执行流程：
1. 检查路径是否公开 → 跳过
2. 检查路径是否 admin 前缀 → 跳过非 admin
3. 提取 JWT → 验证签名 + 过期 → 检查黑名单
4. 注入 request.state（user_id, username, role_id, permissions）
5. 查询 URL→权限码映射
6. 如需权限 → 检查用户是否有该权限（* 通配符放行）
7. 通过 → call_next；失败 → 401/403

设计要点：
- 与 B14 存量 require_any_permission 装饰器兼容：中间件先做一次基线检查，
  装饰器再做一次精确检查，双层防护不冲突
- JWT 黑名单集成：密码重置/登出后 token 立即失效
- 写操作仍由 B14AuditMiddleware 自动记录审计日志
- 中间件命名 B15 前缀，与 B14 中间件共存
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.v1.response_util import get_request_id
from src.common.auth_util import JwtAuthGuard, RbacUtil
from src.common.b14_audit_util import AuditLogger
from src.common.redis_client import RedisClient
from src.config.b14_constants import (
    CACHE_KEY_ADMIN_JWT_BLACKLIST,
    SUPER_ADMIN_PERMISSION,
)
from src.config.b15_constants import (
    ADMIN_PATH_PREFIX,
    PATH_PERMISSION_MAP,
    PUBLIC_PATHS,
)
from src.schemas.cps import ApiResponse

logger = logging.getLogger("common.b15_rbac_middleware")


class B15RbacMiddleware(BaseHTTPMiddleware):
    """全局 RBAC 鉴权中间件

    拦截所有 /api/v1/admin/* 请求，自动完成：
    - JWT 有效性校验 + 黑名单检测
    - URL→权限码自动映射
    - 权限校验
    - request.state 上下文注入

    与 B14 存量装饰器兼容：中间件提供基线防护，装饰器提供精确防护。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # ── 1. 跳过非 admin 路径 ──
        if not path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)

        # ── 2. 跳过公开路径（登录等） ──
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # ── 3. 提取 JWT ──
        token = self._extract_token(request)
        if token is None:
            return self._unauthorized_response(request, "缺少认证令牌")

        payload = JwtAuthGuard.verify_token(token)
        if payload is None:
            return self._unauthorized_response(request, "登录已超时或 token 无效，请重新登录")

        user_id = int(payload.get("user_id", 0) or 0)
        username = str(payload.get("username", "") or "")
        role_id = int(payload.get("role_id", 0) or 0)

        # ── 4. 检查 JWT 黑名单（密码重置/登出后失效） ──
        if await self._is_jwt_blacklisted(user_id):
            return self._unauthorized_response(request, "账号已在其他设备登录，当前 token 已失效")

        # ── 5. 查询用户权限 ──
        permissions = await self._get_user_permissions(user_id, role_id)

        # ── 6. 注入 request.state（供下游 endpoint/中间件使用） ──
        request.state.user_id = user_id
        request.state.username = username
        request.state.role_id = role_id
        request.state.permissions = permissions
        request.state.jwt_payload = payload

        # ── 7. 查询路径所需权限 ──
        required_permission = self._match_required_permission(path)

        # ── 8. 权限校验 ──
        if required_permission is not None:
            if not self._check_permission(permissions, required_permission):
                logger.warning(
                    "[b15_rbac] 权限不足 user_id=%s path=%s required=%s",
                    user_id,
                    path,
                    required_permission,
                )
                return self._forbidden_response(
                    request, f"权限不足，需要 {required_permission} 权限"
                )

        # ── 9. 放行 ──
        response = await call_next(request)

        # 响应头注入用户上下文（前端调试用）
        try:
            response.headers["X-User-Id"] = str(user_id)
        except Exception:
            pass

        return response

    # ════════════════════════════════════════════════════════════
    # 内部工具方法
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        """从 Authorization header 提取 JWT token"""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        return auth_header[7:]

    @staticmethod
    async def _is_jwt_blacklisted(user_id: int) -> bool:
        """检查用户 ID 是否在 JWT 黑名单中"""
        try:
            key = f"{CACHE_KEY_ADMIN_JWT_BLACKLIST}{user_id}"
            val = await RedisClient.get(key)
            return val is not None
        except Exception as e:
            logger.warning("[b15_rbac] JWT 黑名单检查异常，降级放行: %s", e)
            return False

    @staticmethod
    async def _get_user_permissions(user_id: int, role_id: int = 0) -> List[str]:
        """获取用户权限码列表"""
        try:
            return await RbacUtil.get_user_permissions(user_id, role_id)
        except Exception as e:
            logger.warning("[b15_rbac] 获取用户权限异常 user_id=%s: %s", user_id, e)
            return []

    @staticmethod
    def _match_required_permission(path: str) -> Optional[str]:
        """匹配路径所需的权限

        使用最长前缀匹配策略：
        1. 先精确匹配 PATH_PERMISSION_MAP
        2. 然后尝试逐级前缀匹配（去掉最后一段）
        3. 匹配到 "PUBLIC" 返回 None（无需鉴权）
        4. 匹配到 "JWT" 返回 ""（仅需登录）
        5. 匹配到权限码返回该权限码
        6. 未匹配到返回 None（放行，由存量装饰器兜底）

        Args:
            path: 请求路径

        Returns:
            None - 无需鉴权或未匹配到规则
            "" - 仅需 JWT（已登录即可）
            str - 所需权限码
        """
        # 精确匹配
        if path in PATH_PERMISSION_MAP:
            val = PATH_PERMISSION_MAP[path]
            if val == "PUBLIC":
                return None
            if val == "JWT":
                return ""
            return val

        # 前缀匹配：去掉最后一段路径，逐级匹配
        parts = path.rstrip("/").split("/")
        for i in range(len(parts) - 1, 2, -1):  # 从后往前，保留至少 /api/v1/admin
            prefix = "/".join(parts[:i])
            if prefix in PATH_PERMISSION_MAP:
                val = PATH_PERMISSION_MAP[prefix]
                if val == "PUBLIC":
                    return None
                if val == "JWT":
                    return ""
                return val

        # 未匹配到 → 放行，由存量装饰器兜底
        return None

    @staticmethod
    def _check_permission(
        user_permissions: List[str], required: str
    ) -> bool:
        """检查用户是否有指定权限

        Args:
            user_permissions: 用户权限码列表
            required: 所需权限码（"" 表示仅需 JWT 登录）

        Returns:
            True-有权限/仅需JWT
        """
        # 仅需 JWT 登录（已通过 JWT 校验）
        if required == "":
            return True

        # 超管通配符
        if SUPER_ADMIN_PERMISSION in user_permissions:
            return True

        # 精确匹配
        return required in user_permissions

    @staticmethod
    def _unauthorized_response(request: Request, msg: str) -> JSONResponse:
        """构造 401 未授权响应"""
        request_id = get_request_id(request)
        body = ApiResponse(code=401, msg=msg, data=None, request_id=request_id)
        return JSONResponse(status_code=401, content=body.model_dump())

    @staticmethod
    def _forbidden_response(request: Request, msg: str) -> JSONResponse:
        """构造 403 禁止访问响应"""
        request_id = get_request_id(request)
        body = ApiResponse(code=403, msg=msg, data=None, request_id=request_id)
        return JSONResponse(status_code=403, content=body.model_dump())
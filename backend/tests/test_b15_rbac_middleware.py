# @ai-generated
"""
B15 全局 RBAC 鉴权中间件单元测试
覆盖：
1. 中间件核心逻辑：JWT 校验、黑名单检测、URL→权限码映射、权限校验、request.state 注入
2. 公开路径跳过（login, healthz, readyz, metrics）
3. 非 admin 路径跳过（正常 API 请求不受影响）
4. 缺少 JWT → 401
5. 无效 JWT → 401
6. JWT 黑名单命中 → 401
7. 权限不足 → 403
8. 权限匹配 → 放行
9. 超管通配符 * → 放行
10. 仅需 JWT 路径（logout, me, password）→ 放行
11. 未匹配路径 → 放行（由存量装饰器兜底）
12. 最长前缀匹配逻辑
13. Redis 异常降级（黑名单检查失败放行）
14. request.state 注入验证

覆盖率目标：≥90%
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

sys.path.insert(0, ".")

from src.common.auth_util import JwtAuthGuard, RbacUtil
from src.common.b15_rbac_middleware import B15RbacMiddleware


# ══════════════════════════════════════════════════════
# 全局 fixture
# ══════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def init_jwt():
    """初始化 JwtAuthGuard 使用测试密钥"""
    JwtAuthGuard._secret = "test_jwt_secret_for_b15_unit_tests_at_least_32_chars!!"
    JwtAuthGuard._expires_in = 3600
    yield


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_request(path: str, token: str = None, method: str = "GET") -> MagicMock:
    """构造 FastAPI Request mock"""
    req = MagicMock(spec=Request)
    req.url.path = path
    req.method = method
    req.headers = {}
    if token:
        req.headers = {"Authorization": f"Bearer {token}"}
    req.state = MagicMock()
    req.query_params = {}
    return req


def _make_valid_token(user_id: int = 1, username: str = "admin", role_id: int = 1) -> str:
    """生成有效 JWT token"""
    return JwtAuthGuard.create_token(
        user_id=user_id,
        username=username,
        role_id=role_id,
    )


def _make_expired_token() -> str:
    """生成过期 JWT token（直接构造带过期 payload）"""
    import jwt
    from datetime import datetime, timedelta

    payload = {
        "user_id": 1,
        "username": "admin",
        "role_id": 1,
        "exp": datetime.utcnow() - timedelta(hours=1),
        "iat": datetime.utcnow() - timedelta(hours=2),
    }
    return jwt.encode(payload, JwtAuthGuard._secret, algorithm="HS256")


# ══════════════════════════════════════════════════════
# 1. 公开路径跳过
# ══════════════════════════════════════════════════════


class TestB15RbacPublicPaths:
    """公开路径应完全跳过 RBAC 中间件"""

    @pytest.mark.asyncio
    async def test_login_path_skipped(self):
        """POST /api/v1/admin/auth/login → 公开，跳过"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/api/v1/admin/auth/login", method="POST")
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)

        assert response is not None
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_healthz_skipped(self):
        """GET /healthz → 公开，跳过"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/healthz")
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)

        assert response is not None
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_metrics_skipped(self):
        """GET /metrics → 公开，跳过"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/metrics")
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)

        assert response is not None
        call_next.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 2. 非 admin 路径跳过
# ══════════════════════════════════════════════════════


class TestB15RbacNonAdminPaths:
    """非 /api/v1/admin/ 路径应跳过"""

    @pytest.mark.asyncio
    async def test_api_v1_path_skipped(self):
        """GET /api/v1/cps/order → 非 admin，跳过"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/api/v1/cps/order")
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)

        assert response is not None
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_static_path_skipped(self):
        """GET /static/file.js → 非 admin，跳过"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/static/file.js")
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 3. JWT 校验
# ══════════════════════════════════════════════════════


class TestB15RbacJwtValidation:
    """JWT 校验逻辑"""

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self):
        """缺少 Authorization header → 401"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/api/v1/admin/auth/me", token=None)
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        import json

        body = json.loads(response.body)
        assert body["code"] == 401
        assert "缺少认证令牌" in body["msg"]
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """无效 JWT → 401"""
        middleware = B15RbacMiddleware(MagicMock())
        request = _make_request("/api/v1/admin/auth/me", token="invalid_token_here")
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        import json

        body = json.loads(response.body)
        assert body["code"] == 401
        assert "token 无效" in body["msg"]
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self):
        """过期 JWT → 401"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_expired_token()
        request = _make_request("/api/v1/admin/auth/me", token=token)
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        call_next.assert_not_awaited()


# ══════════════════════════════════════════════════════
# 4. JWT 黑名单检测
# ══════════════════════════════════════════════════════


class TestB15RbacJwtBlacklist:
    """JWT 黑名单检测"""

    @pytest.mark.asyncio
    async def test_blacklisted_user_returns_401(self):
        """黑名单中的 user_id → 401"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/auth/me", token=token)
        call_next = AsyncMock()

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value="1"),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        import json

        body = json.loads(response.body)
        assert "token 已失效" in body["msg"]
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blacklist_redis_exception_allows(self):
        """Redis 异常时黑名单检查降级放行"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/auth/me", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(side_effect=Exception("Redis down")),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["*"]),
        ):
            response = await middleware.dispatch(request, call_next)

        # Redis 异常降级，应放行
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_blacklisted_allows(self):
        """不在黑名单中 → 放行（非公开路径且有权限）"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/rbac/roles", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["rbac:manage"]),
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 5. 权限校验
# ══════════════════════════════════════════════════════


class TestB15RbacPermissionCheck:
    """权限校验逻辑"""

    @pytest.mark.asyncio
    async def test_no_permission_returns_403(self):
        """无所需权限 → 403"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=2, username="operator")
        request = _make_request("/api/v1/admin/rbac/roles", token=token)
        call_next = AsyncMock()

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["audit:view"]),  # 没有 rbac:manage
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 403
        import json

        body = json.loads(response.body)
        assert "权限不足" in body["msg"]
        call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_has_permission_allows(self):
        """有所需权限 → 放行"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/config", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["config:manage"]),
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_super_admin_wildcard_allows(self):
        """超管通配符 * → 放行"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/config/batch", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["*"]),
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_jwt_only_path_allows(self):
        """仅需 JWT 路径（logout）→ 放行（无需权限码）"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/auth/logout", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=[]),
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmatched_path_allows(self):
        """未匹配路径 → 放行（由存量装饰器兜底）"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        # 假设 /api/v1/admin/some-unknown-path 不在映射表中
        request = _make_request("/api/v1/admin/some-unknown-path", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=[]),
        ):
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 6. request.state 注入
# ══════════════════════════════════════════════════════


class TestB15RbacStateInjection:
    """request.state 上下文注入"""

    @pytest.mark.asyncio
    async def test_state_injected(self):
        """验证 request.state 正确注入 user_id, username, role_id, permissions, jwt_payload"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=42, username="testuser", role_id=2)
        request = _make_request("/api/v1/admin/audit/logs", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["audit:view"]),
        ):
            response = await middleware.dispatch(request, call_next)

        assert request.state.user_id == 42
        assert request.state.username == "testuser"
        assert request.state.role_id == 2
        assert "audit:view" in request.state.permissions
        assert request.state.jwt_payload is not None
        assert request.state.jwt_payload["user_id"] == 42
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_response_header_injected(self):
        """验证响应头 X-User-Id 注入"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=99)
        request = _make_request("/api/v1/admin/audit/stats", token=token)
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["audit:view"]),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.headers.get("X-User-Id") == "99"


# ══════════════════════════════════════════════════════
# 7. 最长前缀匹配
# ══════════════════════════════════════════════════════


class TestB15RbacPathMatching:
    """URL→权限码最长前缀匹配逻辑"""

    def test_exact_match_returns_permission(self):
        """精确路径匹配 → 返回对应权限码"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/rbac/roles"
        )
        assert perm == "rbac:manage"

    def test_prefix_match_with_id(self):
        """带 ID 的动态路径 → 前缀匹配"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/rbac/roles/123"
        )
        assert perm == "rbac:manage"

    def test_nested_prefix_match(self):
        """嵌套路径 → 前缀匹配"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/rbac/roles/123/permissions"
        )
        assert perm == "rbac:manage"

    def test_public_path_returns_none(self):
        """公开路径 → 返回 None"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/auth/login"
        )
        assert perm is None

    def test_jwt_only_path_returns_empty(self):
        """仅需 JWT 路径 → 返回空字符串"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/auth/me"
        )
        assert perm == ""

    def test_unknown_path_returns_none(self):
        """未匹配路径 → 返回 None"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/unknown/module"
        )
        assert perm is None

    def test_menu_tree_path(self):
        """菜单树路径 → menu:manage"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/rbac/menus/tree"
        )
        assert perm == "menu:manage"

    def test_menu_with_id(self):
        """菜单详情路径 → menu:manage"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/rbac/menus/5"
        )
        assert perm == "menu:manage"

    def test_config_with_key(self):
        """配置详情路径 → config:manage"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/config/settlement_delay_days"
        )
        assert perm == "config:manage"

    def test_audit_log_with_id(self):
        """审计日志详情路径 → audit:view"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/audit/logs/123"
        )
        assert perm == "audit:view"

    def test_dashboard_export_path(self):
        """大盘导出路径 → dashboard:export"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/dashboard/export/commission-stats"
        )
        assert perm == "dashboard:export"

    def test_b13_orders_with_id(self):
        """B13 订单详情路径 → order:manage"""
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/b13/orders/10086"
        )
        assert perm == "order:manage"


# ══════════════════════════════════════════════════════
# 8. 工具方法测试
# ══════════════════════════════════════════════════════


class TestB15RbacUtils:
    """内部工具方法测试"""

    def test_extract_token_with_bearer(self):
        """提取 Bearer token"""
        request = _make_request("/test", token="mytoken")
        token = B15RbacMiddleware._extract_token(request)
        assert token == "mytoken"

    def test_extract_token_without_bearer(self):
        """无 Bearer 前缀 → 返回 None"""
        request = MagicMock()
        request.headers = {"Authorization": "Basic xyz"}
        token = B15RbacMiddleware._extract_token(request)
        assert token is None

    def test_extract_token_no_header(self):
        """无 Authorization header → 返回 None"""
        request = MagicMock()
        request.headers = {}
        token = B15RbacMiddleware._extract_token(request)
        assert token is None

    def test_check_permission_wildcard(self):
        """超管通配符 * → True"""
        assert B15RbacMiddleware._check_permission(["*"], "config:manage")

    def test_check_permission_exact_match(self):
        """精确匹配 → True"""
        assert B15RbacMiddleware._check_permission(
            ["config:manage"], "config:manage"
        )

    def test_check_permission_no_match(self):
        """不匹配 → False"""
        assert not B15RbacMiddleware._check_permission(
            ["audit:view"], "config:manage"
        )

    def test_check_permission_empty_user(self):
        """空用户权限 → False"""
        assert not B15RbacMiddleware._check_permission([], "config:manage")

    def test_check_permission_jwt_only(self):
        """仅需 JWT → True"""
        assert B15RbacMiddleware._check_permission([], "")

    @pytest.mark.asyncio
    async def test_get_user_permissions_redis_error_fallback(self):
        """获取用户权限时 Redis 异常→返回空列表（不阻塞）"""
        with patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(side_effect=Exception("DB error")),
        ):
            perms = await B15RbacMiddleware._get_user_permissions(1)
            assert perms == []

    @pytest.mark.asyncio
    async def test_is_jwt_blacklisted_redis_error_fallback(self):
        """黑名单检查 Redis 异常→降级返回 False（不阻塞）"""
        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(side_effect=Exception("Redis error")),
        ):
            result = await B15RbacMiddleware._is_jwt_blacklisted(1)
            assert result is False


# ══════════════════════════════════════════════════════
# 9. 边界场景测试
# ══════════════════════════════════════════════════════


class TestB15RbacEdgeCases:
    """边界场景测试"""

    def test_prefix_match_public_in_loop(self):
        """前缀匹配中遇到 PUBLIC 值 → 返回 None（覆盖循环内 line 200）"""
        # 构造一个路径，其前缀在 PATH_PERMISSION_MAP 中值为 "PUBLIC"
        # 使用 /api/v1/admin/auth/login/extra 匹配 /api/v1/admin/auth/login
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/auth/login/extra"
        )
        assert perm is None

    def test_prefix_match_jwt_in_loop(self):
        """前缀匹配中遇到 JWT 值 → 返回 ''（覆盖循环内 line 202）"""
        # 构造一个路径，其前缀在 PATH_PERMISSION_MAP 中值为 "JWT"
        # 使用 /api/v1/admin/auth/me/extra 匹配 /api/v1/admin/auth/me
        perm = B15RbacMiddleware._match_required_permission(
            "/api/v1/admin/auth/me/extra"
        )
        assert perm == ""

    @pytest.mark.asyncio
    async def test_response_header_exception_caught(self):
        """响应头注入异常时被捕获（覆盖 line 127-128）"""
        middleware = B15RbacMiddleware(MagicMock())
        token = _make_valid_token(user_id=1)
        request = _make_request("/api/v1/admin/auth/me", token=token)

        # 构造一个 Mock 响应，设置 headers 时抛出异常
        bad_response = MagicMock()
        bad_response.headers = MagicMock()
        # 使用 __setitem__ 模拟 headers["X-User-Id"] 赋值异常
        type(bad_response.headers).__setitem__ = MagicMock(
            side_effect=Exception("header error")
        )
        call_next = AsyncMock(return_value=bad_response)

        with patch(
            "src.common.b15_rbac_middleware.RedisClient.get",
            AsyncMock(return_value=None),
        ), patch(
            "src.common.b15_rbac_middleware.RbacUtil.get_user_permissions",
            AsyncMock(return_value=["*"]),
        ):
            # 不应抛出异常
            response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once()
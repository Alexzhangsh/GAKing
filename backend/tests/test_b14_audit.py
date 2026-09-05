# @ai-generated
"""
B14 审计日志服务 + 审计中间件单元测试
覆盖：
1. B14AuditService：list_audit_logs（多条件筛选）、get_audit_log（找到/未找到）、get_audit_stats（聚合统计）
2. B14AuditMiddleware：写操作审计/跳过GET/跳过非admin路径/best-effort解析JWT
3. AuditLogger：log（写入/异常吞掉）、sanitize_details（脱敏）、get_client_ip、get_user_agent
4. B14ExceptionHandlers：HTTPException/ValueError/RequestValidationError/PyJWTError 统一封装

覆盖率目标：单文件 ≥90%
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from fastapi import FastAPI, HTTPException

from src.services.b14_audit_service import B14AuditService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_audit_log(log_id=1, action="HTTP_POST", user_id=1, target_type="endpoint"):
    log = MagicMock()
    log.id = log_id
    log.user_id = user_id
    log.user_name = "admin"
    log.action = action
    log.target_type = target_type
    log.target_id = 0
    log.details = '{"path": "/api/v1/admin/config/"}'
    log.ip_address = "127.0.0.1"
    log.user_agent = "test-agent"
    log.create_time = datetime.now()
    return log


def _make_session_cm():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


# ══════════════════════════════════════════════════════
# 1. 审计日志查询测试
# ══════════════════════════════════════════════════════


class TestB14AuditQuery:
    """审计日志查询测试"""

    @pytest.mark.asyncio
    async def test_list_audit_logs_no_filter(self):
        """无筛选条件查询"""
        log = _make_audit_log()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_with_filters.return_value = ([log], 1)

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_audit_service.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B14AuditService.list_audit_logs()
        assert total == 1
        assert len(items) == 1
        assert items[0].action == "HTTP_POST"

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filters(self):
        """多条件筛选查询"""
        log = _make_audit_log(user_id=1, action="ADMIN_LOGIN")
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_with_filters.return_value = ([log], 1)

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_audit_service.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B14AuditService.list_audit_logs(
                user_id=1,
                action="ADMIN_LOGIN",
                target_type="login",
                start_time=datetime(2026, 1, 1),
                end_time=datetime(2026, 12, 31),
                page=1,
                page_size=20,
            )
        assert total == 1
        mock_dao.list_with_filters.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_audit_log_found(self):
        """按 ID 查询审计日志 - 找到"""
        log = _make_audit_log(log_id=1)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = log

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_audit_service.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14AuditService.get_audit_log(1)
        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_audit_log_not_found(self):
        """按 ID 查询审计日志 - 未找到"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_audit_service.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14AuditService.get_audit_log(999)
        assert result is None


# ══════════════════════════════════════════════════════
# 2. 审计日志统计测试
# ══════════════════════════════════════════════════════


class TestB14AuditStats:
    """审计日志统计测试"""

    @pytest.mark.asyncio
    async def test_get_audit_stats_no_time_range(self):
        """无时间范围统计"""
        session = AsyncMock()
        # 模拟 4 个查询的返回值（count, action group, target group, user group）
        total_result = MagicMock()
        total_result.scalar.return_value = 100

        action_result = MagicMock()
        action_result.all.return_value = [("HTTP_POST", 50), ("ADMIN_LOGIN", 50)]

        target_result = MagicMock()
        target_result.all.return_value = [("endpoint", 80), ("login", 20)]

        user_result = MagicMock()
        user_result.all.return_value = [(1, 100)]

        session.execute = AsyncMock(
            side_effect=[total_result, action_result, target_result, user_result]
        )

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            stats = await B14AuditService.get_audit_stats()
        assert stats["total"] == 100
        assert stats["by_action"]["HTTP_POST"] == 50
        assert stats["by_target_type"]["endpoint"] == 80
        assert stats["by_user"]["1"] == 100

    @pytest.mark.asyncio
    async def test_get_audit_stats_with_time_range(self):
        """带时间范围统计"""
        session = AsyncMock()
        total_result = MagicMock()
        total_result.scalar.return_value = 10

        action_result = MagicMock()
        action_result.all.return_value = []

        target_result = MagicMock()
        target_result.all.return_value = []

        user_result = MagicMock()
        user_result.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[total_result, action_result, target_result, user_result]
        )

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.services.b14_audit_service.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm

            stats = await B14AuditService.get_audit_stats(
                start_time=datetime(2026, 1, 1),
                end_time=datetime(2026, 12, 31),
            )
        assert stats["total"] == 10


# ══════════════════════════════════════════════════════
# 3. 审计中间件测试
# ══════════════════════════════════════════════════════


class TestB14AuditMiddleware:
    """审计中间件测试"""

    @pytest.mark.asyncio
    async def test_audit_skip_non_admin_path(self):
        """非 admin 路径跳过审计"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        middleware = B14AuditMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/cps/orders"
        request.method = "POST"
        request.headers = {}
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_audit_skip_get_method(self):
        """GET 请求跳过审计（仅审计写操作）"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        middleware = B14AuditMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.method = "GET"
        request.headers = {}
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    @pytest.mark.asyncio
    async def test_audit_write_op_logged(self):
        """POST 写操作记录审计日志"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        middleware = B14AuditMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.query_params = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.common.b14_audit_middleware.AuditLogger") as mock_audit:
            mock_audit.get_client_ip = MagicMock(return_value="127.0.0.1")
            mock_audit.get_user_agent = MagicMock(return_value="test-agent")
            mock_audit.log = AsyncMock()

            await middleware.dispatch(request, call_next)

        mock_audit.log.assert_awaited()

    @pytest.mark.asyncio
    async def test_audit_with_jwt(self):
        """带 JWT 的写操作审计（解析操作人信息）"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        middleware = B14AuditMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/rbac/roles"
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "Bearer valid_token" if key == "Authorization" else default
        )
        request.query_params = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.common.b14_audit_middleware.AuditLogger") as mock_audit, \
             patch("src.common.b14_audit_middleware.JwtAuthGuard") as mock_jwt:
            mock_audit.get_client_ip = MagicMock(return_value="127.0.0.1")
            mock_audit.get_user_agent = MagicMock(return_value="test-agent")
            mock_audit.log = AsyncMock()
            mock_jwt.verify_token.return_value = {"user_id": 1, "username": "admin"}

            await middleware.dispatch(request, call_next)

        mock_audit.log.assert_awaited()

    @pytest.mark.asyncio
    async def test_audit_log_failure_not_blocking(self):
        """审计日志写入失败不阻塞业务"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        middleware = B14AuditMiddleware(app=MagicMock())
        request = MagicMock()
        request.url.path = "/api/v1/admin/config/"
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.query_params = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("src.common.b14_audit_middleware.AuditLogger") as mock_audit:
            mock_audit.get_client_ip = MagicMock(return_value="127.0.0.1")
            mock_audit.get_user_agent = MagicMock(return_value="test-agent")
            mock_audit.log = AsyncMock(side_effect=Exception("DB down"))

            # 不应抛异常
            response = await middleware.dispatch(request, call_next)
        call_next.assert_awaited()

    def test_extract_user_no_token(self):
        """无 Authorization header → user_id=0"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        user_id, user_name = B14AuditMiddleware._extract_user(request)
        assert user_id == 0
        assert user_name == ""

    def test_extract_user_invalid_token(self):
        """无效 token → user_id=0"""
        from src.common.b14_audit_middleware import B14AuditMiddleware

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "Bearer invalid_token" if key == "Authorization" else default
        )
        with patch("src.common.b14_audit_middleware.JwtAuthGuard") as mock_jwt:
            mock_jwt.verify_token.return_value = None
            user_id, user_name = B14AuditMiddleware._extract_user(request)
        assert user_id == 0


# ══════════════════════════════════════════════════════
# 4. AuditLogger 工具测试
# ══════════════════════════════════════════════════════


class TestAuditLogger:
    """AuditLogger 工具方法测试"""

    @pytest.mark.asyncio
    async def test_log_success(self):
        """审计日志写入成功"""
        mock_dao = AsyncMock()
        session, cm = _make_session_cm()

        with patch("src.common.b14_audit_util.DatabaseManager") as mock_db, \
             patch("src.common.b14_audit_util.AuditLogDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            from src.common.b14_audit_util import AuditLogger
            await AuditLogger.log(action="TEST", user_id=1, user_name="admin")
        mock_dao.create_log.assert_awaited()

    @pytest.mark.asyncio
    async def test_log_failure_not_raising(self):
        """审计日志写入失败不抛异常"""
        with patch("src.common.b14_audit_util.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB down")

            from src.common.b14_audit_util import AuditLogger
            # 不应抛异常
            await AuditLogger.log(action="TEST", user_id=1)

    # ── S04 P2-2：user_name 自动补齐 ──────────────

    @pytest.mark.asyncio
    async def test_log_resolves_user_name_when_missing(self):
        """P2-2：user_name 为空且 user_id 有效时自动补齐"""
        mock_dao = AsyncMock()
        session, cm = _make_session_cm()

        with patch("src.common.b14_audit_util.DatabaseManager") as mock_db, \
             patch("src.common.b14_audit_util.AuditLogDAO") as mock_dao_cls, \
             patch(
                 "src.common.b14_audit_util.AuditLogger._resolve_user_name",
                 new=AsyncMock(return_value="张三"),
             ) as mock_resolve:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            from src.common.b14_audit_util import AuditLogger
            await AuditLogger.log(action="TEST", user_id=5, user_name="")
        mock_resolve.assert_awaited_once_with(5)
        call_kwargs = mock_dao.create_log.call_args.kwargs
        assert call_kwargs["user_id"] == 5
        assert call_kwargs["user_name"] == "张三"

    @pytest.mark.asyncio
    async def test_log_keeps_provided_user_name(self):
        """P2-2：user_name 已提供时不触发补齐查询"""
        mock_dao = AsyncMock()
        session, cm = _make_session_cm()

        with patch("src.common.b14_audit_util.DatabaseManager") as mock_db, \
             patch("src.common.b14_audit_util.AuditLogDAO") as mock_dao_cls, \
             patch(
                 "src.common.b14_audit_util.AuditLogger._resolve_user_name",
                 new=AsyncMock(),
             ) as mock_resolve:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            from src.common.b14_audit_util import AuditLogger
            await AuditLogger.log(action="TEST", user_id=5, user_name="李四")
        mock_resolve.assert_not_awaited()
        call_kwargs = mock_dao.create_log.call_args.kwargs
        assert call_kwargs["user_name"] == "李四"

    @pytest.mark.asyncio
    async def test_log_no_resolve_when_user_id_zero(self):
        """P2-2：user_id=0（匿名）不触发补齐"""
        mock_dao = AsyncMock()
        session, cm = _make_session_cm()

        with patch("src.common.b14_audit_util.DatabaseManager") as mock_db, \
             patch("src.common.b14_audit_util.AuditLogDAO") as mock_dao_cls, \
             patch(
                 "src.common.b14_audit_util.AuditLogger._resolve_user_name",
                 new=AsyncMock(),
             ) as mock_resolve:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            from src.common.b14_audit_util import AuditLogger
            await AuditLogger.log(action="TEST", user_id=0)
        mock_resolve.assert_not_awaited()
        call_kwargs = mock_dao.create_log.call_args.kwargs
        assert call_kwargs["user_name"] == ""

    @pytest.mark.asyncio
    async def test_resolve_user_name_found_real_name(self):
        """P2-2：查询到管理员，返回 real_name"""
        session, cm = _make_session_cm()
        result = MagicMock()
        result.one_or_none.return_value = ("张三", "zhangsan")

        with patch("src.db.init_db.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm
            session.execute = AsyncMock(return_value=result)

            from src.common.b14_audit_util import AuditLogger
            name = await AuditLogger._resolve_user_name(5)
        assert name == "张三"

    @pytest.mark.asyncio
    async def test_resolve_user_name_fallback_username(self):
        """P2-2：real_name 为空时兜底用 username"""
        session, cm = _make_session_cm()
        result = MagicMock()
        result.one_or_none.return_value = ("", "zhangsan")

        with patch("src.db.init_db.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm
            session.execute = AsyncMock(return_value=result)

            from src.common.b14_audit_util import AuditLogger
            name = await AuditLogger._resolve_user_name(5)
        assert name == "zhangsan"

    @pytest.mark.asyncio
    async def test_resolve_user_name_not_found(self):
        """P2-2：管理员不存在返回空字符串"""
        session, cm = _make_session_cm()
        result = MagicMock()
        result.one_or_none.return_value = None

        with patch("src.db.init_db.DatabaseManager") as mock_db:
            mock_db.get_session.return_value = cm
            session.execute = AsyncMock(return_value=result)

            from src.common.b14_audit_util import AuditLogger
            name = await AuditLogger._resolve_user_name(999)
        assert name == ""

    @pytest.mark.asyncio
    async def test_resolve_user_name_error_returns_empty(self):
        """P2-2：查询异常返回空字符串（不抛异常）"""
        with patch("src.db.init_db.DatabaseManager") as mock_db:
            mock_db.get_session.side_effect = Exception("DB down")

            from src.common.b14_audit_util import AuditLogger
            name = await AuditLogger._resolve_user_name(5)
        assert name == ""

    def test_sanitize_details_password(self):
        """脱敏 password 字段"""
        from src.common.b14_audit_util import AuditLogger
        details = {"username": "admin", "password": "secret123", "action": "login"}
        sanitized = AuditLogger.sanitize_details(details)
        assert sanitized["password"] == "***"
        assert sanitized["username"] == "admin"

    def test_sanitize_details_nested(self):
        """脱敏嵌套字典中的敏感字段"""
        from src.common.b14_audit_util import AuditLogger
        details = {"user": {"name": "admin", "api_key": "key123"}}
        sanitized = AuditLogger.sanitize_details(details)
        assert sanitized["user"]["api_key"] == "***"
        assert sanitized["user"]["name"] == "admin"

    def test_sanitize_details_token(self):
        """脱敏 token 字段"""
        from src.common.b14_audit_util import AuditLogger
        details = {"access_token": "abc123", "data": "ok"}
        sanitized = AuditLogger.sanitize_details(details)
        assert sanitized["access_token"] == "***"

    def test_sanitize_details_non_dict(self):
        """非字典直接返回"""
        from src.common.b14_audit_util import AuditLogger
        assert AuditLogger.sanitize_details("string") == "string"
        assert AuditLogger.sanitize_details(None) is None

    def test_get_client_ip_forwarded(self):
        """从 X-Forwarded-For 提取 IP"""
        from src.common.b14_audit_util import AuditLogger
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "10.0.0.1, 192.168.1.1" if key == "X-Forwarded-For" else default
        )
        ip = AuditLogger.get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_direct(self):
        """无 X-Forwarded-For 时从 client.host 提取"""
        from src.common.b14_audit_util import AuditLogger
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.100"
        ip = AuditLogger.get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_user_agent(self):
        """获取 User-Agent"""
        from src.common.b14_audit_util import AuditLogger
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get.side_effect = lambda key, default="": (
            "Mozilla/5.0 test-agent" if key == "User-Agent" else default
        )
        ua = AuditLogger.get_user_agent(request)
        assert "test-agent" in ua

    def test_serialize_details_none(self):
        """序列化 None → 空字符串"""
        from src.common.b14_audit_util import AuditLogger
        assert AuditLogger._serialize_details(None) == ""

    def test_serialize_details_string(self):
        """序列化字符串 → 截断"""
        from src.common.b14_audit_util import AuditLogger
        long_str = "x" * 3000
        result = AuditLogger._serialize_details(long_str)
        assert len(result) == 2000

    def test_serialize_details_dict(self):
        """序列化字典 → JSON 字符串"""
        from src.common.b14_audit_util import AuditLogger
        result = AuditLogger._serialize_details({"key": "value"})
        assert '"key"' in result

    def test_serialize_details_other(self):
        """序列化其他类型 → 字符串"""
        from src.common.b14_audit_util import AuditLogger
        result = AuditLogger._serialize_details(12345)
        assert result == "12345"


# ══════════════════════════════════════════════════════
# 5. 异常处理器测试
# ══════════════════════════════════════════════════════


class TestB14ExceptionHandlers:
    """统一异常处理器测试"""

    def test_register_handlers(self):
        """注册异常处理器不报错"""
        from fastapi import FastAPI
        from src.common.b14_exception_handlers import register_b14_exception_handlers

        app = FastAPI()
        register_b14_exception_handlers(app)
        # 验证异常处理器已注册
        assert HTTPException in app.exception_handlers
        assert ValueError in app.exception_handlers

    @pytest.mark.asyncio
    async def test_http_exception_handler(self):
        """HTTPException → 标准 ApiResponse"""
        from fastapi import HTTPException, Request
        from src.common.b14_exception_handlers import register_b14_exception_handlers

        app = FastAPI()
        register_b14_exception_handlers(app)
        handler = app.exception_handlers[HTTPException]

        request = MagicMock()
        request.headers.get.return_value = "test_req_id"
        exc = HTTPException(status_code=403, detail="权限不足")
        response = await handler(request, exc)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_value_error_handler(self):
        """ValueError → 400 标准 ApiResponse"""
        from fastapi import Request
        from src.common.b14_exception_handlers import register_b14_exception_handlers

        app = FastAPI()
        register_b14_exception_handlers(app)
        handler = app.exception_handlers[ValueError]

        request = MagicMock()
        request.headers.get.return_value = "test_req_id"
        exc = ValueError("参数错误")
        response = await handler(request, exc)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_jwt_error_handler(self):
        """PyJWTError → 401 标准 ApiResponse"""
        import jwt
        from src.common.b14_exception_handlers import register_b14_exception_handlers

        app = FastAPI()
        register_b14_exception_handlers(app)
        handler = app.exception_handlers[jwt.PyJWTError]

        request = MagicMock()
        request.headers.get.return_value = "test_req_id"
        exc = jwt.ExpiredSignatureError("token expired")
        response = await handler(request, exc)
        assert response.status_code == 401

    def test_format_validation_errors(self):
        """格式化参数校验错误"""
        from src.common.b14_exception_handlers import _format_validation_errors

        errors = [
            {"loc": ("body", "username"), "msg": "field required", "type": "missing"},
            {"loc": ("body", "password"), "msg": "too short", "type": "value_error"},
        ]
        formatted = _format_validation_errors(errors)
        assert len(formatted) == 2
        assert formatted[0]["field"] == "username"
        assert formatted[1]["field"] == "password"


# ══════════════════════════════════════════════════════
# 6. audit_action 装饰器测试
# ══════════════════════════════════════════════════════


class TestAuditActionDecorator:
    """audit_action 装饰器测试"""

    @pytest.mark.asyncio
    async def test_decorator_logs_audit_with_request(self):
        """带 request 参数时记录审计日志"""
        from src.common.b14_audit_util import audit_action

        @audit_action(action="TEST_ACTION", target_type="endpoint")
        async def endpoint(request, admin_user_id=0):
            return {"ok": True}

        # 构造 request mock
        request = MagicMock()
        request.url.path = "/api/v1/admin/test/"
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.state.user_name = "admin"

        with patch("src.common.b14_audit_util.AuditLogger") as mock_logger:
            mock_logger.get_client_ip = MagicMock(return_value="127.0.0.1")
            mock_logger.get_user_agent = MagicMock(return_value="test-agent")
            mock_logger.log = AsyncMock()

            result = await endpoint(request=request, admin_user_id=1)

        assert result == {"ok": True}
        mock_logger.log.assert_awaited()
        # 验证调用参数包含正确的 action
        call_kwargs = mock_logger.log.call_args.kwargs
        assert call_kwargs["action"] == "TEST_ACTION"
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["user_name"] == "admin"

    @pytest.mark.asyncio
    async def test_decorator_skips_audit_without_request(self):
        """无 request 参数时不记录审计日志"""
        from src.common.b14_audit_util import audit_action

        @audit_action(action="TEST_ACTION", target_type="endpoint")
        async def endpoint(admin_user_id=0):
            return {"ok": True}

        with patch("src.common.b14_audit_util.AuditLogger") as mock_logger:
            mock_logger.log = AsyncMock()
            result = await endpoint(admin_user_id=1)

        assert result == {"ok": True}
        mock_logger.log.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_decorator_audit_failure_not_blocking(self):
        """审计记录失败不阻塞业务"""
        from src.common.b14_audit_util import audit_action

        @audit_action(action="TEST_ACTION", target_type="endpoint")
        async def endpoint(request, admin_user_id=0):
            return {"ok": True}

        request = MagicMock()
        request.url.path = "/api/v1/admin/test/"
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get.return_value = ""
        request.state.user_name = "admin"

        with patch("src.common.b14_audit_util.AuditLogger") as mock_logger:
            mock_logger.get_client_ip = MagicMock(return_value="127.0.0.1")
            mock_logger.get_user_agent = MagicMock(return_value="test-agent")
            # 审计写入抛异常
            mock_logger.log = AsyncMock(side_effect=Exception("DB down"))

            # 业务不应受影响
            result = await endpoint(request=request, admin_user_id=1)

        assert result == {"ok": True}


# ══════════════════════════════════════════════════════
# 7. B14PasswordUtil 密码工具测试
# ══════════════════════════════════════════════════════


class TestB14PasswordUtil:
    """B14PasswordUtil 密码哈希工具测试"""

    def test_hash_and_verify_success(self):
        """哈希 + 校验匹配"""
        from src.common.b14_password_util import B14PasswordUtil

        plain = "admin@12345"
        hashed = B14PasswordUtil.hash_password(plain)
        assert hashed.startswith("$2b$12$")
        assert B14PasswordUtil.verify_password(plain, hashed) is True

    def test_hash_empty_password_raises(self):
        """空密码 → ValueError"""
        from src.common.b14_password_util import B14PasswordUtil

        with pytest.raises(ValueError, match="不能为空"):
            B14PasswordUtil.hash_password("")

    def test_verify_wrong_password(self):
        """密码不匹配 → False"""
        from src.common.b14_password_util import B14PasswordUtil

        hashed = B14PasswordUtil.hash_password("correct_password")
        assert B14PasswordUtil.verify_password("wrong_password", hashed) is False

    def test_verify_empty_inputs(self):
        """空明文或空哈希 → False"""
        from src.common.b14_password_util import B14PasswordUtil

        assert B14PasswordUtil.verify_password("", "hashed") is False
        assert B14PasswordUtil.verify_password("plain", "") is False

    def test_verify_invalid_hash_format(self):
        """非法哈希格式 → False（不抛异常）"""
        from src.common.b14_password_util import B14PasswordUtil

        assert B14PasswordUtil.verify_password("plain", "invalid_hash") is False

    def test_hash_truncates_long_password(self):
        """超长密码（>72 字节）截断后哈希成功"""
        from src.common.b14_password_util import B14PasswordUtil

        long_password = "x" * 200  # 200 字节，超过 bcrypt 72 字节限制
        hashed = B14PasswordUtil.hash_password(long_password)
        # 截断到 72 字节后能正常校验
        assert B14PasswordUtil.verify_password(long_password, hashed) is True
        # 前 72 字节相同的密码也能匹配（因被截断）
        assert B14PasswordUtil.verify_password("x" * 72 + "y", hashed) is True

    def test_needs_rehash_low_cost(self):
        """低 cost 哈希 → 需重新哈希"""
        from src.common.b14_password_util import B14PasswordUtil

        # cost=4 的哈希（低于 _COST=12）
        import bcrypt
        low_cost_hash = bcrypt.hashpw(
            b"test", bcrypt.gensalt(rounds=4)
        ).decode("utf-8")
        assert B14PasswordUtil.needs_rehash(low_cost_hash) is True

    def test_needs_rehash_current_cost(self):
        """当前 cost 哈希 → 不需重新哈希"""
        from src.common.b14_password_util import B14PasswordUtil

        hashed = B14PasswordUtil.hash_password("test")
        assert B14PasswordUtil.needs_rehash(hashed) is False

    def test_needs_rehash_invalid_format(self):
        """非法格式 → 返回 True（保守判断需重新哈希）"""
        from src.common.b14_password_util import B14PasswordUtil

        assert B14PasswordUtil.needs_rehash("invalid_hash") is True
        assert B14PasswordUtil.needs_rehash("") is True


# 需要 import HTTPException 用于 test_register_handlers
from fastapi import HTTPException  # noqa: E402

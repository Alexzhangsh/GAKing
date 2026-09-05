# @ai-generated
"""
B15 增强认证服务单元测试
覆盖：
1. B15AuthService.logout：登出成功 + JWT 黑名单写入 + 审计日志
2. B15AuthService.change_password：成功 + 新旧密码相同 + 原密码错误 + 用户不存在 + 密码长度不足
3. JWT 黑名单写入异常降级
4. 审计日志写入异常降级
5. API 路由层测试（TestClient）：登出/改密端点

覆盖率目标：≥90%
"""
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from src.services.b15_auth_service import B15AuthService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_admin_user(
    user_id: int = 1,
    username: str = "admin",
    password_hash: str = "$2b$12$somehash",
    real_name: str = "系统超管",
    role_id: int = 1,
    status: bool = True,
):
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.password = password_hash
    user.real_name = real_name
    user.role_id = role_id
    user.status = status
    user.phone = ""
    user.email = ""
    return user


def _make_session_cm():
    """构造 DatabaseManager.get_session() 的 async context manager mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _mock_redis_client(get_return=None):
    """构造 RedisClient mock"""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=get_return)
    mock.set = AsyncMock(return_value=True)
    return mock


# ══════════════════════════════════════════════════════
# 1. logout 登出测试
# ══════════════════════════════════════════════════════


class TestB15AuthLogout:
    """登出流程测试"""

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """登出成功：JWT 黑名单写入 + 审计日志记录"""
        mock_redis = _mock_redis_client()
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()

        with patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit):
            result = await B15AuthService.logout(
                user_id=1,
                username="admin",
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )

        assert result is True
        # 验证 JWT 黑名单写入
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.await_args
        assert call_args is not None
        assert "blacklist" in str(call_args)
        # 验证审计日志记录
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logout_redis_error_does_not_block(self):
        """Redis 异常时登出不阻塞"""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()

        with patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit):
            result = await B15AuthService.logout(
                user_id=1,
                username="admin",
            )

        assert result is True
        # 审计日志仍应写入
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logout_audit_error_does_not_block(self):
        """审计日志异常时登出不阻塞"""
        mock_redis = _mock_redis_client()
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock(side_effect=Exception("DB error"))

        with patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit):
            result = await B15AuthService.logout(
                user_id=1,
                username="admin",
            )

        assert result is True
        mock_redis.set.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 2. change_password 修改密码测试
# ══════════════════════════════════════════════════════


class TestB15AuthChangePassword:
    """修改密码流程测试"""

    @pytest.mark.asyncio
    async def test_change_password_success(self):
        """修改密码成功：更新哈希 + JWT 黑名单 + 审计日志"""
        mock_redis = _mock_redis_client()
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id = AsyncMock()

        with patch("src.services.b15_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b15_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b15_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = True
            mock_pwd.hash_password.return_value = "$2b$12$newhash"

            result = await B15AuthService.change_password(
                user_id=1,
                old_password="old_pass",
                new_password="new_pass_123",
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )

        assert result is True
        mock_user_dao.update_by_id.assert_awaited_once()
        mock_redis.set.assert_awaited_once()
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_change_password_same_password(self):
        """新旧密码相同 → 抛出 ValueError"""
        with pytest.raises(ValueError, match="新密码不能与原密码相同"):
            await B15AuthService.change_password(
                user_id=1,
                old_password="samepass",
                new_password="samepass",
            )

    @pytest.mark.asyncio
    async def test_change_password_too_short(self):
        """新密码长度不足 8 位 → 抛出 ValueError"""
        with pytest.raises(ValueError, match="不能少于 8 位"):
            await B15AuthService.change_password(
                user_id=1,
                old_password="old_pass",
                new_password="1234567",
            )

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self):
        """用户不存在 → 抛出 ValueError"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = None

        with patch("src.services.b15_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b15_auth_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            with pytest.raises(ValueError, match="用户不存在"):
                await B15AuthService.change_password(
                    user_id=999,
                    old_password="old_pass",
                    new_password="new_pass_123",
                )

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_password(self):
        """原密码错误 → 抛出 ValueError"""
        session, cm = _make_session_cm()
        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user

        with patch("src.services.b15_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b15_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b15_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = False

            with pytest.raises(ValueError, match="原密码错误"):
                await B15AuthService.change_password(
                    user_id=1,
                    old_password="wrong_pass",
                    new_password="new_pass_123",
                )
        mock_user_dao.update_by_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_change_password_redis_error_does_not_block(self):
        """Redis 异常时改密不阻塞"""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id = AsyncMock()

        with patch("src.services.b15_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b15_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b15_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = True
            mock_pwd.hash_password.return_value = "$2b$12$newhash"

            result = await B15AuthService.change_password(
                user_id=1,
                old_password="old_pass",
                new_password="new_pass_123",
            )

        assert result is True
        mock_user_dao.update_by_id.assert_awaited_once()
        mock_audit.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_change_password_audit_error_does_not_block(self):
        """审计日志异常时改密不阻塞（覆盖 change_password 的 except 分支）"""
        mock_redis = _mock_redis_client()
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock(side_effect=Exception("Audit DB error"))
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id = AsyncMock()

        with patch("src.services.b15_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b15_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b15_auth_service.RedisClient", mock_redis), \
             patch("src.services.b15_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b15_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = True
            mock_pwd.hash_password.return_value = "$2b$12$newhash"

            result = await B15AuthService.change_password(
                user_id=1,
                old_password="old_pass",
                new_password="new_pass_123",
            )

        assert result is True
        mock_user_dao.update_by_id.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 3. 内部工具方法测试
# ══════════════════════════════════════════════════════


class TestB15AuthUtils:
    """内部工具方法测试"""

    @pytest.mark.asyncio
    async def test_add_jwt_blacklist_success(self):
        """JWT 黑名单写入成功"""
        mock_redis = _mock_redis_client()
        with patch("src.services.b15_auth_service.RedisClient", mock_redis):
            await B15AuthService._add_jwt_blacklist(1, expires_in=3600)
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_jwt_blacklist_error_does_not_raise(self):
        """JWT 黑名单写入异常不抛出"""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis error"))
        with patch("src.services.b15_auth_service.RedisClient", mock_redis):
            # 不应抛出异常
            await B15AuthService._add_jwt_blacklist(1, expires_in=3600)
        mock_redis.set.assert_awaited_once()


# ══════════════════════════════════════════════════════
# 4. API 路由层测试（TestClient）
# ══════════════════════════════════════════════════════


class TestB15AuthApiRoutes:
    """API 路由层测试（覆盖 b15_auth.py 路由处理函数）"""

    @pytest.fixture
    def app(self):
        """构造测试用 FastAPI app，注册 B15 auth 路由"""
        from src.api.v1.admin.b15_auth import router as b15_auth_router
        from src.common.auth_util import get_current_user

        app = FastAPI()
        app.include_router(b15_auth_router)

        # 默认 override get_current_user 返回测试用户
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": 1,
            "username": "admin",
            "role_id": 1,
        }
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_logout_success(self, client):
        """POST /api/v1/admin/auth/logout → 登出成功"""
        with patch(
            "src.api.v1.admin.b15_auth.B15AuthService.logout",
            AsyncMock(return_value=True),
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_client_ip",
            return_value="127.0.0.1",
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_user_agent",
            return_value="test-agent",
        ):
            resp = client.post("/api/v1/admin/auth/logout")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert "JWT 已销毁" in body["msg"]

    def test_logout_service_error(self, client):
        """POST /api/v1/admin/auth/logout → Service 异常时返回错误响应"""
        with patch(
            "src.api.v1.admin.b15_auth.B15AuthService.logout",
            AsyncMock(side_effect=ValueError("service error")),
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_client_ip",
            return_value="127.0.0.1",
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_user_agent",
            return_value="test-agent",
        ):
            resp = client.post("/api/v1/admin/auth/logout")

        assert resp.status_code == 200  # 业务异常仍返回 200，code 标记错误
        body = resp.json()
        assert body["code"] != 200

    def test_change_password_success(self, client):
        """PUT /api/v1/admin/auth/password → 修改密码成功"""
        with patch(
            "src.api.v1.admin.b15_auth.B15AuthService.change_password",
            AsyncMock(return_value=True),
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_client_ip",
            return_value="127.0.0.1",
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_user_agent",
            return_value="test-agent",
        ):
            resp = client.put(
                "/api/v1/admin/auth/password",
                json={"old_password": "old_pass", "new_password": "new_pass_123"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert "密码修改成功" in body["msg"]

    def test_change_password_service_error(self, client):
        """PUT /api/v1/admin/auth/password → Service 异常时返回错误响应"""
        with patch(
            "src.api.v1.admin.b15_auth.B15AuthService.change_password",
            AsyncMock(side_effect=ValueError("原密码错误")),
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_client_ip",
            return_value="127.0.0.1",
        ), patch(
            "src.api.v1.admin.b15_auth.AuditLogger.get_user_agent",
            return_value="test-agent",
        ):
            resp = client.put(
                "/api/v1/admin/auth/password",
                json={"old_password": "wrong", "new_password": "new_pass_123"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] != 200

    def test_change_password_validation_error(self, client):
        """PUT /api/v1/admin/auth/password → 请求体验证失败"""
        resp = client.put(
            "/api/v1/admin/auth/password",
            json={"old_password": "old", "new_password": "short"},  # 新密码不足8位
        )

        assert resp.status_code == 422  # Pydantic 校验失败
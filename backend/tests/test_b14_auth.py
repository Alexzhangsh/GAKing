# @ai-generated
"""
B14 认证服务单元测试
覆盖：
1. B14AuthService.login：成功/用户不存在/密码错误/账号禁用/账号锁定/Redis异常降级
2. B14AuthService.change_password：成功/相同密码/原密码错误/用户不存在
3. B14AuthService.reset_password：成功/用户不存在
4. B14AuthService.get_user_info：成功/用户不存在
5. 登录失败锁定机制：_check_login_fail_lock / _record_login_fail / _reset_login_fail
6. JWT 黑名单：_add_jwt_blacklist / is_jwt_blacklisted
7. 工具方法：_parse_permissions / _create_token / _get_jwt_expires_in

覆盖率目标：单文件 ≥90%
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.auth_util import JwtAuthGuard
from src.services.b14_auth_service import B14AuthService


# ══════════════════════════════════════════════════════
# 全局 fixture
# ══════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def init_jwt():
    """初始化 JwtAuthGuard 使用测试密钥"""
    JwtAuthGuard._secret = "test_jwt_secret_for_b14_unit_tests_at_least_32_chars!!"
    JwtAuthGuard._expires_in = 3600
    yield


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


def _make_admin_role(
    role_id: int = 1,
    role_name: str = "超级管理员",
    permissions: str = '["*"]',
    status: bool = True,
):
    role = MagicMock()
    role.id = role_id
    role.role_name = role_name
    role.permissions = permissions
    role.status = status
    role.role_desc = "系统超管"
    return role


def _make_session_cm():
    """构造 DatabaseManager.get_session() 的 async context manager mock"""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


def _mock_redis_client(
    get_return=None,
    incr_return=1,
    ttl_return=600,
    delete_return=1,
    set_return=True,
    expire_return=True,
):
    """构造 RedisClient mock，所有方法均为 AsyncMock"""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=get_return)
    mock.set = AsyncMock(return_value=set_return)
    mock.delete = AsyncMock(return_value=delete_return)
    mock.incr = AsyncMock(return_value=incr_return)
    mock.ttl = AsyncMock(return_value=ttl_return)
    mock.expire = AsyncMock(return_value=expire_return)
    mock.exists = AsyncMock(return_value=0)
    return mock


def _mock_audit_logger():
    """构造 AuditLogger mock，log 方法为 AsyncMock"""
    mock = MagicMock()
    mock.log = AsyncMock()
    mock.get_client_ip = MagicMock(return_value="127.0.0.1")
    mock.get_user_agent = MagicMock(return_value="test-agent")
    mock.sanitize_details = MagicMock(side_effect=lambda x: x)
    return mock


# ══════════════════════════════════════════════════════
# 1. login 登录测试
# ══════════════════════════════════════════════════════


class TestB14AuthLogin:
    """登录流程测试"""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """登录成功：返回 token + 用户信息 + 权限码"""
        mock_redis = _mock_redis_client(get_return=None)
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        role = _make_admin_role()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = user
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = role

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AdminRoleDAO") as mock_role_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14ConfigUtil") as mock_config, \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao
            mock_pwd.verify_password.return_value = True
            mock_config.get_int = AsyncMock(return_value=3600)

            result = await B14AuthService.login("admin", "admin@12345")

        assert result["token"] is not None
        assert result["user_id"] == 1
        assert result["username"] == "admin"
        assert result["role_name"] == "超级管理员"
        assert "*" in result["permissions"]
        mock_audit.log.assert_awaited()

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """用户不存在 → 401"""
        mock_redis = _mock_redis_client(get_return=None)
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = None

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis):
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.login("nouser", "pass")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """密码错误 → 401 + 失败计数+1"""
        mock_redis = _mock_redis_client(get_return=None, incr_return=1)
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = user

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = False

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.login("admin", "wrongpass")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_disabled_user(self):
        """账号被禁用 → 401"""
        mock_redis = _mock_redis_client(get_return=None)
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user(status=False)
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = user

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis):
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.login("admin", "pass")
            assert exc_info.value.status_code == 401
            assert "禁用" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_locked_account(self):
        """账号被锁定 → 423"""
        from src.config.b14_constants import ADMIN_LOGIN_FAIL_MAX
        mock_redis = _mock_redis_client(
            get_return=str(ADMIN_LOGIN_FAIL_MAX), ttl_return=600
        )
        mock_audit = _mock_audit_logger()

        with patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.DatabaseManager"):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.login("admin", "pass")
            assert exc_info.value.status_code == 423
            assert "锁定" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_redis_error_degraded(self):
        """Redis 异常时降级放行（不锁定）"""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis down"))
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        role = _make_admin_role()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = user
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = role

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AdminRoleDAO") as mock_role_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14ConfigUtil") as mock_config, \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao
            mock_pwd.verify_password.return_value = True
            mock_config.get_int = AsyncMock(return_value=3600)

            result = await B14AuthService.login("admin", "admin@12345")
            assert result["token"] is not None

    @pytest.mark.asyncio
    async def test_login_max_fail_triggers_lock(self):
        """第 5 次失败触发锁定 → 423"""
        from src.config.b14_constants import ADMIN_LOGIN_FAIL_MAX
        mock_redis = _mock_redis_client(
            get_return=str(ADMIN_LOGIN_FAIL_MAX - 1),
            incr_return=ADMIN_LOGIN_FAIL_MAX,
        )
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = user

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = False

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.login("admin", "wrongpass")
            assert exc_info.value.status_code == 423


# ══════════════════════════════════════════════════════
# 2. change_password 修改密码测试
# ══════════════════════════════════════════════════════


class TestB14ChangePassword:
    """修改密码测试"""

    @pytest.mark.asyncio
    async def test_change_password_success(self):
        """修改密码成功"""
        mock_redis = _mock_redis_client()
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id = AsyncMock()

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = True
            mock_pwd.hash_password.return_value = "newhash"

            result = await B14AuthService.change_password(1, "oldpass", "newpass123")
        assert result is True
        mock_user_dao.update_by_id.assert_awaited()

    @pytest.mark.asyncio
    async def test_change_password_same_password(self):
        """新旧密码相同 → 400"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await B14AuthService.change_password(1, "samepass", "samepass")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self):
        """原密码错误 → 401"""
        mock_redis = _mock_redis_client()
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.verify_password.return_value = False

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.change_password(1, "wrongold", "newpass123")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self):
        """用户不存在 → 404"""
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = None

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit):
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.change_password(999, "old", "newpass123")
            assert exc_info.value.status_code == 404


# ══════════════════════════════════════════════════════
# 3. reset_password 重置密码测试
# ══════════════════════════════════════════════════════


class TestB14ResetPassword:
    """重置密码测试"""

    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """重置密码成功"""
        mock_redis = _mock_redis_client()
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        user = _make_admin_user()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id = AsyncMock()

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit), \
             patch("src.services.b14_auth_service.RedisClient", mock_redis), \
             patch("src.services.b14_auth_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_pwd.hash_password.return_value = "newhash"

            result = await B14AuthService.reset_password(2, "newpass123", 1, "admin")
        assert result is True
        mock_audit.log.assert_awaited()

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self):
        """用户不存在 → 404"""
        mock_audit = _mock_audit_logger()
        session, cm = _make_session_cm()

        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = None

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_auth_service.AuditLogger", mock_audit):
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.reset_password(999, "newpass", 1, "admin")
            assert exc_info.value.status_code == 404


# ══════════════════════════════════════════════════════
# 4. get_user_info 用户信息测试
# ══════════════════════════════════════════════════════


class TestB14GetUserInfo:
    """获取用户信息测试"""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self):
        """成功获取用户信息"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_with_role.return_value = {
            "id": 1,
            "username": "admin",
            "real_name": "超管",
            "phone": "13800000000",
            "email": "admin@gaking.com",
            "role_id": 1,
            "role_name": "超级管理员",
            "role_permissions": '["*"]',
        }

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            result = await B14AuthService.get_user_info(1)
        assert result["user_id"] == 1
        assert result["username"] == "admin"
        assert result["role_name"] == "超级管理员"
        assert "*" in result["permissions"]

    @pytest.mark.asyncio
    async def test_get_user_info_not_found(self):
        """用户不存在 → 404"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_with_role.return_value = None

        with patch("src.services.b14_auth_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_auth_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await B14AuthService.get_user_info(999)
            assert exc_info.value.status_code == 404


# ══════════════════════════════════════════════════════
# 5. 登录失败锁定机制测试
# ══════════════════════════════════════════════════════


class TestLoginFailLock:
    """登录失败锁定机制测试"""

    @pytest.mark.asyncio
    async def test_check_lock_not_locked(self):
        """未达到锁定阈值 → 未锁定"""
        from src.config.b14_constants import ADMIN_LOGIN_FAIL_MAX
        mock_redis = _mock_redis_client(get_return="2")
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            locked, remaining, retry = await B14AuthService._check_login_fail_lock("admin")
        assert locked is False
        assert remaining == ADMIN_LOGIN_FAIL_MAX - 2
        assert retry == 0

    @pytest.mark.asyncio
    async def test_check_lock_locked(self):
        """达到锁定阈值 → 已锁定"""
        from src.config.b14_constants import ADMIN_LOGIN_FAIL_MAX
        mock_redis = _mock_redis_client(
            get_return=str(ADMIN_LOGIN_FAIL_MAX), ttl_return=600
        )
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            locked, remaining, retry = await B14AuthService._check_login_fail_lock("admin")
        assert locked is True
        assert remaining == 0
        assert retry == 600

    @pytest.mark.asyncio
    async def test_check_lock_no_record(self):
        """无失败记录 → 未锁定"""
        mock_redis = _mock_redis_client(get_return=None)
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            locked, remaining, retry = await B14AuthService._check_login_fail_lock("admin")
        assert locked is False

    @pytest.mark.asyncio
    async def test_check_lock_redis_error(self):
        """Redis 异常 → 降级放行"""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            locked, remaining, retry = await B14AuthService._check_login_fail_lock("admin")
        assert locked is False

    @pytest.mark.asyncio
    async def test_record_login_fail_success(self):
        """记录失败次数成功"""
        mock_redis = _mock_redis_client(incr_return=3)
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            count = await B14AuthService._record_login_fail("admin")
        assert count == 3

    @pytest.mark.asyncio
    async def test_record_login_fail_redis_error(self):
        """记录失败次数 Redis 异常 → 返回 0"""
        mock_redis = MagicMock()
        mock_redis.incr = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            count = await B14AuthService._record_login_fail("admin")
        assert count == 0

    @pytest.mark.asyncio
    async def test_reset_login_fail_success(self):
        """重置失败计数成功"""
        mock_redis = _mock_redis_client()
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            await B14AuthService._reset_login_fail("admin")
        mock_redis.delete.assert_awaited()

    @pytest.mark.asyncio
    async def test_reset_login_fail_redis_error(self):
        """重置失败计数 Redis 异常 → 不抛错"""
        mock_redis = MagicMock()
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            await B14AuthService._reset_login_fail("admin")  # 不应抛异常


# ══════════════════════════════════════════════════════
# 6. JWT 黑名单测试
# ══════════════════════════════════════════════════════


class TestJwtBlacklist:
    """JWT 黑名单测试"""

    @pytest.mark.asyncio
    async def test_add_jwt_blacklist_success(self):
        """写入黑名单成功"""
        mock_redis = _mock_redis_client()
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            await B14AuthService._add_jwt_blacklist(1, 3600)
        mock_redis.set.assert_awaited()

    @pytest.mark.asyncio
    async def test_add_jwt_blacklist_fail(self):
        """写入黑名单失败 → 不抛错"""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            await B14AuthService._add_jwt_blacklist(1, 3600)  # 不应抛异常

    @pytest.mark.asyncio
    async def test_is_jwt_blacklisted_true(self):
        """用户在黑名单中"""
        mock_redis = _mock_redis_client(get_return="1")
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            result = await B14AuthService.is_jwt_blacklisted(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_jwt_blacklisted_false(self):
        """用户不在黑名单中"""
        mock_redis = _mock_redis_client(get_return=None)
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            result = await B14AuthService.is_jwt_blacklisted(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_jwt_blacklisted_error(self):
        """Redis 异常 → 返回 False"""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        with patch("src.services.b14_auth_service.RedisClient", mock_redis):
            result = await B14AuthService.is_jwt_blacklisted(1)
        assert result is False


# ══════════════════════════════════════════════════════
# 7. 工具方法测试
# ══════════════════════════════════════════════════════


class TestB14AuthUtils:
    """工具方法测试"""

    def test_parse_permissions_valid_json(self):
        """解析合法 JSON 权限列表"""
        result = B14AuthService._parse_permissions('["*", "order:sync"]')
        assert result == ["*", "order:sync"]

    def test_parse_permissions_empty(self):
        """空字符串 → 空列表"""
        result = B14AuthService._parse_permissions("")
        assert result == []

    def test_parse_permissions_invalid_json(self):
        """非法 JSON → 空列表"""
        result = B14AuthService._parse_permissions("not a json")
        assert result == []

    def test_parse_permissions_not_list(self):
        """JSON 非 list → 空列表"""
        result = B14AuthService._parse_permissions('{"key": "value"}')
        assert result == []

    @pytest.mark.asyncio
    async def test_get_jwt_expires_in_from_config(self):
        """从配置读取 JWT 过期时间"""
        with patch("src.services.b14_auth_service.B14ConfigUtil") as mock_config:
            mock_config.get_int = AsyncMock(return_value=7200)
            result = await B14AuthService._get_jwt_expires_in()
        assert result == 7200

    @pytest.mark.asyncio
    async def test_get_jwt_expires_in_fallback(self):
        """配置读取异常 → 降级 EnvConfig"""
        from src.config.env_config import EnvConfig
        with patch("src.services.b14_auth_service.B14ConfigUtil") as mock_config:
            mock_config.get_int = AsyncMock(side_effect=Exception("Config error"))
            result = await B14AuthService._get_jwt_expires_in()
        assert result == EnvConfig.JWT_EXPIRES_IN

    def test_create_token(self):
        """生成 JWT token"""
        user = _make_admin_user()
        token = B14AuthService._create_token(user, 3600)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

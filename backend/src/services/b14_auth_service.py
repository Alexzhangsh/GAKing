# @ai-generated
"""
B14 后台管理员认证 Service（登录 / 改密 / 重置 / 用户信息）
新建独立文件，不修改 B01-B13 任何基线 service

业务流程：
1. login：失败锁定校验 → 用户查询 → 密码哈希校验 → JWT 生成 → 审计日志 → 失败计数重置
2. change_password：自助改密，校验原密码后更新 bcrypt 哈希
3. reset_password：特权用户重置他人密码，写审计日志 + JWT 黑名单（best-effort）
4. get_user_info：查询当前登录用户信息 + 角色权限码列表

安全设计：
- 登录失败 5 次锁定 15 分钟（Redis CACHE_KEY_ADMIN_LOGIN_FAIL，TTL=ADMIN_LOGIN_FAIL_TTL）
- 密码统一 bcrypt 哈希存储（B14PasswordUtil，cost=12）
- 登录成功/失败均写审计日志（AuditLogger.log）
- JWT 过期时间支持动态配置（admin_jwt_expires_in），降级 EnvConfig.JWT_EXPIRES_IN
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.auth_util import JwtAuthGuard
from src.common.b14_audit_util import AuditLogger
from src.common.b14_config_util import B14ConfigUtil
from src.common.b14_password_util import B14PasswordUtil
from src.common.redis_client import RedisClient
from src.config.b14_constants import (
    ADMIN_LOGIN_FAIL_MAX,
    ADMIN_LOGIN_FAIL_TTL,
    AuditAction,
    AuditTargetType,
    CACHE_KEY_ADMIN_JWT_BLACKLIST,
    CACHE_KEY_ADMIN_LOGIN_FAIL,
)
from src.dao.admin_role_dao import AdminRoleDAO
from src.dao.admin_user_dao import AdminUserDAO
from src.db.init_db import DatabaseManager
from src.db.models import AdminRole, AdminUser

logger = logging.getLogger("service.b14_auth")


class B14AuthService:
    """后台管理员认证服务"""

    # ════════════════════════════════════════════════════
    # 1. 登录
    # ════════════════════════════════════════════════════

    @classmethod
    async def login(
        cls,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Dict[str, Any]:
        """管理员登录

        Args:
            username: 用户名
            password: 明文密码
            ip_address: 客户端 IP（审计用）
            user_agent: User-Agent（审计用）
        Returns:
            {token, expires_in, user_id, username, real_name, role_id,
             role_name, permissions, must_change_password}
        Raises:
            HTTPException: 401 用户名/密码错误或账号被禁用；423 账号被锁定
        """
        # 1. 校验登录失败锁定
        locked, remaining_attempts, retry_after = await cls._check_login_fail_lock(
            username
        )
        if locked:
            logger.warning(
                "[b14_auth] 登录被锁定 username=%s retry_after=%ss",
                username,
                retry_after,
            )
            # 写审计日志（best-effort）
            await AuditLogger.log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                target_type=AuditTargetType.LOGIN,
                target_id=0,
                details={"username": username, "reason": "locked"},
                user_id=0,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=423,
                detail=f"账号已被锁定，请 {retry_after} 秒后重试",
            )

        # 2. 查询用户
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            user = await user_dao.get_by_username(username)

            # 用户不存在或被删除
            if user is None:
                await cls._record_login_fail(username)
                logger.warning(
                    "[b14_auth] 登录失败：用户不存在 username=%s", username
                )
                await AuditLogger.log(
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    target_type=AuditTargetType.LOGIN,
                    target_id=0,
                    details={"username": username, "reason": "user_not_found"},
                    user_id=0,
                    user_name=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(status_code=401, detail="用户名或密码错误")

            # 账号被禁用
            if not user.status:
                logger.warning(
                    "[b14_auth] 登录失败：账号已禁用 username=%s", username
                )
                await AuditLogger.log(
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    target_type=AuditTargetType.LOGIN,
                    target_id=user.id,
                    details={"username": username, "reason": "disabled"},
                    user_id=user.id,
                    user_name=user.real_name or username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(status_code=401, detail="账号已被禁用，请联系超管")

            # 3. 校验密码
            if not B14PasswordUtil.verify_password(password, user.password):
                fail_count = await cls._record_login_fail(username)
                logger.warning(
                    "[b14_auth] 登录失败：密码错误 username=%s fail_count=%s",
                    username,
                    fail_count,
                )
                await AuditLogger.log(
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    target_type=AuditTargetType.LOGIN,
                    target_id=user.id,
                    details={
                        "username": username,
                        "reason": "wrong_password",
                        "fail_count": fail_count,
                    },
                    user_id=user.id,
                    user_name=user.real_name or username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                remaining = max(0, ADMIN_LOGIN_FAIL_MAX - fail_count)
                if remaining > 0:
                    raise HTTPException(
                        status_code=401,
                        detail=f"用户名或密码错误，剩余尝试次数 {remaining}",
                    )
                else:
                    raise HTTPException(
                        status_code=423,
                        detail=f"登录失败次数过多，账号已被锁定 {ADMIN_LOGIN_FAIL_TTL} 秒",
                    )

            # 4. 查询角色 + 权限
            role_dao = AdminRoleDAO(session)
            role = await role_dao.get_by_id(user.role_id) if user.role_id else None
            permissions = cls._parse_permissions(role.permissions if role else "")

            # 5. 生成 JWT（过期时间动态读取配置）
            expires_in = await cls._get_jwt_expires_in()
            token = cls._create_token(user, expires_in)

            # 6. 重置失败计数
            await cls._reset_login_fail(username)

            # 7. 写审计日志（成功）
            await AuditLogger.log(
                action=AuditAction.ADMIN_LOGIN,
                target_type=AuditTargetType.LOGIN,
                target_id=user.id,
                details={"username": username, "role_id": user.role_id},
                user_id=user.id,
                user_name=user.real_name or username,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(
                "[b14_auth] 登录成功 user_id=%s username=%s role_id=%s",
                user.id,
                username,
                user.role_id,
            )

            return {
                "token": token,
                "expires_in": expires_in,
                "user_id": user.id,
                "username": user.username,
                "real_name": user.real_name or "",
                "role_id": user.role_id,
                "role_name": role.role_name if role else "",
                "permissions": permissions,
                "must_change_password": False,
            }

    # ════════════════════════════════════════════════════
    # 2. 修改密码（自助）
    # ════════════════════════════════════════════════════

    @classmethod
    async def change_password(
        cls,
        user_id: int,
        old_password: str,
        new_password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> bool:
        """管理员自助修改密码

        Args:
            user_id: 管理员ID
            old_password: 原密码
            new_password: 新密码（至少 8 位）
            ip_address: 客户端 IP（审计用）
            user_agent: User-Agent（审计用）
        Returns:
            True-修改成功
        Raises:
            HTTPException: 400 新旧密码相同；401 原密码错误；404 用户不存在
        """
        if old_password == new_password:
            raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            user = await user_dao.get_by_id(user_id)
            if user is None:
                raise HTTPException(status_code=404, detail="用户不存在")

            # 校验原密码
            if not B14PasswordUtil.verify_password(old_password, user.password):
                logger.warning(
                    "[b14_auth] 修改密码失败：原密码错误 user_id=%s", user_id
                )
                raise HTTPException(status_code=401, detail="原密码错误")

            # 哈希新密码 + 更新
            new_hash = B14PasswordUtil.hash_password(new_password)
            await user_dao.update_by_id(user_id, {"password": new_hash})

            # 写审计日志
            await AuditLogger.log(
                action=AuditAction.PASSWORD_RESET,
                target_type=AuditTargetType.ADMIN_USER,
                target_id=user_id,
                details={"reason": "self_change"},
                user_id=user_id,
                user_name=user.real_name or user.username,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # 写 JWT 黑名单（best-effort，强制旧 token 失效）
            await cls._add_jwt_blacklist(user_id, expires_in=86400)

            logger.info("[b14_auth] 修改密码成功 user_id=%s", user_id)
            return True

    # ════════════════════════════════════════════════════
    # 3. 重置密码（特权）
    # ════════════════════════════════════════════════════

    @classmethod
    async def reset_password(
        cls,
        target_user_id: int,
        new_password: str,
        operator_id: int,
        operator_name: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> bool:
        """特权用户重置他人密码

        Args:
            target_user_id: 被重置密码的管理员ID
            new_password: 新密码（至少 8 位）
            operator_id: 操作人ID
            operator_name: 操作人姓名
            ip_address: 客户端 IP
            user_agent: User-Agent
        Returns:
            True-重置成功
        Raises:
            HTTPException: 404 用户不存在
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            user = await user_dao.get_by_id(target_user_id)
            if user is None:
                raise HTTPException(status_code=404, detail="用户不存在")

            new_hash = B14PasswordUtil.hash_password(new_password)
            await user_dao.update_by_id(target_user_id, {"password": new_hash})

            # 写审计日志
            await AuditLogger.log(
                action=AuditAction.PASSWORD_RESET,
                target_type=AuditTargetType.ADMIN_USER,
                target_id=target_user_id,
                details={
                    "reason": "admin_reset",
                    "operator_id": operator_id,
                    "operator_name": operator_name,
                },
                user_id=operator_id,
                user_name=operator_name,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # 写 JWT 黑名单（best-effort）
            await cls._add_jwt_blacklist(target_user_id, expires_in=86400)

            logger.info(
                "[b14_auth] 重置密码成功 target_user_id=%s operator_id=%s",
                target_user_id,
                operator_id,
            )
            return True

    # ════════════════════════════════════════════════════
    # 4. 获取当前用户信息
    # ════════════════════════════════════════════════════

    @classmethod
    async def get_user_info(cls, user_id: int) -> Dict[str, Any]:
        """获取当前登录用户信息（含角色 + 权限码列表）

        Args:
            user_id: 管理员ID
        Returns:
            {user_id, username, real_name, phone, email, role_id,
             role_name, permissions}
        Raises:
            HTTPException: 404 用户不存在
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            data = await user_dao.get_with_role(user_id)
            if data is None:
                raise HTTPException(status_code=404, detail="用户不存在")

            permissions = cls._parse_permissions(data.get("role_permissions", ""))

            return {
                "user_id": data["id"],
                "username": data["username"],
                "real_name": data.get("real_name", ""),
                "phone": data.get("phone", ""),
                "email": data.get("email", ""),
                "role_id": data["role_id"],
                "role_name": data.get("role_name", ""),
                "permissions": permissions,
            }

    # ════════════════════════════════════════════════════
    # 内部工具方法
    # ════════════════════════════════════════════════════

    @classmethod
    async def _check_login_fail_lock(
        cls, username: str
    ) -> Tuple[bool, int, int]:
        """检查登录失败锁定状态

        Args:
            username: 用户名
        Returns:
            (is_locked, remaining_attempts, retry_after_seconds)
            is_locked=True 时 remaining_attempts=0
        """
        try:
            fail_count_str = await RedisClient.get(
                f"{CACHE_KEY_ADMIN_LOGIN_FAIL}{username}"
            )
            fail_count = int(fail_count_str) if fail_count_str else 0
        except Exception as e:
            logger.warning(
                "[b14_auth] 读取登录失败计数异常，降级放行: %s", e
            )
            return False, ADMIN_LOGIN_FAIL_MAX, 0

        if fail_count >= ADMIN_LOGIN_FAIL_MAX:
            try:
                ttl = await RedisClient.ttl(
                    f"{CACHE_KEY_ADMIN_LOGIN_FAIL}{username}"
                )
                retry_after = max(0, ttl)
            except Exception:
                retry_after = ADMIN_LOGIN_FAIL_TTL
            return True, 0, retry_after

        remaining = ADMIN_LOGIN_FAIL_MAX - fail_count
        return False, remaining, 0

    @classmethod
    async def _record_login_fail(cls, username: str) -> int:
        """记录一次登录失败，返回当前失败次数"""
        key = f"{CACHE_KEY_ADMIN_LOGIN_FAIL}{username}"
        try:
            count = await RedisClient.incr(key)
            if count == 1:
                await RedisClient.expire(key, ADMIN_LOGIN_FAIL_TTL)
            return count
        except Exception as e:
            logger.warning("[b14_auth] 记录登录失败计数异常: %s", e)
            return 0

    @classmethod
    async def _reset_login_fail(cls, username: str) -> None:
        """重置登录失败计数"""
        try:
            await RedisClient.delete(
                f"{CACHE_KEY_ADMIN_LOGIN_FAIL}{username}"
            )
        except Exception as e:
            logger.warning("[b14_auth] 重置登录失败计数异常: %s", e)

    @classmethod
    async def _add_jwt_blacklist(cls, user_id: int, expires_in: int) -> None:
        """将 user_id 加入 JWT 黑名单（best-effort，失败不阻塞）

        注：当前 B01-B13 的 JwtAuthGuard.verify_token 未感知黑名单，
        此处仅记录，B14 自有接口可通过 is_jwt_blacklisted() 主动校验
        """
        try:
            key = f"{CACHE_KEY_ADMIN_JWT_BLACKLIST}{user_id}"
            await RedisClient.set(key, "1", expire=expires_in)
        except Exception as e:
            logger.warning(
                "[b14_auth] 写入 JWT 黑名单失败 user_id=%s: %s", user_id, e
            )

    @classmethod
    async def is_jwt_blacklisted(cls, user_id: int) -> bool:
        """检查 user_id 是否在 JWT 黑名单中"""
        try:
            val = await RedisClient.get(
                f"{CACHE_KEY_ADMIN_JWT_BLACKLIST}{user_id}"
            )
            return val is not None
        except Exception:
            return False

    @classmethod
    async def _get_jwt_expires_in(cls) -> int:
        """获取 JWT 过期时间（动态配置，降级 EnvConfig）"""
        try:
            return await B14ConfigUtil.get_int(
                "admin_jwt_expires_in",
                default=None,  # 触发注册表默认值
            )
        except Exception:
            from src.config.env_config import EnvConfig

            return EnvConfig.JWT_EXPIRES_IN

    @classmethod
    def _create_token(cls, user: AdminUser, expires_in: int) -> str:
        """生成 JWT token

        临时调整 JwtAuthGuard._expires_in，避免修改基线类的初始化逻辑
        """
        # 保存原值，生成后恢复（线程不安全但同步调用，FastAPI 单请求内安全）
        original_expires = JwtAuthGuard._expires_in
        try:
            JwtAuthGuard._expires_in = expires_in
            return JwtAuthGuard.create_token(
                user_id=user.id,
                username=user.username,
                role_id=user.role_id,
            )
        finally:
            JwtAuthGuard._expires_in = original_expires

    @staticmethod
    def _parse_permissions(permissions_str: str) -> List[str]:
        """解析角色 permissions JSON 字符串为列表"""
        if not permissions_str:
            return []
        try:
            perms = json.loads(permissions_str)
            if isinstance(perms, list):
                return [str(p) for p in perms]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

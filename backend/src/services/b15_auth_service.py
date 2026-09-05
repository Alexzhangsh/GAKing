# @ai-generated
"""
B15 增强认证 Service（登出 JWT 销毁 + 密码重置黑名单集成）
新建文件，不修改 B01-B14 任何基线 service

与 B14AuthService 的关系：
- 本 Service 提供 B14AuthService 的增强版本
- 登出时主动将 JWT 加入黑名单（原 B14 登出仅记录审计日志）
- 密码重置后黑名单由 B14AuthService 已实现，本 Service 新增登出黑名单功能
- 跨域调用：B14 接口仍正常工作，B15 中间件自动拦截并校验黑名单
"""
import logging
from typing import Any, Dict

from src.common.b14_audit_util import AuditLogger
from src.common.b14_password_util import B14PasswordUtil
from src.common.redis_client import RedisClient
from src.config.b14_constants import (
    CACHE_KEY_ADMIN_JWT_BLACKLIST,
    AuditAction,
    AuditTargetType,
)
from src.dao.admin_user_dao import AdminUserDAO
from src.db.init_db import DatabaseManager

logger = logging.getLogger("service.b15_auth")


class B15AuthService:
    """B15 增强认证服务（登出/改密/黑名单）"""

    @classmethod
    async def logout(
        cls,
        user_id: int,
        username: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> bool:
        """管理员登出（销毁 JWT：加入黑名单）
        
        与 B14AuthService 不同，本方法主动将 user_id 加入 JWT 黑名单，
        使该用户当前所有 JWT token 立即失效（强制下线）。

        Args:
            user_id: 管理员ID
            username: 管理员用户名
            ip_address: 客户端 IP
            user_agent: User-Agent
        Returns:
            True-登出成功
        """
        # 1. 加入 JWT 黑名单（24小时过期，覆盖 JWT 正常有效期）
        await cls._add_jwt_blacklist(user_id, expires_in=86400)

        # 2. 记录审计日志（异常不阻塞主流程）
        try:
            await AuditLogger.log(
                action=AuditAction.ADMIN_LOGOUT,
                target_type=AuditTargetType.LOGIN,
                target_id=user_id,
                details={"username": username, "jwt_blacklisted": True},
                user_id=user_id,
                user_name=username,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.warning(
                "[b15_auth] 登出审计日志写入失败 user_id=%s: %s", user_id, e
            )

        logger.info("[b15_auth] 登出成功 user_id=%s JWT 已加入黑名单", user_id)
        return True

    @classmethod
    async def change_password(
        cls,
        user_id: int,
        old_password: str,
        new_password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> bool:
        """管理员自助修改密码（增强版：校验原密码 + 更新哈希 + JWT 黑名单）

        Args:
            user_id: 管理员ID
            old_password: 原密码
            new_password: 新密码（至少 8 位）
            ip_address: 客户端 IP
            user_agent: User-Agent
        Returns:
            True-修改成功
        Raises:
            ValueError: 新旧密码相同 / 原密码错误 / 用户不存在
        """
        if old_password == new_password:
            raise ValueError("新密码不能与原密码相同")

        if len(new_password) < 8:
            raise ValueError("新密码长度不能少于 8 位")

        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            user = await user_dao.get_by_id(user_id)
            if user is None:
                raise ValueError("用户不存在")

            # 校验原密码
            if not B14PasswordUtil.verify_password(old_password, user.password):
                logger.warning(
                    "[b15_auth] 修改密码失败：原密码错误 user_id=%s", user_id
                )
                raise ValueError("原密码错误")

            # 哈希新密码 + 更新
            new_hash = B14PasswordUtil.hash_password(new_password)
            await user_dao.update_by_id(user_id, {"password": new_hash})

        # 加入 JWT 黑名单（强制旧 token 失效）
        await cls._add_jwt_blacklist(user_id, expires_in=86400)

        # 记录审计日志（异常不阻塞主流程）
        user_name = user.real_name or user.username
        try:
            await AuditLogger.log(
                action=AuditAction.PASSWORD_RESET,
                target_type=AuditTargetType.ADMIN_USER,
                target_id=user_id,
                details={"reason": "self_change", "jwt_blacklisted": True},
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.warning(
                "[b15_auth] 修改密码审计日志写入失败 user_id=%s: %s", user_id, e
            )

        logger.info("[b15_auth] 修改密码成功 user_id=%s", user_id)
        return True

    # ════════════════════════════════════════════════════
    # 内部工具方法
    # ════════════════════════════════════════════════════

    @classmethod
    async def _add_jwt_blacklist(cls, user_id: int, expires_in: int) -> None:
        """将 user_id 加入 JWT 黑名单

        Args:
            user_id: 管理员ID
            expires_in: 黑名单过期时间（秒）
        """
        try:
            key = f"{CACHE_KEY_ADMIN_JWT_BLACKLIST}{user_id}"
            await RedisClient.set(key, "1", expire=expires_in)
        except Exception as e:
            logger.warning(
                "[b15_auth] 写入 JWT 黑名单失败 user_id=%s: %s", user_id, e
            )
# @ai-generated
"""
审计日志工具（B14 新建，不修改 B01-B13 基线）
提供审计日志写入 + 敏感数据脱敏 + 装饰器封装

设计要点：
1. AuditLogger.log() —— 同步 await DAO 写入 + try/except 吞异常（参考 B11 _log_review 模式）
   日志失败不阻塞主业务流程，仅记 warn
2. sanitize_details() —— 脱敏 password/token/secret 等敏感字段
3. @audit_action(action, target_type) —— 装饰器，包裹 B14 新增 endpoint，自动记录审计日志
   从 request.state（中间件预解析）或 kwargs 取操作人信息
"""
import functools
import json
import logging
from typing import Any, Callable, Dict, Optional

from fastapi import Request

from src.config.b14_constants import SENSITIVE_FIELD_PATTERNS
from src.dao.audit_log_dao import AuditLogDAO
from src.db.init_db import DatabaseManager

logger = logging.getLogger("common.b14_audit")


class AuditLogger:
    """审计日志写入工具（fire-and-forget，失败不阻塞业务）"""

    @classmethod
    async def log(
        cls,
        action: str,
        target_type: str = "",
        target_id: int = 0,
        details: Any = None,
        user_id: int = 0,
        user_name: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> None:
        """写入一条审计日志

        S04 P2-2 优化：当 user_name 为空但 user_id 有效时，自动从数据库
        查询管理员真实姓名补齐，确保审计日志可读性。

        Args:
            action: 操作动作（AuditAction 枚举值）
            target_type: 目标类型（AuditTargetType 枚举值）
            target_id: 目标ID
            details: 操作详情（dict/str，自动脱敏后转 JSON 字符串）
            user_id: 操作人ID（0 表示匿名/未认证）
            user_name: 操作人姓名
            ip_address: IP 地址
            user_agent: User Agent
        """
        try:
            # S04 P2-2：user_name 为空时按 user_id 补齐
            if not user_name and user_id > 0:
                user_name = await cls._resolve_user_name(user_id)

            # 脱敏 + 序列化 details
            details_str = cls._serialize_details(details)

            async with DatabaseManager.get_session() as session:
                dao = AuditLogDAO(session)
                await dao.create_log(
                    user_id=user_id,
                    user_name=user_name,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    details=details_str,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except Exception as e:
            # 审计日志失败不阻塞主业务，仅记 warn
            logger.warning(
                "[audit] 审计日志写入失败 action=%s target_id=%s: %s",
                action,
                target_id,
                e,
            )

    @staticmethod
    async def _resolve_user_name(user_id: int) -> str:
        """按 user_id 查询管理员真实姓名（审计日志补齐用）

        S04 P2-2：从 admin_user 表查询 real_name，兜底用 username。
        查询失败时不抛异常，返回空字符串。
        """
        try:
            from sqlalchemy import select
            from src.db.init_db import DatabaseManager
            from src.db.models import AdminUser

            async with DatabaseManager.get_session() as session:
                stmt = select(AdminUser.real_name, AdminUser.username).where(
                    AdminUser.id == user_id,
                    AdminUser.is_delete == False,  # noqa: E712
                )
                result = await session.execute(stmt)
                row = result.one_or_none()
                if row:
                    return row[0] or row[1] or ""
                return ""
        except Exception:
            return ""

    @classmethod
    def _serialize_details(cls, details: Any) -> str:
        """序列化 + 脱敏 details 为 JSON 字符串"""
        if details is None:
            return ""
        if isinstance(details, str):
            return details[:2000]  # 限制长度
        if isinstance(details, dict):
            sanitized = cls.sanitize_details(details)
            return json.dumps(sanitized, ensure_ascii=False, default=str)[:2000]
        # 其他类型转字符串
        return str(details)[:2000]

    @staticmethod
    def sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏字典中的敏感字段（password/token/secret 等）

        Args:
            details: 原始字典
        Returns:
            脱敏后的字典副本（敏感字段值替换为 ***）
        """
        if not isinstance(details, dict):
            return details
        sanitized: Dict[str, Any] = {}
        for key, value in details.items():
            key_lower = str(key).lower()
            if any(p in key_lower for p in SENSITIVE_FIELD_PATTERNS):
                sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = AuditLogger.sanitize_details(value)
            else:
                sanitized[key] = value
        return sanitized

    @staticmethod
    def get_client_ip(request: Request) -> str:
        """从请求中提取客户端 IP（X-Forwarded-For 首段优先）"""
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host or "unknown"
        return "unknown"

    @staticmethod
    def get_user_agent(request: Request) -> str:
        """从请求中提取 User-Agent"""
        return request.headers.get("User-Agent", "")[:512]


def audit_action(
    action: str,
    target_type: str = "endpoint",
) -> Callable:
    """审计装饰器：包裹 async endpoint，自动记录审计日志

    从 endpoint kwargs 中提取 request（Request）和 admin_user_id（int）
    适用于 B14 新增的写操作 endpoint

    用法：
        @router.post("/roles")
        @audit_action(AuditAction.ROLE_CREATE, AuditTargetType.ROLE)
        async def create_role(request: Request, admin_user_id: int = Depends(...), ...):
            ...

    Args:
        action: AuditAction 枚举值
        target_type: AuditTargetType 枚举值
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            admin_user_id: int = int(kwargs.get("admin_user_id", 0) or 0)

            # 执行原函数
            result = await func(*args, **kwargs)

            # 记录审计日志（best-effort，失败不阻塞）
            if request is not None:
                try:
                    user_name = getattr(request.state, "user_name", "") or ""
                    ip = AuditLogger.get_client_ip(request)
                    ua = AuditLogger.get_user_agent(request)
                    await AuditLogger.log(
                        action=action,
                        target_type=target_type,
                        target_id=0,
                        details={"path": request.url.path, "method": request.method},
                        user_id=admin_user_id,
                        user_name=user_name,
                        ip_address=ip,
                        user_agent=ua,
                    )
                except Exception as e:
                    logger.warning("[audit] 装饰器审计记录失败: %s", e)

            return result

        return wrapper

    return decorator

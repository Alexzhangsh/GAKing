# @ai-generated
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config.env_config import EnvConfig
from src.db.init_db import DatabaseManager
from src.db.models import AdminUser, AdminRole
from sqlalchemy import select


class JwtAuthGuard:
    _secret: str = ""
    _expires_in: int = 3600

    @classmethod
    def initialize(cls) -> None:
        cls._secret = EnvConfig.JWT_SECRET
        cls._expires_in = EnvConfig.JWT_EXPIRES_IN

    @classmethod
    def create_token(cls, user_id: int, username: str, role_id: int = 1) -> str:
        payload = {
            "user_id": user_id,
            "username": username,
            "role_id": role_id,
            "exp": datetime.utcnow() + timedelta(seconds=cls._expires_in),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, cls._secret, algorithm="HS256")

    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, cls._secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @classmethod
    def refresh_token(cls, token: str) -> Optional[str]:
        payload = cls.verify_token(token)
        if not payload:
            return None

        new_payload = {
            "user_id": payload["user_id"],
            "username": payload["username"],
            "role_id": payload["role_id"],
            "exp": datetime.now() + timedelta(seconds=cls._expires_in),
            "iat": datetime.now(),
        }
        return jwt.encode(new_payload, cls._secret, algorithm="HS256")


class RbacUtil:
    @classmethod
    async def get_user_permissions(cls, user_id: int, role_id: int = 0) -> List[str]:
        # C端用户 token 的 role_id=0，与后台管理员 ID 空间重叠，
        # 必须直接拒绝，防止 C 端用户借 ID 碰撞越权访问后台
        if role_id == 0:
            return []

        async with DatabaseManager.get_session() as session:
            result = await session.execute(
                select(AdminUser).where(
                    AdminUser.id == user_id, AdminUser.is_delete == False
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                return []

            result = await session.execute(
                select(AdminRole).where(
                    AdminRole.id == user.role_id, AdminRole.is_delete == False
                )
            )
            role = result.scalar_one_or_none()

            if not role or not role.permissions:
                return []

            try:
                import json

                permissions = json.loads(role.permissions)
                if isinstance(permissions, list):
                    return permissions
            except (json.JSONDecodeError, TypeError):
                pass

            return []

    @classmethod
    async def has_permission(
        cls, user_id: int, permission: str, role_id: int = 0
    ) -> bool:
        permissions = await cls.get_user_permissions(user_id, role_id)
        # 通配符 "*" 表示超级管理员，拥有全部权限（向后兼容：无 "*" 时按精确匹配）
        if "*" in permissions:
            return True
        return permission in permissions

    @classmethod
    async def has_any_permission(
        cls, user_id: int, permissions: List[str], role_id: int = 0
    ) -> bool:
        user_permissions = await cls.get_user_permissions(user_id, role_id)
        if "*" in user_permissions:
            return True
        return any(p in user_permissions for p in permissions)

    @classmethod
    async def has_all_permissions(
        cls, user_id: int, permissions: List[str], role_id: int = 0
    ) -> bool:
        user_permissions = await cls.get_user_permissions(user_id, role_id)
        if "*" in user_permissions:
            return True
        return all(p in user_permissions for p in permissions)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
):
    token = credentials.credentials
    payload = JwtAuthGuard.verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def require_permission(permission: str):
    async def dependency(payload: dict = Depends(get_current_user)):
        role_id = int(payload.get("role_id", 0) or 0)
        has_perm = await RbacUtil.has_permission(
            payload["user_id"], permission, role_id=role_id
        )
        if not has_perm:
            raise HTTPException(status_code=403, detail="Permission denied")
        return payload

    return dependency


def require_any_permission(permissions: List[str]):
    async def dependency(payload: dict = Depends(get_current_user)):
        role_id = int(payload.get("role_id", 0) or 0)
        has_perm = await RbacUtil.has_any_permission(
            payload["user_id"], permissions, role_id=role_id
        )
        if not has_perm:
            raise HTTPException(status_code=403, detail="Permission denied")
        return payload

    return dependency


class AuthUtil(JwtAuthGuard):
    pass

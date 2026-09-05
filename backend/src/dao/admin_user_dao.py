# @ai-generated
"""
后台管理员 DAO（B14 新建，不修改 B01-B13 基线）
继承 BaseDAO；操作 src/db/models.py 中的 AdminUser 模型
提供按用户名查询、关联角色信息查询、分页筛选
仅做数据存取，不含业务逻辑
"""
import logging
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.db.models import AdminRole, AdminUser

logger = logging.getLogger("dao.admin_user")


class AdminUserDAO(BaseDAO):
    """后台管理员 DAO"""

    model_class = AdminUser

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_username(self, username: str) -> Optional[AdminUser]:
        """按用户名查询（自动过滤软删除，登录校验用）

        Args:
            username: 用户名
        Returns:
            管理员实例 或 None
        """
        stmt = self._active_query().where(AdminUser.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_role(self, user_id: int) -> Optional[dict]:
        """查询管理员详情（关联角色信息）

        Args:
            user_id: 管理员ID
        Returns:
            {user 字段 + role_name + role_permissions} 或 None
        """
        stmt = (
            select(AdminUser, AdminRole)
            .outerjoin(AdminRole, AdminRole.id == AdminUser.role_id)
            .where(
                and_(
                    AdminUser.id == user_id,
                    AdminUser.is_delete == False,  # noqa: E712
                )
            )
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        user, role = row
        data = {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "phone": user.phone,
            "email": user.email,
            "role_id": user.role_id,
            "status": user.status,
            "create_time": user.create_time.strftime("%Y-%m-%d %H:%M:%S") if user.create_time else None,
            "update_time": user.update_time.strftime("%Y-%m-%d %H:%M:%S") if user.update_time else None,
            "role_name": role.role_name if role else "",
            "role_permissions": role.permissions if role else "",
        }
        return data

    async def list_with_role_info(
        self,
        username: Optional[str] = None,
        role_id: Optional[int] = None,
        status: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        """分页查询管理员列表（关联角色名）

        Args:
            username: 用户名模糊筛选
            role_id: 角色ID筛选
            status: 状态筛选
            page: 页码
            page_size: 每页条数
        Returns:
            (管理员列表[dict], 总数)
        """
        from sqlalchemy import func

        # 主查询
        stmt = (
            select(AdminUser, AdminRole)
            .outerjoin(AdminRole, AdminRole.id == AdminUser.role_id)
            .where(AdminUser.is_delete == False)  # noqa: E712
        )
        conditions = []
        if username:
            conditions.append(AdminUser.username.like(f"%{username}%"))
        if role_id is not None:
            conditions.append(AdminUser.role_id == role_id)
        if status is not None:
            conditions.append(AdminUser.status == status)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 总数
        count_stmt = select(func.count()).select_from(
            select(AdminUser).where(AdminUser.is_delete == False)  # noqa: E712
        )
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        page_stmt = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_stmt)
        rows = result.all()

        items = []
        for user, role in rows:
            items.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "real_name": user.real_name,
                    "phone": user.phone,
                    "email": user.email,
                    "role_id": user.role_id,
                    "status": user.status,
                    "create_time": user.create_time.strftime("%Y-%m-%d %H:%M:%S") if user.create_time else None,
                    "role_name": role.role_name if role else "",
                }
            )
        return items, total

    async def get_password(self, user_id: int) -> Optional[str]:
        """获取管理员密码哈希（登录/改密校验用，避免全字段查询泄露）

        Args:
            user_id: 管理员ID
        Returns:
            密码哈希 或 None
        """
        stmt = (
            self._active_query()
            .where(AdminUser.id == user_id)
            .with_only_columns(AdminUser.password)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return row[0] if row else None

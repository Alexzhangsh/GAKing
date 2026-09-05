# @ai-generated
"""
后台角色 DAO（B14 新建，不修改 B01-B13 基线）
继承 BaseDAO；操作 src/db/models.py 中的 AdminRole 模型
提供按角色名查询、按状态查询、分页筛选
仅做数据存取，不含业务逻辑
"""
import logging
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.db.models import AdminRole

logger = logging.getLogger("dao.admin_role")


class AdminRoleDAO(BaseDAO):
    """后台角色 DAO"""

    model_class = AdminRole

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_role_name(self, role_name: str) -> Optional[AdminRole]:
        """按角色名查询（自动过滤软删除）

        Args:
            role_name: 角色名称
        Returns:
            角色实例 或 None
        """
        stmt = self._active_query().where(AdminRole.role_name == role_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_status(self, status: Optional[bool] = None) -> List[AdminRole]:
        """按状态查询角色列表

        Args:
            status: True-启用 False-禁用 None-全部
        Returns:
            角色列表
        """
        stmt = self._active_query()
        if status is not None:
            stmt = stmt.where(AdminRole.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_filters(
        self,
        role_name: Optional[str] = None,
        status: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        """多条件分页查询角色

        Args:
            role_name: 角色名模糊筛选（None 不过滤）
            status: 状态筛选
            page: 页码
            page_size: 每页条数
        Returns:
            (角色列表, 总数)
        """
        filters = {}
        if status is not None:
            filters["status"] = status
        # role_name 用 list_all 等值不适用，这里用 paginate_list + 后置过滤
        items, total = await self.paginate_list(
            page=page, page_size=page_size, filters=filters or None
        )
        if role_name:
            items = [r for r in items if role_name in (r.role_name or "")]
            total = len(items)
        return items, total

    async def count_admin_users_by_role(self, role_id: int) -> int:
        """统计绑定该角色的管理员数量（删除角色前校验用）

        Args:
            role_id: 角色ID
        Returns:
            管理员数量
        """
        from src.db.models import AdminUser

        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(AdminUser)
            .where(
                and_(
                    AdminUser.role_id == role_id,
                    AdminUser.is_delete == False,  # noqa: E712
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

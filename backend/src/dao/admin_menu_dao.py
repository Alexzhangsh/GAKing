# @ai-generated
"""
后台菜单 DAO（B14 新建，不修改 B01-B13 基线）
继承 BaseDAO；提供按编码查询、子菜单查询、菜单树构建、按类型查询
仅做数据存取，不含业务逻辑
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.system.admin_menu_model import AdminMenu

logger = logging.getLogger("dao.admin_menu")


class AdminMenuDAO(BaseDAO):
    """后台菜单 DAO"""

    model_class = AdminMenu

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_menu_code(self, menu_code: str) -> Optional[AdminMenu]:
        """按菜单编码查询（自动过滤软删除）

        Args:
            menu_code: 菜单唯一编码
        Returns:
            菜单实例 或 None
        """
        stmt = self._active_query().where(AdminMenu.menu_code == menu_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_children(self, parent_id: int) -> List[AdminMenu]:
        """查询指定父菜单下的所有子菜单（自动过滤软删除）

        Args:
            parent_id: 父菜单ID
        Returns:
            子菜单列表（按 sort_num 升序）
        """
        stmt = (
            self._active_query()
            .where(AdminMenu.parent_id == parent_id)
            .order_by(AdminMenu.sort_num.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_type(self, menu_type: str) -> List[AdminMenu]:
        """按菜单类型查询

        Args:
            menu_type: directory / menu / button
        Returns:
            菜单列表（按 sort_num 升序）
        """
        stmt = (
            self._active_query()
            .where(AdminMenu.menu_type == menu_type)
            .order_by(AdminMenu.sort_num.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_enabled(self) -> List[AdminMenu]:
        """查询所有启用状态的菜单（构建菜单树用）

        Returns:
            启用菜单列表（按 sort_num 升序）
        """
        stmt = (
            self._active_query()
            .where(AdminMenu.status == True)  # noqa: E712
            .order_by(AdminMenu.sort_num.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def build_tree(self) -> List[Dict[str, Any]]:
        """构建完整菜单树结构（仅启用菜单）

        Returns:
            嵌套树结构列表，每个节点含 menu 信息 + children 子节点列表
        """
        all_menus = await self.list_all_enabled()
        return self._build_tree_recursive(all_menus, parent_id=0)

    @staticmethod
    def _build_tree_recursive(
        menus: List[AdminMenu], parent_id: int
    ) -> List[Dict[str, Any]]:
        """递归构建菜单树"""
        tree: List[Dict[str, Any]] = []
        for menu in menus:
            if menu.parent_id == parent_id:
                node = menu.to_dict()
                node["children"] = AdminMenuDAO._build_tree_recursive(menus, menu.id)
                tree.append(node)
        return tree

    async def has_children(self, menu_id: int) -> bool:
        """判断指定菜单是否有子菜单（删除前校验用）

        Args:
            menu_id: 菜单ID
        Returns:
            True-有子菜单 False-无子菜单
        """
        stmt = self._active_query().where(AdminMenu.parent_id == menu_id)
        result = await self.session.execute(stmt)
        return result.first() is not None

# @ai-generated
"""
B14 RBAC 权限管理 Service（菜单 / 角色 / 管理员账号）
新建独立文件，不修改 B01-B13 任何基线 service

业务范围：
1. 菜单管理：CRUD + 树构建（菜单-角色绑定通过 AdminRole.permissions JSON 实现）
2. 角色管理：CRUD + 权限码分配 + 删除前管理员占用校验
3. 管理员账号管理：CRUD + 密码重置 + 角色/状态变更

设计要点：
- 菜单 menu_code 同时作为权限码，存入 AdminRole.permissions JSON 数组
- 角色 permissions JSON 数组：["*", "order:sync", "menu:order", ...]
- 管理员账号密码：B14PasswordUtil 哈希存储，禁止明文
- 删除前校验：角色被管理员绑定时拒绝删除；菜单有子菜单时拒绝删除
- 写操作后由 API 层 audit_action 装饰器补全审计日志
- 业务异常统一 ValueError，API 层由 handle_service_exception 转 400
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.b14_audit_util import AuditLogger
from src.common.b14_password_util import B14PasswordUtil
from src.config.b14_constants import (
    ALL_ADMIN_PERMISSIONS,
    AuditAction,
    AuditTargetType,
    DEFAULT_SUPER_ADMIN_ROLE_NAME,
    DEFAULT_SUPER_ADMIN_USERNAME,
)
from src.dao.admin_menu_dao import AdminMenuDAO
from src.dao.admin_role_dao import AdminRoleDAO
from src.dao.admin_user_dao import AdminUserDAO
from src.db.init_db import DatabaseManager
from src.db.models import AdminRole, AdminUser
from src.models.system.admin_menu_model import AdminMenu
from src.schemas.b14_rbac import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    MenuCreateRequest,
    MenuUpdateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
)

logger = logging.getLogger("service.b14_rbac")


class B14RbacService:
    """RBAC 权限管理服务（菜单 + 角色 + 管理员账号）"""

    # ════════════════════════════════════════════════════════════
    # 1. 菜单管理
    # ════════════════════════════════════════════════════════════

    @classmethod
    async def create_menu(cls, request: MenuCreateRequest) -> AdminMenu:
        """新增菜单

        Args:
            request: 菜单创建请求体
        Returns:
            创建的菜单实例
        Raises:
            ValueError: menu_code 已存在 / 父菜单不存在
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            # 校验 menu_code 唯一
            existing = await dao.get_by_menu_code(request.menu_code)
            if existing is not None:
                raise ValueError(f"菜单编码 '{request.menu_code}' 已存在")

            # 校验父菜单存在（parent_id > 0 时）
            if request.parent_id > 0:
                parent = await dao.get_by_id(request.parent_id)
                if parent is None:
                    raise ValueError(f"父菜单ID {request.parent_id} 不存在")

            menu = await dao.create(
                {
                    "parent_id": request.parent_id,
                    "menu_name": request.menu_name,
                    "menu_code": request.menu_code,
                    "menu_path": request.menu_path,
                    "menu_icon": request.menu_icon,
                    "menu_type": request.menu_type,
                    "sort_num": request.sort_num,
                    "status": request.status,
                    "remark": request.remark,
                }
            )
            logger.info(
                "[b14_rbac] 新增菜单 menu_code=%s name=%s",
                request.menu_code,
                request.menu_name,
            )
            return menu

    @classmethod
    async def update_menu(
        cls, menu_id: int, request: MenuUpdateRequest
    ) -> AdminMenu:
        """更新菜单（menu_code 不可改）

        Args:
            menu_id: 菜单ID
            request: 更新请求体
        Returns:
            更新后的菜单实例
        Raises:
            ValueError: 菜单不存在 / 父菜单不存在 / 形成环
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            menu = await dao.get_by_id(menu_id)
            if menu is None:
                raise ValueError(f"菜单ID {menu_id} 不存在")

            # 校验父菜单存在 + 不形成环
            if request.parent_id is not None and request.parent_id > 0:
                if request.parent_id == menu_id:
                    raise ValueError("父菜单不能为自身")
                parent = await dao.get_by_id(request.parent_id)
                if parent is None:
                    raise ValueError(f"父菜单ID {request.parent_id} 不存在")
                # 简单环检测：不允许将自己设为父菜单的祖先（这里仅做单层校验）
                if request.parent_id != menu.parent_id:
                    # 检查新父菜单是否是当前菜单的子孙（避免环）
                    if await cls._is_descendant(dao, menu_id, request.parent_id):
                        raise ValueError("不能将子菜单设为父菜单（会形成环）")

            update_data: Dict[str, Any] = {}
            for field in (
                "parent_id",
                "menu_name",
                "menu_path",
                "menu_icon",
                "menu_type",
                "sort_num",
                "status",
                "remark",
            ):
                value = getattr(request, field, None)
                if value is not None:
                    update_data[field] = value

            if not update_data:
                return menu

            updated = await dao.update_by_id(menu_id, update_data)
            logger.info("[b14_rbac] 更新菜单 menu_id=%s", menu_id)
            return updated

    @classmethod
    async def delete_menu(cls, menu_id: int) -> bool:
        """删除菜单（软删除）

        Args:
            menu_id: 菜单ID
        Returns:
            True-删除成功
        Raises:
            ValueError: 菜单不存在 / 有子菜单
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            menu = await dao.get_by_id(menu_id)
            if menu is None:
                raise ValueError(f"菜单ID {menu_id} 不存在")

            # 校验无子菜单
            has_children = await dao.has_children(menu_id)
            if has_children:
                raise ValueError(f"菜单ID {menu_id} 存在子菜单，请先删除子菜单")

            await dao.logic_delete_by_id(menu_id)
            logger.info("[b14_rbac] 删除菜单 menu_id=%s", menu_id)
            return True

    @classmethod
    async def get_menu(cls, menu_id: int) -> Optional[AdminMenu]:
        """获取菜单详情"""
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            return await dao.get_by_id(menu_id)

    @classmethod
    async def list_menu_tree(cls) -> List[Dict[str, Any]]:
        """构建启用菜单的树结构（前端渲染用）

        Returns:
            嵌套树结构列表
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            return await dao.build_tree()

    @classmethod
    async def list_all_menus(cls) -> List[AdminMenu]:
        """查询所有菜单（含禁用，管理后台列表用）"""
        async with DatabaseManager.get_session() as session:
            dao = AdminMenuDAO(session)
            return await dao.list_all()

    # ════════════════════════════════════════════════════════════
    # 2. 角色管理
    # ════════════════════════════════════════════════════════════

    @classmethod
    async def create_role(cls, request: RoleCreateRequest) -> AdminRole:
        """新增角色

        Args:
            request: 角色创建请求体
        Returns:
            创建的角色实例
        Raises:
            ValueError: 角色名已存在 / 权限码不在白名单
        """
        # 校验权限码合法性
        cls._validate_permissions(request.permissions)

        async with DatabaseManager.get_session() as session:
            dao = AdminRoleDAO(session)
            # 校验角色名唯一
            existing = await dao.get_by_role_name(request.role_name)
            if existing is not None:
                raise ValueError(f"角色名 '{request.role_name}' 已存在")

            role = await dao.create(
                {
                    "role_name": request.role_name,
                    "role_desc": request.role_desc,
                    "permissions": json.dumps(
                        request.permissions, ensure_ascii=False
                    ),
                    "status": request.status,
                }
            )
            logger.info(
                "[b14_rbac] 新增角色 role_id=%s name=%s",
                role.id,
                request.role_name,
            )
            return role

    @classmethod
    async def update_role(
        cls, role_id: int, request: RoleUpdateRequest
    ) -> AdminRole:
        """更新角色

        Args:
            role_id: 角色ID
            request: 更新请求体
        Returns:
            更新后的角色实例
        Raises:
            ValueError: 角色不存在 / 权限码不合法 / 修改默认超管角色名
        """
        # 校验权限码合法性
        if request.permissions is not None:
            cls._validate_permissions(request.permissions)

        async with DatabaseManager.get_session() as session:
            dao = AdminRoleDAO(session)
            role = await dao.get_by_id(role_id)
            if role is None:
                raise ValueError(f"角色ID {role_id} 不存在")

            # 默认超管角色名不可改
            if (
                role.role_name == DEFAULT_SUPER_ADMIN_ROLE_NAME
                and request.role_name is not None
                and request.role_name != DEFAULT_SUPER_ADMIN_ROLE_NAME
            ):
                raise ValueError(f"默认超管角色 '{DEFAULT_SUPER_ADMIN_ROLE_NAME}' 名称不可修改")

            # 校验角色名唯一（如果改名）
            if (
                request.role_name is not None
                and request.role_name != role.role_name
            ):
                existing = await dao.get_by_role_name(request.role_name)
                if existing is not None:
                    raise ValueError(f"角色名 '{request.role_name}' 已存在")

            update_data: Dict[str, Any] = {}
            if request.role_name is not None:
                update_data["role_name"] = request.role_name
            if request.role_desc is not None:
                update_data["role_desc"] = request.role_desc
            if request.permissions is not None:
                update_data["permissions"] = json.dumps(
                    request.permissions, ensure_ascii=False
                )
            if request.status is not None:
                update_data["status"] = request.status

            if not update_data:
                return role

            updated = await dao.update_by_id(role_id, update_data)
            logger.info("[b14_rbac] 更新角色 role_id=%s", role_id)
            return updated

    @classmethod
    async def delete_role(cls, role_id: int) -> bool:
        """删除角色（软删除）

        Args:
            role_id: 角色ID
        Returns:
            True-删除成功
        Raises:
            ValueError: 角色不存在 / 被管理员绑定 / 默认超管角色不可删
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminRoleDAO(session)
            role = await dao.get_by_id(role_id)
            if role is None:
                raise ValueError(f"角色ID {role_id} 不存在")

            # 默认超管角色不可删
            if role.role_name == DEFAULT_SUPER_ADMIN_ROLE_NAME:
                raise ValueError(
                    f"默认超管角色 '{DEFAULT_SUPER_ADMIN_ROLE_NAME}' 不可删除"
                )

            # 校验无管理员绑定
            user_count = await dao.count_admin_users_by_role(role_id)
            if user_count > 0:
                raise ValueError(
                    f"角色ID {role_id} 仍有 {user_count} 个管理员绑定，请先解绑"
                )

            await dao.logic_delete_by_id(role_id)
            logger.info("[b14_rbac] 删除角色 role_id=%s", role_id)
            return True

    @classmethod
    async def get_role(cls, role_id: int) -> Optional[AdminRole]:
        """获取角色详情"""
        async with DatabaseManager.get_session() as session:
            dao = AdminRoleDAO(session)
            return await dao.get_by_id(role_id)

    @classmethod
    async def list_roles(
        cls,
        page: int = 1,
        page_size: int = 20,
        role_name: Optional[str] = None,
        status: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页查询角色列表（含管理员绑定数）

        Args:
            page: 页码
            page_size: 每页条数
            role_name: 角色名模糊筛选
            status: 状态筛选
        Returns:
            (角色列表[dict], 总数)
        """
        async with DatabaseManager.get_session() as session:
            dao = AdminRoleDAO(session)
            roles, total = await dao.list_with_filters(
                role_name=role_name,
                status=status,
                page=page,
                page_size=page_size,
            )
            items: List[Dict[str, Any]] = []
            for role in roles:
                user_count = await dao.count_admin_users_by_role(role.id)
                items.append(
                    {
                        "id": role.id,
                        "role_name": role.role_name,
                        "role_desc": role.role_desc,
                        "permissions": cls._parse_permissions(role.permissions),
                        "status": role.status,
                        "create_time": role.create_time.strftime("%Y-%m-%d %H:%M:%S") if role.create_time else None,
                        "update_time": role.update_time.strftime("%Y-%m-%d %H:%M:%S") if role.update_time else None,
                        "admin_user_count": user_count,
                    }
                )
            return items, total

    @classmethod
    async def get_all_permissions(cls) -> List[Dict[str, str]]:
        """获取全部权限码字典（前端角色编辑时下发可选项）

        Returns:
            [{code, label, group}, ...]  字段名与前端 PermissionCatalogItem 对齐
        """
        return [
            {
                "code": p["code"],
                "label": p["name"],
                "group": p.get("group", p["module"]),
            }
            for p in ALL_ADMIN_PERMISSIONS
        ]

    # ════════════════════════════════════════════════════════════
    # 3. 管理员账号管理
    # ════════════════════════════════════════════════════════════

    @classmethod
    async def create_admin_user(
        cls, request: AdminUserCreateRequest
    ) -> AdminUser:
        """新增管理员账号

        Args:
            request: 管理员创建请求体
        Returns:
            创建的管理员实例
        Raises:
            ValueError: 用户名已存在 / 角色不存在
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            role_dao = AdminRoleDAO(session)

            # 校验用户名唯一
            existing = await user_dao.get_by_username(request.username)
            if existing is not None:
                raise ValueError(f"用户名 '{request.username}' 已存在")

            # 校验角色存在
            role = await role_dao.get_by_id(request.role_id)
            if role is None:
                raise ValueError(f"角色ID {request.role_id} 不存在")

            # 哈希密码
            password_hash = B14PasswordUtil.hash_password(request.password)

            user = await user_dao.create(
                {
                    "username": request.username,
                    "password": password_hash,
                    "real_name": request.real_name,
                    "phone": request.phone,
                    "email": request.email,
                    "role_id": request.role_id,
                    "status": request.status,
                }
            )
            logger.info(
                "[b14_rbac] 新增管理员 user_id=%s username=%s",
                user.id,
                request.username,
            )
            return user

    @classmethod
    async def update_admin_user(
        cls, user_id: int, request: AdminUserUpdateRequest
    ) -> AdminUser:
        """更新管理员账号（不含密码，密码走重置接口）

        Args:
            user_id: 管理员ID
            request: 更新请求体
        Returns:
            更新后的管理员实例
        Raises:
            ValueError: 用户不存在 / 角色不存在 / 修改默认超管账号状态
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            role_dao = AdminRoleDAO(session)

            user = await user_dao.get_by_id(user_id)
            if user is None:
                raise ValueError(f"管理员ID {user_id} 不存在")

            # 默认超管账号不可禁用
            if (
                user.username == DEFAULT_SUPER_ADMIN_USERNAME
                and request.status is False
            ):
                raise ValueError(
                    f"默认超管账号 '{DEFAULT_SUPER_ADMIN_USERNAME}' 不可禁用"
                )

            # 校验角色存在
            if request.role_id is not None:
                role = await role_dao.get_by_id(request.role_id)
                if role is None:
                    raise ValueError(f"角色ID {request.role_id} 不存在")

            update_data: Dict[str, Any] = {}
            if request.real_name is not None:
                update_data["real_name"] = request.real_name
            if request.phone is not None:
                update_data["phone"] = request.phone
            if request.email is not None:
                update_data["email"] = request.email
            if request.role_id is not None:
                update_data["role_id"] = request.role_id
            if request.status is not None:
                update_data["status"] = request.status

            if not update_data:
                return user

            updated = await user_dao.update_by_id(user_id, update_data)
            logger.info("[b14_rbac] 更新管理员 user_id=%s", user_id)
            return updated

    @classmethod
    async def delete_admin_user(cls, user_id: int) -> bool:
        """删除管理员账号（软删除）

        Args:
            user_id: 管理员ID
        Returns:
            True-删除成功
        Raises:
            ValueError: 用户不存在 / 默认超管账号不可删
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            user = await user_dao.get_by_id(user_id)
            if user is None:
                raise ValueError(f"管理员ID {user_id} 不存在")

            if user.username == DEFAULT_SUPER_ADMIN_USERNAME:
                raise ValueError(
                    f"默认超管账号 '{DEFAULT_SUPER_ADMIN_USERNAME}' 不可删除"
                )

            await user_dao.logic_delete_by_id(user_id)
            logger.info("[b14_rbac] 删除管理员 user_id=%s", user_id)
            return True

    @classmethod
    async def get_admin_user_detail(cls, user_id: int) -> Optional[Dict[str, Any]]:
        """获取管理员详情（含角色信息）

        Args:
            user_id: 管理员ID
        Returns:
            管理员详情字典 或 None
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            data = await user_dao.get_with_role(user_id)
            if data is None:
                return None
            data["permissions"] = cls._parse_permissions(
                data.pop("role_permissions", "")
            )
            return data

    @classmethod
    async def list_admin_users(
        cls,
        page: int = 1,
        page_size: int = 20,
        username: Optional[str] = None,
        role_id: Optional[int] = None,
        status: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页查询管理员列表（含角色名）

        Args:
            page: 页码
            page_size: 每页条数
            username: 用户名模糊筛选
            role_id: 角色ID筛选
            status: 状态筛选
        Returns:
            (管理员列表[dict], 总数)
        """
        async with DatabaseManager.get_session() as session:
            user_dao = AdminUserDAO(session)
            return await user_dao.list_with_role_info(
                username=username,
                role_id=role_id,
                status=status,
                page=page,
                page_size=page_size,
            )

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
        """特权用户重置他人密码（调用 B14AuthService）

        注：此处直接委托 B14AuthService.reset_password，避免循环依赖
        """
        from src.services.b14_auth_service import B14AuthService

        return await B14AuthService.reset_password(
            target_user_id=target_user_id,
            new_password=new_password,
            operator_id=operator_id,
            operator_name=operator_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ════════════════════════════════════════════════════════════
    # 内部工具方法
    # ════════════════════════════════════════════════════════════

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

    @staticmethod
    def _validate_permissions(permissions: List[str]) -> None:
        """校验权限码合法性

        Args:
            permissions: 权限码列表
        Raises:
            ValueError: 权限码不在白名单
        """
        # 超管通配符 * 直接放行
        valid_codes = {p["code"] for p in ALL_ADMIN_PERMISSIONS}
        valid_codes.add("*")  # 超管通配符

        for perm in permissions:
            if perm not in valid_codes:
                raise ValueError(
                    f"权限码 '{perm}' 不在合法权限码白名单内"
                )

    @classmethod
    async def _is_descendant(
        cls, dao: AdminMenuDAO, ancestor_id: int, candidate_id: int
    ) -> bool:
        """检查 candidate_id 是否是 ancestor_id 的子孙（递归）

        Args:
            dao: AdminMenuDAO
            ancestor_id: 祖先菜单ID
            candidate_id: 候选菜单ID
        Returns:
            True-candidate 是 ancestor 的子孙
        """
        children = await dao.list_children(ancestor_id)
        for child in children:
            if child.id == candidate_id:
                return True
            if await cls._is_descendant(dao, child.id, candidate_id):
                return True
        return False

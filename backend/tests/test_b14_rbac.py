# @ai-generated
"""
B14 RBAC 权限管理服务单元测试
覆盖：
1. 菜单 CRUD：create（编码重复/父菜单不存在）、update（不存在/环检测）、delete（有子菜单）、get、tree
2. 角色 CRUD：create（名称重复/权限码非法）、update（不存在/超管改名/名称重复）、delete（有绑定/超管不可删）、get、list
3. 管理员账号 CRUD：create（用户名重复/角色不存在）、update（不存在/超管禁用/角色不存在）、delete（超管不可删）、get、list
4. 权限校验：_validate_permissions（合法/非法）、_parse_permissions（合法/空/非法）
5. 越权访问场景：无权限码被拦截

覆盖率目标：单文件 ≥90%
"""
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b14_constants import (
    DEFAULT_SUPER_ADMIN_ROLE_NAME,
    DEFAULT_SUPER_ADMIN_USERNAME,
)
from src.schemas.b14_rbac import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    MenuCreateRequest,
    MenuUpdateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
)
from src.services.b14_rbac_service import B14RbacService


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_menu(menu_id=1, menu_code="menu:order", parent_id=0, status=True):
    m = MagicMock()
    m.id = menu_id
    m.parent_id = parent_id
    m.menu_name = "订单管理"
    m.menu_code = menu_code
    m.menu_path = "/order"
    m.menu_icon = "order"
    m.menu_type = "menu"
    m.sort_num = 1
    m.status = status
    m.remark = ""
    m.create_time = None
    m.update_time = None
    return m


def _make_role(role_id=1, role_name="运营管理员", permissions='["order:sync"]', status=True):
    r = MagicMock()
    r.id = role_id
    r.role_name = role_name
    r.role_desc = "运营"
    r.permissions = permissions
    r.status = status
    r.create_time = None
    r.update_time = None
    return r


def _make_admin_user(user_id=1, username="operator1", role_id=2, status=True):
    u = MagicMock()
    u.id = user_id
    u.username = username
    u.password = "hashed"
    u.real_name = "运营员"
    u.phone = ""
    u.email = ""
    u.role_id = role_id
    u.status = status
    u.create_time = None
    u.update_time = None
    return u


def _make_session_cm():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return session, cm


# ══════════════════════════════════════════════════════
# 1. 菜单管理测试
# ══════════════════════════════════════════════════════


class TestB14Menu:
    """菜单 CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_menu_success(self):
        """新增菜单成功"""
        menu = _make_menu()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_menu_code.return_value = None
        mock_dao.create.return_value = menu

        request = MenuCreateRequest(
            menu_name="订单管理", menu_code="menu:order", menu_path="/order"
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.create_menu(request)
        assert result.menu_code == "menu:order"

    @pytest.mark.asyncio
    async def test_create_menu_code_exists(self):
        """菜单编码已存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_menu_code.return_value = _make_menu()

        request = MenuCreateRequest(menu_name="订单", menu_code="menu:order")

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="已存在"):
                await B14RbacService.create_menu(request)

    @pytest.mark.asyncio
    async def test_create_menu_parent_not_found(self):
        """父菜单不存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_menu_code.return_value = None
        mock_dao.get_by_id.return_value = None

        request = MenuCreateRequest(
            menu_name="子菜单", menu_code="menu:child", parent_id=999
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="父菜单ID 999 不存在"):
                await B14RbacService.create_menu(request)

    @pytest.mark.asyncio
    async def test_update_menu_success(self):
        """更新菜单成功"""
        menu = _make_menu()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = menu
        mock_dao.update_by_id.return_value = menu

        request = MenuUpdateRequest(menu_name="订单管理V2")

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.update_menu(1, request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_menu_not_found(self):
        """菜单不存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不存在"):
                await B14RbacService.update_menu(999, MenuUpdateRequest(menu_name="x"))

    @pytest.mark.asyncio
    async def test_update_menu_self_parent(self):
        """父菜单不能为自身 → ValueError"""
        menu = _make_menu(menu_id=1)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = menu

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="父菜单不能为自身"):
                await B14RbacService.update_menu(1, MenuUpdateRequest(parent_id=1))

    @pytest.mark.asyncio
    async def test_delete_menu_success(self):
        """删除菜单成功"""
        menu = _make_menu()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = menu
        mock_dao.has_children.return_value = False
        mock_dao.logic_delete_by_id = AsyncMock()

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.delete_menu(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_menu_has_children(self):
        """有子菜单 → ValueError"""
        menu = _make_menu()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = menu
        mock_dao.has_children.return_value = True

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="存在子菜单"):
                await B14RbacService.delete_menu(1)

    @pytest.mark.asyncio
    async def test_get_menu(self):
        """获取菜单详情"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = _make_menu()

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.get_menu(1)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_menu_tree(self):
        """构建菜单树"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.build_tree.return_value = [{"id": 1, "children": []}]

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.list_menu_tree()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_all_menus(self):
        """查询全部菜单"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_all.return_value = [_make_menu()]

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.list_all_menus()
        assert len(result) == 1


# ══════════════════════════════════════════════════════
# 2. 角色管理测试
# ══════════════════════════════════════════════════════


class TestB14Role:
    """角色 CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_role_success(self):
        """新增角色成功"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_role_name.return_value = None
        mock_dao.create.return_value = role

        request = RoleCreateRequest(
            role_name="运营管理员", permissions=["order:sync"]
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.create_role(request)
        assert result.role_name == "运营管理员"

    @pytest.mark.asyncio
    async def test_create_role_name_exists(self):
        """角色名已存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_role_name.return_value = _make_role()

        request = RoleCreateRequest(role_name="运营管理员", permissions=["order:sync"])

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="已存在"):
                await B14RbacService.create_role(request)

    @pytest.mark.asyncio
    async def test_create_role_invalid_permission(self):
        """权限码非法 → ValueError"""
        request = RoleCreateRequest(role_name="新角色", permissions=["invalid:perm"])

        with pytest.raises(ValueError, match="不在合法权限码白名单"):
            await B14RbacService.create_role(request)

    @pytest.mark.asyncio
    async def test_update_role_success(self):
        """更新角色成功"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role
        mock_dao.update_by_id.return_value = role

        request = RoleUpdateRequest(role_desc="运营管理")

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.update_role(1, request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_role_not_found(self):
        """角色不存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = None

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不存在"):
                await B14RbacService.update_role(999, RoleUpdateRequest(role_desc="x"))

    @pytest.mark.asyncio
    async def test_update_super_admin_role_name(self):
        """超管角色名不可改 → ValueError"""
        role = _make_role(role_name=DEFAULT_SUPER_ADMIN_ROLE_NAME)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="名称不可修改"):
                await B14RbacService.update_role(
                    1, RoleUpdateRequest(role_name="新超管")
                )

    @pytest.mark.asyncio
    async def test_delete_role_success(self):
        """删除角色成功"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role
        mock_dao.count_admin_users_by_role.return_value = 0
        mock_dao.logic_delete_by_id = AsyncMock()

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.delete_role(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_role_has_users(self):
        """角色被管理员绑定 → ValueError"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role
        mock_dao.count_admin_users_by_role.return_value = 3

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="仍有 3 个管理员绑定"):
                await B14RbacService.delete_role(1)

    @pytest.mark.asyncio
    async def test_delete_super_admin_role(self):
        """默认超管角色不可删 → ValueError"""
        role = _make_role(role_name=DEFAULT_SUPER_ADMIN_ROLE_NAME)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不可删除"):
                await B14RbacService.delete_role(1)

    @pytest.mark.asyncio
    async def test_get_role(self):
        """获取角色详情"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = _make_role()

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.get_role(1)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_roles(self):
        """分页查询角色列表"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_with_filters.return_value = ([role], 1)
        mock_dao.count_admin_users_by_role.return_value = 2

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            items, total = await B14RbacService.list_roles()
        assert total == 1
        assert items[0]["admin_user_count"] == 2

    @pytest.mark.asyncio
    async def test_get_all_permissions(self):
        """获取全部权限码字典"""
        perms = await B14RbacService.get_all_permissions()
        assert len(perms) > 0
        assert any(p["code"] == "*" or "manage" in p["code"] for p in perms)


# ══════════════════════════════════════════════════════
# 3. 管理员账号管理测试
# ══════════════════════════════════════════════════════


class TestB14AdminUser:
    """管理员账号 CRUD 测试"""

    @pytest.mark.asyncio
    async def test_create_admin_user_success(self):
        """新增管理员成功"""
        user = _make_admin_user()
        role = _make_role()
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = None
        mock_user_dao.create.return_value = user
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = role

        request = AdminUserCreateRequest(
            username="operator1", password="pass12345", role_id=2
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_role_cls, \
             patch("src.services.b14_rbac_service.B14PasswordUtil") as mock_pwd:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao
            mock_pwd.hash_password.return_value = "hashed"

            result = await B14RbacService.create_admin_user(request)
        assert result.username == "operator1"

    @pytest.mark.asyncio
    async def test_create_admin_user_username_exists(self):
        """用户名已存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = _make_admin_user()

        request = AdminUserCreateRequest(
            username="operator1", password="pass12345", role_id=2
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            with pytest.raises(ValueError, match="已存在"):
                await B14RbacService.create_admin_user(request)

    @pytest.mark.asyncio
    async def test_create_admin_user_role_not_found(self):
        """角色不存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_username.return_value = None
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = None

        request = AdminUserCreateRequest(
            username="newuser", password="pass12345", role_id=999
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_role_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao

            with pytest.raises(ValueError, match="角色ID 999 不存在"):
                await B14RbacService.create_admin_user(request)

    @pytest.mark.asyncio
    async def test_update_admin_user_success(self):
        """更新管理员成功"""
        user = _make_admin_user()
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id.return_value = user

        request = AdminUserUpdateRequest(real_name="新名字")

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            result = await B14RbacService.update_admin_user(1, request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_admin_user_not_found(self):
        """管理员不存在 → ValueError"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = None

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            with pytest.raises(ValueError, match="不存在"):
                await B14RbacService.update_admin_user(999, AdminUserUpdateRequest(real_name="x"))

    @pytest.mark.asyncio
    async def test_update_super_admin_disabled(self):
        """默认超管账号不可禁用 → ValueError"""
        user = _make_admin_user(username=DEFAULT_SUPER_ADMIN_USERNAME)
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            with pytest.raises(ValueError, match="不可禁用"):
                await B14RbacService.update_admin_user(1, AdminUserUpdateRequest(status=False))

    @pytest.mark.asyncio
    async def test_delete_admin_user_success(self):
        """删除管理员成功"""
        user = _make_admin_user()
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.logic_delete_by_id = AsyncMock()

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            result = await B14RbacService.delete_admin_user(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_super_admin(self):
        """默认超管账号不可删 → ValueError"""
        user = _make_admin_user(username=DEFAULT_SUPER_ADMIN_USERNAME)
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            with pytest.raises(ValueError, match="不可删除"):
                await B14RbacService.delete_admin_user(1)

    @pytest.mark.asyncio
    async def test_get_admin_user_detail(self):
        """获取管理员详情"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_with_role.return_value = {
            "id": 1,
            "username": "admin",
            "real_name": "超管",
            "phone": "",
            "email": "",
            "role_id": 1,
            "role_name": "超级管理员",
            "role_permissions": '["*"]',
        }

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            result = await B14RbacService.get_admin_user_detail(1)
        assert result is not None
        assert "*" in result["permissions"]

    @pytest.mark.asyncio
    async def test_list_admin_users(self):
        """分页查询管理员列表"""
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.list_with_role_info.return_value = (
            [{"id": 1, "username": "admin", "role_name": "超管"}],
            1,
        )

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            items, total = await B14RbacService.list_admin_users()
        assert total == 1

    @pytest.mark.asyncio
    async def test_reset_password_delegates(self):
        """重置密码委托 B14AuthService"""
        # B14AuthService 在 rbac_service.reset_password 函数内部局部 import
        # 故需 patch 源模块的属性，使其在函数内部 import 时拿到 mock
        with patch("src.services.b14_auth_service.B14AuthService") as mock_auth:
            mock_auth.reset_password = AsyncMock(return_value=True)
            result = await B14RbacService.reset_password(2, "newpass123", 1, "admin")
        assert result is True
        mock_auth.reset_password.assert_awaited()


# ══════════════════════════════════════════════════════
# 4. 权限校验工具方法测试
# ══════════════════════════════════════════════════════


class TestB14RbacUtils:
    """工具方法测试"""

    def test_parse_permissions_valid(self):
        """解析合法 JSON 权限列表"""
        result = B14RbacService._parse_permissions('["*", "order:sync"]')
        assert result == ["*", "order:sync"]

    def test_parse_permissions_empty(self):
        """空字符串 → 空列表"""
        assert B14RbacService._parse_permissions("") == []

    def test_parse_permissions_invalid(self):
        """非法 JSON → 空列表"""
        assert B14RbacService._parse_permissions("invalid") == []

    def test_validate_permissions_valid(self):
        """合法权限码通过校验"""
        B14RbacService._validate_permissions(["*", "order:sync", "rbac:manage"])

    def test_validate_permissions_invalid(self):
        """非法权限码 → ValueError"""
        with pytest.raises(ValueError, match="不在合法权限码白名单"):
            B14RbacService._validate_permissions(["invalid:perm"])

    def test_validate_permissions_wildcard(self):
        """超管通配符 * 通过校验"""
        B14RbacService._validate_permissions(["*"])

    @pytest.mark.asyncio
    async def test_is_descendant_direct_child(self):
        """_is_descendant 直接子节点"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        child = _make_menu(menu_id=2, parent_id=1)
        mock_dao.list_children.return_value = [child]

        result = await B14RbacService._is_descendant(mock_dao, 1, 2)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_descendant_no_match(self):
        """_is_descendant 无匹配"""
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.list_children.return_value = []

        result = await B14RbacService._is_descendant(mock_dao, 1, 999)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_descendant_recursive_match(self):
        """_is_descendant 递归匹配多层子孙"""
        mock_dao = AsyncMock()
        # 第一层：ancestor=1 的孩子是 menu_id=2，非直接命中 candidate=3
        # 第二层：menu_id=2 的孩子命中 candidate=3
        child_level1 = _make_menu(menu_id=2, parent_id=1)
        child_level2 = _make_menu(menu_id=3, parent_id=2)

        async def mock_list_children(parent_id):
            if parent_id == 1:
                return [child_level1]
            if parent_id == 2:
                return [child_level2]
            return []

        mock_dao.list_children = mock_list_children

        result = await B14RbacService._is_descendant(mock_dao, 1, 3)
        assert result is True


# ══════════════════════════════════════════════════════
# 5. 边界场景补充测试（提升覆盖率）
# ══════════════════════════════════════════════════════


class TestB14RbacEdgeCases:
    """边界场景测试"""

    @pytest.mark.asyncio
    async def test_update_menu_parent_not_found(self):
        """update_menu：父菜单不存在 → ValueError"""
        menu = _make_menu(menu_id=1, parent_id=0)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.side_effect = [menu, None]  # 自身存在, 父菜单不存在

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="父菜单ID 99 不存在"):
                await B14RbacService.update_menu(1, MenuUpdateRequest(parent_id=99))

    @pytest.mark.asyncio
    async def test_update_menu_cycle_detected(self):
        """update_menu：将子孙设为父菜单形成环 → ValueError"""
        menu = _make_menu(menu_id=1, parent_id=0)
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        # 自身 menu_id=1 存在；新父菜单 menu_id=2 存在
        parent_menu = _make_menu(menu_id=2, parent_id=1)
        mock_dao.get_by_id.side_effect = [menu, parent_menu]

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminMenuDAO") as mock_dao_cls, \
             patch.object(
                 B14RbacService, "_is_descendant", new=AsyncMock(return_value=True)
             ):
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="不能将子菜单设为父菜单"):
                await B14RbacService.update_menu(1, MenuUpdateRequest(parent_id=2))

    @pytest.mark.asyncio
    async def test_update_role_name_duplicate(self):
        """update_role：名称与其他角色重复 → ValueError"""
        role = _make_role(role_id=1, role_name="运营")
        existing = _make_role(role_id=2, role_name="客服")
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role
        mock_dao.get_by_role_name.return_value = existing

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            with pytest.raises(ValueError, match="已存在"):
                await B14RbacService.update_role(
                    1, RoleUpdateRequest(role_name="客服")
                )

    @pytest.mark.asyncio
    async def test_update_role_no_change(self):
        """update_role：无任何更新字段 → 直接返回原角色"""
        role = _make_role()
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            result = await B14RbacService.update_role(1, RoleUpdateRequest())
        assert result is role
        mock_dao.update_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_role_full_fields(self):
        """update_role：更新所有字段（name/desc/permissions/status）"""
        role = _make_role(role_id=1, role_name="运营")
        session, cm = _make_session_cm()
        mock_dao = AsyncMock()
        mock_dao.get_by_id.return_value = role
        mock_dao.update_by_id.return_value = role

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_dao_cls:
            mock_db.get_session.return_value = cm
            mock_dao_cls.return_value = mock_dao

            request = RoleUpdateRequest(
                role_desc="新描述",
                permissions=["order:sync", "withdraw:review"],
                status=True,
            )
            result = await B14RbacService.update_role(1, request)
        assert result is role
        mock_dao.update_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_admin_user_role_not_found(self):
        """update_admin_user：角色不存在 → ValueError"""
        user = _make_admin_user()
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = None

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_role_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao

            with pytest.raises(ValueError, match="角色ID 99 不存在"):
                await B14RbacService.update_admin_user(
                    1, AdminUserUpdateRequest(role_id=99)
                )

    @pytest.mark.asyncio
    async def test_update_admin_user_no_change(self):
        """update_admin_user：无更新字段 → 直接返回原用户"""
        user = _make_admin_user()
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao

            result = await B14RbacService.update_admin_user(1, AdminUserUpdateRequest())
        assert result is user
        mock_user_dao.update_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_admin_user_full_fields(self):
        """update_admin_user：更新所有字段（real_name/phone/email/role_id/status）"""
        user = _make_admin_user()
        role = _make_role(role_id=2)
        session, cm = _make_session_cm()
        mock_user_dao = AsyncMock()
        mock_user_dao.get_by_id.return_value = user
        mock_user_dao.update_by_id.return_value = user
        mock_role_dao = AsyncMock()
        mock_role_dao.get_by_id.return_value = role

        with patch("src.services.b14_rbac_service.DatabaseManager") as mock_db, \
             patch("src.services.b14_rbac_service.AdminUserDAO") as mock_user_cls, \
             patch("src.services.b14_rbac_service.AdminRoleDAO") as mock_role_cls:
            mock_db.get_session.return_value = cm
            mock_user_cls.return_value = mock_user_dao
            mock_role_cls.return_value = mock_role_dao

            request = AdminUserUpdateRequest(
                real_name="新名字",
                phone="13800138000",
                email="new@test.com",
                role_id=2,
                status=True,
            )
            result = await B14RbacService.update_admin_user(1, request)
        assert result is user
        mock_user_dao.update_by_id.assert_called_once()

# @ai-generated
"""
B14 RBAC 权限管理 API（菜单 / 角色 / 管理员账号）
路由前缀：/api/v1/admin/rbac
新建独立文件，不修改 B01-B13 任何基线 API

接口清单：

【菜单管理 menu:manage】
1. GET    /api/v1/admin/rbac/menus/tree       启用菜单树（前端渲染用）
2. GET    /api/v1/admin/rbac/menus             全部菜单列表（含禁用）
3. GET    /api/v1/admin/rbac/menus/{menu_id}   菜单详情
4. POST   /api/v1/admin/rbac/menus             新增菜单
5. PUT    /api/v1/admin/rbac/menus/{menu_id}   更新菜单
6. DELETE /api/v1/admin/rbac/menus/{menu_id}   删除菜单

【角色管理 rbac:manage】
7.  GET    /api/v1/admin/rbac/roles             角色分页列表
8.  GET    /api/v1/admin/rbac/roles/{role_id}   角色详情
9.  POST   /api/v1/admin/rbac/roles             新增角色
10. PUT    /api/v1/admin/rbac/roles/{role_id}   更新角色
11. DELETE /api/v1/admin/rbac/roles/{role_id}   删除角色
12. GET    /api/v1/admin/rbac/permissions       全部权限码字典

【管理员账号管理 rbac:manage】
13. GET    /api/v1/admin/rbac/users             管理员分页列表
14. GET    /api/v1/admin/rbac/users/{user_id}   管理员详情
15. POST   /api/v1/admin/rbac/users             新增管理员
16. PUT    /api/v1/admin/rbac/users/{user_id}   更新管理员
17. DELETE /api/v1/admin/rbac/users/{user_id}   删除管理员
18. PUT    /api/v1/admin/rbac/users/{user_id}/password  重置密码

权限设计：
- 菜单管理需 menu:manage 权限
- 角色管理需 rbac:manage 权限
- 管理员账号管理需 rbac:manage 权限
- 超管 * 通配符自动放行全部接口
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.common.b14_audit_util import AuditLogger
from src.config.b14_constants import (
    AuditAction,
    AuditTargetType,
    PERM_MENU_MANAGE,
    PERM_RBAC_MANAGE,
)
from src.schemas.b14_rbac import (
    AdminUserCreateRequest,
    AdminUserPasswordResetRequest,
    AdminUserUpdateRequest,
    MenuCreateRequest,
    MenuUpdateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
)
from src.services.b14_rbac_service import B14RbacService

logger = logging.getLogger("api.admin.b14_rbac")

router = APIRouter(prefix="/api/v1/admin/rbac", tags=["后台-RBAC权限管理(B14)"])


# ── 依赖注入 ──────────────


async def get_admin_user_id_rbac(
    payload: dict = Depends(require_any_permission([PERM_RBAC_MANAGE])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC rbac:manage 权限）"""
    return int(payload["user_id"])


async def get_admin_user_id_menu(
    payload: dict = Depends(require_any_permission([PERM_MENU_MANAGE])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC menu:manage 权限）"""
    return int(payload["user_id"])


def _get_admin_info(payload: dict) -> tuple:
    """从 JWT payload 提取 (user_id, username)"""
    return int(payload.get("user_id", 0)), str(payload.get("username", ""))


def _serialize_menu(menu) -> dict:
    return {
        "id": menu.id,
        "parent_id": menu.parent_id,
        "menu_name": menu.menu_name,
        "menu_code": menu.menu_code,
        "menu_path": menu.menu_path,
        "menu_icon": menu.menu_icon,
        "menu_type": menu.menu_type,
        "sort_num": menu.sort_num,
        "status": menu.status,
        "remark": menu.remark,
        "create_time": menu.create_time,
        "update_time": menu.update_time,
    }


# ════════════════════════════════════════════════════════════
# 1. 菜单管理
# ════════════════════════════════════════════════════════════


@router.get("/menus/tree")
async def get_menu_tree(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """获取启用菜单树（前端渲染用，嵌套结构）"""
    request_id = get_request_id(request)
    try:
        tree = await B14RbacService.list_menu_tree()
        return success_response(data=tree, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/menus")
async def list_menus(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """获取全部菜单列表（含禁用，管理后台列表用）"""
    request_id = get_request_id(request)
    try:
        menus = await B14RbacService.list_all_menus()
        return success_response(
            data=[_serialize_menu(m) for m in menus], request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/menus/{menu_id}")
async def get_menu(
    request: Request,
    menu_id: int,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """获取菜单详情"""
    request_id = get_request_id(request)
    try:
        menu = await B14RbacService.get_menu(menu_id)
        if menu is None:
            return handle_service_exception(
                ValueError(f"菜单ID {menu_id} 不存在"), request_id
            )
        return success_response(data=_serialize_menu(menu), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/menus")
async def create_menu(
    request: Request,
    body: MenuCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """新增菜单"""
    request_id = get_request_id(request)
    try:
        menu = await B14RbacService.create_menu(body)
        return success_response(
            data=_serialize_menu(menu), msg="菜单创建成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/menus/{menu_id}")
async def update_menu(
    request: Request,
    menu_id: int,
    body: MenuUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """更新菜单（menu_code 不可改）"""
    request_id = get_request_id(request)
    try:
        menu = await B14RbacService.update_menu(menu_id, body)
        return success_response(
            data=_serialize_menu(menu), msg="菜单更新成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/menus/{menu_id}")
async def delete_menu(
    request: Request,
    menu_id: int,
    admin_user_id: int = Depends(get_admin_user_id_menu),
):
    """删除菜单（有子菜单时拒绝删除）"""
    request_id = get_request_id(request)
    try:
        await B14RbacService.delete_menu(menu_id)
        return success_response(
            data={"menu_id": menu_id}, msg="菜单删除成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 角色管理
# ════════════════════════════════════════════════════════════


@router.get("/permissions")
async def get_all_permissions(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """获取全部权限码字典（前端角色编辑时下发可选项）"""
    request_id = get_request_id(request)
    try:
        perms = await B14RbacService.get_all_permissions()
        return success_response(data=perms, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/roles")
async def list_roles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role_name: Optional[str] = Query(None, description="角色名模糊筛选"),
    status: Optional[bool] = Query(None, description="状态筛选"),
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """分页查询角色列表（含管理员绑定数）"""
    request_id = get_request_id(request)
    try:
        items, total = await B14RbacService.list_roles(
            page=page, page_size=page_size, role_name=role_name, status=status
        )
        return success_response(
            data={"total": total, "page": page, "page_size": page_size, "items": items},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/roles/{role_id}")
async def get_role(
    request: Request,
    role_id: int,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """获取角色详情"""
    request_id = get_request_id(request)
    try:
        role = await B14RbacService.get_role(role_id)
        if role is None:
            return handle_service_exception(
                ValueError(f"角色ID {role_id} 不存在"), request_id
            )
        import json
        from src.services.b14_rbac_service import B14RbacService as _Svc

        data = {
            "id": role.id,
            "role_name": role.role_name,
            "role_desc": role.role_desc,
            "permissions": _Svc._parse_permissions(role.permissions),
            "status": role.status,
            "create_time": role.create_time,
            "update_time": role.update_time,
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/roles")
async def create_role(
    request: Request,
    body: RoleCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """新增角色"""
    request_id = get_request_id(request)
    try:
        role = await B14RbacService.create_role(body)
        from src.services.b14_rbac_service import B14RbacService as _Svc

        data = {
            "id": role.id,
            "role_name": role.role_name,
            "role_desc": role.role_desc,
            "permissions": _Svc._parse_permissions(role.permissions),
            "status": role.status,
            "create_time": role.create_time,
            "update_time": role.update_time,
        }
        return success_response(data=data, msg="角色创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/roles/{role_id}")
async def update_role(
    request: Request,
    role_id: int,
    body: RoleUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """更新角色（默认超管角色名不可改）"""
    request_id = get_request_id(request)
    try:
        role = await B14RbacService.update_role(role_id, body)
        from src.services.b14_rbac_service import B14RbacService as _Svc

        data = {
            "id": role.id,
            "role_name": role.role_name,
            "role_desc": role.role_desc,
            "permissions": _Svc._parse_permissions(role.permissions),
            "status": role.status,
            "create_time": role.create_time,
            "update_time": role.update_time,
        }
        return success_response(data=data, msg="角色更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/roles/{role_id}")
async def delete_role(
    request: Request,
    role_id: int,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """删除角色（被管理员绑定时拒绝删除；默认超管角色不可删）"""
    request_id = get_request_id(request)
    try:
        await B14RbacService.delete_role(role_id)
        return success_response(
            data={"role_id": role_id}, msg="角色删除成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 管理员账号管理
# ════════════════════════════════════════════════════════════


@router.get("/users")
async def list_admin_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: Optional[str] = Query(None, description="用户名模糊筛选"),
    role_id: Optional[int] = Query(None, gt=0, description="角色ID筛选"),
    status: Optional[bool] = Query(None, description="状态筛选"),
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """分页查询管理员列表（含角色名）"""
    request_id = get_request_id(request)
    try:
        items, total = await B14RbacService.list_admin_users(
            page=page,
            page_size=page_size,
            username=username,
            role_id=role_id,
            status=status,
        )
        return success_response(
            data={"total": total, "page": page, "page_size": page_size, "items": items},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/users/{user_id}")
async def get_admin_user(
    request: Request,
    user_id: int,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """获取管理员详情（含角色 + 权限码）"""
    request_id = get_request_id(request)
    try:
        data = await B14RbacService.get_admin_user_detail(user_id)
        if data is None:
            return handle_service_exception(
                ValueError(f"管理员ID {user_id} 不存在"), request_id
            )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/users")
async def create_admin_user(
    request: Request,
    body: AdminUserCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """新增管理员账号"""
    request_id = get_request_id(request)
    try:
        user = await B14RbacService.create_admin_user(body)
        data = {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "phone": user.phone,
            "email": user.email,
            "role_id": user.role_id,
            "status": user.status,
            "create_time": user.create_time,
            "update_time": user.update_time,
        }
        return success_response(data=data, msg="管理员创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/users/{user_id}")
async def update_admin_user(
    request: Request,
    user_id: int,
    body: AdminUserUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """更新管理员账号（不含密码，密码走重置接口）"""
    request_id = get_request_id(request)
    try:
        user = await B14RbacService.update_admin_user(user_id, body)
        data = {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "phone": user.phone,
            "email": user.email,
            "role_id": user.role_id,
            "status": user.status,
            "create_time": user.create_time,
            "update_time": user.update_time,
        }
        return success_response(data=data, msg="管理员更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/users/{user_id}")
async def delete_admin_user(
    request: Request,
    user_id: int,
    admin_user_id: int = Depends(get_admin_user_id_rbac),
):
    """删除管理员账号（默认超管账号不可删）"""
    request_id = get_request_id(request)
    try:
        await B14RbacService.delete_admin_user(user_id)
        return success_response(
            data={"user_id": user_id}, msg="管理员删除成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/users/{user_id}/password")
async def reset_admin_password(
    request: Request,
    user_id: int,
    body: AdminUserPasswordResetRequest,
    payload: dict = Depends(require_any_permission([PERM_RBAC_MANAGE])),
):
    """特权用户重置他人密码（写审计日志 + JWT 黑名单）"""
    request_id = get_request_id(request)
    operator_id, operator_name = _get_admin_info(payload)
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        await B14RbacService.reset_password(
            target_user_id=user_id,
            new_password=body.new_password,
            operator_id=operator_id,
            operator_name=operator_name,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(
            data={"user_id": user_id}, msg="密码重置成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)

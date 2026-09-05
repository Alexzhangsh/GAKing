# @ai-generated
"""
B14 RBAC 权限管理 Schema（菜单 / 角色 / 管理员账号）
新建独立文件，不修改 B01-B13 任何基线 schema

设计要点：
- 菜单 menu_code 同时作为权限码，存入 AdminRole.permissions JSON 数组
- 角色 permissions JSON 数组：["*", "order:sync", "menu:order", ...]
- 管理员账号密码：B14PasswordUtil 哈希存储，禁止明文
- 所有写操作入参严格校验，权限码白名单通过 ALL_ADMIN_PERMISSIONS + B14_PERMISSIONS 控制
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════
# 1. 菜单 Schema
# ════════════════════════════════════════════════════════════


class MenuCreateRequest(BaseModel):
    """菜单新增请求体"""

    parent_id: int = Field(default=0, ge=0, description="父菜单ID，0表示顶级")
    menu_name: str = Field(..., min_length=1, max_length=128, description="菜单名称")
    menu_code: str = Field(
        ..., min_length=1, max_length=64, description="菜单唯一编码（同时作为权限码）"
    )
    menu_path: str = Field(default="", max_length=256, description="前端路由路径")
    menu_icon: str = Field(default="", max_length=64, description="菜单图标")
    menu_type: str = Field(
        default="menu",
        max_length=16,
        description="菜单类型：directory/menu/button",
    )
    sort_num: int = Field(default=0, ge=0, description="排序权重")
    status: bool = Field(default=True, description="状态：True-启用 False-禁用")
    remark: str = Field(default="", max_length=512, description="备注说明")

    @field_validator("menu_type")
    @classmethod
    def validate_menu_type(cls, v: str) -> str:
        if v not in ("directory", "menu", "button"):
            raise ValueError("menu_type 必须为 directory/menu/button")
        return v


class MenuUpdateRequest(BaseModel):
    """菜单更新请求体（menu_code 不可改）"""

    parent_id: Optional[int] = Field(default=None, ge=0, description="父菜单ID")
    menu_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    menu_path: Optional[str] = Field(default=None, max_length=256)
    menu_icon: Optional[str] = Field(default=None, max_length=64)
    menu_type: Optional[str] = Field(default=None, max_length=16)
    sort_num: Optional[int] = Field(default=None, ge=0)
    status: Optional[bool] = Field(default=None)
    remark: Optional[str] = Field(default=None, max_length=512)

    @field_validator("menu_type")
    @classmethod
    def validate_menu_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("directory", "menu", "button"):
            raise ValueError("menu_type 必须为 directory/menu/button")
        return v


class MenuResponse(BaseModel):
    """菜单响应体"""

    id: int = Field(..., description="主键ID")
    parent_id: int = Field(..., description="父菜单ID")
    menu_name: str = Field(..., description="菜单名称")
    menu_code: str = Field(..., description="菜单编码")
    menu_path: str = Field(..., description="前端路由路径")
    menu_icon: str = Field(..., description="菜单图标")
    menu_type: str = Field(..., description="菜单类型")
    sort_num: int = Field(..., description="排序权重")
    status: bool = Field(..., description="状态")
    remark: str = Field(..., description="备注")
    create_time: Optional[datetime] = Field(default=None)
    update_time: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class MenuTreeNode(BaseModel):
    """菜单树节点（递归结构）"""

    id: int
    parent_id: int
    menu_name: str
    menu_code: str
    menu_path: str
    menu_icon: str
    menu_type: str
    sort_num: int
    status: bool
    remark: str
    children: List["MenuTreeNode"] = Field(default_factory=list)


# ════════════════════════════════════════════════════════════
# 2. 角色 Schema
# ════════════════════════════════════════════════════════════


class RoleCreateRequest(BaseModel):
    """角色新增请求体"""

    role_name: str = Field(..., min_length=1, max_length=64, description="角色名称")
    role_desc: str = Field(default="", max_length=512, description="角色描述")
    permissions: List[str] = Field(
        default_factory=list, description="权限码列表（含 * 表示超管）"
    )
    status: bool = Field(default=True, description="状态：True-启用 False-禁用")


class RoleUpdateRequest(BaseModel):
    """角色更新请求体"""

    role_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    role_desc: Optional[str] = Field(default=None, max_length=512)
    permissions: Optional[List[str]] = Field(default=None, description="权限码列表")
    status: Optional[bool] = Field(default=None)


class RoleResponse(BaseModel):
    """角色响应体"""

    id: int = Field(..., description="主键ID")
    role_name: str = Field(..., description="角色名称")
    role_desc: str = Field(..., description="角色描述")
    permissions: List[str] = Field(default_factory=list, description="权限码列表")
    status: bool = Field(..., description="状态")
    create_time: Optional[datetime] = Field(default=None)
    update_time: Optional[datetime] = Field(default=None)
    admin_user_count: int = Field(default=0, description="绑定该角色的管理员数量")

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """角色分页列表响应体"""

    total: int
    page: int
    page_size: int
    items: List[RoleResponse]


# ════════════════════════════════════════════════════════════
# 3. 管理员账号 Schema
# ════════════════════════════════════════════════════════════


class AdminUserCreateRequest(BaseModel):
    """管理员账号新增请求体"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(
        ..., min_length=8, max_length=128, description="明文密码（至少 8 位）"
    )
    real_name: str = Field(default="", max_length=64, description="真实姓名")
    phone: str = Field(default="", max_length=32, description="手机号")
    email: str = Field(default="", max_length=128, description="邮箱")
    role_id: int = Field(..., gt=0, description="角色ID")
    status: bool = Field(default=True, description="状态：True-启用 False-禁用")


class AdminUserUpdateRequest(BaseModel):
    """管理员账号更新请求体（不可改密码，密码走重置接口）"""

    real_name: Optional[str] = Field(default=None, max_length=64)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=128)
    role_id: Optional[int] = Field(default=None, gt=0)
    status: Optional[bool] = Field(default=None)


class AdminUserResponse(BaseModel):
    """管理员账号响应体（不含密码）"""

    id: int = Field(..., description="主键ID")
    username: str = Field(..., description="用户名")
    real_name: str = Field(..., description="真实姓名")
    phone: str = Field(..., description="手机号")
    email: str = Field(..., description="邮箱")
    role_id: int = Field(..., description="角色ID")
    role_name: str = Field(default="", description="角色名称")
    status: bool = Field(..., description="状态")
    create_time: Optional[datetime] = Field(default=None)
    update_time: Optional[datetime] = Field(default=None)

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """管理员账号分页列表响应体"""

    total: int
    page: int
    page_size: int
    items: List[AdminUserResponse]


class AdminUserPasswordResetRequest(BaseModel):
    """管理员密码重置请求体（特权用户重置他人密码）"""

    new_password: str = Field(
        ..., min_length=8, max_length=128, description="新密码（至少 8 位）"
    )

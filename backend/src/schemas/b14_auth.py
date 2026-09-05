# @ai-generated
"""
B14 后台管理员认证 Schema（登录 / 改密 / 登出）
新建独立文件，不修改 B01-B13 任何基线 schema

字段说明：
- 用户名/密码：登录入参，密码明文传输由 HTTPS 保证，落库前由 B14PasswordUtil 哈希
- token：JWT，由 JwtAuthGuard.create_token 生成，前端放 Authorization: Bearer <token>
- permissions：角色权限码列表（含 "*" 表示超管），前端用于菜单/按钮显隐控制
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    """管理员登录请求体"""

    username: str = Field(..., min_length=1, max_length=64, description="管理员用户名")
    password: str = Field(..., min_length=1, max_length=128, description="管理员明文密码")


class AdminLoginResponse(BaseModel):
    """管理员登录响应体"""

    token: str = Field(..., description="JWT token")
    expires_in: int = Field(..., description="token 有效期（秒）")
    user_id: int = Field(..., description="管理员ID")
    username: str = Field(..., description="用户名")
    real_name: str = Field(default="", description="真实姓名")
    role_id: int = Field(..., description="角色ID")
    role_name: str = Field(default="", description="角色名称")
    permissions: List[str] = Field(default_factory=list, description="权限码列表")
    must_change_password: bool = Field(
        default=False,
        description="是否需要强制修改密码（首次登录或密码重置后为 True）",
    )


class AdminChangePasswordRequest(BaseModel):
    """管理员修改密码请求体（自助修改，需校验原密码）"""

    old_password: str = Field(..., min_length=1, max_length=128, description="原密码")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="新密码（至少 8 位）",
    )


class AdminResetPasswordRequest(BaseModel):
    """管理员重置密码请求体（超管/特权用户重置他人密码，无需原密码）"""

    user_id: int = Field(..., gt=0, description="被重置密码的管理员ID")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="新密码（至少 8 位）",
    )


class AdminLoginFailResponse(BaseModel):
    """登录失败响应体（用于限流/锁定提示）"""

    code: int = Field(..., description="业务状态码")
    msg: str = Field(..., description="提示消息")
    retry_after_seconds: Optional[int] = Field(
        default=None, description="锁定剩余秒数（被锁定时返回）"
    )
    remaining_attempts: Optional[int] = Field(
        default=None, description="剩余尝试次数（未锁定时返回）"
    )


class AdminUserInfoResponse(BaseModel):
    """管理员个人信息响应体（用于前端展示当前登录用户）"""

    user_id: int = Field(..., description="管理员ID")
    username: str = Field(..., description="用户名")
    real_name: str = Field(default="", description="真实姓名")
    phone: str = Field(default="", description="手机号")
    email: str = Field(default="", description="邮箱")
    role_id: int = Field(..., description="角色ID")
    role_name: str = Field(default="", description="角色名称")
    permissions: List[str] = Field(default_factory=list, description="权限码列表")

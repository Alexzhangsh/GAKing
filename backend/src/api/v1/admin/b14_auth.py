# @ai-generated
"""
B14 后台管理员认证 API（登录 / 登出 / 当前用户 / 改密）
路由前缀：/api/v1/admin/auth
新建独立文件，不修改 B01-B13 任何基线 API

接口清单：
1. POST /api/v1/admin/auth/login       管理员登录（无需鉴权，独立防爆破限流）
2. POST /api/v1/admin/auth/logout      管理员登出（需 JWT）
3. GET  /api/v1/admin/auth/me          获取当前登录用户信息（需 JWT）
4. PUT  /api/v1/admin/auth/password    修改密码（需 JWT，校验原密码）

权限设计：
- login 无需鉴权（任何人可尝试，但有 5 次/15 分钟失败锁定）
- logout / me / password 需要有效 JWT（任意已登录管理员可访问）
- 限流中间件已跳过 login 端点（独立防爆破），其他端点走通用 admin 限流
"""
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import get_current_user
from src.common.b14_audit_util import AuditLogger
from src.config.b14_constants import AuditAction, AuditTargetType
from src.schemas.b14_auth import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
)
from src.services.b14_auth_service import B14AuthService

logger = logging.getLogger("api.admin.b14_auth")

router = APIRouter(prefix="/api/v1/admin/auth", tags=["后台-认证(B14)"])

# login 端点不强依赖 Bearer（允许匿名访问），但 FastAPI 需要显式声明
_login_security = HTTPBearer(auto_error=False)


@router.post("/login")
async def admin_login(request: Request, body: AdminLoginRequest):
    """管理员登录

    无需 JWT 鉴权，独立防爆破（5 次/15 分钟失败锁定）
    成功返回 token + 用户信息 + 权限码列表
    """
    request_id = get_request_id(request)
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        result = await B14AuthService.login(
            username=body.username,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(data=result, msg="登录成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/logout")
async def admin_logout(
    request: Request,
    payload: dict = Depends(get_current_user),
):
    """管理员登出

    注：当前 JWT 为无状态，登出仅记录审计日志，前端负责清除 token
    后续可扩展 JWT 黑名单强制下线
    """
    request_id = get_request_id(request)
    user_id = int(payload.get("user_id", 0))
    username = str(payload.get("username", ""))
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        await AuditLogger.log(
            action=AuditAction.ADMIN_LOGOUT,
            target_type=AuditTargetType.LOGIN,
            target_id=user_id,
            details={"username": username},
            user_id=user_id,
            user_name=username,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(
            data={"user_id": user_id}, msg="登出成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/me")
async def get_current_admin(
    request: Request,
    payload: dict = Depends(get_current_user),
):
    """获取当前登录管理员信息（含角色 + 权限码列表）"""
    request_id = get_request_id(request)
    user_id = int(payload.get("user_id", 0))
    try:
        result = await B14AuthService.get_user_info(user_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/password")
async def change_password(
    request: Request,
    body: AdminChangePasswordRequest,
    payload: dict = Depends(get_current_user),
):
    """管理员自助修改密码（校验原密码）"""
    request_id = get_request_id(request)
    user_id = int(payload.get("user_id", 0))
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        await B14AuthService.change_password(
            user_id=user_id,
            old_password=body.old_password,
            new_password=body.new_password,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(
            data={"user_id": user_id}, msg="密码修改成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)

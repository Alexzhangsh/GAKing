# @ai-generated
"""
B15 增强认证 API（登出 JWT 销毁 + 修改密码黑名单）
路由前缀：/api/v1/admin/auth（与 B14 路由前缀相同，注册时优先匹配）
新建文件，不修改 B01-B14 任何基线 API

与 B14 路由的关系：
- 本路由文件与 B14 b14_auth.py 使用相同路由前缀 /api/v1/admin/auth
- B15 路由在 setup 中先于 B14 注册，FastAPI 优先匹配先注册的路由
- 覆盖的端点：POST /logout（登出销毁 JWT）、PUT /password（改密 + 黑名单）
- 未覆盖的端点（POST /login、GET /me）仍由 B14 路由处理

注意：FastAPI 路由匹配规则是先注册先匹配，因此 B15 路由必须在 B14 之前注册，
但 B15 只注册了特定路径的端点，B14 未覆盖的路径由 B14 处理。
"""
import logging

from fastapi import APIRouter, Depends, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import get_current_user
from src.common.b14_audit_util import AuditLogger
from src.schemas.b14_auth import (
    AdminChangePasswordRequest,
)
from src.services.b15_auth_service import B15AuthService

logger = logging.getLogger("api.admin.b15_auth")

router = APIRouter(prefix="/api/v1/admin/auth", tags=["后台-认证(B15增强)"])


@router.post("/logout")
async def admin_logout(
    request: Request,
    payload: dict = Depends(get_current_user),
):
    """管理员登出（销毁 JWT：加入黑名单，强制当前 token 失效）

    增强点：与 B14 登出不同，本接口将 JWT 加入黑名单，
    使该用户当前所有 token 立即失效（需重新登录）。
    """
    request_id = get_request_id(request)
    user_id = int(payload.get("user_id", 0))
    username = str(payload.get("username", ""))
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        await B15AuthService.logout(
            user_id=user_id,
            username=username,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(
            data={"user_id": user_id}, msg="登出成功，JWT 已销毁", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/password")
async def change_password(
    request: Request,
    body: AdminChangePasswordRequest,
    payload: dict = Depends(get_current_user),
):
    """管理员修改密码（增强版：校验原密码 + 更新 + JWT 黑名单失效）

    增强点：与 B14 改密不同，本接口修改密码后自动将 JWT 加入黑名单，
    强制该用户所有旧 token 立即失效，需重新登录。
    """
    request_id = get_request_id(request)
    user_id = int(payload.get("user_id", 0))
    ip = AuditLogger.get_client_ip(request)
    ua = AuditLogger.get_user_agent(request)
    try:
        await B15AuthService.change_password(
            user_id=user_id,
            old_password=body.old_password,
            new_password=body.new_password,
            ip_address=ip,
            user_agent=ua,
        )
        return success_response(
            data={"user_id": user_id}, msg="密码修改成功，请重新登录", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)
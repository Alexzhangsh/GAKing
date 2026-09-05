# @ai-generated
"""
B13-补全 C端用户管理后台 API 路由
权限码：user:manage（全部接口需此权限）
路由前缀：/api/v1/admin/users-manage（避免与 B14 RBAC 的 /rbac/users 冲突）
所有写操作自动被 B14 审计中间件记录
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_USER_MANAGE
from src.schemas.b13_user_admin import (
    UserFreezeRequest,
    UserRemarkRequest,
)
from src.services.b13_user_admin_service import B13UserAdminService

logger = logging.getLogger("api.b13_user")

router = APIRouter(
    prefix="/api/v1/admin/users-manage",
    tags=["后台-C端用户管理(B13-补全)"],
)


@router.get("")
async def list_users(
    request: Request,
    status: Optional[str] = Query(None, description="管理状态筛选：normal/frozen"),
    keyword: Optional[str] = Query(None, description="用户ID 模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_USER_MANAGE])),
):
    """用户列表（联表查询佣金账户 + 管理档案）"""
    request_id = get_request_id(request)
    try:
        items, total = await B13UserAdminService.list_users(
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{user_id}")
async def get_user_detail(
    request: Request,
    user_id: int,
    payload: dict = Depends(require_any_permission([PERM_USER_MANAGE])),
):
    """用户详情（佣金账户 + 管理档案）"""
    request_id = get_request_id(request)
    try:
        data = await B13UserAdminService.get_user_detail(user_id)
        if data is None:
            return error_response(
                code=404, msg="用户不存在", request_id=request_id
            )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{user_id}/remark")
async def update_user_remark(
    request: Request,
    user_id: int,
    body: UserRemarkRequest,
    payload: dict = Depends(require_any_permission([PERM_USER_MANAGE])),
):
    """更新用户备注"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13UserAdminService.update_remark(
            user_id=user_id,
            admin_remark=body.admin_remark,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="备注更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{user_id}/freeze")
async def freeze_user(
    request: Request,
    user_id: int,
    body: UserFreezeRequest,
    payload: dict = Depends(require_any_permission([PERM_USER_MANAGE])),
):
    """冻结用户"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13UserAdminService.freeze_user(
            user_id=user_id,
            frozen_reason=body.frozen_reason,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="用户已冻结", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{user_id}/unfreeze")
async def unfreeze_user(
    request: Request,
    user_id: int,
    payload: dict = Depends(require_any_permission([PERM_USER_MANAGE])),
):
    """解冻用户"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B13UserAdminService.unfreeze_user(
            user_id=user_id,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, msg="用户已解冻", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

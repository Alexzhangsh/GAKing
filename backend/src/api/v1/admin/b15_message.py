# @ai-generated
"""
F04 营销消息管理 API
路由前缀：/api/v1/admin/message
权限码：message:manage
审计中间件自动记录所有写操作（POST/PUT/DELETE）

接口清单：
1. GET    /api/v1/admin/message/templates          分页查询模板列表
2. POST   /api/v1/admin/message/templates          新增模板
3. GET    /api/v1/admin/message/templates/{id}     模板详情
4. PUT    /api/v1/admin/message/templates/{id}     更新模板
5. DELETE /api/v1/admin/message/templates/{id}     删除模板（软删除）
6. PUT    /api/v1/admin/message/templates/{id}/toggle  启停切换
7. GET    /api/v1/admin/message/push-records       推送记录列表
8. GET    /api/v1/admin/message/subscriptions      订阅绑定列表
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
from src.config.b15_constants import PERM_MESSAGE_MANAGE
from src.schemas.b15_message import (
    MessageTemplateCreate,
    MessageTemplateUpdate,
)
from src.services.b15_message_service import B15MessageService

logger = logging.getLogger("api.admin.b15_message")

router = APIRouter(prefix="/api/v1/admin/message", tags=["后台-营销消息(F04)"])


# ── 依赖注入：管理员身份识别 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_MESSAGE_MANAGE])),
) -> int:
    """获取管理员ID（强制 JWT + RBAC message:manage 权限）"""
    return int(payload["user_id"])


# ════════════════════════════════════════════════════════════
# 消息模板 CRUD
# ════════════════════════════════════════════════════════════


@router.get("/templates")
async def list_templates(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    template_type: Optional[int] = Query(None, ge=1, le=2, description="模板类型：1=微信订阅 2=站内消息"),
    status: Optional[int] = Query(None, ge=0, le=1, description="状态：1=启用 0=停用"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """分页查询消息模板列表"""
    request_id = get_request_id(request)
    try:
        items, total = await B15MessageService.list_templates(
            page=page, page_size=page_size, template_type=template_type, status=status
        )
        data = {"total": total, "page": page, "page_size": page_size, "items": items}
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/templates")
async def create_template(
    request: Request,
    body: MessageTemplateCreate,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """新增消息模板"""
    request_id = get_request_id(request)
    try:
        data = await B15MessageService.create_template(body)
        return success_response(data=data, msg="模板创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/templates/{template_id}")
async def get_template(
    request: Request,
    template_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """获取消息模板详情"""
    request_id = get_request_id(request)
    try:
        data = await B15MessageService.get_template(template_id)
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/templates/{template_id}")
async def update_template(
    request: Request,
    template_id: int,
    body: MessageTemplateUpdate,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """更新消息模板"""
    request_id = get_request_id(request)
    try:
        data = await B15MessageService.update_template(template_id, body)
        return success_response(data=data, msg="模板更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/templates/{template_id}")
async def delete_template(
    request: Request,
    template_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """删除消息模板（软删除）"""
    request_id = get_request_id(request)
    try:
        await B15MessageService.delete_template(template_id)
        return success_response(
            data={"template_id": template_id}, msg="模板删除成功", request_id=request_id
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/templates/{template_id}/toggle")
async def toggle_template_status(
    request: Request,
    template_id: int,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """切换模板启停状态"""
    request_id = get_request_id(request)
    try:
        data = await B15MessageService.toggle_template_status(template_id)
        return success_response(data=data, msg="状态切换成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 推送记录 & 订阅绑定（只读查询）
# ════════════════════════════════════════════════════════════


@router.get("/push-records")
async def list_push_records(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    template_id: Optional[int] = Query(None, description="按模板ID筛选"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    push_status: Optional[int] = Query(None, ge=1, le=3, description="推送状态：1=成功 2=失败 3=待发送"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """推送记录列表"""
    request_id = get_request_id(request)
    try:
        items, total = await B15MessageService.list_push_records(
            page=page, page_size=page_size, template_id=template_id,
            user_id=user_id, push_status=push_status,
        )
        data = {"total": total, "page": page, "page_size": page_size, "items": items}
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/subscriptions")
async def list_subscribe_bindings(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    template_id: Optional[int] = Query(None, description="按模板ID筛选"),
    subscribe_status: Optional[int] = Query(None, ge=0, le=1, description="订阅状态：1=已订阅 0=已取消"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """订阅绑定列表"""
    request_id = get_request_id(request)
    try:
        items, total = await B15MessageService.list_subscribe_bindings(
            page=page, page_size=page_size, user_id=user_id,
            template_id=template_id, subscribe_status=subscribe_status,
        )
        data = {"total": total, "page": page, "page_size": page_size, "items": items}
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

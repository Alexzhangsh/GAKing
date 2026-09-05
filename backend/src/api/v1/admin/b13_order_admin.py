# @ai-generated
"""
B13-1 订单管理后台 API 路由
权限码：order:manage（全部接口需此权限）
路由前缀：/api/v1/admin/b13/orders
所有写操作自动被 B14 审计中间件记录
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_ORDER_MANAGE
from src.schemas.b13_order_admin import (
    OrderBatchValidateRequest,
    OrderTransitionExecuteRequest,
    OrderTransitionValidateRequest,
)
from src.services.b13_order_admin_service import B13OrderAdminService

logger = logging.getLogger("api.b13_order_admin")

router = APIRouter(
    prefix="/api/v1/admin/b13/orders",
    tags=["后台-订单管理(B13-1)"],
)


@router.get("")
async def list_orders(
    request: Request,
    keyword: Optional[str] = Query(None, max_length=256, description="搜索关键词（商品标题/渠道订单号/平台订单号模糊匹配）"),
    order_status: Optional[int] = Query(None, ge=10, le=60, description="订单状态筛选：10-待付款 20-已付款(冻结) 30-可结算 40-已结算 50-已失效 60-已退款"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识：myq/orderx"),
    user_id: Optional[int] = Query(None, ge=1, description="用户ID精确筛选"),
    start_time: Optional[datetime] = Query(None, description="创建时间范围-开始"),
    end_time: Optional[datetime] = Query(None, description="创建时间范围-结束"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """订单列表多条件筛选查询"""
    request_id = get_request_id(request)
    try:
        items, total = await B13OrderAdminService.list_orders(
            keyword=keyword,
            order_status=order_status,
            channel_code=channel_code,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
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


@router.get("/{order_id}")
async def get_order_detail(
    request: Request,
    order_id: int,
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """订单详情（含佣金流水）"""
    request_id = get_request_id(request)
    try:
        data = await B13OrderAdminService.get_order_detail(order_id)
        if data is None:
            return error_response(
                code=404, msg="订单不存在", request_id=request_id
            )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/validate")
async def validate_transition(
    request: Request,
    body: OrderTransitionValidateRequest,
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """校验单个订单状态流转是否合法"""
    request_id = get_request_id(request)
    try:
        data = await B13OrderAdminService.validate_transition(
            order_id=body.order_id,
            target_status=body.target_status,
            is_manual_override=body.is_manual_override,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/validate/batch")
async def batch_validate_transition(
    request: Request,
    body: OrderBatchValidateRequest,
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """批量校验多个订单的状态流转"""
    request_id = get_request_id(request)
    try:
        items_data = [item.model_dump() for item in body.items]
        data = await B13OrderAdminService.batch_validate_transition(items_data)
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/{order_id}/transition")
async def execute_transition(
    request: Request,
    order_id: int,
    body: OrderTransitionExecuteRequest,
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """执行订单状态流转"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        admin_user_name = payload.get("username", "")
        data = await B13OrderAdminService.execute_transition(
            order_id=order_id,
            target_status=body.target_status,
            operation_type=body.operation_type,
            operator_id=admin_user_id,
            operator_name=admin_user_name,
            remark=body.remark,
        )
        return success_response(data=data, msg="状态流转成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{order_id}/logs")
async def list_operation_logs(
    request: Request,
    order_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_ORDER_MANAGE])),
):
    """查询指定订单的操作日志"""
    request_id = get_request_id(request)
    try:
        data = await B13OrderAdminService.list_operation_logs(
            order_id=order_id,
            page=page,
            page_size=page_size,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
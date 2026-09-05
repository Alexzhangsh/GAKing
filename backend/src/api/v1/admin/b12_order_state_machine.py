# @ai-generated
"""
B12-1 后台订单状态机管控 API 路由
路由前缀：/api/v1/admin/b12/order-state

功能范围：
1. 订单状态信息查询（含合法流转目标）
2. 状态流转校验（单条/批量）
3. 执行状态流转（含人工干预）
4. 操作日志查询
5. 异常订单巡检手动触发
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b12_constants import (
    ORDER_STATUS_LABELS,
    PERM_ORDER_OPERATION_LOG,
    PERM_ORDER_STATE_MACHINE,
    OrderOperationType,
)
from src.config.constants import OrderStatus
from src.dao.b12_order_operation_log_dao import OrderOperationLogDAO
from src.dao.order_dao import OrderDAO
from src.db.base import DatabaseManager
from src.services.b12_order_state_machine_service import B12OrderStateMachineService

logger = logging.getLogger("api.admin.b12_order_state")

router = APIRouter(prefix="/api/v1/admin/b12/order-state", tags=["后台-订单状态机(B12)"])


# ── 依赖注入 ──────────────────────────────────────────────


async def get_admin_info(
    payload: dict = Depends(require_any_permission([PERM_ORDER_STATE_MACHINE, PERM_ORDER_OPERATION_LOG])),
) -> dict:
    return {"user_id": int(payload["user_id"]), "user_name": payload.get("real_name", "")}


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════


class TransitionValidateRequest(BaseModel):
    """单条状态流转校验请求"""
    order_id: int = Field(..., description="订单ID")
    target_status: int = Field(..., description="目标状态值")


class BatchTransitionValidateRequest(BaseModel):
    """批量状态流转校验请求"""
    order_ids: List[int] = Field(..., min_length=1, max_length=100, description="订单ID列表")
    target_status: int = Field(..., description="目标状态值")


class TransitionExecuteRequest(BaseModel):
    """执行状态流转请求"""
    order_id: int = Field(..., description="订单ID")
    target_status: int = Field(..., description="目标状态值")
    operation_type: str = Field(OrderOperationType.STATUS_TRANSITION, description="操作类型")
    remark: str = Field("", max_length=512, description="操作原因")


class ManualOverrideRequest(BaseModel):
    """人工干预状态请求"""
    order_id: int = Field(..., description="订单ID")
    target_status: int = Field(..., description="目标状态值")
    remark: str = Field(..., max_length=512, description="人工干预原因")


# ════════════════════════════════════════════════════════════
# 1. 订单状态信息
# ════════════════════════════════════════════════════════════


@router.get("/status/{order_id}")
async def get_order_status(
    request: Request,
    order_id: int,
    admin_info: dict = Depends(get_admin_info),
):
    """查询订单当前状态信息（含合法流转目标）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)
            data = await svc.get_order_status_info(order_id)
            if data is None:
                raise ValueError(f"订单不存在: order_id={order_id}")
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 状态流转校验
# ════════════════════════════════════════════════════════════


@router.post("/validate")
async def validate_transition(
    request: Request,
    body: TransitionValidateRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """校验单条订单状态流转是否合法"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            order = await order_dao.get_by_id(body.order_id)
            if order is None:
                raise ValueError(f"订单不存在: order_id={body.order_id}")

            current_status = int(order.order_status)
            validation = svc.validate_transition(current_status, body.target_status)
            validation["order_id"] = body.order_id
            validation["out_order_no"] = order.out_order_no or ""
            validation["current_status"] = current_status
            validation["current_status_label"] = ORDER_STATUS_LABELS.get(current_status, "未知")
            validation["target_status"] = body.target_status
            validation["target_status_label"] = ORDER_STATUS_LABELS.get(body.target_status, "未知")

            return success_response(data=validation, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/validate/batch")
async def batch_validate_transitions(
    request: Request,
    body: BatchTransitionValidateRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """批量校验多个订单的状态流转"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            results = await svc.batch_validate_transitions(
                order_ids=body.order_ids,
                target_status=body.target_status,
            )
            return success_response(data={
                "total": len(results),
                "valid_count": sum(1 for r in results if r["valid"]),
                "invalid_count": sum(1 for r in results if not r["valid"]),
                "target_status": body.target_status,
                "target_status_label": ORDER_STATUS_LABELS.get(body.target_status, "未知"),
                "items": results,
            }, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 执行状态流转
# ════════════════════════════════════════════════════════════


@router.post("/transition")
async def execute_transition(
    request: Request,
    body: TransitionExecuteRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """执行订单状态流转（自动校验+写入操作日志）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            data = await svc.transition_order_status(
                order_id=body.order_id,
                target_status=body.target_status,
                operation_type=body.operation_type,
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
                remark=body.remark,
            )
            return success_response(data=data, msg="状态流转成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/manual-override")
async def manual_override_status(
    request: Request,
    body: ManualOverrideRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """人工干预订单状态（跳过部分终态检查，需记录操作原因）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            data = await svc.transition_order_status(
                order_id=body.order_id,
                target_status=body.target_status,
                operation_type=OrderOperationType.MANUAL_OVERRIDE,
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
                remark=body.remark,
            )
            return success_response(data=data, msg="人工干预成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 操作日志查询
# ════════════════════════════════════════════════════════════


@router.get("/operation-logs")
async def list_operation_logs(
    request: Request,
    order_id: Optional[int] = Query(None, description="订单ID"),
    operation_type: Optional[str] = Query(None, description="操作类型"),
    operator_id: Optional[int] = Query(None, description="操作人ID"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    order_status_from: Optional[int] = Query(None, description="操作前状态"),
    order_status_to: Optional[int] = Query(None, description="操作后状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    admin_info: dict = Depends(get_admin_info),
):
    """订单操作日志列表（多条件分页查询）"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            data = await svc.list_operation_logs(
                order_id=order_id,
                operation_type=operation_type,
                operator_id=operator_id,
                start_time=start_dt,
                end_time=end_dt,
                order_status_from=order_status_from,
                order_status_to=order_status_to,
                page=page,
                page_size=page_size,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 异常订单巡检
# ════════════════════════════════════════════════════════════


@router.post("/patrol")
async def trigger_anomaly_patrol(
    request: Request,
    admin_info: dict = Depends(get_admin_info),
):
    """手动触发订单异常巡检"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            svc = B12OrderStateMachineService(order_dao, log_dao)

            data = await svc.patrol_anomaly_orders()
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 6. 状态机规则查询
# ════════════════════════════════════════════════════════════


@router.get("/rules")
async def get_state_machine_rules(
    request: Request,
    admin_info: dict = Depends(get_admin_info),
):
    """查询订单状态机完整规则（所有合法流转路径）"""
    request_id = get_request_id(request)
    try:
        from src.config.b12_constants import (
            ORDER_STATUS_TRANSITIONS,
            ORDER_STATUS_TRANSITION_CONDITIONS,
            TERMINAL_STATUSES,
            MANUAL_OVERRIDEABLE_STATUSES,
        )

        rules = []
        for from_status, to_statuses in ORDER_STATUS_TRANSITIONS.items():
            from_label = ORDER_STATUS_LABELS.get(from_status, str(from_status))
            for to_status in to_statuses:
                to_label = ORDER_STATUS_LABELS.get(to_status, str(to_status))
                condition = ORDER_STATUS_TRANSITION_CONDITIONS.get(
                    (from_status, to_status), ""
                )
                rules.append({
                    "from_status": int(from_status),
                    "from_label": from_label,
                    "to_status": int(to_status),
                    "to_label": to_label,
                    "condition": condition,
                })

        return success_response(data={
            "rules": rules,
            "terminal_statuses": [int(s) for s in TERMINAL_STATUSES],
            "manual_overrideable_statuses": [int(s) for s in MANUAL_OVERRIDEABLE_STATUSES],
            "all_statuses": [
                {"status": int(s), "label": label}
                for s, label in ORDER_STATUS_LABELS.items()
            ],
        }, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
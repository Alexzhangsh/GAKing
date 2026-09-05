# @ai-generated
"""
后台退款冲减管理接口层（B05-6）
路由前缀：/api/v1/admin/refund-deduction
职责：管理员身份识别 → 参数校验 → 调用 RefundDeductionService → 统一响应封装
不包含任何业务逻辑，业务规则全部在 Service 层

接口清单：
1. POST /pre-validate             退款扣减前置校验
2. POST /execute                  执行退款扣减
3. GET  /logs/{order_id}          按订单ID查询退款操作日志
4. GET  /logs                     多条件查询退款操作日志（后台审计）
"""
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.dao.order_refund_operation_log_dao import OrderRefundOperationLogDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.db.init_db import DatabaseManager
from src.schemas.refund_deduction import (
    RefundDeductionExecuteRequest,
    RefundDeductionPreValidateRequest,
    RefundOperationLogItem,
    RefundOperationLogListResponse,
)
from src.services.commission_flow_validation_service import (
    CommissionFlowValidationService,
)
from src.services.refund_deduction_service import RefundDeductionService

logger = logging.getLogger("api.admin.refund_deduction")

router = APIRouter(
    prefix="/api/v1/admin/refund-deduction",
    tags=["后台-退款冲减管理"],
)


# ── 依赖注入 ──────────────────────────────────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["commission:settle"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC commission:settle 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_deduction_service(
    db: AsyncSession = Depends(get_db),
) -> RefundDeductionService:
    """构造 RefundDeductionService 实例"""
    order_dao = OrderDAO(db)
    flow_dao = CommissionFlowDAO(db)
    settlement_dao = CommissionSettlementDAO(db)
    account_dao = UserCommissionAccountDAO(db)
    log_dao = OrderRefundOperationLogDAO(db)
    validation_log_dao = CommissionFlowValidationLogDAO(db)
    validation_service = CommissionFlowValidationService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        validation_log_dao=validation_log_dao,
    )
    return RefundDeductionService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        settlement_dao=settlement_dao,
        account_dao=account_dao,
        log_dao=log_dao,
        validation_service=validation_service,
    )


# ══════════════════════════════════════════════════════
# 1. 退款扣减前置校验
# ══════════════════════════════════════════════════════


@router.post("/pre-validate")
async def pre_validate_deduct(
    body: RefundDeductionPreValidateRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: RefundDeductionService = Depends(get_deduction_service),
):
    """1. 退款扣减前置校验

    校验项：
    - 订单存在性
    - 订单状态（必须为 REFUNDED 已退款）
    - 佣金流水存在性（至少有一条 ORDER 类型流水）
    - 佣金流水转账状态（PENDING 或 SUCCESS）
    - 重复扣减拦截（已有 DEDUCT 流水拦截）
    - 用户归属校验

    返回各项校验明细（passed/failed），支持前端逐项展示。
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 退款扣减前置校验 admin=%s order_id=%s",
        request_id, admin_user_id, body.order_id,
    )
    try:
        result = await svc.pre_validate_deduct(
            order_id=body.order_id,
            operator_id=admin_user_id,
        )
        if result.validation_result == "FAIL":
            return error_response(
                code=400,
                msg=result.error_message or "退款扣减前置校验未通过",
                request_id=request_id,
                data=result.model_dump(),
            )
        return success_response(data=result.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 执行退款扣减
# ══════════════════════════════════════════════════════


@router.post("/execute")
async def execute_refund_deduction(
    body: RefundDeductionExecuteRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: RefundDeductionService = Depends(get_deduction_service),
):
    """2. 执行单订单退款扣减

    流程：
    1. 前置校验（复用 B05-5 校验服务）
    2. 校验通过 → 执行原子冲减（PENDING→FAILED / SUCCESS→扣余额）
    3. 记录退款操作日志

    幂等：已有 DEDUCT 流水自动跳过，返回 skipped 状态。

    Args:
        order_id: 订单ID
        remark: 操作备注（可选）
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 执行退款扣减 admin=%s order_id=%s",
        request_id, admin_user_id, body.order_id,
    )
    try:
        result = await svc.execute_refund_deduction(
            order_id=body.order_id,
            operator_id=admin_user_id,
            remark=body.remark,
        )
        return success_response(data=result.model_dump(), request_id=request_id)
    except ValueError as ve:
        return error_response(
            code=400,
            msg=str(ve),
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 按订单查询退款操作日志
# ══════════════════════════════════════════════════════


@router.get("/logs/{order_id}")
async def list_refund_logs_by_order(
    order_id: int,
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
):
    """3. 按订单ID查询退款操作日志（B05-6 新增）

    查询指定订单的退款冲减操作历史记录，按时间降序排列。
    """
    request_id = get_request_id(request)
    try:
        log_dao = OrderRefundOperationLogDAO(db)
        items, total = await log_dao.list_by_order_id(
            order_id=order_id,
            page=page,
            page_size=page_size,
        )
        log_items = [
            RefundOperationLogItem(
                id=item.id,
                order_id=item.order_id,
                operator_id=item.operator_id,
                operation_type=item.operation_type,
                order_status_before=item.order_status_before,
                order_status_after=item.order_status_after,
                deduct_amount=float(item.deduct_amount),
                flow_type=item.flow_type or "",
                flow_transfer_status=item.flow_transfer_status or "",
                old_available_balance=float(item.old_available_balance),
                new_available_balance=float(item.new_available_balance),
                old_total_balance=float(item.old_total_balance),
                new_total_balance=float(item.new_total_balance),
                deduct_flow_id=item.deduct_flow_id,
                remark=item.remark or "",
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = RefundOperationLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 多条件查询退款操作日志
# ══════════════════════════════════════════════════════


@router.get("/logs")
async def list_refund_logs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    operator_id: int = Query(default=None, gt=0, description="操作人ID筛选"),
    operation_type: str = Query(default=None, description="操作类型筛选：DEDUCT"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """4. 多条件查询退款操作日志（后台审计用）

    支持按订单ID、操作人ID、操作类型筛选。
    """
    request_id = get_request_id(request)
    try:
        log_dao = OrderRefundOperationLogDAO(db)
        items, total = await log_dao.list_with_filters(
            order_id=order_id,
            operator_id=operator_id,
            operation_type=operation_type or None,
            page=page,
            page_size=page_size,
        )
        log_items = [
            RefundOperationLogItem(
                id=item.id,
                order_id=item.order_id,
                operator_id=item.operator_id,
                operation_type=item.operation_type,
                order_status_before=item.order_status_before,
                order_status_after=item.order_status_after,
                deduct_amount=float(item.deduct_amount),
                flow_type=item.flow_type or "",
                flow_transfer_status=item.flow_transfer_status or "",
                old_available_balance=float(item.old_available_balance),
                new_available_balance=float(item.new_available_balance),
                old_total_balance=float(item.old_total_balance),
                new_total_balance=float(item.new_total_balance),
                deduct_flow_id=item.deduct_flow_id,
                remark=item.remark or "",
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = RefundOperationLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
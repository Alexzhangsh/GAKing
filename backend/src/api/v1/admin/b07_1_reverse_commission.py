# @ai-generated
"""
B07-1 退款逆向佣金冲减 API 路由
路由前缀：/api/v1/admin/b07/reverse-commission
权限码：reverse:commission

功能范围：
1. 识别退款订单（手动触发扫描）
2. 执行单条冲减
3. 批量执行冲减
4. 冲减记录查询
5. 手动重试失败记录
6. 手动调整冲减金额
7. 冲减统计概览
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b07_1_constants import (
    PERM_REVERSE_COMMISSION,
    REVERSE_STATUS_LABELS,
    ReverseCommissionStatus,
    TASK_REVERSE_COMMISSION_BATCH_SIZE,
)
from src.dao.b07_1_reverse_commission_dao import (
    ReverseCommissionQueryDAO,
    ReverseCommissionRecordDAO,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.dao.order_refund_operation_log_dao import OrderRefundOperationLogDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.db.init_db import DatabaseManager
from src.services.b07_1_reverse_commission_service import ReverseCommissionService
from src.services.commission_flow_validation_service import (
    CommissionFlowValidationService,
)
from src.services.refund_deduction_service import RefundDeductionService

logger = logging.getLogger("api.admin.b07_1_reverse_commission")

router = APIRouter(
    prefix="/api/v1/admin/b07/reverse-commission",
    tags=["后台-逆向佣金冲减(B07-1)"],
)


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════


class AdjustRequest(BaseModel):
    """手动调整冲减金额请求"""
    adjust_amount: float = Field(..., gt=0, description="调整后的冲减金额(元)，必须大于0")
    remark: str = Field("", max_length=512, description="调整备注")


class BatchExecuteRequest(BaseModel):
    """批量执行冲减请求"""
    limit: int = Field(TASK_REVERSE_COMMISSION_BATCH_SIZE, ge=1, le=200, description="单次处理条数")


class IdentifyRequest(BaseModel):
    """识别退款订单请求"""
    limit: int = Field(TASK_REVERSE_COMMISSION_BATCH_SIZE, ge=1, le=200, description="单次识别上限")


# ════════════════════════════════════════════════════════════
# 依赖注入
# ════════════════════════════════════════════════════════════


async def get_admin_info(
    payload: dict = Depends(require_any_permission([PERM_REVERSE_COMMISSION])),
) -> dict:
    """获取后台管理员信息"""
    return {
        "user_id": int(payload["user_id"]),
        "user_name": payload.get("real_name", ""),
    }


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def _build_service(db: AsyncSession) -> ReverseCommissionService:
    """构造逆向冲减服务（注入所有依赖）"""
    record_dao = ReverseCommissionRecordDAO(db)
    query_dao = ReverseCommissionQueryDAO(db)
    order_dao = OrderDAO(db)
    flow_dao = CommissionFlowDAO(db)
    account_dao = UserCommissionAccountDAO(db)
    settlement_dao = CommissionSettlementDAO(db)
    log_dao = OrderRefundOperationLogDAO(db)
    validation_log_dao = CommissionFlowValidationLogDAO(db)
    validation_service = CommissionFlowValidationService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        validation_log_dao=validation_log_dao,
    )
    deduction_service = RefundDeductionService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        settlement_dao=settlement_dao,
        account_dao=account_dao,
        log_dao=log_dao,
        validation_service=validation_service,
    )
    return ReverseCommissionService(
        record_dao=record_dao,
        query_dao=query_dao,
        order_dao=order_dao,
        flow_dao=flow_dao,
        deduction_service=deduction_service,
    )


def _serialize_record(record) -> Dict[str, Any]:
    """序列化冲减记录"""
    return {
        "id": record.id,
        "order_id": record.order_id,
        "out_order_no": record.out_order_no or "",
        "user_id": record.user_id,
        "channel_code": record.channel_code or "",
        "original_commission": float(record.original_commission or 0),
        "deducted_amount": float(record.deducted_amount or 0),
        "flow_type": record.flow_type or "",
        "flow_transfer_status": record.flow_transfer_status or "",
        "status": record.status,
        "status_label": REVERSE_STATUS_LABELS.get(ReverseCommissionStatus(record.status), record.status),
        "retry_count": record.retry_count or 0,
        "max_retry": record.max_retry or 3,
        "error_message": record.error_message or "",
        "deduct_flow_id": record.deduct_flow_id,
        "operator_id": record.operator_id,
        "operator_name": record.operator_name or "",
        "remark": record.remark or "",
        "frozen_at": record.frozen_at.strftime("%Y-%m-%d %H:%M:%S") if record.frozen_at else None,
        "clawback_at": record.clawback_at.strftime("%Y-%m-%d %H:%M:%S") if record.clawback_at else None,
        "create_time": record.create_time.strftime("%Y-%m-%d %H:%M:%S") if record.create_time else None,
        "update_time": record.update_time.strftime("%Y-%m-%d %H:%M:%S") if record.update_time else None,
    }


# ════════════════════════════════════════════════════════════
# 1. 识别退款订单
# ════════════════════════════════════════════════════════════


@router.post("/identify")
async def identify_refund_orders(
    request: Request,
    body: IdentifyRequest = IdentifyRequest(),
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """识别退款订单并创建冲减记录

    扫描 REFUNDED 状态且无冲减记录的订单，为其创建 IDENTIFIED 状态记录。
    """
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        result = await service.identify_refund_orders(
            limit=body.limit,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 执行单条冲减
# ════════════════════════════════════════════════════════════


@router.post("/execute/{record_id}")
async def execute_reverse_commission(
    request: Request,
    record_id: int = Path(..., description="冲减记录ID"),
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """执行单条逆向冲减

    标记 FROZEN → 调用 B05-6 扣减逻辑 → 成功标记 CLAWBACK_DONE / 失败标记 FAILED
    """
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        result = await service.execute_reverse_commission(
            record_id=record_id,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 批量执行冲减
# ════════════════════════════════════════════════════════════


@router.post("/batch-execute")
async def batch_execute_reverse_commission(
    request: Request,
    body: BatchExecuteRequest = BatchExecuteRequest(),
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """批量执行逆向冲减

    先处理 IDENTIFIED 状态的记录，再处理可重试的失败记录。
    """
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        result = await service.batch_execute(
            limit=body.limit,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 冲减记录查询
# ════════════════════════════════════════════════════════════


@router.get("/records")
async def list_reverse_commission_records(
    request: Request,
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="冲减状态筛选"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    order_id: Optional[int] = Query(None, description="订单ID"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """多条件分页查询逆向冲减记录"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        dao = ReverseCommissionRecordDAO(db)
        items, total = await dao.list_with_filters(
            status=status or None,
            channel_code=channel_code or None,
            user_id=user_id,
            order_id=order_id,
            start_time=start_dt,
            end_time=end_dt,
            page=page,
            page_size=page_size,
        )

        return success_response(
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_serialize_record(item) for item in items],
            },
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 手动重试
# ════════════════════════════════════════════════════════════


@router.post("/{record_id}/retry")
async def retry_failed_record(
    request: Request,
    record_id: int = Path(..., description="冲减记录ID"),
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """手动重试失败的冲减记录"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        result = await service.retry_failed(
            record_id=record_id,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 6. 手动调整冲减金额
# ════════════════════════════════════════════════════════════


@router.post("/{record_id}/adjust")
async def adjust_commission_amount(
    request: Request,
    record_id: int = Path(..., description="冲减记录ID"),
    body: AdjustRequest = ...,
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """手动调整冲减金额

    仅对 FAILED/IDENTIFIED 状态的记录可调整。
    调整后记录状态变为 ADJUSTED。
    """
    request_id = get_request_id(request)
    try:
        adjust_amount = Decimal(str(body.adjust_amount))
        service = _build_service(db)
        result = await service.adjust_commission(
            record_id=record_id,
            adjust_amount=adjust_amount,
            operator_id=admin_info["user_id"],
            operator_name=admin_info.get("user_name", ""),
            remark=body.remark,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 7. 冲减统计概览
# ════════════════════════════════════════════════════════════


@router.get("/statistics")
async def get_reverse_commission_statistics(
    request: Request,
    admin_info: dict = Depends(get_admin_info),
    db: AsyncSession = Depends(get_db),
):
    """获取逆向冲减统计概览"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        stats = await service.get_statistics()
        return success_response(data=stats, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
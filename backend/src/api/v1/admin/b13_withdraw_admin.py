# @ai-generated
"""
B13-1 提现管理后台 API 路由
权限码：withdraw:manage（全部接口需此权限）
路由前缀：/api/v1/admin/b13/withdraws
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
from src.config.b13_b14_constants import PERM_WITHDRAW_MANAGE
from src.schemas.b13_withdraw_admin import (
    WithdrawReviewRequest,
    WithdrawTransferRequest,
)
from src.services.b13_withdraw_admin_service import B13WithdrawAdminService

logger = logging.getLogger("api.b13_withdraw_admin")

router = APIRouter(
    prefix="/api/v1/admin/b13/withdraws",
    tags=["后台-提现管理(B13-1)"],
)


@router.get("")
async def list_withdraws(
    request: Request,
    user_id: Optional[int] = Query(None, description="平台用户ID筛选"),
    status: Optional[str] = Query(
        None, description="提现状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED"
    ),
    start_time: Optional[str] = Query(None, description="创建时间起始(ISO格式，如 2026-01-01T00:00:00)"),
    end_time: Optional[str] = Query(None, description="创建时间截止(ISO格式，如 2026-01-31T23:59:59)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_WITHDRAW_MANAGE])),
):
    """提现列表（多条件分页查询）"""
    request_id = get_request_id(request)
    try:
        # 解析可选的时间范围参数
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        items, total = await B13WithdrawAdminService.list_withdraws(
            user_id=user_id,
            status=status,
            start_time=start_dt,
            end_time=end_dt,
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


@router.get("/{apply_id}")
async def get_withdraw_detail(
    request: Request,
    apply_id: int,
    payload: dict = Depends(require_any_permission([PERM_WITHDRAW_MANAGE])),
):
    """提现详情"""
    request_id = get_request_id(request)
    try:
        data = await B13WithdrawAdminService.get_withdraw_detail(apply_id)
        if data is None:
            return error_response(
                code=404, msg="提现申请不存在", request_id=request_id
            )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/{apply_id}/review")
async def review_withdraw(
    request: Request,
    apply_id: int,
    body: WithdrawReviewRequest,
    payload: dict = Depends(require_any_permission([PERM_WITHDRAW_MANAGE])),
):
    """审核提现（通过/驳回）

    状态机：
        approve: PENDING → APPROVED
        reject:  PENDING/APPROVED → REJECTED
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        admin_user_name = payload.get("username", "")
        data = await B13WithdrawAdminService.review_withdraw(
            apply_id=apply_id,
            action=body.action,
            review_remark=body.review_remark,
            reject_reason=body.reject_reason,
            operator_id=admin_user_id,
            operator_name=admin_user_name,
        )
        msg = "审核通过" if body.action == "approve" else "已驳回"
        return success_response(data=data, msg=msg, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{apply_id}/transfer")
async def update_transfer_info(
    request: Request,
    apply_id: int,
    body: WithdrawTransferRequest,
    payload: dict = Depends(require_any_permission([PERM_WITHDRAW_MANAGE])),
):
    """更新转账信息（微信打款后）

    状态流转：APPROVED/PROCESSING → PROCESSING（更新转账批次号和时间）
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        admin_user_name = payload.get("username", "")
        data = await B13WithdrawAdminService.update_transfer_info(
            apply_id=apply_id,
            transfer_batch_id=body.transfer_batch_id,
            operator_id=admin_user_id,
            operator_name=admin_user_name,
        )
        return success_response(data=data, msg="转账信息已更新", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{apply_id}/logs")
async def get_review_logs(
    request: Request,
    apply_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    payload: dict = Depends(require_any_permission([PERM_WITHDRAW_MANAGE])),
):
    """获取提现审核日志（按时间升序）"""
    request_id = get_request_id(request)
    try:
        items, total = await B13WithdrawAdminService.get_review_logs(
            apply_id=apply_id,
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
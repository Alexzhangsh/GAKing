# @ai-generated
"""
B08-1 用户佣金资产账户管理 API 路由
路由前缀：/api/v1/admin/b08
权限码：fund:account:view / fund:account:credit / fund:account:debit / fund:account:freeze / fund:flow:view

功能范围：
1. 账户列表查询（分页+筛选）
2. 账户详情查询
3. 手工入账
4. 手工扣款
5. 冻结余额
6. 解冻余额
7. 资金流水查询
8. 平台资产统计
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

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
from src.config.b08_1_constants import (
    FUND_FLOW_TYPE_LABELS,
    PERM_ACCOUNT_CREDIT,
    PERM_ACCOUNT_DEBIT,
    PERM_ACCOUNT_FREEZE,
    PERM_ACCOUNT_VIEW,
    PERM_FUND_FLOW_VIEW,
)
from src.dao.b08_1_fund_flow_dao import FundFlowDAO
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.db.init_db import DatabaseManager
from src.services.b08_1_account_service import AccountService

logger = logging.getLogger("api.admin.b08_1_account")

router = APIRouter(
    prefix="/api/v1/admin/b08",
    tags=["后台-用户佣金资产管理(B08-1)"],
)


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════


class CreditRequest(BaseModel):
    """手工入账请求"""
    amount: float = Field(..., gt=0, description="入账金额(元)，必须大于0")
    remark: str = Field("", max_length=512, description="备注")
    order_id: Optional[int] = Field(None, description="关联订单ID")


class DebitRequest(BaseModel):
    """手工扣款请求"""
    amount: float = Field(..., gt=0, description="扣款金额(元)，必须大于0")
    remark: str = Field("", max_length=512, description="备注")
    order_id: Optional[int] = Field(None, description="关联订单ID")


class FreezeRequest(BaseModel):
    """冻结/解冻余额请求"""
    amount: float = Field(..., gt=0, description="金额(元)，必须大于0")
    remark: str = Field("", max_length=512, description="备注")


# ════════════════════════════════════════════════════════════
# 依赖注入
# ════════════════════════════════════════════════════════════


async def get_admin_info_view(
    payload: dict = Depends(require_any_permission([PERM_ACCOUNT_VIEW])),
) -> dict:
    """获取后台管理员信息（账户查看权限）"""
    return {
        "user_id": int(payload["user_id"]),
        "user_name": payload.get("real_name", ""),
    }


async def get_admin_info_full(
    payload: dict = Depends(require_any_permission([
        PERM_ACCOUNT_VIEW,
        PERM_ACCOUNT_CREDIT,
        PERM_ACCOUNT_DEBIT,
        PERM_ACCOUNT_FREEZE,
        PERM_FUND_FLOW_VIEW,
    ])),
) -> dict:
    """获取后台管理员信息（全量权限）"""
    return {
        "user_id": int(payload["user_id"]),
        "user_name": payload.get("real_name", ""),
    }


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def _build_service(db: AsyncSession) -> AccountService:
    """构造账户管理服务"""
    account_dao = UserCommissionAccountDAO(db)
    fund_flow_dao = FundFlowDAO(db)
    return AccountService(
        account_dao=account_dao,
        fund_flow_dao=fund_flow_dao,
    )


def _parse_time(t: Optional[str]) -> Optional[datetime]:
    """解析时间字符串"""
    if t:
        try:
            return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None


# ════════════════════════════════════════════════════════════
# 1. 账户列表查询
# ════════════════════════════════════════════════════════════


@router.get("/accounts")
async def list_accounts(
    request: Request,
    admin_info: dict = Depends(get_admin_info_view),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Query(None, description="用户ID"),
    min_available: Optional[float] = Query(None, ge=0, description="可用余额下限(元)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """分页查询用户佣金账户列表"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        min_avail = Decimal(str(min_available)) if min_available is not None else None
        result = await service.list_accounts(
            user_id=user_id,
            min_available=min_avail,
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 账户详情查询
# ════════════════════════════════════════════════════════════


@router.get("/accounts/{user_id}")
async def get_account_detail(
    request: Request,
    user_id: int = Path(..., description="用户ID"),
    admin_info: dict = Depends(get_admin_info_view),
    db: AsyncSession = Depends(get_db),
):
    """查询用户账户详情（含余额信息）"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        account = await service.get_account_by_user_id(user_id)
        if account is None:
            return error_response(
                msg=f"用户账户不存在: user_id={user_id}",
                request_id=request_id,
            )
        return success_response(data=account, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 手工入账
# ════════════════════════════════════════════════════════════


@router.post("/accounts/{user_id}/credit")
async def credit_account(
    request: Request,
    user_id: int = Path(..., description="用户ID"),
    body: CreditRequest = ...,
    admin_info: dict = Depends(require_any_permission([PERM_ACCOUNT_CREDIT])),
    db: AsyncSession = Depends(get_db),
):
    """手工入账：向用户账户增加可用余额"""
    request_id = get_request_id(request)
    try:
        admin_data = {
            "user_id": int(admin_info["user_id"]),
            "user_name": admin_info.get("real_name", ""),
        }
        amount = Decimal(str(body.amount))
        service = _build_service(db)
        result = await service.credit(
            user_id=user_id,
            amount=amount,
            remark=body.remark,
            operator_id=admin_data["user_id"],
            operator_name=admin_data["user_name"],
            order_id=body.order_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 手工扣款
# ════════════════════════════════════════════════════════════


@router.post("/accounts/{user_id}/debit")
async def debit_account(
    request: Request,
    user_id: int = Path(..., description="用户ID"),
    body: DebitRequest = ...,
    admin_info: dict = Depends(require_any_permission([PERM_ACCOUNT_DEBIT])),
    db: AsyncSession = Depends(get_db),
):
    """手工扣款：从用户账户扣减可用余额（FOR UPDATE 行锁防超扣）"""
    request_id = get_request_id(request)
    try:
        admin_data = {
            "user_id": int(admin_info["user_id"]),
            "user_name": admin_info.get("real_name", ""),
        }
        amount = Decimal(str(body.amount))
        service = _build_service(db)
        result = await service.debit(
            user_id=user_id,
            amount=amount,
            remark=body.remark,
            operator_id=admin_data["user_id"],
            operator_name=admin_data["user_name"],
            order_id=body.order_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 冻结余额
# ════════════════════════════════════════════════════════════


@router.post("/accounts/{user_id}/freeze")
async def freeze_account_balance(
    request: Request,
    user_id: int = Path(..., description="用户ID"),
    body: FreezeRequest = ...,
    admin_info: dict = Depends(require_any_permission([PERM_ACCOUNT_FREEZE])),
    db: AsyncSession = Depends(get_db),
):
    """冻结余额：可用余额减少，冻结余额增加"""
    request_id = get_request_id(request)
    try:
        admin_data = {
            "user_id": int(admin_info["user_id"]),
            "user_name": admin_info.get("real_name", ""),
        }
        amount = Decimal(str(body.amount))
        service = _build_service(db)
        result = await service.freeze_balance(
            user_id=user_id,
            amount=amount,
            remark=body.remark,
            operator_id=admin_data["user_id"],
            operator_name=admin_data["user_name"],
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 6. 解冻余额
# ════════════════════════════════════════════════════════════


@router.post("/accounts/{user_id}/unfreeze")
async def unfreeze_account_balance(
    request: Request,
    user_id: int = Path(..., description="用户ID"),
    body: FreezeRequest = ...,
    admin_info: dict = Depends(require_any_permission([PERM_ACCOUNT_FREEZE])),
    db: AsyncSession = Depends(get_db),
):
    """解冻余额：冻结余额减少，可用余额增加"""
    request_id = get_request_id(request)
    try:
        admin_data = {
            "user_id": int(admin_info["user_id"]),
            "user_name": admin_info.get("real_name", ""),
        }
        amount = Decimal(str(body.amount))
        service = _build_service(db)
        result = await service.unfreeze_balance(
            user_id=user_id,
            amount=amount,
            remark=body.remark,
            operator_id=admin_data["user_id"],
            operator_name=admin_data["user_name"],
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 7. 资金流水查询
# ════════════════════════════════════════════════════════════


@router.get("/fund-flows")
async def list_fund_flows(
    request: Request,
    admin_info: dict = Depends(require_any_permission([PERM_FUND_FLOW_VIEW])),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Query(None, description="用户ID"),
    flow_type: Optional[str] = Query(None, description="流水类型"),
    order_id: Optional[int] = Query(None, description="关联订单ID"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """多条件分页查询资金流水"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        result = await service.list_fund_flows(
            user_id=user_id,
            flow_type=flow_type,
            order_id=order_id,
            start_time=_parse_time(start_time),
            end_time=_parse_time(end_time),
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 8. 平台资产统计
# ════════════════════════════════════════════════════════════


@router.get("/statistics")
async def get_platform_statistics(
    request: Request,
    admin_info: dict = Depends(get_admin_info_view),
    db: AsyncSession = Depends(get_db),
):
    """获取全平台资产统计概览"""
    request_id = get_request_id(request)
    try:
        service = _build_service(db)
        stats = await service.get_platform_statistics()
        return success_response(data=stats, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
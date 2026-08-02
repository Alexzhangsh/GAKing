# @ai-generated
"""
B07 佣金结算接口请求/响应 Pydantic DTO
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── 请求 DTO ─────────────────────────────────────────


class CommissionSettleRequest(BaseModel):
    """手动触发批量结算请求"""

    limit: Optional[int] = Field(
        default=200,
        ge=1,
        le=1000,
        description="单轮处理订单上限（默认200，最大1000）",
    )


class CommissionRecalculateRequest(BaseModel):
    """佣金重算请求"""

    order_id: int = Field(..., gt=0, description="订单ID")


class RefundDeductRequest(BaseModel):
    """退款扣减请求（支持单笔和批量）"""

    order_id: Optional[int] = Field(
        default=None, gt=0, description="指定订单ID（单笔扣减）"
    )
    limit: Optional[int] = Field(
        default=100,
        ge=1,
        le=500,
        description="批量扣减上限（仅 order_id 为空时生效）",
    )


class CommissionFlowQuery(BaseModel):
    """佣金流水查询参数"""

    user_id: Optional[int] = Field(default=None, gt=0, description="用户ID筛选")
    order_id: Optional[int] = Field(default=None, gt=0, description="订单ID筛选")
    flow_type: Optional[str] = Field(
        default=None, description="流水类型：ORDER/SUPPLEMENT/DEDUCT"
    )
    transfer_status: Optional[str] = Field(
        default=None, description="转账状态：PENDING/PROCESSING/SUCCESS/FAILED"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")

    @field_validator("flow_type")
    @classmethod
    def validate_flow_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("ORDER", "SUPPLEMENT", "DEDUCT"):
            raise ValueError("flow_type 必须为 ORDER / SUPPLEMENT / DEDUCT")
        return v

    @field_validator("transfer_status")
    @classmethod
    def validate_transfer_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("PENDING", "PROCESSING", "SUCCESS", "FAILED"):
            raise ValueError("transfer_status 必须为 PENDING/PROCESSING/SUCCESS/FAILED")
        return v


class SettlementOrderQuery(BaseModel):
    """结算状态订单查询参数"""

    order_status: Optional[int] = Field(
        default=None, ge=10, le=60, description="订单状态：10/30/40/50/60"
    )
    channel_code: Optional[str] = Field(
        default=None, description="渠道标识：myq/orderx/dta"
    )
    has_flow: Optional[bool] = Field(
        default=None, description="True=有流水(已结算), False=无流水(待结算)"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("myq", "orderx", "dta"):
            raise ValueError("channel_code 必须为 myq / orderx / dta")
        return v


# ── 响应 DTO ─────────────────────────────────────────


class CommissionSettleResponse(BaseModel):
    """批量结算响应"""

    status: str = Field(..., description="success/partial")
    total: int = Field(default=0, ge=0, description="待结算订单总数")
    success_count: int = Field(default=0, ge=0, description="成功结算数")
    failed_count: int = Field(default=0, ge=0, description="失败数")
    skipped_count: int = Field(default=0, ge=0, description="跳过数（幂等）")
    details: List[Dict[str, Any]] = Field(
        default_factory=list, description="各订单明细"
    )


class CommissionRecalculateResponse(BaseModel):
    """重算响应"""

    order_id: int = Field(..., description="订单ID")
    old_user_commission: float = Field(..., description="原用户佣金")
    new_user_commission: float = Field(..., description="新用户佣金")
    old_platform_commission: float = Field(..., description="原平台佣金")
    new_platform_commission: float = Field(..., description="新平台佣金")
    user_rate: float = Field(..., description="用户比例")
    platform_rate: float = Field(..., description="平台比例")


class RefundDeductResponse(BaseModel):
    """退款扣减响应"""

    status: str = Field(..., description="success/partial")
    total: int = Field(default=0, ge=0, description="待扣减订单总数")
    success_count: int = Field(default=0, ge=0, description="成功扣减数")
    failed_count: int = Field(default=0, ge=0, description="失败数")
    skipped_count: int = Field(default=0, ge=0, description="跳过数")
    details: List[Dict[str, Any]] = Field(
        default_factory=list, description="各订单明细"
    )

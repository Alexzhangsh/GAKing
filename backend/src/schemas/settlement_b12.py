# @ai-generated
"""
B12 佣金结算状态机接口请求/响应 Pydantic DTO（独立新建，不修改 B01-B11 schemas）
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.config.b12_constants import (
    ACTION_CREATE_SETTLEMENT,
    ACTION_FREEZE,
    ACTION_MARK_PAID,
    ACTION_UNFREEZE,
    SettlementStatus,
)


# ── 手动触发请求 DTO ─────────────────────────────────


class SettlementBatchFreezeRequest(BaseModel):
    """手动触发批量冻结入账请求"""

    limit: Optional[int] = Field(
        default=200,
        ge=1,
        le=1000,
        description="单轮处理订单上限（默认200，最大1000）",
    )


class SettlementBatchUnfreezeRequest(BaseModel):
    """手动触发批量解冻转可用请求"""

    limit: Optional[int] = Field(
        default=200,
        ge=1,
        le=1000,
        description="单轮处理订单上限（默认200，最大1000）",
    )


class SettlementSingleFreezeRequest(BaseModel):
    """手动触发单笔冻结入账请求"""

    order_id: int = Field(..., gt=0, description="订单ID")
    delay_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="延迟结算天数（留空则从配置读取，仅快照用）",
    )


class SettlementSingleUnfreezeRequest(BaseModel):
    """手动触发单笔解冻转可用请求"""

    order_id: int = Field(..., gt=0, description="订单ID")


# ── 查询/导出筛选 DTO ─────────────────────────────────


class SettlementRecordQuery(BaseModel):
    """结算单分页查询/导出筛选参数

    支持多条件组合：单号/订单/用户/渠道/状态/金额区间/时间区间
    """

    settlement_no: Optional[str] = Field(default=None, description="结算单号筛选")
    order_id: Optional[int] = Field(default=None, gt=0, description="订单ID筛选")
    user_id: Optional[int] = Field(default=None, gt=0, description="用户ID筛选")
    channel_code: Optional[str] = Field(default=None, description="渠道标识筛选")
    settlement_status: Optional[str] = Field(
        default=None, description="结算单状态：ORDERED/SETTLABLE/SETTLED/PAID"
    )
    min_amount: Optional[float] = Field(
        default=None, ge=0, description="用户佣金下限（元）"
    )
    max_amount: Optional[float] = Field(
        default=None, ge=0, description="用户佣金上限（元）"
    )
    start_time: Optional[str] = Field(
        default=None, description="创建时间起始（含，ISO8601）"
    )
    end_time: Optional[str] = Field(
        default=None, description="创建时间截止（不含，ISO8601）"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(
        default=20, ge=1, le=500, description="每页条数（导出最大500）"
    )

    @field_validator("settlement_status")
    @classmethod
    def validate_settlement_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            SettlementStatus.ORDERED.value,
            SettlementStatus.SETTLABLE.value,
            SettlementStatus.SETTLED.value,
            SettlementStatus.PAID.value,
        ):
            raise ValueError(
                "settlement_status 必须为 ORDERED / SETTLABLE / SETTLED / PAID"
            )
        return v


class SettlementOverdueQuery(BaseModel):
    """超期未解冻结算单预警查询参数"""

    delay_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="超期阈值天数（留空则从配置读取，默认30天）",
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=200, description="每页条数")


class SettlementLogQuery(BaseModel):
    """结算操作日志查询参数"""

    settlement_id: Optional[int] = Field(default=None, gt=0, description="结算单ID筛选")
    order_id: Optional[int] = Field(default=None, gt=0, description="订单ID筛选")
    action: Optional[str] = Field(
        default=None,
        description="操作类型：CREATE_SETTLEMENT/FREEZE/UNFREEZE/MARK_PAID",
    )
    operator_id: Optional[int] = Field(default=None, gt=0, description="操作人ID筛选")
    start_time: Optional[str] = Field(
        default=None, description="创建时间起始（含，ISO8601）"
    )
    end_time: Optional[str] = Field(
        default=None, description="创建时间截止（不含，ISO8601）"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            ACTION_CREATE_SETTLEMENT,
            ACTION_FREEZE,
            ACTION_UNFREEZE,
            ACTION_MARK_PAID,
        ):
            raise ValueError(
                "action 必须为 CREATE_SETTLEMENT / FREEZE / UNFREEZE / MARK_PAID"
            )
        return v

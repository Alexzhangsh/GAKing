# @ai-generated
"""
B13 全链路数据对账接口请求 Pydantic DTO（独立新建，不修改 B01-B12 schemas）
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.config.b13_constants import (
    AlertLevel,
    DiffStatus,
    DiffType,
    ReconciliationStatus,
    ReconciliationType,
)


# ── 手动触发请求 DTO ─────────────────────────────────


class ManualReconciliationRequest(BaseModel):
    """手动触发对账请求"""

    reconcile_date: Optional[date] = Field(
        default=None, description="对账日期（留空默认昨天）"
    )


class RetryReconciliationRequest(BaseModel):
    """重跑对账批次请求"""

    reconciliation_id: int = Field(..., gt=0, description="原对账批次ID")


class DiffReviewRequest(BaseModel):
    """差异复核请求"""

    action: str = Field(..., description="复核动作：REVIEWING/RESOLVED/IGNORED")
    review_remark: str = Field(
        ..., min_length=1, max_length=512, description="复核说明（调平原因）"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in (
            DiffStatus.REVIEWING.value,
            DiffStatus.RESOLVED.value,
            DiffStatus.IGNORED.value,
        ):
            raise ValueError("action 必须为 REVIEWING / RESOLVED / IGNORED")
        return v


# ── 查询/导出筛选 DTO ─────────────────────────────────


class ReconciliationRecordQuery(BaseModel):
    """对账批次分页查询/导出筛选参数"""

    reconciliation_no: Optional[str] = Field(default=None, description="批次号筛选")
    reconcile_type: Optional[str] = Field(
        default=None, description="对账类型：DAILY/MANUAL"
    )
    status: Optional[str] = Field(
        default=None,
        description="对账状态：PENDING/RUNNING/SUCCESS/PARTIAL/FAILED",
    )
    start_date: Optional[date] = Field(default=None, description="对账日期起始（含）")
    end_date: Optional[date] = Field(default=None, description="对账日期截止（含）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=500, description="每页条数")

    @field_validator("reconcile_type")
    @classmethod
    def validate_reconcile_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            ReconciliationType.DAILY.value,
            ReconciliationType.MANUAL.value,
        ):
            raise ValueError("reconcile_type 必须为 DAILY / MANUAL")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            ReconciliationStatus.PENDING.value,
            ReconciliationStatus.RUNNING.value,
            ReconciliationStatus.SUCCESS.value,
            ReconciliationStatus.PARTIAL.value,
            ReconciliationStatus.FAILED.value,
        ):
            raise ValueError(
                "status 必须为 PENDING / RUNNING / SUCCESS / PARTIAL / FAILED"
            )
        return v


class ReconciliationDiffQuery(BaseModel):
    """差异明细分页查询/导出筛选参数"""

    reconciliation_id: Optional[int] = Field(
        default=None, gt=0, description="对账批次ID筛选"
    )
    user_id: Optional[int] = Field(default=None, gt=0, description="用户ID筛选")
    order_id: Optional[int] = Field(default=None, gt=0, description="订单ID筛选")
    diff_type: Optional[str] = Field(
        default=None, description="差异类型：ORDER_SETTLEMENT_MISMATCH 等"
    )
    status: Optional[str] = Field(
        default=None, description="复核状态：PENDING/REVIEWING/RESOLVED/IGNORED"
    )
    alert_level: Optional[str] = Field(
        default=None, description="告警级别：INFO/WARNING/CRITICAL"
    )
    start_time: Optional[str] = Field(
        default=None, description="创建时间起始（含，ISO8601）"
    )
    end_time: Optional[str] = Field(
        default=None, description="创建时间截止（不含，ISO8601）"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=500, description="每页条数")

    @field_validator("diff_type")
    @classmethod
    def validate_diff_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in DiffType._value2member_map_:
            raise ValueError("diff_type 取值非法")
        return v

    @field_validator("status")
    @classmethod
    def validate_diff_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            DiffStatus.PENDING.value,
            DiffStatus.REVIEWING.value,
            DiffStatus.RESOLVED.value,
            DiffStatus.IGNORED.value,
        ):
            raise ValueError("status 必须为 PENDING / REVIEWING / RESOLVED / IGNORED")
        return v

    @field_validator("alert_level")
    @classmethod
    def validate_alert_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            AlertLevel.INFO.value,
            AlertLevel.WARNING.value,
            AlertLevel.CRITICAL.value,
        ):
            raise ValueError("alert_level 必须为 INFO / WARNING / CRITICAL")
        return v


class AlertQuery(BaseModel):
    """告警查询参数"""

    alert_level: Optional[str] = Field(
        default=None, description="告警级别：INFO/WARNING/CRITICAL"
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=200, description="每页条数")

    @field_validator("alert_level")
    @classmethod
    def validate_alert_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in (
            AlertLevel.INFO.value,
            AlertLevel.WARNING.value,
            AlertLevel.CRITICAL.value,
        ):
            raise ValueError("alert_level 必须为 INFO / WARNING / CRITICAL")
        return v

# @ai-generated
"""
订单同步任务请求/响应 DTO 定义（B05）

管理员手动触发/重试/状态查询接口的入参出参校验模型。
字段与 OrderSyncService 方法签名对齐。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════
# 请求 DTO
# ══════════════════════════════════════════════════════


class OrderSyncTriggerRequest(BaseModel):
    """手动触发单渠道订单同步请求"""

    channel_code: str = Field(
        ...,
        description="渠道标识：myq(喵有券) / orderx(订单侠) / dta(大淘客)",
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="拉取起始时间（缺省走 Redis 游标，首次回溯60分钟）",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="拉取结束时间（缺省取当前时间）",
    )

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: str) -> str:
        if v not in ("myq", "orderx", "dta"):
            raise ValueError("channel_code 必须为 myq / orderx / dta")
        return v


class OrderSyncRetryRequest(BaseModel):
    """手动补发失败队列请求"""

    channel_code: str = Field(
        ...,
        description="渠道标识：myq / orderx / dta",
    )
    batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="单次补发条数（默认10，最大100）",
    )

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: str) -> str:
        if v not in ("myq", "orderx", "dta"):
            raise ValueError("channel_code 必须为 myq / orderx / dta")
        return v


# ══════════════════════════════════════════════════════
# 响应 DTO
# ══════════════════════════════════════════════════════


class OrderSyncTriggerResponse(BaseModel):
    """同步触发响应"""

    channel_code: str = Field(..., description="渠道标识")
    status: str = Field(..., description="success / skipped / failed / partial")
    message: str = Field(default="", description="结果描述")
    windows_total: int = Field(default=0, ge=0, description="本轮拉取窗口数")
    pulled_count: int = Field(default=0, ge=0, description="渠道拉取到的订单总数")
    inserted_count: int = Field(default=0, ge=0, description="新插入订单数")
    updated_count: int = Field(default=0, ge=0, description="状态更新订单数")
    failed_count: int = Field(default=0, ge=0, description="失败窗口数")
    cursor: Optional[str] = Field(
        default=None, description="同步游标（最后成功时间 ISO）"
    )
    details: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="各窗口明细（start/end/pulled/inserted/updated/status）",
    )


class OrderSyncRetryResponse(BaseModel):
    """补发响应"""

    channel_code: str = Field(..., description="渠道标识")
    status: str = Field(..., description="success / partial / failed")
    message: str = Field(default="", description="结果描述")
    retried_count: int = Field(default=0, ge=0, description="尝试补发条数")
    success_count: int = Field(default=0, ge=0, description="补发成功条数")
    still_failed_count: int = Field(default=0, ge=0, description="仍失败条数")
    details: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="各条补发明细",
    )


class ChannelSyncStatus(BaseModel):
    """单渠道同步状态"""

    channel_code: str = Field(..., description="渠道标识")
    enabled: bool = Field(..., description="渠道任务开关")
    cursor: Optional[str] = Field(
        default=None, description="同步游标（最后成功时间 ISO，None 表示首次未运行）"
    )
    failed_queue_length: int = Field(default=0, ge=0, description="失败队列积压条数")
    breaker_state: str = Field(
        default="CLOSED",
        description="熔断器状态：CLOSED / OPEN / HALF_OPEN",
    )
    cron_expr: str = Field(default="", description="定时任务 cron 表达式")


class OrderSyncStatusResponse(BaseModel):
    """同步状态查询响应"""

    total_enabled: int = Field(default=0, ge=0, description="启用渠道数")
    channels: List[ChannelSyncStatus] = Field(
        default_factory=list, description="各渠道状态明细"
    )

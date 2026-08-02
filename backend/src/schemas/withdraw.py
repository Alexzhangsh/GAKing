# @ai-generated
"""
用户佣金提现 Pydantic DTO 定义
统一入参/出参校验模型，字段与 ORM Model 对齐
- 金额统一 Decimal，禁止 float（避免精度污染）
- 提现状态枚举 WithdrawStatus 来源 constants.py（唯一权威源）
"""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.config.constants import WITHDRAW_MIN_AMOUNT, WithdrawStatus


# ══════════════════════════════════════════════════════
# 用户端请求 DTO
# ══════════════════════════════════════════════════════


class WithdrawApplyRequest(BaseModel):
    """用户发起提现请求体（user_id 由 JWT/请求头提取，不在 body 内）"""

    apply_amount: Decimal = Field(
        ..., gt=0, description="申请提现金额(元)，需 >= 最低门槛 10 元"
    )

    @field_validator("apply_amount")
    @classmethod
    def validate_min_amount(cls, v: Decimal) -> Decimal:
        if v < WITHDRAW_MIN_AMOUNT:
            raise ValueError(f"最低提现金额 {WITHDRAW_MIN_AMOUNT} 元")
        return v


# ══════════════════════════════════════════════════════
# 后台审核请求 DTO
# ══════════════════════════════════════════════════════


class WithdrawApproveRequest(BaseModel):
    """审核通过请求体（review_user_id 由 JWT 提取）"""

    review_remark: str = Field(default="", max_length=512, description="审核备注")


class WithdrawRejectRequest(BaseModel):
    """驳回请求体（驳回原因必填，用于 reject_reason 落库 + 用户可见）"""

    reject_reason: str = Field(..., min_length=1, max_length=512, description="驳回原因")


class WithdrawCompleteRequest(BaseModel):
    """标记打款完成请求体（绑定微信转账批次ID，触发冻结释放）"""

    transfer_batch_id: str = Field(
        ..., min_length=1, max_length=64, description="微信转账批次ID"
    )


class WithdrawFailRequest(BaseModel):
    """打款失败退回请求体（APPROVED/PROCESSING → REJECTED，退回可用余额）

    场景：微信转账失败 / 银行卡异常（V2.0：资金退回可用余额，后台留痕）。
    """

    reason: str = Field(..., min_length=1, max_length=512, description="打款失败原因")


# ══════════════════════════════════════════════════════
# 后台列表查询参数 DTO
# ══════════════════════════════════════════════════════


class WithdrawAdminListQuery(BaseModel):
    """后台提现申请列表查询参数"""

    user_id: Optional[int] = Field(default=None, gt=0, description="平台用户ID筛选")
    status: Optional[str] = Field(default=None, description="提现状态筛选：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = {s.value for s in WithdrawStatus}
        if v not in valid:
            raise ValueError(f"status 必须为合法值: {sorted(valid)}")
        return v

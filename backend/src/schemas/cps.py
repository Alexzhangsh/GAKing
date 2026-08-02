# @ai-generated
"""
CPS 订单 & 佣金 Pydantic DTO 定义
统一入参/出参校验模型，字段与 ORM Model 对齐
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════
# 统一响应体
# ══════════════════════════════════════════════════════


class ApiResponse(BaseModel):
    """全局统一响应体"""

    code: int = Field(default=200, description="业务状态码：200-成功，400-参数错误，500-服务异常")
    msg: str = Field(default="success", description="提示消息")
    data: Optional[Any] = Field(default=None, description="业务数据")
    request_id: Optional[str] = Field(default=None, description="请求ID，用于链路追踪")


# ══════════════════════════════════════════════════════
# 订单 DTO
# ══════════════════════════════════════════════════════


class OrderCreateRequest(BaseModel):
    """渠道订单推送入库请求体"""

    out_order_no: str = Field(..., min_length=1, max_length=64, description="渠道订单号")
    internal_order_no: str = Field(..., min_length=1, max_length=64, description="平台内部订单号")
    user_id: int = Field(..., gt=0, description="用户ID")
    goods_title: str = Field(default="", max_length=256, description="商品标题")
    goods_img: str = Field(default="", max_length=512, description="商品主图URL")
    pay_amount: Decimal = Field(..., ge=0, description="支付金额(元)")
    total_commission: Decimal = Field(default=Decimal("0"), ge=0, description="总佣金(元)")
    user_commission: Decimal = Field(default=Decimal("0"), ge=0, description="用户佣金(元)")
    platform_commission: Decimal = Field(default=Decimal("0"), ge=0, description="平台佣金(元)")
    channel_code: str = Field(..., min_length=1, max_length=32, description="渠道标识：myq/orderx")
    pay_time: Optional[datetime] = Field(default=None, description="支付时间")

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: str) -> str:
        if v not in ("myq", "orderx"):
            raise ValueError("channel_code 必须为 myq 或 orderx")
        return v


class OrderStatusUpdateRequest(BaseModel):
    """订单状态手动变更请求体"""

    order_id: int = Field(..., gt=0, description="订单ID")
    target_status: int = Field(..., description="目标状态值：10-待付款 20-冻结 30-可结算 40-已结算 50-失效 60-已退款")

    @field_validator("target_status")
    @classmethod
    def validate_target_status(cls, v: int) -> int:
        valid_statuses = {10, 20, 30, 40, 50, 60}
        if v not in valid_statuses:
            raise ValueError(f"target_status 必须为合法值: {valid_statuses}")
        return v


class OrderListRequest(BaseModel):
    """订单分页列表查询参数"""

    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，最大100")
    channel_code: Optional[str] = Field(default=None, description="渠道标识筛选")
    order_status: Optional[int] = Field(default=None, description="订单状态筛选")
    user_id: Optional[int] = Field(default=None, gt=0, description="用户ID筛选")


# ══════════════════════════════════════════════════════
# 佣金 DTO
# ══════════════════════════════════════════════════════


class CommissionGenerateRequest(BaseModel):
    """订单佣金流水生成触发请求体"""

    order_id: int = Field(..., gt=0, description="订单ID")


class CommissionSettleRequest(BaseModel):
    """批量标记佣金结算完成请求体"""

    flow_ids: List[int] = Field(..., min_length=1, description="佣金流水ID列表")
    transfer_batch_id: str = Field(..., min_length=1, max_length=64, description="微信转账批次ID")


class CommissionFlowSerializeRequest(BaseModel):
    """流水明细批量导出序列化请求体"""

    flow_ids: List[int] = Field(..., min_length=1, description="佣金流水ID列表")

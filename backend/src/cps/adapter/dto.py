# @ai-generated
"""
CPS 渠道统一 DTO 定义
标准化统一商品 DTO、转链结果 DTO、订单 DTO
抹平三方渠道字段差异，输出统一结构供上层业务使用
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_serializer


# ══════════════════════════════════════════════════════
# 商品搜索 DTO
# ══════════════════════════════════════════════════════


class GoodsDTO(BaseModel):
    """统一商品 DTO

    字段与现有订单/商品模型兼容：goods_id, goods_title, goods_img 等
    """

    goods_id: str = Field(..., min_length=1, description="商品唯一ID（外部渠道商品ID）")
    goods_title: str = Field(default="", description="商品完整标题")
    goods_img: str = Field(default="", description="商品主图链接")
    original_price: Decimal = Field(
        default=Decimal("0"), ge=0, description="商品原价（元）"
    )
    sale_price: Decimal = Field(
        default=Decimal("0"), ge=0, description="券后真实售价（元）"
    )
    commission_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="商品佣金比例（百分比，如 3.5 表示 3.5%）",
    )
    estimate_commission: Decimal = Field(
        default=Decimal("0"), ge=0, description="预估原始联盟佣金（元）"
    )
    category: str = Field(default="", description="商品类目/分类")
    promote_url: str = Field(default="", description="CPS 推广跳转链接")
    coupon_info: Optional[Dict[str, Any]] = Field(
        default=None, description="优惠券信息（面额/有效期/使用条件）"
    )
    shop_name: str = Field(default="", description="店铺名称")
    sales_volume: int = Field(default=0, ge=0, description="商品销量")
    source_channel: str = Field(
        default="", description="来源渠道标识（myq / dta / orderx）"
    )

    @field_serializer(
        "original_price", "sale_price", "commission_rate", "estimate_commission"
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class GoodsSearchResult(BaseModel):
    """商品搜索结果列表"""

    items: List[GoodsDTO] = Field(default_factory=list, description="商品列表")
    total: int = Field(default=0, ge=0, description="总记录数")
    page: int = Field(default=1, ge=1, description="当前页码")
    size: int = Field(default=20, ge=1, description="每页条数")


# ══════════════════════════════════════════════════════
# 转链结果 DTO
# ══════════════════════════════════════════════════════


class ConvertLinkResult(BaseModel):
    """链接转链结果 DTO"""

    promote_url: str = Field(..., min_length=1, description="CPS 推广短链接")
    tpwd: str = Field(default="", description="淘口令（淘宝App打开自动识别）")
    channel_pid: str = Field(default="", description="渠道 PID（推广员标识）")
    estimate_commission: Decimal = Field(
        default=Decimal("0"), ge=0, description="预估佣金（元）"
    )
    goods_id: str = Field(default="", description="商品唯一ID")
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None, description="渠道原始响应数据（调试用）"
    )

    @field_serializer("estimate_commission")
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


# ══════════════════════════════════════════════════════
# 订单 DTO
# ══════════════════════════════════════════════════════


class OrderDTO(BaseModel):
    """统一订单 DTO

    兼容现有订单状态机字段映射：order_status, channel_code 等
    """

    origin_order_id: str = Field(
        ..., min_length=0, description="淘宝原生订单ID（全局唯一幂等主键）"
    )
    pay_time: Optional[datetime] = Field(default=None, description="订单付款时间")
    confirm_time: Optional[datetime] = Field(
        default=None, description="用户确认收货时间"
    )
    settle_time: Optional[datetime] = Field(
        default=None, description="联盟佣金正式结算时间"
    )
    order_status: str = Field(
        default="", description="订单全生命周期状态（渠道原始状态）"
    )
    order_amount: Decimal = Field(
        default=Decimal("0"), ge=0, description="订单实付金额（元）"
    )
    channel_pid: str = Field(default="", description="推广PID，渠道溯源对账")
    refund_info: Optional[Dict[str, Any]] = Field(default=None, description="退款明细")
    goods_id: str = Field(default="", description="商品唯一ID")
    goods_title: str = Field(default="", description="商品标题")
    goods_img: str = Field(default="", description="商品主图")
    total_commission: Decimal = Field(
        default=Decimal("0"), ge=0, description="总佣金（元）"
    )
    user_commission: Decimal = Field(
        default=Decimal("0"), ge=0, description="用户佣金（元）"
    )
    platform_commission: Decimal = Field(
        default=Decimal("0"), ge=0, description="平台佣金（元）"
    )
    channel_code: str = Field(default="", description="渠道标识（myq / dta / orderx）")
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None, description="渠道原始订单数据"
    )

    @field_serializer(
        "order_amount",
        "total_commission",
        "user_commission",
        "platform_commission",
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)

    @field_serializer("pay_time", "confirm_time", "settle_time")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()


class OrderPullResult(BaseModel):
    """订单批量拉取结果"""

    orders: List[OrderDTO] = Field(default_factory=list, description="订单列表")
    total: int = Field(default=0, ge=0, description="拉取到的订单总数")
    start_time: Optional[datetime] = Field(default=None, description="拉取起始时间")
    end_time: Optional[datetime] = Field(default=None, description="拉取结束时间")

# @ai-generated
"""
CPS 商品搜索 / 链接转链 Pydantic DTO 定义
对外公开接口入参/出参校验模型，字段与 B01 适配器 DTO 对齐
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════
# 统一业务异常
# ══════════════════════════════════════════════════════


class BizException(Exception):
    """CPS 对外接口统一业务异常

    支持自定义 code（HTTP 状态码语义）与 msg
    接口层 catch 后通过 error_response 返回对应状态码
    """

    def __init__(self, code: int, msg: str, data: Optional[Any] = None) -> None:
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(msg)


# ══════════════════════════════════════════════════════
# 商品搜索 DTO
# ══════════════════════════════════════════════════════


class GoodsSearchRequest(BaseModel):
    """商品搜索请求参数（Query 参数）"""

    keyword: str = Field(..., min_length=1, max_length=64, description="搜索关键词")
    page: int = Field(default=1, ge=1, le=100, description="页码，从1开始")
    size: int = Field(default=20, ge=1, le=100, description="每页条数，最大100")
    channel_code: str = Field(
        default="myq",
        description="渠道标识：myq(喵有券) / orderx(订单侠) / dta(大淘客)",
    )

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: str) -> str:
        if v not in ("myq", "orderx", "dta"):
            raise ValueError("channel_code 必须为 myq / orderx / dta")
        return v


class GoodsItemResponse(BaseModel):
    """商品出参项（与 B01 GoodsDTO 字段对齐，Decimal 序列化为 float）"""

    goods_id: str = Field(..., description="商品唯一ID")
    goods_title: str = Field(default="", description="商品标题")
    goods_img: str = Field(default="", description="商品主图URL")
    original_price: float = Field(default=0.0, ge=0, description="商品原价(元)")
    sale_price: float = Field(default=0.0, ge=0, description="券后售价(元)")
    commission_rate: float = Field(default=0.0, ge=0, description="佣金比例(%)")
    estimate_commission: float = Field(default=0.0, ge=0, description="预估佣金(元)")
    category: str = Field(default="", description="类目")
    promote_url: str = Field(default="", description="CPS推广链接")
    shop_name: str = Field(default="", description="店铺名称")
    sales_volume: int = Field(default=0, ge=0, description="销量")
    source_channel: str = Field(default="", description="来源渠道标识")


class GoodsSearchResponse(BaseModel):
    """商品搜索响应体"""

    items: List[GoodsItemResponse] = Field(default_factory=list, description="商品列表")
    total: int = Field(default=0, ge=0, description="总记录数")
    page: int = Field(default=1, ge=1, description="当前页码")
    size: int = Field(default=20, ge=1, description="每页条数")
    cache_hit: bool = Field(default=False, description="是否命中缓存（调试用）")


# ══════════════════════════════════════════════════════
# 链接转链 DTO
# ══════════════════════════════════════════════════════


class ConvertLinkRequest(BaseModel):
    """链接转链请求体"""

    original_url: str = Field(
        ..., min_length=1, max_length=512, description="原始商品链接"
    )
    user_channel_id: str = Field(
        ..., min_length=1, max_length=64, description="用户渠道溯源标识( relation_id )"
    )
    channel_code: str = Field(
        default="myq",
        description="渠道标识：myq(喵有券) / orderx(订单侠) / dta(大淘客)",
    )

    @field_validator("channel_code")
    @classmethod
    def validate_channel_code(cls, v: str) -> str:
        if v not in ("myq", "orderx", "dta"):
            raise ValueError("channel_code 必须为 myq / orderx / dta")
        return v


class ConvertLinkResponse(BaseModel):
    """链接转链响应体"""

    promote_url: str = Field(..., description="CPS推广短链接")
    tpwd: str = Field(default="", description="淘口令（淘宝App打开自动识别）")
    channel_pid: str = Field(default="", description="渠道PID")
    estimate_commission: float = Field(default=0.0, ge=0, description="预估佣金(元)")
    goods_id: str = Field(default="", description="商品唯一ID")
    channel_code: str = Field(default="", description="实际使用的渠道标识")

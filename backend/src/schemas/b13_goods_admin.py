# @ai-generated
"""B13-补全 商品管理后台 Schema 定义"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class GoodsListResponse(BaseModel):
    """商品管理列表项响应"""
    id: int = Field(..., description="主键ID")
    goods_id: str = Field(..., description="CPS 渠道商品唯一ID")
    source_channel: str = Field(..., description="来源渠道码")
    goods_title: str = Field(default="", description="商品标题")
    goods_img: str = Field(default="", description="商品主图链接")
    sale_price: str = Field(default="0.00", description="销售价(元)")
    original_price: str = Field(default="0.00", description="商品原价(元)")
    commission_rate: str = Field(default="0.00", description="佣金比例(%)")
    bonus_price_normal: str = Field(default="0.00", description="普通会员奖金(元)")
    bonus_rate_normal: str = Field(default="0.00", description="普通会员奖金比例(%)")
    bonus_price_vip: str = Field(default="0.00", description="VIP会员奖金(元)")
    bonus_rate_vip: str = Field(default="0.00", description="VIP会员奖金比例(%)")
    category: str = Field(default="", description="商品类目")
    shop_name: str = Field(default="", description="店铺名称")
    shelf_status: str = Field(default="on_shelf", description="上下架状态")
    sort_order: int = Field(default=0, description="排序权重")
    admin_remark: str = Field(default="", description="管理员备注")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")


class GoodsDetailResponse(GoodsListResponse):
    """商品管理详情响应（继承列表项，可扩展）"""
    last_admin_id: int = Field(default=0, description="最后操作管理员ID")


class GoodsUpsertRequest(BaseModel):
    """商品创建/更新请求（从 CPS 渠道同步或手动添加）"""
    goods_id: str = Field(..., min_length=1, max_length=128, description="CPS 商品ID")
    source_channel: str = Field(..., min_length=1, max_length=16, description="来源渠道码")
    goods_title: str = Field(default="", max_length=512, description="商品标题")
    goods_img: str = Field(default="", max_length=1024, description="商品主图链接")
    sale_price: Decimal = Field(default=Decimal("0.00"), description="销售价(元)")
    original_price: Decimal = Field(default=Decimal("0.00"), description="商品原价(元)")
    commission_rate: Decimal = Field(default=Decimal("0.00"), description="佣金比例(%)")
    bonus_price_normal: Decimal = Field(default=Decimal("0.00"), description="普通会员奖金(元)")
    bonus_rate_normal: Decimal = Field(default=Decimal("0.00"), description="普通会员奖金比例(%)")
    bonus_price_vip: Decimal = Field(default=Decimal("0.00"), description="VIP会员奖金(元)")
    bonus_rate_vip: Decimal = Field(default=Decimal("0.00"), description="VIP会员奖金比例(%)")
    category: str = Field(default="", max_length=64, description="商品类目")
    shop_name: str = Field(default="", max_length=128, description="店铺名称")
    sort_order: int = Field(default=0, ge=0, description="排序权重")
    admin_remark: str = Field(default="", max_length=512, description="管理员备注")


class GoodsShelfRequest(BaseModel):
    """商品上下架请求"""
    shelf_status: str = Field(..., pattern="^(on_shelf|off_shelf)$", description="上下架状态")


class GoodsBatchShelfRequest(BaseModel):
    """商品批量上下架请求"""
    goods_ids: List[str] = Field(..., min_length=1, description="商品ID列表")
    source_channel: str = Field(..., min_length=1, max_length=16, description="来源渠道码")
    shelf_status: str = Field(..., pattern="^(on_shelf|off_shelf)$", description="目标上下架状态")


class GoodsBatchDeleteRequest(BaseModel):
    """商品批量删除请求"""
    goods_ids: List[str] = Field(..., min_length=1, description="商品ID列表")
    source_channel: str = Field(..., min_length=1, max_length=16, description="来源渠道码")


class GoodsSyncRequest(BaseModel):
    """商品同步请求（从 CPS 渠道拉取商品到本地管理表）"""
    source_channel: str = Field(..., min_length=1, max_length=16, description="来源渠道码")
    keyword: str = Field(default="", max_length=128, description="搜索关键词")
    page: int = Field(default=1, ge=1, description="拉取页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页拉取数量")

# @ai-generated
"""B14-补全 数据大盘 Schema 定义"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DashboardCardsResponse(BaseModel):
    """首页卡片聚合数据响应"""
    total_orders: int = Field(..., description="累计订单数")
    pending_settle_commission: str = Field(..., description="待结算佣金(元)")
    settled_commission: str = Field(..., description="已结算佣金(元)")
    total_withdrawn: str = Field(..., description="提现总额(元)")
    pending_review_withdraws: int = Field(..., description="待审核提现数量")


class CommissionStatsByDateItem(BaseModel):
    """按日期分组佣金统计项"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    total_commission: str = Field(..., description="佣金总额(元)")
    order_count: int = Field(..., description="订单数")


class CommissionStatsByChannelItem(BaseModel):
    """按渠道分组佣金统计项"""
    channel_code: str = Field(..., description="渠道码")
    total_commission: str = Field(..., description="佣金总额(元)")
    order_count: int = Field(..., description="订单数")


class CommissionStatsByUserItem(BaseModel):
    """按用户分组佣金统计项"""
    user_id: int = Field(..., description="用户ID")
    total_commission: str = Field(..., description="佣金总额(元)")
    order_count: int = Field(..., description="订单数")


class CommissionStatsByUserResponse(BaseModel):
    """按用户分组佣金统计响应（分页）"""
    total: int = Field(..., description="总用户数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[CommissionStatsByUserItem] = Field(default_factory=list)


class OrderTrendItem(BaseModel):
    """订单趋势折线数据项"""
    date: str = Field(..., description="日期/周/月标识")
    order_count: int = Field(..., description="订单数")
    total_commission: str = Field(..., description="佣金总额(元)")

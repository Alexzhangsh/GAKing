# @ai-generated
"""
短链 & 异常订单 Pydantic Schema 定义
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════
# 短链 DTO
# ══════════════════════════════════════════════════════

class ShortLinkCreateRequest(BaseModel):
    """创建短链请求体"""
    user_id: int = Field(..., gt=0, description="用户ID")
    goods_id: str = Field(..., min_length=1, description="商品ID")
    goods_title: str = Field(default="", description="商品标题")
    channel_code: str = Field(default="", description="渠道标识")
    source_url: str = Field(default="", description="原始CPS推广链接")


class ShortLinkResponse(BaseModel):
    """短链响应体"""
    short_key: str = Field(..., description="短链唯一标识")
    short_url: str = Field(..., description="完整短链URL")
    user_id: int = Field(..., description="用户ID")
    goods_id: str = Field(..., description="商品ID")
    goods_title: str = Field(default="", description="商品标题")
    channel_code: str = Field(default="", description="渠道标识")
    expire_at: str = Field(default="", description="过期时间")
    click_count: int = Field(default=0, description="累计点击次数")


# ══════════════════════════════════════════════════════
# 异常订单 DTO
# ══════════════════════════════════════════════════════

class AbnormalOrderItem(BaseModel):
    """异常订单列表项"""
    id: int = Field(..., description="记录ID")
    out_order_no: str = Field(..., description="渠道订单号")
    channel_code: str = Field(default="", description="渠道标识")
    goods_id: str = Field(default="", description="商品ID")
    goods_title: str = Field(default="", description="商品标题")
    pay_amount: float = Field(default=0.0, description="支付金额")
    total_commission: float = Field(default=0.0, description="总佣金")
    order_status: str = Field(default="", description="渠道原始状态")
    pay_time: Optional[str] = Field(default=None, description="支付时间")
    abnormal_reason: str = Field(default="", description="异常原因")
    matched_click_key: str = Field(default="", description="最近匹配短链key")
    matched_user_id: int = Field(default=0, description="可能匹配的用户ID")
    assigned_user_id: int = Field(default=0, description="复核指定归属用户ID")
    review_status: str = Field(default="PENDING", description="复核状态")
    review_remark: str = Field(default="", description="复核备注")
    create_time: Optional[str] = Field(default=None, description="创建时间")


class AbnormalOrderListResponse(BaseModel):
    """异常订单分页列表响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[AbnormalOrderItem] = Field(default_factory=list, description="异常订单列表")


class AbnormalOrderReviewRequest(BaseModel):
    """异常订单复核请求体"""
    review_status: str = Field(..., description="复核状态：REVIEWED-已复核 / IGNORED-已忽略")
    review_remark: str = Field(default="", description="复核备注")
    assigned_user_id: int = Field(default=0, ge=0, description="手动指定归属用户ID（0=不指定）")


class AbnormalOrderEditRequest(BaseModel):
    """异常订单编辑请求体（复核后修改）"""
    assigned_user_id: int = Field(default=0, ge=0, description="手动指定归属用户ID（0=不指定）")
    review_remark: str = Field(default="", description="复核备注")


class AbnormalOrderStatsResponse(BaseModel):
    """异常订单统计响应"""
    total: int = Field(default=0, description="总数")
    pending: int = Field(default=0, description="待审核数")
    reviewed: int = Field(default=0, description="已复核数")
    ignored: int = Field(default=0, description="已忽略数")


# ══════════════════════════════════════════════════════
# 归属操作日志 DTO（B05-4-3 新增）
# ══════════════════════════════════════════════════════

class AbnormalOrderOperationLogItem(BaseModel):
    """归属操作日志列表项"""
    id: int = Field(..., description="日志ID")
    abnormal_order_id: int = Field(..., description="异常订单ID")
    operator_id: int = Field(..., description="操作人管理员ID")
    operation_type: str = Field(..., description="操作类型：REVIEW-复核 / EDIT-编辑")
    old_assigned_user_id: int = Field(default=0, description="变更前归属用户ID")
    new_assigned_user_id: int = Field(default=0, description="变更后归属用户ID")
    old_review_remark: str = Field(default="", description="变更前复核备注")
    new_review_remark: str = Field(default="", description="变更后复核备注")
    old_review_status: str = Field(default="", description="变更前复核状态")
    new_review_status: str = Field(default="", description="变更后复核状态")
    remark: str = Field(default="", description="操作补充说明")
    create_time: Optional[str] = Field(default=None, description="创建时间")


class AbnormalOrderOperationLogListResponse(BaseModel):
    """归属操作日志分页列表响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[AbnormalOrderOperationLogItem] = Field(default_factory=list, description="操作日志列表")
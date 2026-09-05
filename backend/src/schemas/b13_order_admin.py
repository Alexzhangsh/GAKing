# @ai-generated
"""B13-1 订单管理后台 Schema 定义"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderListRequest(BaseModel):
    """订单列表查询请求参数"""
    keyword: Optional[str] = Field(default=None, max_length=256, description="搜索关键词（商品标题/渠道订单号/平台订单号模糊匹配）")
    order_status: Optional[int] = Field(default=None, ge=10, le=60, description="订单状态筛选：10-待付款 20-已付款(冻结) 30-可结算 40-已结算 50-已失效 60-已退款")
    channel_code: Optional[str] = Field(default=None, max_length=32, description="渠道标识：myq/orderx")
    user_id: Optional[int] = Field(default=None, ge=1, description="用户ID精确筛选")
    start_time: Optional[datetime] = Field(default=None, description="创建时间范围-开始")
    end_time: Optional[datetime] = Field(default=None, description="创建时间范围-结束")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class OrderListResponseItem(BaseModel):
    """订单列表项响应"""
    id: int = Field(..., description="订单ID")
    out_order_no: str = Field(..., description="渠道订单号")
    internal_order_no: str = Field(..., description="平台内部订单号")
    goods_title: str = Field(default="", description="商品标题")
    goods_img: str = Field(default="", description="商品主图URL")
    user_id: int = Field(..., description="用户ID")
    channel_code: str = Field(default="", description="渠道标识")
    order_status: int = Field(..., description="订单状态")
    pay_amount: str = Field(default="0.00", description="支付金额(元)")
    total_commission: str = Field(default="0.00", description="总佣金(元)")
    user_commission: str = Field(default="0.00", description="用户佣金(元)")
    platform_commission: str = Field(default="0.00", description="平台佣金(元)")
    transfer_status: str = Field(default="PENDING", description="转账状态")
    create_time: Optional[str] = Field(default=None, description="创建时间")
    pay_time: Optional[str] = Field(default=None, description="支付时间")
    settle_time: Optional[str] = Field(default=None, description="结算时间")


class CommissionFlowItem(BaseModel):
    """佣金流水明细项"""
    id: int = Field(..., description="流水ID")
    order_id: Optional[int] = Field(default=None, description="关联订单ID")
    user_id: int = Field(..., description="用户ID")
    flow_type: str = Field(..., description="流水类型：ORDER-订单佣金/SUPPLEMENT-补发/DEDUCT-扣减")
    amount: str = Field(default="0.00", description="流水金额(元)")
    before_balance: str = Field(default="0.00", description="变更前余额(元)")
    after_balance: str = Field(default="0.00", description="变更后余额(元)")
    transfer_status: str = Field(default="PENDING", description="转账状态")
    remark: str = Field(default="", description="备注说明")
    create_time: Optional[str] = Field(default=None, description="创建时间")


class OrderDetailResponse(BaseModel):
    """订单详情响应（含佣金流水）"""
    id: int = Field(..., description="订单ID")
    out_order_no: str = Field(..., description="渠道订单号")
    internal_order_no: str = Field(..., description="平台内部订单号")
    goods_title: str = Field(default="", description="商品标题")
    goods_img: str = Field(default="", description="商品主图URL")
    user_id: int = Field(..., description="用户ID")
    channel_code: str = Field(default="", description="渠道标识")
    order_status: int = Field(..., description="订单状态")
    pay_amount: str = Field(default="0.00", description="支付金额(元)")
    total_commission: str = Field(default="0.00", description="总佣金(元)")
    user_commission: str = Field(default="0.00", description="用户佣金(元)")
    platform_commission: str = Field(default="0.00", description="平台佣金(元)")
    transfer_status: str = Field(default="PENDING", description="转账状态")
    wx_batch_id: str = Field(default="", description="微信转账批次ID")
    create_time: Optional[str] = Field(default=None, description="创建时间")
    pay_time: Optional[str] = Field(default=None, description="支付时间")
    settle_time: Optional[str] = Field(default=None, description="结算时间")
    commission_flows: List[CommissionFlowItem] = Field(default_factory=list, description="佣金流水列表")


class OrderTransitionValidateRequest(BaseModel):
    """单个订单状态流转校验请求"""
    order_id: int = Field(..., ge=1, description="订单ID")
    target_status: int = Field(..., ge=10, le=60, description="目标状态")
    is_manual_override: bool = Field(default=False, description="是否人工干预（跳过终态检查）")


class OrderTransitionExecuteRequest(BaseModel):
    """单个订单状态流转执行请求"""
    order_id: int = Field(..., ge=1, description="订单ID")
    target_status: int = Field(..., ge=10, le=60, description="目标状态")
    operation_type: str = Field(default="status_transition", max_length=32, description="操作类型：status_transition/manual_override/sync_update/anomaly_mark")
    remark: str = Field(default="", max_length=512, description="操作原因/备注")


class OrderBatchValidateRequest(BaseModel):
    """批量校验请求"""
    items: List[OrderTransitionValidateRequest] = Field(..., min_length=1, max_length=100, description="批量校验条目列表")


class OrderBatchValidateItem(BaseModel):
    """批量校验结果单项"""
    order_id: int = Field(..., description="订单ID")
    out_order_no: str = Field(default="", description="渠道订单号")
    current_status: int = Field(..., description="当前状态")
    current_status_label: str = Field(default="", description="当前状态中文描述")
    valid: bool = Field(..., description="是否合法")
    message: str = Field(default="", description="校验结果消息")
    allowed_targets: List[int] = Field(default_factory=list, description="允许的目标状态列表")


class OrderBatchValidateResponse(BaseModel):
    """批量校验响应"""
    total: int = Field(..., description="总校验数")
    valid_count: int = Field(..., description="合法数量")
    invalid_count: int = Field(..., description="非法数量")
    items: List[OrderBatchValidateItem] = Field(..., description="校验结果明细")


class OrderTransitionResult(BaseModel):
    """状态流转执行结果"""
    order_id: int = Field(..., description="订单ID")
    out_order_no: str = Field(default="", description="渠道订单号")
    internal_order_no: str = Field(default="", description="平台内部订单号")
    order_status: int = Field(..., description="当前状态")
    order_status_label: str = Field(default="", description="当前状态中文描述")
    channel_code: str = Field(default="", description="渠道标识")
    user_id: int = Field(..., description="用户ID")
    pay_amount: str = Field(default="0.00", description="支付金额(元)")
    total_commission: str = Field(default="0.00", description="总佣金(元)")
    create_time: Optional[str] = Field(default=None, description="创建时间")
    pay_time: Optional[str] = Field(default=None, description="支付时间")
    settle_time: Optional[str] = Field(default=None, description="结算时间")


class OrderOperationLogItem(BaseModel):
    """订单操作日志项"""
    id: int = Field(..., description="日志ID")
    order_id: int = Field(..., description="订单ID")
    out_order_no: str = Field(default="", description="渠道订单号")
    internal_order_no: str = Field(default="", description="平台内部订单号")
    order_status_from: int = Field(..., description="操作前状态")
    order_status_to: int = Field(..., description="操作后状态")
    status_from_label: str = Field(default="", description="操作前状态中文描述")
    status_to_label: str = Field(default="", description="操作后状态中文描述")
    operation_type: str = Field(default="", description="操作类型")
    operation_type_label: str = Field(default="", description="操作类型中文描述")
    operator_id: int = Field(default=0, description="操作人ID")
    operator_name: str = Field(default="", description="操作人名称")
    remark: str = Field(default="", description="操作原因/备注")
    create_time: Optional[str] = Field(default=None, description="操作时间")
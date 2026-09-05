# @ai-generated
"""B13-1 提现管理后台 Schema 定义"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WithdrawListRequest(BaseModel):
    """提现列表查询参数"""
    user_id: Optional[int] = Field(default=None, description="平台用户ID筛选")
    status: Optional[str] = Field(default=None, description="提现状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED")
    start_time: Optional[datetime] = Field(default=None, description="创建时间起始")
    end_time: Optional[datetime] = Field(default=None, description="创建时间截止")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class WithdrawListItemResponse(BaseModel):
    """提现列表项响应"""
    id: int = Field(..., description="提现申请ID")
    apply_no: str = Field(..., description="提现单号")
    user_id: int = Field(..., description="平台用户ID")
    apply_amount: str = Field(..., description="申请提现金额(元)")
    fee: str = Field(..., description="手续费(元)")
    actual_amount: str = Field(..., description="实际到账金额(元)")
    status: str = Field(..., description="提现状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED")
    review_user_id: Optional[int] = Field(default=None, description="审核人ID")
    review_remark: str = Field(default="", description="审核备注")
    review_time: Optional[datetime] = Field(default=None, description="审核时间")
    transfer_time: Optional[datetime] = Field(default=None, description="打款完成时间")
    reject_reason: str = Field(default="", description="驳回原因（含打款失败原因）")
    remark: str = Field(default="", description="备注")
    create_time: datetime = Field(..., description="创建时间")


class WithdrawDetailResponse(WithdrawListItemResponse):
    """提现详情响应（继承列表项，包含转账信息）"""
    transfer_batch_id: str = Field(default="", description="微信转账批次ID")


class WithdrawReviewRequest(BaseModel):
    """提现审核请求"""
    action: str = Field(..., description="审核动作：approve(通过)/reject(驳回)")
    review_remark: str = Field(default="", max_length=512, description="审核备注")
    reject_reason: str = Field(default="", max_length=512, description="驳回原因（action=reject时必填）")


class WithdrawTransferRequest(BaseModel):
    """提现转账信息更新请求"""
    transfer_batch_id: str = Field(..., min_length=1, max_length=64, description="微信转账批次ID")
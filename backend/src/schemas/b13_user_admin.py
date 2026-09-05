# @ai-generated
"""B13-补全 C端用户管理后台 Schema 定义"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UserListResponse(BaseModel):
    """用户列表项响应（含佣金账户 + 管理档案）"""
    user_id: int = Field(..., description="平台用户ID")
    total_balance: str = Field(default="0.00", description="累计已结算佣金(元)")
    available_balance: str = Field(default="0.00", description="可用余额(元)")
    frozen_balance: str = Field(default="0.00", description="冻结余额(元)")
    cumulative_withdrawn: str = Field(default="0.00", description="累计成功提现(元)")
    cumulative_fee: str = Field(default="0.00", description="累计手续费(元)")
    account_create_time: Optional[datetime] = Field(default=None, description="账户创建时间")
    status: str = Field(default="normal", description="管理状态：normal/frozen")
    frozen_reason: str = Field(default="", description="冻结原因")
    frozen_time: Optional[datetime] = Field(default=None, description="冻结时间")
    admin_remark: str = Field(default="", description="管理员备注")
    last_admin_id: int = Field(default=0, description="最后操作管理员ID")


class UserDetailResponse(UserListResponse):
    """用户详情响应（继承列表项，可扩展）"""


class UserRemarkRequest(BaseModel):
    """用户备注更新请求"""
    admin_remark: str = Field(..., min_length=0, max_length=512, description="管理员备注")


class UserFreezeRequest(BaseModel):
    """用户冻结请求"""
    frozen_reason: str = Field(..., min_length=1, max_length=512, description="冻结原因")


class UserUnfreezeRequest(BaseModel):
    """用户解冻请求（无必填字段）"""
    pass

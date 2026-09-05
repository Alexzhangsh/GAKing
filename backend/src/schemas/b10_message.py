# @ai-generated
"""
B10 站内消息 Pydantic DTO 定义
统一入参/出参校验模型，字段与 ORM Model 对齐
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.config.b10_constants import MessageType


# ══════════════════════════════════════════════════════
# 用户端请求 DTO
# ══════════════════════════════════════════════════════


class UserMessageListQuery(BaseModel):
    """用户消息列表查询参数"""

    message_type: Optional[str] = Field(default=None, description="消息类型筛选：commission/withdraw/order/refund")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class MarkReadRequest(BaseModel):
    """标记已读请求体"""

    message_id: Optional[int] = Field(default=None, gt=0, description="消息ID，为空时标记全部已读")


# ══════════════════════════════════════════════════════
# 消息生产 DTO（Service 内部调用）
# ══════════════════════════════════════════════════════


class MessageCreateRequest(BaseModel):
    """创建消息请求体（Service 内部调用，非 API 入参）"""

    user_id: int = Field(..., gt=0, description="接收用户ID")
    message_type: str = Field(..., description="消息类型")
    title: str = Field(..., max_length=256, description="消息标题")
    content: str = Field(..., description="消息内容")
    biz_id: str = Field(default="", max_length=64, description="关联业务ID")

    @field_validator("message_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid = {t.value for t in MessageType}
        if v not in valid:
            raise ValueError(f"message_type 必须为合法值: {sorted(valid)}")
        return v


# ══════════════════════════════════════════════════════
# 后台管理 DTO
# ══════════════════════════════════════════════════════


class AdminMessageListQuery(BaseModel):
    """后台消息管理列表查询参数"""

    user_id: Optional[int] = Field(default=None, gt=0, description="用户ID筛选")
    message_type: Optional[str] = Field(default=None, description="消息类型筛选")
    is_read: Optional[int] = Field(default=None, ge=0, le=1, description="已读状态：0=未读 1=已读")
    push_status: Optional[int] = Field(default=None, ge=0, le=2, description="推送状态：0=待推送 1=已推送 2=推送失败")
    start_time: Optional[str] = Field(default=None, description="创建时间起始")
    end_time: Optional[str] = Field(default=None, description="创建时间截止")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


# ══════════════════════════════════════════════════════
# 响应 DTO
# ══════════════════════════════════════════════════════


class MessageResponse(BaseModel):
    """消息响应体"""

    id: int
    user_id: int
    message_type: str
    title: str
    content: str
    biz_id: str
    is_read: int
    read_time: str
    push_status: int
    push_error: str
    create_time: Optional[str] = None
    update_time: Optional[str] = None


class UnreadCountResponse(BaseModel):
    """未读消息计数响应"""

    unread_count: int
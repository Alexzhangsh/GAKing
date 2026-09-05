# @ai-generated
"""
F05 营销消息用户端 Pydantic Schema
订阅授权请求/响应模型定义
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════
# 订阅授权请求
# ════════════════════════════════════════════════════════════

class SubscribeRequest(BaseModel):
    """订阅授权请求体（POST /api/v1/message/subscribe）"""
    template_id: int = Field(..., gt=0, description="消息模板ID")
    action: str = Field(..., description="授权结果：accept=已同意 reject=用户拒绝 expired=授权过期/不可用")
    tmpl_id: str = Field("", max_length=128, description="微信订阅消息模板ID（冗余存储，可选）")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"accept", "reject", "expired"}
        if v not in allowed:
            raise ValueError(f"action 必须为: {sorted(allowed)}")
        return v


class UnsubscribeRequest(BaseModel):
    """取消订阅请求体（POST /api/v1/message/unsubscribe）"""
    template_id: int = Field(..., gt=0, description="消息模板ID")


# ════════════════════════════════════════════════════════════
# 响应模型
# ════════════════════════════════════════════════════════════

class SubscribeTemplateItem(BaseModel):
    """可订阅模板项（消息中心订阅弹窗渲染用）"""
    id: int
    template_name: str
    tmpl_id: str
    title: str
    content: str
    keywords: Optional[List[str]] = None


class SubscribeStatusItem(BaseModel):
    """订阅状态项（按模板返回）"""
    template_id: int
    template_name: str
    tmpl_id: str
    subscribe_status: int  # 1=已订阅 0=未订阅/已取消
    subscribe_time: Optional[str] = None
    expire_time: Optional[str] = None
    expired: bool  # 是否已过期（一次性模板7天有效期）

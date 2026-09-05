# @ai-generated
"""
F04 营销消息模块 Pydantic Schema
请求/响应模型定义
"""
from typing import List, Optional

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════
# 消息模板 Schema
# ════════════════════════════════════════════════════════════

class MessageTemplateCreate(BaseModel):
    """新增消息模板"""
    template_name: str = Field(..., max_length=128, description="模板名称")
    template_type: int = Field(1, ge=1, le=2, description="模板类型：1=微信订阅消息 2=站内消息")
    tmpl_id: str = Field("", max_length=128, description="微信订阅消息模板ID（type=1时必填）")
    title: str = Field("", max_length=256, description="消息标题")
    content: str = Field(..., description="消息内容（支持占位符 {{keyword1}}）")
    keywords: Optional[List[str]] = Field(None, description="关键词列表（微信订阅消息用）")
    remark: str = Field("", max_length=512, description="备注")


class MessageTemplateUpdate(BaseModel):
    """更新消息模板"""
    template_name: Optional[str] = Field(None, max_length=128)
    template_type: Optional[int] = Field(None, ge=1, le=2)
    tmpl_id: Optional[str] = Field(None, max_length=128)
    title: Optional[str] = Field(None, max_length=256)
    content: Optional[str] = None
    keywords: Optional[List[str]] = None
    remark: Optional[str] = Field(None, max_length=512)


class MessageTemplateResponse(BaseModel):
    """消息模板响应"""
    id: int
    template_name: str
    template_type: int
    tmpl_id: str
    title: str
    content: str
    keywords: Optional[List[str]] = None
    status: int
    remark: str
    create_time: Optional[str] = None
    update_time: Optional[str] = None


# ════════════════════════════════════════════════════════════
# 推送记录 Schema
# ════════════════════════════════════════════════════════════

class PushRecordResponse(BaseModel):
    """推送记录响应"""
    id: int
    template_id: str
    user_id: str
    push_status: int
    push_time: Optional[str] = None
    error_msg: str
    create_time: Optional[str] = None


# ════════════════════════════════════════════════════════════
# 订阅绑定 Schema
# ════════════════════════════════════════════════════════════

class SubscribeBindingResponse(BaseModel):
    """订阅绑定响应"""
    id: int
    user_id: str
    template_id: str
    subscribe_status: int
    subscribe_time: Optional[str] = None
    expire_time: Optional[str] = None
    create_time: Optional[str] = None


# ════════════════════════════════════════════════════════════
# 渠道密钥测试 Schema
# ════════════════════════════════════════════════════════════

class ChannelKeyTestRequest(BaseModel):
    """渠道密钥测试请求"""
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq / orderx")
    api_token: str = Field(..., max_length=256, description="渠道API Token")
    api_secret: str = Field("", max_length=256, description="渠道API密钥")


class ChannelKeyTestResponse(BaseModel):
    """渠道密钥测试响应"""
    success: bool
    message: str
    channel_code: str

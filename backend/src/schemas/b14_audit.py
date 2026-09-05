# @ai-generated
"""
B14 审计日志 Schema（查询 / 详情 / 导出）
新建独立文件，不修改 B01-B13 任何基线 schema

设计要点：
- 审计日志只读不写（写入由 AuditLogger / B14AuditMiddleware 自动完成）
- 多条件分页查询：user_id / action / target_type / 时间范围
- details 字段已脱敏，原样返回即可
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """审计日志响应体"""

    id: int = Field(..., description="主键ID")
    user_id: int = Field(..., description="操作人ID（0 表示匿名）")
    user_name: str = Field(default="", description="操作人姓名")
    action: str = Field(..., description="操作动作")
    target_type: str = Field(default="", description="目标类型")
    target_id: int = Field(default=0, description="目标ID")
    details: str = Field(default="", description="脱敏操作内容（JSON 字符串）")
    ip_address: str = Field(default="", description="IP 地址")
    user_agent: str = Field(default="", description="User Agent")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """审计日志分页列表响应体"""

    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[AuditLogResponse] = Field(default_factory=list, description="日志列表")


class AuditLogStatsResponse(BaseModel):
    """审计日志统计响应体（按动作类型聚合）"""

    total: int = Field(..., description="日志总数")
    by_action: dict = Field(default_factory=dict, description="按动作类型聚合：{action: count}")
    by_target_type: dict = Field(
        default_factory=dict, description="按目标类型聚合：{target_type: count}"
    )
    by_user: dict = Field(default_factory=dict, description="按操作人聚合：{user_id: count}")

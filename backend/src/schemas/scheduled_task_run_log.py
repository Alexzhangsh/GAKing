# @ai-generated
"""
B05-7 定时任务运行日志 Pydantic Schema 定义
"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════
# 响应 DTO
# ══════════════════════════════════════════════════════

class ScheduledTaskRunLogItem(BaseModel):
    """定时任务运行日志列表项"""
    id: int = Field(..., description="日志ID")
    task_name: str = Field(..., description="任务名称")
    run_id: str = Field(..., description="运行批次ID")
    status: str = Field(..., description="运行状态：running/success/failed/partial")
    started_at: str = Field(..., description="开始时间")
    finished_at: Optional[str] = Field(default=None, description="结束时间")
    duration_seconds: int = Field(default=0, description="耗时(秒)")
    total_orders: int = Field(default=0, description="总处理订单数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
    skipped_count: int = Field(default=0, description="跳过数")
    error_message: str = Field(default="", description="错误信息")


class ScheduledTaskRunLogListResponse(BaseModel):
    """定时任务运行日志分页列表响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[ScheduledTaskRunLogItem] = Field(default_factory=list, description="运行日志列表")


class ScheduledTaskRunLogDetailResponse(BaseModel):
    """定时任务运行日志详情响应"""
    id: int = Field(..., description="日志ID")
    task_name: str = Field(..., description="任务名称")
    run_id: str = Field(..., description="运行批次ID")
    status: str = Field(..., description="运行状态")
    started_at: str = Field(..., description="开始时间")
    finished_at: Optional[str] = Field(default=None, description="结束时间")
    duration_seconds: int = Field(default=0, description="耗时(秒)")
    total_orders: int = Field(default=0, description="总处理订单数")
    success_count: int = Field(default=0, description="成功数")
    failed_count: int = Field(default=0, description="失败数")
    skipped_count: int = Field(default=0, description="跳过数")
    error_message: str = Field(default="", description="错误信息")
    detail_json: Any = Field(default=None, description="详细结果")
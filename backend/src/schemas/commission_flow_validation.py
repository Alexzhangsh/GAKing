# @ai-generated
"""
B05-5 佣金流水结算前置校验 Pydantic Schema 定义
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════
# 请求 DTO
# ══════════════════════════════════════════════════════

class CommissionFlowPreValidateRequest(BaseModel):
    """结算前置校验请求"""
    order_id: int = Field(..., gt=0, description="订单ID")


# ══════════════════════════════════════════════════════
# 响应 DTO
# ══════════════════════════════════════════════════════

class CheckItemDetail(BaseModel):
    """单项校验结果明细"""
    name: str = Field(..., description="校验项名称")
    passed: bool = Field(..., description="是否通过")
    current_value: Any = Field(default=None, description="当前值")
    expected_value: Any = Field(default=None, description="期望值")
    message: str = Field(default="", description="校验信息")


class CommissionFlowPreValidateResponse(BaseModel):
    """结算前置校验响应"""
    order_id: int = Field(..., description="订单ID")
    validation_result: str = Field(..., description="校验结果：PASS-通过 / FAIL-失败")
    check_items: List[CheckItemDetail] = Field(default_factory=list, description="各项校验明细")
    error_message: str = Field(default="", description="总体错误信息（校验失败时）")


class CommissionFlowValidationLogItem(BaseModel):
    """校验日志列表项"""
    id: int = Field(..., description="日志ID")
    order_id: int = Field(..., description="关联订单ID")
    user_id: int = Field(..., description="用户ID")
    validation_type: str = Field(..., description="校验类型")
    validation_result: str = Field(..., description="校验结果：PASS/FAIL")
    check_items: str = Field(..., description="各项校验明细JSON")
    error_message: str = Field(default="", description="总体错误信息")
    operator_id: int = Field(default=0, description="操作人管理员ID")
    create_time: Optional[str] = Field(default=None, description="创建时间")


class CommissionFlowValidationLogListResponse(BaseModel):
    """校验日志分页列表响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[CommissionFlowValidationLogItem] = Field(default_factory=list, description="校验日志列表")
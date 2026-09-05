# @ai-generated
"""
B05-6 退款冲减 Pydantic Schema 定义
"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════
# 请求 DTO
# ══════════════════════════════════════════════════════

class RefundDeductionPreValidateRequest(BaseModel):
    """退款扣减前置校验请求"""
    order_id: int = Field(..., gt=0, description="订单ID")


class RefundDeductionExecuteRequest(BaseModel):
    """执行退款扣减请求"""
    order_id: int = Field(..., gt=0, description="订单ID")
    remark: str = Field(default="", max_length=512, description="操作备注")


# ══════════════════════════════════════════════════════
# 响应 DTO
# ══════════════════════════════════════════════════════

class RefundCheckItemDetail(BaseModel):
    """单项校验结果明细"""
    name: str = Field(..., description="校验项名称")
    passed: bool = Field(..., description="是否通过")
    current_value: Any = Field(default=None, description="当前值")
    expected_value: Any = Field(default=None, description="期望值")
    message: str = Field(default="", description="校验信息")


class RefundDeductionPreValidateResponse(BaseModel):
    """退款扣减前置校验响应"""
    order_id: int = Field(..., description="订单ID")
    validation_result: str = Field(..., description="校验结果：PASS-通过 / FAIL-失败")
    check_items: List[RefundCheckItemDetail] = Field(default_factory=list, description="各项校验明细")
    error_message: str = Field(default="", description="总体错误信息")


class RefundDeductionExecuteResponse(BaseModel):
    """执行退款扣减响应"""
    order_id: int = Field(..., description="订单ID")
    status: str = Field(..., description="状态：success/skipped/failed")
    deduct_flow_id: Optional[int] = Field(default=None, description="关联扣减流水ID")
    deduct_amount: Optional[float] = Field(default=None, description="扣减金额(元)")
    old_available_balance: Optional[float] = Field(default=None, description="扣减前可用余额(元)")
    new_available_balance: Optional[float] = Field(default=None, description="扣减后可用余额(元)")
    message: str = Field(default="", description="处理信息")
    log_id: Optional[int] = Field(default=None, description="操作日志ID")


class RefundOperationLogItem(BaseModel):
    """退款操作日志列表项"""
    id: int = Field(..., description="日志ID")
    order_id: int = Field(..., description="关联订单ID")
    operator_id: int = Field(..., description="操作人管理员ID")
    operation_type: str = Field(..., description="操作类型")
    order_status_before: int = Field(..., description="变更前订单状态")
    order_status_after: int = Field(..., description="变更后订单状态")
    deduct_amount: float = Field(..., description="扣减金额(元)")
    flow_type: str = Field(default="", description="原始流水类型")
    flow_transfer_status: str = Field(default="", description="原始流水转账状态")
    old_available_balance: float = Field(..., description="变更前可用余额")
    new_available_balance: float = Field(..., description="变更后可用余额")
    old_total_balance: float = Field(..., description="变更前累计佣金")
    new_total_balance: float = Field(..., description="变更后累计佣金")
    deduct_flow_id: Optional[int] = Field(default=None, description="关联扣减流水ID")
    remark: str = Field(default="", description="备注说明")
    create_time: Optional[str] = Field(default=None, description="创建时间")


class RefundOperationLogListResponse(BaseModel):
    """退款操作日志分页列表响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[RefundOperationLogItem] = Field(default_factory=list, description="退款操作日志列表")
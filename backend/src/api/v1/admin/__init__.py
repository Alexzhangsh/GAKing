# @ai-generated
"""后台审核 API 包 —— 统一导出提现审核 + 订单同步 + 佣金结算管理 + 结算状态机 + 全链路对账 + B14 路由 + B05-5 前置校验"""
from src.api.v1.admin.withdraw_review import router as withdraw_review_router
from src.api.v1.admin.order_sync import router as order_sync_router
from src.api.v1.admin.commission_settlement import (
    router as commission_settlement_router,
)
from src.api.v1.admin.settlement_b12 import router as settlement_b12_router
from src.api.v1.admin.reconciliation_b13 import router as reconciliation_b13_router
# B14 新增路由
from src.api.v1.admin.b14_auth import router as b14_auth_router
from src.api.v1.admin.b14_config import router as b14_config_router
from src.api.v1.admin.b14_rbac import router as b14_rbac_router
from src.api.v1.admin.b14_audit import router as b14_audit_router
# B05-5 新增路由
from src.api.v1.admin.commission_flow_validation import (
    router as commission_flow_validation_router,
)
# B05-6 新增路由
from src.api.v1.admin.refund_deduction import (
    router as refund_deduction_router,
)
# B05-7 新增路由
from src.api.v1.admin.scheduled_task_run_log import (
    router as scheduled_task_run_log_router,
)
# B06-1 新增路由
from src.api.v1.admin.b06_channel import (
    router as b06_channel_router,
)
# B06-2 新增路由
from src.api.v1.admin.b06_2_channel import (
    router as b06_2_channel_router,
)
# B07-1 新增路由
from src.api.v1.admin.b07_1_reverse_commission import (
    router as b07_1_reverse_commission_router,
)
# B08-1 新增路由
from src.api.v1.admin.b08_1_account import (
    router as b08_1_account_router,
)
# B10-1 新增路由
from src.api.v1.admin.b10_message import (
    router as b10_message_router,
)
# B11-1 新增路由
from src.api.v1.admin.b11_channel import (
    router as b11_channel_router,
)
# B12-1 新增路由
from src.api.v1.admin.b12_order_state_machine import (
    router as b12_order_state_machine_router,
)
# B17 新增路由
from src.api.v1.admin.b17_channel_reconciliation import (
    router as b17_channel_reconciliation_router,
)
# M07-2 新增路由
from src.api.v1.admin.ops_monitor import (
    router as ops_monitor_router,
)
# X02-1 新增路由
from src.api.v1.admin.member_package import (
    router as member_package_router,
)
from src.api.v1.admin.member_record import (
    router as member_record_router,
)
__all__ = [
    "withdraw_review_router",
    "order_sync_router",
    "commission_settlement_router",
    "settlement_b12_router",
    "reconciliation_b13_router",
    # B14
    "b14_auth_router",
    "b14_config_router",
    "b14_rbac_router",
    "b14_audit_router",
    # B05-5
    "commission_flow_validation_router",
    # B05-6
    "refund_deduction_router",
    # B05-7
    "scheduled_task_run_log_router",
    # B06-1
    "b06_channel_router",
    # B06-2
    "b06_2_channel_router",
    # B07-1
    "b07_1_reverse_commission_router",
    # B08-1
    "b08_1_account_router",
    # B10-1
    "b10_message_router",
    # B11-1
    "b11_channel_router",
    # B12-1
    "b12_order_state_machine_router",
    # B17
    "b17_channel_reconciliation_router",
    # M07-2
    "ops_monitor_router",
    # X02-1
    "member_package_router",
    "member_record_router",
]

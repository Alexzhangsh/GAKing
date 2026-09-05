# @ai-generated
"""API v1 路由包 —— 统一导出 CPS 订单 / 佣金 / 用户提现 / 订单同步 / 佣金结算管理 / 结算状态机 / 全链路对账 / 前端埋点 / 短链管理 / 异常订单 / 前置校验路由"""
from src.api.v1.cps_order import router as cps_order_router
from src.api.v1.cps_commission import router as cps_commission_router
from src.api.v1.withdraw import router as withdraw_router
from src.api.v1.admin.withdraw_review import router as withdraw_review_router
from src.api.v1.admin.order_sync import router as order_sync_router
from src.api.v1.admin.commission_settlement import (
    router as commission_settlement_router,
)
from src.api.v1.admin.settlement_b12 import router as settlement_b12_router
from src.api.v1.admin.reconciliation_b13 import router as reconciliation_b13_router
from src.api.v1.track import router as track_router
# B05-4 短链管理 & 异常订单
from src.api.v1.short_link import router as short_link_router
from src.api.v1.admin.abnormal_order import router as abnormal_order_router
# B05-5 佣金流水前置校验
from src.api.v1.admin.commission_flow_validation import (
    router as commission_flow_validation_router,
)
# B05-6 退款冲减管理
from src.api.v1.admin.refund_deduction import (
    router as refund_deduction_router,
)
# B06-2 渠道报表导出与对账
from src.api.v1.admin.b06_2_channel import (
    router as b06_2_channel_router,
)
# B07-1 逆向佣金冲减
from src.api.v1.admin.b07_1_reverse_commission import (
    router as b07_1_reverse_commission_router,
)
# B08-1 用户佣金资产管理
from src.api.v1.admin.b08_1_account import (
    router as b08_1_account_router,
)
# B10-1 站内消息用户端
from src.api.v1.b10_message import router as b10_message_router
# F05 营销消息订阅用户端
from src.api.v1.b15_message_user import router as b15_message_user_router
# B11-1 渠道信息用户端
from src.api.v1.b11_channel import router as b11_channel_router
# B05-8 定时任务运行日志
from src.api.v1.admin.scheduled_task_run_log import (
    router as scheduled_task_run_log_router,
)
# M07-2 运维监控
from src.api.v1.admin.ops_monitor import (
    router as ops_monitor_router,
)
# X02-1 会员套餐管理 + 会员记录
from src.api.v1.admin.member_package import (
    router as member_package_router,
)
from src.api.v1.admin.member_record import (
    router as member_record_router,
)
__all__ = [
    "cps_order_router",
    "cps_commission_router",
    "withdraw_router",
    "withdraw_review_router",
    "order_sync_router",
    "commission_settlement_router",
    "settlement_b12_router",
    "reconciliation_b13_router",
    "track_router",
    "short_link_router",
    "abnormal_order_router",
    "commission_flow_validation_router",
    "refund_deduction_router",
    "b06_2_channel_router",
    "b07_1_reverse_commission_router",
    "b08_1_account_router",
    "b10_message_router",
    "b15_message_user_router",
    "b11_channel_router",
    "scheduled_task_run_log_router",
    "ops_monitor_router",
    "member_package_router",
    "member_record_router",
]

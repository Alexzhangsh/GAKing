# @ai-generated
"""API v1 路由包 —— 统一导出 CPS 订单 / 佣金 / 用户提现 / 订单同步 / 佣金结算管理路由"""
from src.api.v1.cps_order import router as cps_order_router
from src.api.v1.cps_commission import router as cps_commission_router
from src.api.v1.withdraw import router as withdraw_router
from src.api.v1.admin.withdraw_review import router as withdraw_review_router
from src.api.v1.admin.order_sync import router as order_sync_router
from src.api.v1.admin.commission_settlement import (
    router as commission_settlement_router,
)

__all__ = [
    "cps_order_router",
    "cps_commission_router",
    "withdraw_router",
    "withdraw_review_router",
    "order_sync_router",
    "commission_settlement_router",
]

# @ai-generated
"""
B13-补全 + B14-补全 模块装配入口
新建独立装配文件，不修改 B01-B15 存量代码逻辑
在 main.py 中通过 setup_b13_b14(app) 调用挂载 5 个新路由：
  - b13_goods_router    商品管理后台
  - b13_user_router     C端用户管理后台
  - b14_dashboard_router 数据大盘 + 多维度统计
  - b13_order_router    B13-1 订单管理后台
  - b13_withdraw_router B13-1 提现管理后台
"""
import logging

from fastapi import FastAPI

from src.api.v1.admin.b13_goods import router as b13_goods_router
from src.api.v1.admin.b13_user import router as b13_user_router
from src.api.v1.admin.b14_dashboard import router as b14_dashboard_router
# B13-1 新增路由
from src.api.v1.admin.b13_order_admin import router as b13_order_router
from src.api.v1.admin.b13_withdraw_admin import router as b13_withdraw_router
# B14-1 新增路由
from src.api.v1.admin.b14_1_dashboard import router as b14_1_dashboard_router

logger = logging.getLogger("api.b13_b14_setup")


def setup_b13_b14(app: FastAPI) -> None:
    """装配 B13-补全 + B14-补全 模块路由

    在 main.py 中 setup_b14(app) 之后调用：
        setup_b13_b14(app)
    """
    app.include_router(b13_goods_router)
    app.include_router(b13_user_router)
    app.include_router(b14_dashboard_router)
    # B13-1 新增路由
    app.include_router(b13_order_router)
    app.include_router(b13_withdraw_router)
    # B14-1 新增路由
    app.include_router(b14_1_dashboard_router)
    logger.info(
        "[b13_b14_setup] 已挂载 6 个补全路由: goods / users-manage / dashboard / orders / withdraws / dashboard-export"
    )

# @ai-generated
"""
B14-补全 数据大盘 API 路由
权限码：dashboard:view（全部接口需此权限）
路由前缀：/api/v1/admin/dashboard
所有查询自动被 B14 审计中间件记录（GET 请求不被审计中间件拦截，
但 service 层会通过 AuditLogger 记录 DASHBOARD_QUERY 动作）
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_DASHBOARD_VIEW
from src.services.b14_dashboard_service import B14DashboardService

logger = logging.getLogger("api.b14_dashboard")

router = APIRouter(
    prefix="/api/v1/admin/dashboard",
    tags=["后台-数据大盘(B14-补全)"],
)


@router.get("/cards")
async def get_cards(
    request: Request,
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_VIEW])),
):
    """首页 5 张卡片聚合数据

    返回：累计订单、待结算佣金、已结算佣金、提现总额、待审核提现数量
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B14DashboardService.get_cards_data(admin_user_id=admin_user_id)
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/commission-stats")
async def get_commission_stats(
    request: Request,
    group_by: str = Query(..., description="分组维度：date/channel/user"),
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    page: int = Query(1, ge=1, description="页码（仅 group_by=user 时生效）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数（仅 group_by=user 时生效）"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_VIEW])),
):
    """多维度佣金统计

    按日期/渠道/用户分组佣金统计
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B14DashboardService.get_commission_stats(
            group_by=group_by,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/order-trend")
async def get_order_trend(
    request: Request,
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    group_by: str = Query("day", description="分组维度：day/week/month"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_VIEW])),
):
    """订单趋势折线数据

    按天/周/月分组订单数与佣金总额
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B14DashboardService.get_order_trend(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/withdraw-trend")
async def get_withdraw_trend(
    request: Request,
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    group_by: str = Query("day", description="分组维度：day/week/month"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_VIEW])),
):
    """提现趋势折线数据

    按天/周/月分组提现申请数、申请金额和成功金额
    """
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        data = await B14DashboardService.get_withdraw_trend(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            admin_user_id=admin_user_id,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

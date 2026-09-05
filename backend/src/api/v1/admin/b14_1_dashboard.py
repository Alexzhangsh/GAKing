# @ai-generated
"""
B14-1 数据大盘报表导出 API 路由
权限码：dashboard:view（查询）/ dashboard:export（导出）
路由前缀：/api/v1/admin/dashboard
所有导出操作自动记录审计日志
"""
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_DASHBOARD_VIEW
from src.config.b14_1_constants import PERM_DASHBOARD_EXPORT
from src.services.b14_1_dashboard_export_service import (
    B14DashboardExportService,
    EXPORT_DIR,
)

logger = logging.getLogger("api.b14_1_dashboard")

router = APIRouter(
    prefix="/api/v1/admin/dashboard",
    tags=["后台-数据大盘(B14-1)"],
)


@router.get("/export/commission-stats")
async def export_commission_stats(
    request: Request,
    group_by: str = Query(..., description="分组维度：date/channel/user"),
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_EXPORT])),
):
    """导出佣金统计报表（Excel）"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        result = await B14DashboardExportService.export_commission_stats(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            admin_user_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/export/order-trend")
async def export_order_trend(
    request: Request,
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    group_by: str = Query("day", description="分组维度：day/week/month"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_EXPORT])),
):
    """导出订单趋势报表（Excel）"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        result = await B14DashboardExportService.export_order_trend(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            admin_user_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/export/withdraw-trend")
async def export_withdraw_trend(
    request: Request,
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    group_by: str = Query("day", description="分组维度：day/week/month"),
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_EXPORT])),
):
    """导出提现趋势报表（Excel）"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        result = await B14DashboardExportService.export_withdraw_trend(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            admin_user_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/export/cards")
async def export_cards(
    request: Request,
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_EXPORT])),
):
    """导出大盘卡片数据快照（Excel）"""
    request_id = get_request_id(request)
    try:
        admin_user_id = payload.get("user_id", 0)
        result = await B14DashboardExportService.export_cards_report(
            admin_user_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/export/download/{file_name}")
async def download_export(
    request: Request,
    file_name: str,
    payload: dict = Depends(require_any_permission([PERM_DASHBOARD_EXPORT])),
):
    """下载导出的 Excel 报表文件"""
    request_id = get_request_id(request)
    try:
        file_path = os.path.join(EXPORT_DIR, file_name)
        # 安全检查：防止路径穿越
        real_path = os.path.realpath(file_path)
        real_base = os.path.realpath(EXPORT_DIR)
        if not real_path.startswith(real_base):
            return error_response(
                data=None, msg="非法文件路径", code=400, request_id=request_id
            )
        if not os.path.exists(file_path):
            return error_response(
                data=None, msg="文件不存在", code=404, request_id=request_id
            )
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)
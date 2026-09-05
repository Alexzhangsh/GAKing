# @ai-generated
"""
B11-1 后台渠道管理 API 路由
路由前缀：/api/v1/admin/b11/channel

功能范围：
1. 黑名单管理 CRUD
2. 每日统计查询
3. 配置变更日志查询
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b11_constants import (
    BLACKLIST_TYPE_LABELS,
    OPERATION_TYPE_LABELS,
    PERM_CHANNEL_BLACKLIST,
    PERM_CHANNEL_STAT,
    BlacklistType,
    OperationType,
)
from src.dao.b11_channel_dao import (
    ChannelBlacklistDAO,
    ChannelDailyStatDAO,
    ChannelConfigLogDAO,
)
from src.db.base import DatabaseManager
from src.services.b11_channel_service import (
    B11ChannelBlacklistService,
    B11ChannelConfigLogService,
    B11ChannelStatisticsService,
)

logger = logging.getLogger("api.admin.b11_channel")

router = APIRouter(prefix="/api/v1/admin/b11/channel", tags=["后台-渠道管理(B11)"])


# ── 依赖注入 ──────────────────────────────────────────────


async def get_admin_info(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_BLACKLIST, PERM_CHANNEL_STAT])),
) -> dict:
    return {"user_id": int(payload["user_id"]), "user_name": payload.get("real_name", "")}


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════


class BlacklistAddRequest(BaseModel):
    """新增黑名单请求参数"""
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq/orderx")
    blacklist_type: str = Field(..., description=f"黑名单类型：{', '.join(BlacklistType)}")
    blacklist_value: str = Field(..., max_length=128, description="黑名单值（用户ID/IP地址/订单号）")
    reason: str = Field("", max_length=512, description="拉黑原因")


class BlacklistToggleRequest(BaseModel):
    """启停黑名单请求参数"""
    status: int = Field(..., description="目标状态：0-禁用 1-启用")


class DailyStatQueryParams(BaseModel):
    """每日统计查询参数"""
    start_date: str = Field(..., description="起始日期(YYYY-MM-DD)")
    end_date: str = Field(..., description="截止日期(YYYY-MM-DD)")
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识，为空时查询全部")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class ConfigLogQueryParams(BaseModel):
    """配置日志查询参数"""
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识")
    operation_type: Optional[str] = Field(None, description="操作类型")
    start_time: Optional[str] = Field(None, description="起始时间(YYYY-MM-DD HH:mm:ss)")
    end_time: Optional[str] = Field(None, description="截止时间(YYYY-MM-DD HH:mm:ss)")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


# ════════════════════════════════════════════════════════════
# 1. 黑名单管理
# ════════════════════════════════════════════════════════════


@router.get("/blacklist/list")
async def list_blacklist(
    request: Request,
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识"),
    blacklist_type: Optional[str] = Query(None, description="黑名单类型：user/ip/order"),
    status: Optional[int] = Query(None, description="状态：0-禁用 1-启用"),
    keyword: Optional[str] = Query(None, max_length=64, description="搜索关键词（黑名单值）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    admin_info: dict = Depends(get_admin_info),
):
    """黑名单列表（分页+筛选+搜索）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelBlacklistDAO(session)
            svc = B11ChannelBlacklistService(dao)
            data = await svc.list_blacklist(
                channel_code=channel_code,
                blacklist_type=blacklist_type,
                status=status,
                keyword=keyword,
                page=page,
                page_size=page_size,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/blacklist/{item_id}")
async def get_blacklist_detail(
    request: Request,
    item_id: int,
    admin_info: dict = Depends(get_admin_info),
):
    """黑名单详情"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelBlacklistDAO(session)
            svc = B11ChannelBlacklistService(dao)
            data = await svc.get_blacklist_detail(item_id)
            if data is None:
                raise ValueError(f"黑名单记录不存在: {item_id}")
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/blacklist")
async def add_blacklist(
    request: Request,
    body: BlacklistAddRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """新增黑名单"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelBlacklistDAO(session)
            svc = B11ChannelBlacklistService(dao)
            data = await svc.add_blacklist(
                channel_code=body.channel_code,
                blacklist_type=body.blacklist_type,
                blacklist_value=body.blacklist_value,
                reason=body.reason,
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
            )

            # 写入变更日志
            log_dao = ChannelConfigLogDAO(session)
            log_svc = B11ChannelConfigLogService(log_dao)
            await log_svc.create_log(
                channel_code=body.channel_code,
                config_key=f"blacklist:{body.blacklist_type}",
                old_value="",
                old_value_label="",
                new_value=body.blacklist_value,
                new_value_label=body.blacklist_value,
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
                operation_type=OperationType.BLACKLIST_ADD,
                remark=f"新增{BLACKLIST_TYPE_LABELS.get(body.blacklist_type, body.blacklist_type)}: {body.blacklist_value}，原因: {body.reason}",
            )

            return success_response(data=data, msg="黑名单新增成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/blacklist/{item_id}")
async def remove_blacklist(
    request: Request,
    item_id: int,
    admin_info: dict = Depends(get_admin_info),
):
    """删除黑名单（软删除）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            # 先获取黑名单详情用于日志
            dao = ChannelBlacklistDAO(session)
            item = await dao.get_by_id(item_id)
            if item is None:
                raise ValueError(f"黑名单记录不存在: {item_id}")

            svc = B11ChannelBlacklistService(dao)
            result = await svc.remove_blacklist(item_id)
            if not result:
                raise ValueError(f"黑名单记录不存在: {item_id}")

            # 写入变更日志
            log_dao = ChannelConfigLogDAO(session)
            log_svc = B11ChannelConfigLogService(log_dao)
            await log_svc.create_log(
                channel_code=item.channel_code,
                config_key=f"blacklist:{item.blacklist_type}",
                old_value=item.blacklist_value,
                old_value_label=item.blacklist_value,
                new_value="",
                new_value_label="",
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
                operation_type=OperationType.BLACKLIST_REMOVE,
                remark=f"移除{BLACKLIST_TYPE_LABELS.get(item.blacklist_type, item.blacklist_type)}: {item.blacklist_value}",
            )

            return success_response(data={"id": item_id}, msg="黑名单已删除", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/blacklist/{item_id}/toggle-status")
async def toggle_blacklist_status(
    request: Request,
    item_id: int,
    body: BlacklistToggleRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """启停黑名单"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelBlacklistDAO(session)
            svc = B11ChannelBlacklistService(dao)
            data = await svc.toggle_blacklist_status(item_id, body.status)
            if data is None:
                raise ValueError(f"黑名单记录不存在: {item_id}")

            # 写入变更日志
            log_dao = ChannelConfigLogDAO(session)
            log_svc = B11ChannelConfigLogService(log_dao)
            status_text = "启用" if body.status == 1 else "禁用"
            await log_svc.create_log(
                channel_code=data["channel_code"],
                config_key=f"blacklist:{data['blacklist_type']}",
                old_value=str(1 - body.status),
                old_value_label="禁用" if body.status == 1 else "启用",
                new_value=str(body.status),
                new_value_label=status_text,
                operator_id=admin_info["user_id"],
                operator_name=admin_info.get("user_name", ""),
                operation_type=OperationType.BLACKLIST_TOGGLE,
                remark=f"{status_text}黑名单: {data['blacklist_value']}",
            )

            return success_response(data=data, msg=f"黑名单已{status_text}", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 每日统计查询
# ════════════════════════════════════════════════════════════


@router.get("/stat/daily")
async def list_daily_stat(
    request: Request,
    start_date: str = Query(..., description="起始日期(YYYY-MM-DD)"),
    end_date: str = Query(..., description="截止日期(YYYY-MM-DD)"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    admin_info: dict = Depends(get_admin_info),
):
    """渠道每日统计数据（分页）"""
    request_id = get_request_id(request)
    try:
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)

        async with DatabaseManager.get_session() as session:
            dao = ChannelDailyStatDAO(session)
            svc = B11ChannelStatisticsService(dao)
            data = await svc.list_daily_stat(
                start_date=start_dt,
                end_date=end_dt,
                channel_code=channel_code,
                page=page,
                page_size=page_size,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/stat/summary")
async def get_stat_summary(
    request: Request,
    start_date: str = Query(..., description="起始日期(YYYY-MM-DD)"),
    end_date: str = Query(..., description="截止日期(YYYY-MM-DD)"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识，为空时查询全部"),
    admin_info: dict = Depends(get_admin_info),
):
    """渠道统计汇总（按渠道聚合）"""
    request_id = get_request_id(request)
    try:
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)

        async with DatabaseManager.get_session() as session:
            dao = ChannelDailyStatDAO(session)
            svc = B11ChannelStatisticsService(dao)
            data = await svc.get_summary(
                start_date=start_dt,
                end_date=end_dt,
                channel_code=channel_code,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 配置变更日志
# ════════════════════════════════════════════════════════════


@router.get("/config-log/list")
async def list_config_logs(
    request: Request,
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道标识"),
    operation_type: Optional[str] = Query(None, description="操作类型"),
    start_time: Optional[str] = Query(None, description="起始时间(YYYY-MM-DD HH:mm:ss)"),
    end_time: Optional[str] = Query(None, description="截止时间(YYYY-MM-DD HH:mm:ss)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    admin_info: dict = Depends(get_admin_info),
):
    """配置变更日志列表（分页+筛选）"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if start_time else None
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if end_time else None

        async with DatabaseManager.get_session() as session:
            dao = ChannelConfigLogDAO(session)
            svc = B11ChannelConfigLogService(dao)
            data = await svc.list_logs(
                channel_code=channel_code,
                operation_type=operation_type,
                start_time=start_dt,
                end_time=end_dt,
                page=page,
                page_size=page_size,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
# @ai-generated
"""
B06-1 渠道管理模块 API 路由
路由前缀：/api/v1/admin/b06-channel
权限码：channel:manage（全部接口需此权限）

功能范围：
1. 渠道管理 CRUD（新增/编辑/启停/列表/详情）
2. 佣金比例配置（普通用户 + 付费会员双套比例）
3. 渠道数据看板（汇总/详情/趋势）
4. 操作审计日志自动记录
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b06_constants import (
    PERM_CHANNEL_MANAGE,
    UserType,
    USER_TYPE_LABELS,
    AuditAction as B06AuditAction,
    AuditTargetType as B06AuditTargetType,
)
from src.dao.audit_log_dao import AuditLogDAO
from src.dao.b06_channel_dao import ChannelCommissionConfigDAO, ChannelDashboardQueryDAO
from src.dao.base_dao import BaseDAO
from src.db.base import DatabaseManager
from src.models.system.b06_channel_config import ChannelCommissionConfig
from src.models.system.channel_config import ChannelMapping

logger = logging.getLogger("api.admin.b06_channel")

router = APIRouter(prefix="/api/v1/admin/b06-channel", tags=["后台-渠道管理(B06-1)"])


# ── 依赖注入 ──────────────────────────────────────────────


async def get_admin_info(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_MANAGE])),
) -> dict:
    return {"user_id": int(payload["user_id"]), "user_name": payload.get("real_name", "")}


# ════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════

# ── 渠道基础 CRUD Schema ──────────────────────────────────


class ChannelCreateRequest(BaseModel):
    """新增渠道请求参数"""
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq/orderx/dta",
                              pattern=r"^[a-z_][a-z0-9_]{1,31}$")
    channel_name: str = Field(..., max_length=64, description="渠道中文名称")
    api_token: str = Field("", max_length=256, description="渠道API Token")
    api_secret: str = Field("", max_length=256, description="渠道API密钥")
    pid: str = Field("", max_length=64, description="渠道推广位PID")
    settle_rate: float = Field(0.0, ge=0, le=1, description="结算比例(0~1)，如0.80表示渠道结算80%")
    status: bool = Field(True, description="状态：true-启用 false-禁用")
    contact_name: str = Field("", max_length=64, description="联系人")
    contact_phone: str = Field("", max_length=32, description="联系电话")
    remark: str = Field("", max_length=512, description="备注")


class ChannelUpdateRequest(BaseModel):
    """编辑渠道请求参数"""
    channel_name: Optional[str] = Field(None, max_length=64, description="渠道中文名称")
    api_token: Optional[str] = Field(None, max_length=256, description="渠道API Token")
    api_secret: Optional[str] = Field(None, max_length=256, description="渠道API密钥")
    pid: Optional[str] = Field(None, max_length=64, description="渠道推广位PID")
    settle_rate: Optional[float] = Field(None, ge=0, le=1, description="结算比例(0~1)")
    contact_name: Optional[str] = Field(None, max_length=64, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=32, description="联系电话")
    remark: Optional[str] = Field(None, max_length=512, description="备注")


class ChannelToggleStatusRequest(BaseModel):
    """启停渠道请求参数"""
    status: bool = Field(..., description="目标状态：true-启用 false-禁用")


# ── 佣金比例配置 Schema ──────────────────────────────────


class CommissionConfigItem(BaseModel):
    """单条佣金比例配置"""
    user_type: int = Field(..., description="用户类型：1-普通用户 2-付费会员")
    user_commission_rate: float = Field(..., ge=0, le=1, description="用户返利比例(0~1)")
    platform_retention_rate: float = Field(..., ge=0, le=1, description="平台留存比例(0~1)")
    remark: str = Field("", max_length=512, description="备注")

    @model_validator(mode="after")
    def validate_sum(self):
        """校验用户返利比例 + 平台留存比例 = 100%"""
        total = round(self.user_commission_rate + self.platform_retention_rate, 4)
        if abs(total - 1.0) > 0.0001:
            raise ValueError(
                f"用户返利比例({self.user_commission_rate}) + 平台留存比例({self.platform_retention_rate}) "
                f"必须等于 1 (100%)，当前合计 {total}"
            )
        return self


class CommissionConfigBatchRequest(BaseModel):
    """批量配置佣金比例请求"""
    channel_code: str = Field(..., max_length=32, description="渠道标识")
    configs: List[CommissionConfigItem] = Field(..., min_length=1, max_length=2, description="佣金比例配置列表")

    @model_validator(mode="after")
    def validate_user_types(self):
        """校验用户类型不重复"""
        user_types = [c.user_type for c in self.configs]
        if len(user_types) != len(set(user_types)):
            raise ValueError("用户类型不能重复，每条配置一个用户类型")
        for ut in user_types:
            if ut not in (UserType.NORMAL, UserType.VIP):
                raise ValueError(f"不支持的用戶类型: {ut}，仅支持 1-普通用户 2-付费会员")
        return self


# ── 数据看板 Schema ──────────────────────────────────────


class DashboardQueryParams(BaseModel):
    """数据看板查询参数"""
    start_date: Optional[str] = Field(None, description="起始日期(YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="截止日期(YYYY-MM-DD)")
    channel_code: Optional[str] = Field(None, max_length=32, description="渠道标识，为空时查询全部")
    group_by: str = Field("day", description="分组维度：day/week/month")


# ════════════════════════════════════════════════════════════
# 序列化工具函数
# ════════════════════════════════════════════════════════════


def _serialize_channel_ext(c: ChannelMapping) -> Dict[str, Any]:
    """序列化渠道配置（含扩展字段）"""
    return {
        "id": c.id,
        "channel_code": c.channel_code,
        "channel_name": c.channel_name,
        "api_token": "***" if c.api_token else "",
        "api_secret": "***" if c.api_secret else "",
        "pid": c.pid,
        "settle_rate": float(c.settle_rate) if c.settle_rate else 0.0,
        "status": c.status,
        "contact_name": getattr(c, "contact_name", ""),
        "contact_phone": getattr(c, "contact_phone", ""),
        "remark": c.remark or "",
        "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else None,
        "update_time": c.update_time.strftime("%Y-%m-%d %H:%M:%S") if c.update_time else None,
    }


def _serialize_commission_config(c: ChannelCommissionConfig) -> Dict[str, Any]:
    """序列化佣金比例配置"""
    return {
        "id": c.id,
        "channel_code": c.channel_code,
        "user_type": c.user_type,
        "user_type_label": USER_TYPE_LABELS.get(c.user_type, "未知"),
        "user_commission_rate": float(c.user_commission_rate) if c.user_commission_rate else 0.0,
        "platform_retention_rate": float(c.platform_retention_rate) if c.platform_retention_rate else 0.0,
        "remark": c.remark or "",
        "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S") if c.create_time else None,
        "update_time": c.update_time.strftime("%Y-%m-%d %H:%M:%S") if c.update_time else None,
    }


# ════════════════════════════════════════════════════════════
# 审计日志辅助
# ════════════════════════════════════════════════════════════


async def _write_audit_log(
    session,
    admin_info: dict,
    action: str,
    target_type: str,
    target_id: int,
    details: str,
    request: Request,
):
    """写入审计日志"""
    audit_dao = AuditLogDAO(session)
    await audit_dao.create_log(
        user_id=admin_info["user_id"],
        user_name=admin_info.get("user_name", ""),
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("User-Agent", ""),
    )


# ════════════════════════════════════════════════════════════
# 1. 渠道 CRUD
# ════════════════════════════════════════════════════════════


@router.get("/list")
async def list_channels(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: Optional[bool] = Query(None, description="筛选状态：true-启用 false-禁用"),
    keyword: Optional[str] = Query(None, max_length=64, description="搜索关键词（渠道名称/标识）"),
    admin_info: dict = Depends(get_admin_info),
):
    """渠道管理列表（分页+筛选+搜索）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping

            filters = {}
            if status is not None:
                filters["status"] = status

            items, total = await dao.paginate_list(
                page=page, page_size=page_size,
                filters=filters if filters else None,
                order_by="-create_time",
            )

            # 关键词搜索（过滤内存中匹配，数据量小所以可行）
            if keyword and items:
                kw = keyword.lower()
                filtered = [
                    c for c in items
                    if kw in (c.channel_code or "").lower()
                    or kw in (c.channel_name or "").lower()
                ]
                total = len(filtered)
                # 重新分页
                start = (page - 1) * page_size
                items = filtered[start:start + page_size]

            data = {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_serialize_channel_ext(c) for c in items],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{channel_code}")
async def get_channel_detail(
    request: Request,
    channel_code: str,
    admin_info: dict = Depends(get_admin_info),
):
    """渠道详情（含佣金比例配置）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            # 查询渠道基础信息
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            channel = result.scalar_one_or_none()
            if channel is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")

            data = _serialize_channel_ext(channel)

            # 查询佣金比例配置
            commission_dao = ChannelCommissionConfigDAO(session)
            commission_configs = await commission_dao.list_by_channel(channel_code)
            data["commission_configs"] = [_serialize_commission_config(c) for c in commission_configs]

            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("")
async def create_channel(
    request: Request,
    body: ChannelCreateRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """新增渠道配置"""
    request_id = get_request_id(request)
    try:
        # 校验渠道标识唯一性
        valid_codes = {"myq", "orderx", "dta"}
        if body.channel_code not in valid_codes:
            raise ValueError(f"不支持的渠道标识: {body.channel_code}，仅支持 myq / orderx / dta")

        async with DatabaseManager.get_session() as session:
            # 检查是否已存在
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            exist_stmt = dao._active_query().where(ChannelMapping.channel_code == body.channel_code)
            exist_result = await session.execute(exist_stmt)
            if exist_result.scalar_one_or_none():
                raise ValueError(f"渠道标识已存在: {body.channel_code}")

            data = body.model_dump()
            c = await dao.create(data)

            # 写入审计日志
            await _write_audit_log(
                session, admin_info,
                B06AuditAction.CHANNEL_CREATE,
                B06AuditTargetType.CHANNEL,
                c.id,
                f"新增渠道: {body.channel_code}({body.channel_name})",
                request,
            )

            return success_response(data=_serialize_channel_ext(c), msg="渠道创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{channel_code}")
async def update_channel(
    request: Request,
    channel_code: str,
    body: ChannelUpdateRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """编辑渠道配置"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")

            # 记录变更详情
            changes = []
            data = body.model_dump(exclude_unset=True)
            for key, value in data.items():
                if hasattr(c, key):
                    old_val = getattr(c, key)
                    setattr(c, key, value)
                    changes.append(f"{key}: {old_val} -> {value}")

            await session.flush()
            await session.commit()

            # 写入审计日志
            await _write_audit_log(
                session, admin_info,
                B06AuditAction.CHANNEL_UPDATE,
                B06AuditTargetType.CHANNEL,
                c.id,
                f"编辑渠道 {channel_code}: {'; '.join(changes)}",
                request,
            )

            return success_response(data=_serialize_channel_ext(c), msg="渠道更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.delete("/{channel_code}")
async def delete_channel(
    request: Request,
    channel_code: str,
    admin_info: dict = Depends(get_admin_info),
):
    """删除渠道配置（软删除，同时删除关联佣金配置）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")

            c.is_delete = True
            c.update_time = datetime.now()

            # 同时软删除关联的佣金配置
            commission_dao = ChannelCommissionConfigDAO(session)
            await commission_dao.delete_by_channel(channel_code)

            await session.flush()
            await session.commit()

            # 写入审计日志
            await _write_audit_log(
                session, admin_info,
                B06AuditAction.CHANNEL_DELETE,
                B06AuditTargetType.CHANNEL,
                c.id,
                f"删除渠道: {channel_code}",
                request,
            )

            return success_response(data={"channel_code": channel_code}, msg="渠道删除成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 渠道启停
# ════════════════════════════════════════════════════════════


@router.put("/{channel_code}/toggle-status")
async def toggle_channel_status(
    request: Request,
    channel_code: str,
    body: ChannelToggleStatusRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """启停渠道"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if c is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")

            old_status = c.status
            c.status = body.status
            c.update_time = datetime.now()
            await session.flush()
            await session.commit()

            status_text = "启用" if body.status else "禁用"
            await _write_audit_log(
                session, admin_info,
                B06AuditAction.CHANNEL_TOGGLE_STATUS,
                B06AuditTargetType.CHANNEL,
                c.id,
                f"{status_text}渠道 {channel_code}（状态变更: {old_status} -> {body.status}）",
                request,
            )

            return success_response(
                data=_serialize_channel_ext(c),
                msg=f"渠道已{status_text}",
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 佣金比例配置
# ════════════════════════════════════════════════════════════


@router.get("/{channel_code}/commission-configs")
async def get_channel_commission_configs(
    request: Request,
    channel_code: str,
    admin_info: dict = Depends(get_admin_info),
):
    """查询渠道佣金比例配置列表"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            commission_dao = ChannelCommissionConfigDAO(session)
            configs = await commission_dao.list_by_channel(channel_code)
            data = {
                "channel_code": channel_code,
                "items": [_serialize_commission_config(c) for c in configs],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{channel_code}/commission-configs")
async def batch_update_commission_configs(
    request: Request,
    channel_code: str,
    body: CommissionConfigBatchRequest,
    admin_info: dict = Depends(get_admin_info),
):
    """批量配置渠道佣金比例（普通用户 + 付费会员）

    参数校验规则：
    1. 用户返利比例 + 平台留存比例 = 100%（精确到万分位）
    2. 用户类型不能重复
    3. 用户类型仅支持 1-普通用户 2-付费会员
    4. 渠道标识必须存在且已启用
    """
    request_id = get_request_id(request)
    try:
        if body.channel_code != channel_code:
            raise ValueError("路径参数与请求体中的渠道标识不一致")

        async with DatabaseManager.get_session() as session:
            # 校验渠道存在且已启用
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            channel_stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            channel_result = await session.execute(channel_stmt)
            channel = channel_result.scalar_one_or_none()
            if channel is None:
                raise ValueError(f"渠道配置不存在: {channel_code}")
            if not channel.status:
                raise ValueError(f"渠道已禁用，无法配置佣金比例: {channel_code}")

            # 批量更新佣金配置
            commission_dao = ChannelCommissionConfigDAO(session)
            config_details = []
            for config in body.configs:
                updated = await commission_dao.upsert_commission_config(
                    channel_code=channel_code,
                    user_type=config.user_type,
                    user_commission_rate=config.user_commission_rate,
                    platform_retention_rate=config.platform_retention_rate,
                    remark=config.remark,
                )
                config_details.append(_serialize_commission_config(updated))

            # 写入审计日志
            details_parts = []
            for c in body.configs:
                user_type_label = USER_TYPE_LABELS.get(c.user_type, f"用户类型{c.user_type}")
                details_parts.append(
                    f"{user_type_label}: 用户返利={c.user_commission_rate}, 平台留存={c.platform_retention_rate}"
                )
            await _write_audit_log(
                session, admin_info,
                B06AuditAction.CHANNEL_COMMISSION_CONFIG,
                B06AuditTargetType.CHANNEL,
                channel.id,
                f"配置 {channel_code} 佣金比例: {'; '.join(details_parts)}",
                request,
            )

            return success_response(
                data={"channel_code": channel_code, "items": config_details},
                msg="佣金比例配置成功",
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 渠道数据看板
# ════════════════════════════════════════════════════════════


@router.get("/dashboard/summary")
async def get_channel_dashboard_summary(
    request: Request,
    start_date: Optional[str] = Query(None, description="起始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="截止日期(YYYY-MM-DD)"),
    admin_info: dict = Depends(get_admin_info),
):
    """渠道数据看板汇总

    按渠道维度聚合：订单数、总佣金、用户佣金、平台佣金
    """
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        async with DatabaseManager.get_session() as session:
            dashboard_dao = ChannelDashboardQueryDAO(session)
            data = await dashboard_dao.get_channel_summary(
                start_date=start_dt, end_date=end_dt
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/dashboard/detail/{channel_code}")
async def get_channel_dashboard_detail(
    request: Request,
    channel_code: str,
    start_date: Optional[str] = Query(None, description="起始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="截止日期(YYYY-MM-DD)"),
    admin_info: dict = Depends(get_admin_info),
):
    """单个渠道数据看板详情"""
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        async with DatabaseManager.get_session() as session:
            # 校验渠道存在
            dao = BaseDAO(session)
            dao.model_class = ChannelMapping
            channel_stmt = dao._active_query().where(ChannelMapping.channel_code == channel_code)
            channel_result = await session.execute(channel_stmt)
            if not channel_result.scalar_one_or_none():
                raise ValueError(f"渠道配置不存在: {channel_code}")

            dashboard_dao = ChannelDashboardQueryDAO(session)
            data = await dashboard_dao.get_channel_detail(
                channel_code=channel_code,
                start_date=start_dt,
                end_date=end_dt,
            )
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/dashboard/trend")
async def get_channel_dashboard_trend(
    request: Request,
    start_date: str = Query(..., description="起始日期(YYYY-MM-DD)"),
    end_date: str = Query(..., description="截止日期(YYYY-MM-DD)"),
    channel_code: Optional[str] = Query(None, description="渠道标识，为空时查询全渠道汇总"),
    group_by: str = Query("day", description="分组维度：day/week/month"),
    admin_info: dict = Depends(get_admin_info),
):
    """渠道数据趋势折线

    按天/周/月分组订单数与佣金总额
    """
    request_id = get_request_id(request)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if group_by not in ("day", "week", "month"):
            raise ValueError("分组维度仅支持 day/week/month")

        async with DatabaseManager.get_session() as session:
            dashboard_dao = ChannelDashboardQueryDAO(session)

            if channel_code:
                data = await dashboard_dao.get_channel_trend(
                    channel_code=channel_code,
                    start_date=start_dt,
                    end_date=end_dt,
                    group_by=group_by,
                )
            else:
                data = await dashboard_dao.get_all_channels_summary_trend(
                    start_date=start_dt,
                    end_date=end_dt,
                    group_by=group_by,
                )

            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
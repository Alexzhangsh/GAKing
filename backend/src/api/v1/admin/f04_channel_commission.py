# @ai-generated
"""
F04-2 渠道佣金策略管理 API
路由前缀：/api/v1/admin/channel-commission
权限码：config:manage（全部接口）
审计：写操作（新增/更新/启停）自动记录审计日志

接口清单：
1. GET    /api/v1/admin/channel-commission/strategies            策略列表（分页+渠道/状态筛选）
2. GET    /api/v1/admin/channel-commission/strategies/{channel_code}  策略详情（含阶梯明细）
3. POST   /api/v1/admin/channel-commission/strategies            新增策略
4. PUT    /api/v1/admin/channel-commission/strategies/{channel_code}  更新策略
5. PUT    /api/v1/admin/channel-commission/strategies/{channel_code}/toggle  启停策略
6. POST   /api/v1/admin/channel-commission/preview               实时预览分佣结果
7. GET    /api/v1/admin/channel-commission/audit-logs            策略变更审计记录
"""
import json
import logging
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
from src.common.b14_audit_util import AuditLogger
from src.config.b14_constants import PERM_CONFIG_MANAGE
from src.config.b06_constants import UserType, USER_TYPE_LABELS
from src.dao.audit_log_dao import AuditLogDAO
from src.dao.f04_channel_commission_dao import (
    ChannelCommissionStrategyDAO,
    ChannelCommissionTierDAO,
)
from src.db.base import DatabaseManager
from src.models.system.f04_channel_commission import (
    ChannelCommissionStrategy,
    ChannelCommissionTier,
)

logger = logging.getLogger("api.admin.f04_channel_commission")

router = APIRouter(prefix="/api/v1/admin/channel-commission", tags=["后台-渠道佣金策略(F04-2)"])

# 审计动作码
ACTION_STRATEGY_CREATE = "COMMISSION_STRATEGY_CREATE"
ACTION_STRATEGY_UPDATE = "COMMISSION_STRATEGY_UPDATE"
ACTION_STRATEGY_TOGGLE = "COMMISSION_STRATEGY_TOGGLE"
TARGET_TYPE_STRATEGY = "channel_commission_strategy"

# 支持的渠道标识
SUPPORTED_CHANNELS = {"myq", "orderx", "dta"}

# 阶梯维度
TIER_DIMENSION_AMOUNT = 1  # 按订单金额
TIER_DIMENSION_COUNT = 2  # 按订单数量


# ── 依赖注入 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_CONFIG_MANAGE])),
) -> int:
    return int(payload["user_id"])


# ── Schema ──────────────


class TierItem(BaseModel):
    """单条阶梯佣金配置"""
    user_type: int = Field(..., description="用户类型：1-普通用户 2-付费会员")
    tier_name: str = Field("", max_length=64, description="阶梯名称")
    tier_min: float = Field(0.0, ge=0, description="阶梯下限（含）")
    tier_max: float = Field(0.0, ge=0, description="阶梯上限（不含），0表示无上限")
    user_commission_rate: float = Field(..., ge=0, le=1, description="用户返利比例(0~1)")
    platform_retention_rate: float = Field(..., ge=0, le=1, description="平台留存比例(0~1)")
    sort_order: int = Field(0, ge=0, description="排序号")

    @model_validator(mode="after")
    def validate_rates(self):
        """校验比例 0~1 区间 + 双比例之和 = 100%"""
        if self.user_commission_rate < 0 or self.user_commission_rate > 1:
            raise ValueError("用户返利比例必须在 0~1 区间")
        if self.platform_retention_rate < 0 or self.platform_retention_rate > 1:
            raise ValueError("平台留存比例必须在 0~1 区间")
        total = round(self.user_commission_rate + self.platform_retention_rate, 4)
        if abs(total - 1.0) > 0.0001:
            raise ValueError(
                f"用户返利比例({self.user_commission_rate}) + 平台留存比例({self.platform_retention_rate}) "
                f"必须等于 1 (100%)，当前合计 {total}"
            )
        if self.tier_max != 0 and self.tier_min >= self.tier_max:
            raise ValueError(
                f"阶梯区间非法：下限({self.tier_min})必须小于上限({self.tier_max})"
            )
        return self


class StrategyCreateRequest(BaseModel):
    """新增佣金策略请求"""
    channel_code: str = Field(..., max_length=32, description="渠道标识：myq / orderx / dta")
    strategy_name: str = Field("", max_length=128, description="策略名称")
    enabled: bool = Field(False, description="策略生效开关")
    tier_dimension: int = Field(TIER_DIMENSION_AMOUNT, ge=1, le=2, description="阶梯维度：1-按订单金额 2-按订单数量")
    remark: str = Field("", max_length=512, description="备注")
    tiers: List[TierItem] = Field(..., min_length=1, description="阶梯明细列表")

    @model_validator(mode="after")
    def validate_tiers(self):
        """校验阶梯明细：用户类型合法、同用户类型阶梯区间不重叠"""
        user_types = [t.user_type for t in self.tiers]
        for ut in user_types:
            if ut not in (UserType.NORMAL, UserType.VIP):
                raise ValueError(f"不支持的用戶类型: {ut}，仅支持 1-普通用户 2-付费会员")

        # 按用户类型分组，校验同类型下阶梯区间不重叠
        by_type: Dict[int, List[TierItem]] = {}
        for t in self.tiers:
            by_type.setdefault(t.user_type, []).append(t)
        for ut, tier_list in by_type.items():
            sorted_tiers = sorted(tier_list, key=lambda x: x.tier_min)
            for i in range(len(sorted_tiers) - 1):
                cur = sorted_tiers[i]
                nxt = sorted_tiers[i + 1]
                if cur.tier_max == 0:
                    raise ValueError(
                        f"用户类型 {ut} 阶梯区间重叠：阶梯「{cur.tier_name or cur.tier_min}」无上限，"
                        f"不能存在后续阶梯"
                    )
                if nxt.tier_min < cur.tier_max:
                    raise ValueError(
                        f"用户类型 {ut} 阶梯区间重叠：阶梯「{nxt.tier_name or nxt.tier_min}」下限 "
                        f"{nxt.tier_min} 必须 >= 上一阶梯上限 {cur.tier_max}"
                    )
        return self


class StrategyUpdateRequest(BaseModel):
    """更新佣金策略请求"""
    strategy_name: Optional[str] = Field(None, max_length=128, description="策略名称")
    enabled: Optional[bool] = Field(None, description="策略生效开关")
    tier_dimension: Optional[int] = Field(None, ge=1, le=2, description="阶梯维度")
    remark: Optional[str] = Field(None, max_length=512, description="备注")
    tiers: Optional[List[TierItem]] = Field(None, min_length=1, description="阶梯明细列表")


class StrategyToggleRequest(BaseModel):
    """启停策略请求"""
    enabled: bool = Field(..., description="目标状态：True-生效 False-停用")


class CommissionPreviewRequest(BaseModel):
    """分佣结果预览请求"""
    channel_code: str = Field(..., max_length=32, description="渠道标识")
    user_type: int = Field(UserType.NORMAL, description="用户类型：1-普通用户 2-付费会员")
    amount: float = Field(0.0, ge=0, description="订单金额（阶梯维度为金额时使用）")
    order_count: int = Field(0, ge=0, description="订单数量（阶梯维度为数量时使用）")


# ── 序列化 ──────────────


def _serialize_strategy(s: ChannelCommissionStrategy) -> Dict[str, Any]:
    return {
        "id": s.id,
        "channel_code": s.channel_code,
        "strategy_name": s.strategy_name or "",
        "enabled": bool(s.enabled),
        "tier_dimension": s.tier_dimension,
        "tier_dimension_label": "按订单金额" if s.tier_dimension == TIER_DIMENSION_AMOUNT else "按订单数量",
        "remark": s.remark or "",
        "create_time": s.create_time.strftime("%Y-%m-%d %H:%M:%S") if s.create_time else None,
        "update_time": s.update_time.strftime("%Y-%m-%d %H:%M:%S") if s.update_time else None,
    }


def _serialize_tier(t: ChannelCommissionTier) -> Dict[str, Any]:
    return {
        "id": t.id,
        "strategy_id": t.strategy_id,
        "user_type": t.user_type,
        "user_type_label": USER_TYPE_LABELS.get(t.user_type, "未知"),
        "tier_name": t.tier_name or "",
        "tier_min": float(t.tier_min) if t.tier_min is not None else 0.0,
        "tier_max": float(t.tier_max) if t.tier_max is not None else 0.0,
        "user_commission_rate": float(t.user_commission_rate) if t.user_commission_rate is not None else 0.0,
        "platform_retention_rate": float(t.platform_retention_rate) if t.platform_retention_rate is not None else 0.0,
        "sort_order": t.sort_order or 0,
    }


def _serialize_tier_dict(t: Dict[str, Any]) -> Dict[str, Any]:
    """序列化阶梯字典（新增/更新后响应用，此时尚未从 DB 回读）"""
    return {
        "id": t.get("id", 0),
        "strategy_id": t.get("strategy_id", 0),
        "user_type": t["user_type"],
        "user_type_label": USER_TYPE_LABELS.get(t["user_type"], "未知"),
        "tier_name": t.get("tier_name", "") or "",
        "tier_min": float(t.get("tier_min", 0) or 0),
        "tier_max": float(t.get("tier_max", 0) or 0),
        "user_commission_rate": float(t.get("user_commission_rate", 0) or 0),
        "platform_retention_rate": float(t.get("platform_retention_rate", 0) or 0),
        "sort_order": t.get("sort_order", 0) or 0,
    }


def _tier_to_dict(t, strategy_id: int) -> Dict[str, Any]:
    """将 TierItem（pydantic）或 dict 统一转为入库字典"""
    if isinstance(t, dict):
        return {
            "strategy_id": strategy_id,
            "user_type": t["user_type"],
            "tier_name": t.get("tier_name", ""),
            "tier_min": t.get("tier_min", 0),
            "tier_max": t.get("tier_max", 0),
            "user_commission_rate": t.get("user_commission_rate", 0),
            "platform_retention_rate": t.get("platform_retention_rate", 0),
            "sort_order": t.get("sort_order", 0),
        }
    return {
        "strategy_id": strategy_id,
        "user_type": t.user_type,
        "tier_name": t.tier_name,
        "tier_min": t.tier_min,
        "tier_max": t.tier_max,
        "user_commission_rate": t.user_commission_rate,
        "platform_retention_rate": t.platform_retention_rate,
        "sort_order": t.sort_order,
    }


def _channel_name(channel_code: str) -> str:
    names = {"myq": "喵有券", "orderx": "订单侠", "dta": "大淘客"}
    return names.get(channel_code, channel_code)


# ════════════════════════════════════════════════════════════
# 1. 策略列表
# ════════════════════════════════════════════════════════════


@router.get("/strategies")
async def list_strategies(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道筛选"),
    enabled: Optional[bool] = Query(None, description="生效状态筛选"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """佣金策略列表（分页 + 渠道/状态筛选）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = ChannelCommissionStrategyDAO(session)
            items, total = await dao.paginate_strategies(
                page=page, page_size=page_size,
                channel_code=channel_code, enabled=enabled,
            )
            data = {
                "total": total, "page": page, "page_size": page_size,
                "items": [_serialize_strategy(s) for s in items],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 2. 策略详情（含阶梯明细）
# ════════════════════════════════════════════════════════════


@router.get("/strategies/{channel_code}")
async def get_strategy(
    request: Request,
    channel_code: str,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """佣金策略详情（含阶梯明细）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            strategy_dao = ChannelCommissionStrategyDAO(session)
            strategy = await strategy_dao.get_by_channel_code(channel_code)
            if strategy is None:
                raise ValueError(f"渠道佣金策略不存在: {channel_code}")
            tier_dao = ChannelCommissionTierDAO(session)
            tiers = await tier_dao.list_by_strategy(strategy.id)
            data = _serialize_strategy(strategy)
            data["tiers"] = [_serialize_tier(t) for t in tiers]
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 3. 新增策略
# ════════════════════════════════════════════════════════════


@router.post("/strategies")
async def create_strategy(
    request: Request,
    body: StrategyCreateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """新增佣金策略"""
    request_id = get_request_id(request)
    try:
        if body.channel_code not in SUPPORTED_CHANNELS:
            raise ValueError(
                f"不支持的渠道标识: {body.channel_code}，仅支持 {sorted(SUPPORTED_CHANNELS)}"
            )
        async with DatabaseManager.get_session() as session:
            strategy_dao = ChannelCommissionStrategyDAO(session)
            existing = await strategy_dao.get_by_channel_code(body.channel_code)
            if existing is not None:
                raise ValueError(f"渠道 {body.channel_code} 已存在佣金策略，请直接编辑")

            strategy = await strategy_dao.create({
                "channel_code": body.channel_code,
                "strategy_name": body.strategy_name,
                "enabled": body.enabled,
                "tier_dimension": body.tier_dimension,
                "remark": body.remark,
            })

            tier_dao = ChannelCommissionTierDAO(session)
            tier_data = [_tier_to_dict(t, strategy.id) for t in body.tiers]
            await tier_dao.batch_create(tier_data)

            # 审计日志
            await AuditLogger.log(
                action=ACTION_STRATEGY_CREATE,
                target_type=TARGET_TYPE_STRATEGY,
                target_id=strategy.id,
                details={
                    "channel_code": body.channel_code,
                    "strategy_name": body.strategy_name,
                    "enabled": body.enabled,
                    "tier_dimension": body.tier_dimension,
                    "tier_count": len(body.tiers),
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            data = _serialize_strategy(strategy)
            data["tiers"] = [_serialize_tier_dict(t) for t in tier_data]
            return success_response(data=data, msg="佣金策略创建成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 4. 更新策略
# ════════════════════════════════════════════════════════════


@router.put("/strategies/{channel_code}")
async def update_strategy(
    request: Request,
    channel_code: str,
    body: StrategyUpdateRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """更新佣金策略（含阶梯明细整体替换）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            strategy_dao = ChannelCommissionStrategyDAO(session)
            strategy = await strategy_dao.get_by_channel_code(channel_code)
            if strategy is None:
                raise ValueError(f"渠道佣金策略不存在: {channel_code}")

            data = body.model_dump(exclude_unset=True)
            tiers_payload = data.pop("tiers", None)

            for key, value in data.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)
            await session.flush()

            if tiers_payload is not None:
                tier_dao = ChannelCommissionTierDAO(session)
                await tier_dao.delete_by_strategy(strategy.id)
                tier_data = [_tier_to_dict(t, strategy.id) for t in tiers_payload]
                await tier_dao.batch_create(tier_data)

            await session.commit()

            # 审计日志
            await AuditLogger.log(
                action=ACTION_STRATEGY_UPDATE,
                target_type=TARGET_TYPE_STRATEGY,
                target_id=strategy.id,
                details={
                    "channel_code": channel_code,
                    "strategy_name": strategy.strategy_name,
                    "enabled": bool(strategy.enabled),
                    "tier_dimension": strategy.tier_dimension,
                    "tier_count": len(tiers_payload) if tiers_payload is not None else None,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            tier_dao = ChannelCommissionTierDAO(session)
            tiers = await tier_dao.list_by_strategy(strategy.id)
            data = _serialize_strategy(strategy)
            data["tiers"] = [_serialize_tier(t) for t in tiers]
            return success_response(data=data, msg="佣金策略更新成功", request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 5. 启停策略
# ════════════════════════════════════════════════════════════


@router.put("/strategies/{channel_code}/toggle")
async def toggle_strategy(
    request: Request,
    channel_code: str,
    body: StrategyToggleRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """启停佣金策略"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            strategy_dao = ChannelCommissionStrategyDAO(session)
            strategy = await strategy_dao.get_by_channel_code(channel_code)
            if strategy is None:
                raise ValueError(f"渠道佣金策略不存在: {channel_code}")
            old_enabled = bool(strategy.enabled)
            strategy.enabled = body.enabled
            await session.flush()
            await session.commit()

            # 审计日志
            await AuditLogger.log(
                action=ACTION_STRATEGY_TOGGLE,
                target_type=TARGET_TYPE_STRATEGY,
                target_id=strategy.id,
                details={
                    "channel_code": channel_code,
                    "old_enabled": old_enabled,
                    "new_enabled": body.enabled,
                    "path": request.url.path,
                },
                user_id=admin_user_id,
                ip_address=AuditLogger.get_client_ip(request),
                user_agent=AuditLogger.get_user_agent(request),
            )

            return success_response(
                data={"channel_code": channel_code, "enabled": body.enabled},
                msg="策略已启用" if body.enabled else "策略已停用",
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 6. 实时预览分佣结果
# ════════════════════════════════════════════════════════════


def _match_tier(tiers: List[Dict[str, Any]], dimension: int, amount: float, order_count: int) -> Optional[Dict[str, Any]]:
    """按阶梯维度匹配命中的阶梯规则

    命中规则：
    - tier_max == 0 表示无上限，命中 tier_min <= value
    - 否则命中 tier_min <= value < tier_max
    """
    value = amount if dimension == TIER_DIMENSION_AMOUNT else float(order_count)
    for tier in tiers:
        t_min = tier["tier_min"]
        t_max = tier["tier_max"]
        if t_max == 0:
            if value >= t_min:
                return tier
        else:
            if t_min <= value < t_max:
                return tier
    return None


@router.post("/preview")
async def preview_commission(
    request: Request,
    body: CommissionPreviewRequest,
    admin_user_id: int = Depends(get_admin_user_id),
):
    """实时预览分佣结果

    输入渠道 + 用户类型 + 订单金额/数量，返回命中的阶梯规则与分佣拆分结果。
    """
    request_id = get_request_id(request)
    try:
        if body.user_type not in (UserType.NORMAL, UserType.VIP):
            raise ValueError(f"不支持的用戶类型: {body.user_type}")
        async with DatabaseManager.get_session() as session:
            strategy_dao = ChannelCommissionStrategyDAO(session)
            strategy = await strategy_dao.get_by_channel_code(body.channel_code)
            if strategy is None:
                raise ValueError(f"渠道佣金策略不存在: {body.channel_code}")
            if not strategy.enabled:
                return success_response(
                    data={
                        "channel_code": body.channel_code,
                        "enabled": False,
                        "matched_tier": None,
                        "result": None,
                        "message": "策略未生效，当前按默认比例结算",
                    },
                    request_id=request_id,
                )

            tier_dao = ChannelCommissionTierDAO(session)
            tiers = await tier_dao.list_by_strategy(strategy.id)
            tier_list = [_serialize_tier(t) for t in tiers]
            user_tiers = [t for t in tier_list if t["user_type"] == body.user_type]

            matched = _match_tier(
                user_tiers,
                strategy.tier_dimension,
                body.amount,
                body.order_count,
            )

            if matched is None:
                return success_response(
                    data={
                        "channel_code": body.channel_code,
                        "enabled": True,
                        "matched_tier": None,
                        "result": None,
                        "message": "未命中任何阶梯规则，请检查阶梯区间配置",
                    },
                    request_id=request_id,
                )

            # 计算分佣拆分
            total = Decimal(str(body.amount))
            user_rate = Decimal(str(matched["user_commission_rate"]))
            platform_rate = Decimal(str(matched["platform_retention_rate"]))
            user_commission = (total * user_rate).quantize(Decimal("0.01"))
            platform_commission = (total - user_commission).quantize(Decimal("0.01"))

            return success_response(
                data={
                    "channel_code": body.channel_code,
                    "enabled": True,
                    "tier_dimension": strategy.tier_dimension,
                    "matched_tier": matched,
                    "result": {
                        "total_commission": float(total),
                        "user_commission": float(user_commission),
                        "platform_commission": float(platform_commission),
                        "user_rate": float(user_rate),
                        "platform_rate": float(platform_rate),
                    },
                    "message": "分佣预览成功",
                },
                request_id=request_id,
            )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ════════════════════════════════════════════════════════════
# 7. 策略变更审计记录
# ════════════════════════════════════════════════════════════


@router.get("/audit-logs")
async def list_strategy_audit_logs(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    channel_code: Optional[str] = Query(None, max_length=32, description="渠道筛选"),
    admin_user_id: int = Depends(get_admin_user_id),
):
    """策略变更审计记录（复用 audit_logs 表，按动作类型筛选）"""
    request_id = get_request_id(request)
    try:
        async with DatabaseManager.get_session() as session:
            dao = AuditLogDAO(session)
            actions = [ACTION_STRATEGY_CREATE, ACTION_STRATEGY_UPDATE, ACTION_STRATEGY_TOGGLE]
            items, total = await dao.paginate_by_actions(
                actions=actions,
                target_type=TARGET_TYPE_STRATEGY,
                page=page,
                page_size=page_size,
            )
            # 渠道筛选（内存过滤，数据量小）
            if channel_code and items:
                filtered = []
                for log in items:
                    details = log.details or ""
                    try:
                        details_dict = json.loads(details) if isinstance(details, str) else (details or {})
                    except Exception:
                        details_dict = {}
                    if details_dict.get("channel_code") == channel_code:
                        filtered.append(log)
                total = len(filtered)
                start = (page - 1) * page_size
                items = filtered[start:start + page_size]

            data = {
                "total": total, "page": page, "page_size": page_size,
                "items": [_serialize_audit_log(l) for l in items],
            }
            return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


def _serialize_audit_log(log) -> Dict[str, Any]:
    """序列化审计日志"""
    create_time = log.create_time
    if create_time is not None:
        create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")
    details = log.details
    if details and isinstance(details, str):
        try:
            details = json.loads(details)
        except Exception:
            pass
    return {
        "id": log.id,
        "user_id": log.user_id,
        "user_name": log.user_name,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": details,
        "ip_address": log.ip_address,
        "create_time": create_time,
    }

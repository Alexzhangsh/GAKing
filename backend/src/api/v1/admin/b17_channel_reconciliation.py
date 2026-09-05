# @ai-generated
"""
B17 多渠道对账差异处理与多渠道聚合统计 API（独立新建，不修改 B01-B16 基线）
路由前缀：/api/v1/admin/channel-reconciliation
职责：管理员身份识别 → 参数校验 → 调用 B17ChannelReconciliationService → 统一响应封装

接口清单：
1. POST /run                   手动触发渠道对账（指定日期/默认昨天）
2. GET  /summary               渠道对账汇总（按渠道统计差异数量/金额）
3. GET  /aggregate-stats       多渠道聚合统计（佣金/订单/成交分渠道汇总）
4. GET  /order-trend           渠道订单趋势（按天/周/月，支持单渠道筛选）
5. GET  /diffs                 渠道对账差异查询（按渠道筛选）
6. POST /diffs/{diff_id}/review 渠道差异人工复核标记
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.config.b13_b14_constants import PERM_DASHBOARD_VIEW
from src.config.b15_constants import PERM_CHANNEL_TEST
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
from src.dao.reconciliation_record_dao import ReconciliationRecordDAO
from src.db.init_db import DatabaseManager
from src.schemas.reconciliation_b13 import DiffReviewRequest
from src.services.b17_channel_reconciliation_service import (
    B17ChannelReconciliationService,
)

logger = logging.getLogger("api.admin.b17_channel_reconciliation")

router = APIRouter(
    prefix="/api/v1/admin/channel-reconciliation",
    tags=["后台-多渠道对账(B17)"],
)


# ── 依赖注入 ─────────────────────────────────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission([PERM_CHANNEL_TEST])),
) -> int:
    """获取后台管理员ID（JWT + RBAC channel:test 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_channel_reconciliation_service(
    db: AsyncSession = Depends(get_db),
) -> B17ChannelReconciliationService:
    """构造 B17ChannelReconciliationService 实例"""
    return B17ChannelReconciliationService(
        record_dao=ReconciliationRecordDAO(db),
        diff_dao=ReconciliationDiffDAO(db),
        session=db,
        circuit_breaker=CircuitBreaker(),
    )


# ══════════════════════════════════════════════════════
# 1. 手动触发渠道对账
# ══════════════════════════════════════════════════════


@router.post("/run")
async def run_channel_reconciliation(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: B17ChannelReconciliationService = Depends(
        get_channel_reconciliation_service
    ),
    reconcile_date: Optional[date] = Query(default=None, description="对账日期（留空默认昨天）"),
):
    """1. 手动触发渠道对账（指定日期/默认昨天）

    - 幂等：同日重复对账会被幂等锁拦截
    - 熔断：B04 熔断保护
    - 告警：CRITICAL 渠道差异自动推送日志告警
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发渠道对账 admin=%s date=%s",
        request_id, admin_user_id, reconcile_date,
    )
    try:
        result = await svc.run_channel_reconciliation(
            reconcile_date=reconcile_date,
            reconcile_type="MANUAL",
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 渠道对账汇总
# ══════════════════════════════════════════════════════


@router.get("/summary")
async def get_channel_summary(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[date] = Query(default=None, description="对账日期起始（含）"),
    end_date: Optional[date] = Query(default=None, description="对账日期截止（含）"),
):
    """2. 渠道对账汇总（按渠道统计差异数量/金额）

    汇总 reconciliation_diff 表中 CHANNEL_* 类型差异，按渠道分组。
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询渠道对账汇总 admin=%s",
        request_id, admin_user_id,
    )
    try:
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
        diff_dao = ReconciliationDiffDAO(db)
        data = await diff_dao.summary_channel_diffs(
            start_date=start_date, end_date=end_date,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 多渠道聚合统计
# ══════════════════════════════════════════════════════


@router.get("/aggregate-stats")
async def get_aggregate_stats(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
):
    """3. 多渠道聚合统计（佣金/订单/成交分渠道汇总）

    按渠道分组汇总：订单数、总佣金、用户佣金、平台佣金、支付金额、成交单数、成交金额
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询多渠道聚合统计 admin=%s",
        request_id, admin_user_id,
    )
    try:
        svc = B17ChannelReconciliationService(
            record_dao=ReconciliationRecordDAO(db),
            diff_dao=ReconciliationDiffDAO(db),
            session=db,
        )
        data = await svc.get_channel_aggregate_stats(
            start_time=start_date, end_time=end_date,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 渠道订单趋势
# ══════════════════════════════════════════════════════


@router.get("/order-trend")
async def get_channel_order_trend(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    start_date: datetime = Query(..., description="起始日期（含，YYYY-MM-DD）"),
    end_date: datetime = Query(..., description="截止日期（不含，YYYY-MM-DD）"),
    channel_code: Optional[str] = Query(default=None, max_length=32, description="渠道标识，为空时全部渠道"),
    group_by: str = Query(default="day", description="分组维度：day/week/month"),
):
    """4. 渠道订单趋势（按天/周/月分组，支持单渠道筛选）

    返回各渠道的订单数、总佣金、成交单数、成交金额趋势。
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询渠道订单趋势 admin=%s channel=%s",
        request_id, admin_user_id, channel_code,
    )
    try:
        svc = B17ChannelReconciliationService(
            record_dao=ReconciliationRecordDAO(db),
            diff_dao=ReconciliationDiffDAO(db),
            session=db,
        )
        items = await svc.get_channel_order_trend(
            start_time=start_date, end_time=end_date,
            channel_code=channel_code, group_by=group_by,
        )
        return success_response(
            data={
                "group_by": group_by,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "channel_code": channel_code,
                "total": len(items),
                "items": items,
            },
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 5. 渠道对账差异查询
# ══════════════════════════════════════════════════════


@router.get("/diffs")
async def list_channel_diffs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    channel_code: Optional[str] = Query(default=None, max_length=32, description="渠道标识筛选"),
    diff_type: Optional[str] = Query(default=None, description="差异类型筛选"),
    status: Optional[str] = Query(default=None, description="PENDING/REVIEWING/RESOLVED/IGNORED"),
    alert_level: Optional[str] = Query(default=None, description="INFO/WARNING/CRITICAL"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """5. 渠道对账差异查询（按渠道筛选）

    查询 reconciliation_diff 表中 CHANNEL_* 类型差异，支持按渠道/类型/状态/级别筛选。
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询渠道对账差异 admin=%s channel=%s",
        request_id, admin_user_id, channel_code,
    )
    try:
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
        diff_dao = ReconciliationDiffDAO(db)
        data = await diff_dao.list_channel_diffs(
            channel_code=channel_code,
            diff_type=diff_type,
            status=status,
            alert_level=alert_level,
            page=page,
            page_size=page_size,
        )
        return success_response(data=data, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 6. 渠道差异人工复核标记
# ══════════════════════════════════════════════════════


@router.post("/diffs/{diff_id}/review")
async def review_channel_diff(
    diff_id: int,
    body: DiffReviewRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
):
    """6. 渠道差异人工复核标记

    仅支持 CHANNEL_* 类型渠道差异，复用 B13 状态机：
    - PENDING → REVIEWING（认领复核）
    - PENDING/REVIEWING → RESOLVED（已调平）
    - PENDING/REVIEWING → IGNORED（已忽略，如精度误差）
    - 终态不可再操作
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 渠道差异复核 admin=%s diff_id=%s action=%s",
        request_id, admin_user_id, diff_id, body.action,
    )
    try:
        svc = B17ChannelReconciliationService(
            record_dao=ReconciliationRecordDAO(db),
            diff_dao=ReconciliationDiffDAO(db),
            session=db,
        )
        result = await svc.review_channel_diff(
            diff_id=diff_id,
            action=body.action,
            review_remark=body.review_remark,
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
# @ai-generated
"""
后台全链路数据对账管理接口层（B13 新建，不修改 B01-B12 基线）
路由前缀：/api/v1/admin/reconciliation
职责：管理员身份识别 → 参数校验 → 调用 ReconciliationB13Service → 统一响应封装

接口清单：
1. GET  /records                          对账批次分页查询（多条件筛选）
2. GET  /records/export                   对账批次导出筛选（page_size 上限 500）
3. GET  /records/{reconciliation_id}      对账批次详情（含差异统计 + 最近差异）
4. POST /records/run                      手动触发对账（指定日期/默认昨天）
5. POST /records/{reconciliation_id}/retry 重跑对账批次
6. GET  /diffs                            差异明细分页查询（多条件筛选）
7. GET  /diffs/export                     差异明细导出筛选（page_size 上限 500）
8. GET  /diffs/{diff_id}                  差异明细详情
9. POST /diffs/{diff_id}/review           差异人工复核调平
10. GET /alerts                           告警列表查询（CRITICAL/WARNING）
11. GET /dashboard                        告警面板（近7天有差异的对账批次）
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    error_response,
    get_request_id,
    handle_service_exception,
    success_response,
)
from src.common.auth_util import require_any_permission
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO
from src.dao.reconciliation_query_dao import ReconciliationQueryDAO
from src.dao.reconciliation_record_dao import ReconciliationRecordDAO
from src.db.init_db import DatabaseManager
from src.schemas.reconciliation_b13 import (
    AlertQuery,
    DiffReviewRequest,
    ManualReconciliationRequest,
    ReconciliationDiffQuery,
    ReconciliationRecordQuery,
    RetryReconciliationRequest,
)
from src.services.reconciliation_b13_service import ReconciliationB13Service

logger = logging.getLogger("api.admin.reconciliation_b13")

router = APIRouter(
    prefix="/api/v1/admin/reconciliation",
    tags=["后台-全链路数据对账"],
)


# ── 依赖注入 ─────────────────────────────────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["reconciliation:review"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC reconciliation:review 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_reconciliation_service(
    db: AsyncSession = Depends(get_db),
) -> ReconciliationB13Service:
    """构造 ReconciliationB13Service 实例"""
    return ReconciliationB13Service(
        record_dao=ReconciliationRecordDAO(db),
        diff_dao=ReconciliationDiffDAO(db),
        query_dao=ReconciliationQueryDAO(db),
        circuit_breaker=CircuitBreaker(),
    )


# ── 工具函数 ─────────────────────────────────────────


def _parse_datetime(value: Optional[str], request_id: str) -> Optional[datetime]:
    """ISO8601 字符串转 datetime"""
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("[request_id=%s] 时间参数非法，已忽略: %s", request_id, value)
        return None


# ══════════════════════════════════════════════════════
# 1. 对账批次分页查询
# ══════════════════════════════════════════════════════


@router.get("/records")
async def list_records(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    reconciliation_no: str = Query(default=None, description="批次号筛选"),
    reconcile_type: str = Query(default=None, description="DAILY/MANUAL"),
    status: str = Query(
        default=None, description="PENDING/RUNNING/SUCCESS/PARTIAL/FAILED"
    ),
    start_date: Optional[date] = Query(default=None, description="对账日期起始（含）"),
    end_date: Optional[date] = Query(default=None, description="对账日期截止（含）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """1. 对账批次分页查询（多条件筛选）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询对账批次 admin=%s status=%s page=%s",
        request_id,
        admin_user_id,
        status,
        page,
    )
    try:
        query = ReconciliationRecordQuery(
            reconciliation_no=reconciliation_no,
            reconcile_type=reconcile_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_records_with_filters(
            reconciliation_no=query.reconciliation_no,
            reconcile_type=query.reconcile_type,
            status=query.status,
            start_date=query.start_date,
            end_date=query.end_date,
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 对账批次导出筛选
# ══════════════════════════════════════════════════════


@router.get("/records/export")
async def export_records(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    reconciliation_no: str = Query(default=None, description="批次号筛选"),
    reconcile_type: str = Query(default=None, description="DAILY/MANUAL"),
    status: str = Query(
        default=None, description="PENDING/RUNNING/SUCCESS/PARTIAL/FAILED"
    ),
    start_date: Optional[date] = Query(default=None, description="对账日期起始（含）"),
    end_date: Optional[date] = Query(default=None, description="对账日期截止（含）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(
        default=500, ge=1, le=500, description="每页条数（导出最大500）"
    ),
):
    """2. 对账批次导出筛选（page_size 上限 500）"""
    request_id = get_request_id(request)
    try:
        query = ReconciliationRecordQuery(
            reconciliation_no=reconciliation_no,
            reconcile_type=reconcile_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_records_with_filters(
            reconciliation_no=query.reconciliation_no,
            reconcile_type=query.reconcile_type,
            status=query.status,
            start_date=query.start_date,
            end_date=query.end_date,
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 对账批次详情
# ══════════════════════════════════════════════════════


@router.get("/records/{reconciliation_id}")
async def get_record_detail(
    reconciliation_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
):
    """3. 对账批次详情（含差异统计 + 最近 10 条差异）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询对账详情 admin=%s id=%s",
        request_id,
        admin_user_id,
        reconciliation_id,
    )
    try:
        result = await svc.get_record_detail(reconciliation_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 手动触发对账
# ══════════════════════════════════════════════════════


@router.post("/records/run")
async def run_reconciliation(
    body: ManualReconciliationRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
):
    """4. 手动触发对账（指定日期/默认昨天）

    - 幂等：同日重复对账会被幂等锁拦截
    - 熔断：B04 熔断保护
    - 告警：CRITICAL 差异自动推送日志告警
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发对账 admin=%s date=%s",
        request_id,
        admin_user_id,
        body.reconcile_date,
    )
    try:
        result = await svc.run_reconciliation(
            reconcile_date=body.reconcile_date,
            reconcile_type="MANUAL",
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 5. 重跑对账批次
# ══════════════════════════════════════════════════════


@router.post("/records/{reconciliation_id}/retry")
async def retry_reconciliation(
    reconciliation_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
):
    """5. 重跑对账批次（读取原批次日期，创建新批次重新对账）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 重跑对账 admin=%s original_id=%s",
        request_id,
        admin_user_id,
        reconciliation_id,
    )
    try:
        result = await svc.retry_reconciliation(
            reconciliation_id=reconciliation_id,
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 6. 差异明细分页查询
# ══════════════════════════════════════════════════════


@router.get("/diffs")
async def list_diffs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    reconciliation_id: int = Query(default=None, gt=0, description="批次ID筛选"),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    diff_type: str = Query(default=None, description="差异类型筛选"),
    status: str = Query(default=None, description="PENDING/REVIEWING/RESOLVED/IGNORED"),
    alert_level: str = Query(default=None, description="INFO/WARNING/CRITICAL"),
    start_time: str = Query(default=None, description="创建时间起始（ISO8601）"),
    end_time: str = Query(default=None, description="创建时间截止（ISO8601）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """6. 差异明细分页查询（多条件筛选）"""
    request_id = get_request_id(request)
    try:
        query = ReconciliationDiffQuery(
            reconciliation_id=reconciliation_id,
            user_id=user_id,
            order_id=order_id,
            diff_type=diff_type,
            status=status,
            alert_level=alert_level,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_diffs_with_filters(
            reconciliation_id=query.reconciliation_id,
            user_id=query.user_id,
            order_id=query.order_id,
            diff_type=query.diff_type,
            status=query.status,
            alert_level=query.alert_level,
            start_time=_parse_datetime(query.start_time, request_id),
            end_time=_parse_datetime(query.end_time, request_id),
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 7. 差异明细导出筛选
# ══════════════════════════════════════════════════════


@router.get("/diffs/export")
async def export_diffs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    reconciliation_id: int = Query(default=None, gt=0, description="批次ID筛选"),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    diff_type: str = Query(default=None, description="差异类型筛选"),
    status: str = Query(default=None, description="PENDING/REVIEWING/RESOLVED/IGNORED"),
    alert_level: str = Query(default=None, description="INFO/WARNING/CRITICAL"),
    start_time: str = Query(default=None, description="创建时间起始（ISO8601）"),
    end_time: str = Query(default=None, description="创建时间截止（ISO8601）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(
        default=500, ge=1, le=500, description="每页条数（导出最大500）"
    ),
):
    """7. 差异明细导出筛选（page_size 上限 500）"""
    request_id = get_request_id(request)
    try:
        query = ReconciliationDiffQuery(
            reconciliation_id=reconciliation_id,
            user_id=user_id,
            order_id=order_id,
            diff_type=diff_type,
            status=status,
            alert_level=alert_level,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_diffs_with_filters(
            reconciliation_id=query.reconciliation_id,
            user_id=query.user_id,
            order_id=query.order_id,
            diff_type=query.diff_type,
            status=query.status,
            alert_level=query.alert_level,
            start_time=_parse_datetime(query.start_time, request_id),
            end_time=_parse_datetime(query.end_time, request_id),
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 8. 差异明细详情
# ══════════════════════════════════════════════════════


@router.get("/diffs/{diff_id}")
async def get_diff_detail(
    diff_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
):
    """8. 差异明细详情"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询差异详情 admin=%s diff_id=%s",
        request_id,
        admin_user_id,
        diff_id,
    )
    try:
        result = await svc.get_diff_detail(diff_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 9. 差异人工复核调平
# ══════════════════════════════════════════════════════


@router.post("/diffs/{diff_id}/review")
async def review_diff(
    diff_id: int,
    body: DiffReviewRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
):
    """9. 差异人工复核调平

    - PENDING → REVIEWING（认领复核）
    - PENDING/REVIEWING → RESOLVED（已调平）
    - PENDING/REVIEWING → IGNORED（已忽略，如精度误差）
    - 终态不可再操作
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 差异复核 admin=%s diff_id=%s action=%s",
        request_id,
        admin_user_id,
        diff_id,
        body.action,
    )
    try:
        result = await svc.review_diff(
            diff_id=diff_id,
            action=body.action,
            review_remark=body.review_remark,
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 10. 告警列表查询
# ══════════════════════════════════════════════════════


@router.get("/alerts")
async def list_alerts(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    alert_level: str = Query(default=None, description="INFO/WARNING/CRITICAL"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=200, description="每页条数"),
):
    """10. 告警列表查询（CRITICAL/WARNING 级别差异）

    用于运营快速查看需处理的严重差异
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询告警列表 admin=%s level=%s",
        request_id,
        admin_user_id,
        alert_level,
    )
    try:
        query = AlertQuery(alert_level=alert_level, page=page, page_size=page_size)
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_alerts(
            alert_level=query.alert_level,
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 11. 告警面板（近7天有差异的对账批次）
# ══════════════════════════════════════════════════════


@router.get("/dashboard")
async def reconciliation_dashboard(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: ReconciliationB13Service = Depends(get_reconciliation_service),
    days: int = Query(default=7, ge=1, le=90, description="查询天数（默认7天）"),
):
    """11. 告警面板（近 N 天有差异的对账批次概览）

    用于后台首页展示近期对账异常情况
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询对账面板 admin=%s days=%s",
        request_id,
        admin_user_id,
        days,
    )
    try:
        result = await svc.list_recent_records(days=days, limit=20)
        return success_response(
            data={"recent_diff_records": result, "days": days},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)

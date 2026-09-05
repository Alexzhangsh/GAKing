# @ai-generated
"""
后台佣金结算状态机管理接口层（B12 新建，不修改 B01-B11 基线）
路由前缀：/api/v1/admin/settlement
职责：管理员身份识别 → 参数校验 → 调用 CommissionSettlementB12Service → 统一响应封装
不包含任何业务逻辑，业务规则（状态机/原子冻结解冻/熔断/幂等）全部在 Service 层

接口清单：
1. GET  /settlements                       结算单分页查询（多条件筛选）
2. GET  /settlements/export                结算单导出筛选（page_size 上限 500）
3. GET  /settlements/overdue               超期未解冻结算单预警
4. GET  /settlements/{settlement_id}       结算单详情（含操作历史）
5. GET  /settlements/{settlement_id}/logs  结算单操作历史分页
6. GET  /operation-logs                    结算操作日志多条件查询（审计/导出）
7. POST /settle/freeze/batch               手动触发批量冻结入账
8. POST /settle/freeze/single              手动触发单笔冻结（补发漏单）
9. POST /settle/unfreeze/batch             手动触发批量解冻转可用
10. POST /settle/unfreeze/single           手动触发单笔解冻（补发漏单）

身份识别：
- 强制 JWT（Authorization: Bearer <token>）+ RBAC settlement:review 权限校验；
- require_any_permission 完成：HTTPBearer 解析 token → JWT 校验 → RbacUtil 权限校验
  （含 "*" 通配符的超管直接放行；无权限→403；缺 token→401）。
"""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
from src.config.b12_constants import (
    SETTLEMENT_DELAY_DAYS_DEFAULT,
    TASK_SETTLEMENT_FREEZE_BATCH_SIZE,
    TASK_SETTLEMENT_UNFREEZE_BATCH_SIZE,
)
from src.cps.circuit_breaker import CircuitBreaker
from src.dao.order_dao import OrderDAO
from src.dao.settlement_atomic_dao import SettlementAtomicDAO
from src.dao.settlement_operation_log_dao import SettlementOperationLogDAO
from src.dao.settlement_record_dao import SettlementRecordDAO
from src.db.init_db import DatabaseManager
from src.schemas.settlement_b12 import (
    SettlementBatchFreezeRequest,
    SettlementBatchUnfreezeRequest,
    SettlementLogQuery,
    SettlementOverdueQuery,
    SettlementRecordQuery,
    SettlementSingleFreezeRequest,
    SettlementSingleUnfreezeRequest,
)
from src.services.commission_settlement_b12_service import (
    CommissionSettlementB12Service,
)

logger = logging.getLogger("api.admin.settlement_b12")

router = APIRouter(
    prefix="/api/v1/admin/settlement",
    tags=["后台-佣金结算状态机"],
)


# ── 依赖注入：管理员身份识别 + 数据库会话 + Service 实例 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["settlement:review"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC settlement:review 权限校验）

    依赖 require_any_permission(["settlement:review"]) 完成：
      1. HTTPBearer 解析 Authorization: Bearer <token>（缺失→401）
      2. JwtAuthGuard.verify_token 校验 JWT（无效/过期→401）
      3. RbacUtil.has_any_permission 校验角色权限
         （超管 permissions 含 "*" 通配符直接放行；无权限→403）
    """
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_settlement_b12_service(
    db: AsyncSession = Depends(get_db),
) -> CommissionSettlementB12Service:
    """构造 CommissionSettlementB12Service 实例

    注入 4 个 DAO（OrderDAO / SettlementRecordDAO / SettlementAtomicDAO /
    SettlementOperationLogDAO），共享同一 session（保证单事务原子性）。
    熔断器注入 CircuitBreaker 实例（channel_code=settlement）。
    """
    return CommissionSettlementB12Service(
        order_dao=OrderDAO(db),
        settlement_dao=SettlementRecordDAO(db),
        atomic_dao=SettlementAtomicDAO(db),
        log_dao=SettlementOperationLogDAO(db),
        circuit_breaker=CircuitBreaker(),
    )


# ── 工具函数 ─────────────────────────────────────────


def _parse_datetime(value: Optional[str], request_id: str) -> Optional[datetime]:
    """ISO8601 字符串转 datetime，非法返回 None 并记 warning"""
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning(
            "[request_id=%s] 时间参数非法，已忽略: %s",
            request_id,
            value,
        )
        return None


def _parse_decimal(value: Optional[float], request_id: str) -> Optional[Decimal]:
    """float 转 Decimal，非法返回 None 并记 warning"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        logger.warning(
            "[request_id=%s] 金额参数非法，已忽略: %s",
            request_id,
            value,
        )
        return None


# ══════════════════════════════════════════════════════
# 1. 结算单分页查询
# ══════════════════════════════════════════════════════


@router.get("/settlements")
async def list_settlements(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
    settlement_no: str = Query(default=None, description="结算单号筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    channel_code: str = Query(default=None, description="渠道标识筛选"),
    settlement_status: str = Query(
        default=None, description="结算单状态：ORDERED/SETTLABLE/SETTLED/PAID"
    ),
    min_amount: float = Query(default=None, ge=0, description="用户佣金下限（元）"),
    max_amount: float = Query(default=None, ge=0, description="用户佣金上限（元）"),
    start_time: str = Query(default=None, description="创建时间起始（含，ISO8601）"),
    end_time: str = Query(default=None, description="创建时间截止（不含，ISO8601）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """1. 结算单分页查询（多条件筛选）

    支持按单号/订单/用户/渠道/状态/金额区间/时间区间组合筛选
    返回结算单列表 + 总数 + 分页信息
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询结算单 admin=%s status=%s user_id=%s page=%s",
        request_id,
        admin_user_id,
        settlement_status,
        user_id,
        page,
    )
    try:
        query = SettlementRecordQuery(
            settlement_no=settlement_no,
            order_id=order_id,
            user_id=user_id,
            channel_code=channel_code,
            settlement_status=settlement_status,
            min_amount=min_amount,
            max_amount=max_amount,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_settlements_with_filters(
            settlement_no=query.settlement_no,
            order_id=query.order_id,
            user_id=query.user_id,
            channel_code=query.channel_code,
            settlement_status=query.settlement_status,
            min_amount=_parse_decimal(query.min_amount, request_id),
            max_amount=_parse_decimal(query.max_amount, request_id),
            start_time=_parse_datetime(query.start_time, request_id),
            end_time=_parse_datetime(query.end_time, request_id),
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 结算单导出筛选
# ══════════════════════════════════════════════════════


@router.get("/settlements/export")
async def export_settlements(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
    settlement_no: str = Query(default=None, description="结算单号筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    channel_code: str = Query(default=None, description="渠道标识筛选"),
    settlement_status: str = Query(
        default=None, description="结算单状态：ORDERED/SETTLABLE/SETTLED/PAID"
    ),
    min_amount: float = Query(default=None, ge=0, description="用户佣金下限（元）"),
    max_amount: float = Query(default=None, ge=0, description="用户佣金上限（元）"),
    start_time: str = Query(default=None, description="创建时间起始（含，ISO8601）"),
    end_time: str = Query(default=None, description="创建时间截止（不含，ISO8601）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(
        default=500, ge=1, le=500, description="每页条数（导出最大500）"
    ),
):
    """2. 结算单导出筛选（page_size 上限 500，供后台导出 Excel 用）

    与 list_settlements 同条件，仅放宽 page_size 上限至 500
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 导出结算单 admin=%s status=%s page_size=%s",
        request_id,
        admin_user_id,
        settlement_status,
        page_size,
    )
    try:
        query = SettlementRecordQuery(
            settlement_no=settlement_no,
            order_id=order_id,
            user_id=user_id,
            channel_code=channel_code,
            settlement_status=settlement_status,
            min_amount=min_amount,
            max_amount=max_amount,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_settlements_with_filters(
            settlement_no=query.settlement_no,
            order_id=query.order_id,
            user_id=query.user_id,
            channel_code=query.channel_code,
            settlement_status=query.settlement_status,
            min_amount=_parse_decimal(query.min_amount, request_id),
            max_amount=_parse_decimal(query.max_amount, request_id),
            start_time=_parse_datetime(query.start_time, request_id),
            end_time=_parse_datetime(query.end_time, request_id),
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 超期未解冻预警
# ══════════════════════════════════════════════════════


@router.get("/settlements/overdue")
async def list_overdue_settlements(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
    delay_days: int = Query(
        default=None, ge=1, le=365, description="超期阈值天数（留空读配置，默认30）"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
):
    """3. 超期未解冻结算单预警

    查询 SETTLABLE 态且 confirm_time 超过 delay_days 天未转 SETTLED 的结算单
    用于运营人工核查渠道返佣长期未到账的订单
    """
    request_id = get_request_id(request)
    actual_delay_days = (
        delay_days if delay_days is not None else SETTLEMENT_DELAY_DAYS_DEFAULT
    )
    logger.info(
        "[request_id=%s] 查询超期结算单 admin=%s delay_days=%s page=%s",
        request_id,
        admin_user_id,
        actual_delay_days,
        page,
    )
    try:
        result = await svc.list_overdue_settlable(
            delay_days=actual_delay_days,
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 结算单详情（含操作历史）
# ══════════════════════════════════════════════════════


@router.get("/settlements/{settlement_id}")
async def get_settlement_detail(
    settlement_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
):
    """4. 结算单详情（含最近 50 条操作历史）

    返回结算单全字段 + 操作历史列表 + 日志总数
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询结算单详情 admin=%s settlement_id=%s",
        request_id,
        admin_user_id,
        settlement_id,
    )
    try:
        result = await svc.get_settlement_detail(settlement_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 5. 结算单操作历史分页
# ══════════════════════════════════════════════════════


@router.get("/settlements/{settlement_id}/logs")
async def get_settlement_logs(
    settlement_id: int,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
):
    """5. 结算单操作历史分页查询

    按创建时间升序返回该结算单的全部状态流转日志
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询结算单操作历史 admin=%s settlement_id=%s page=%s",
        request_id,
        admin_user_id,
        settlement_id,
        page,
    )
    try:
        result = await svc.get_settlement_logs(
            settlement_id,
            page=page,
            page_size=page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 6. 操作日志多条件查询（审计/导出）
# ══════════════════════════════════════════════════════


@router.get("/operation-logs")
async def list_operation_logs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
    settlement_id: int = Query(default=None, gt=0, description="结算单ID筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    action: str = Query(
        default=None,
        description="操作类型：CREATE_SETTLEMENT/FREEZE/UNFREEZE/MARK_PAID",
    ),
    operator_id: int = Query(default=None, gt=0, description="操作人ID筛选"),
    start_time: str = Query(default=None, description="创建时间起始（含，ISO8601）"),
    end_time: str = Query(default=None, description="创建时间截止（不含，ISO8601）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """6. 结算操作日志多条件查询（后台审计/导出）

    支持按结算单/订单/操作类型/操作人/时间区间筛选
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询结算操作日志 admin=%s action=%s page=%s",
        request_id,
        admin_user_id,
        action,
        page,
    )
    try:
        query = SettlementLogQuery(
            settlement_id=settlement_id,
            order_id=order_id,
            action=action,
            operator_id=operator_id,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_operation_logs_with_filters(
            settlement_id=query.settlement_id,
            order_id=query.order_id,
            action=query.action,
            operator_id=query.operator_id,
            start_time=_parse_datetime(query.start_time, request_id),
            end_time=_parse_datetime(query.end_time, request_id),
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 7. 手动触发批量冻结入账
# ══════════════════════════════════════════════════════


@router.post("/settle/freeze/batch")
async def batch_freeze(
    body: SettlementBatchFreezeRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
):
    """7. 手动触发批量冻结入账

    - 拉取 SETTLABLE(30) 状态无结算单的订单
    - 创建结算单 + PENDING 流水 + frozen += amount
    - 逐单 try/except，单条失败不阻断整体，返回 partial 状态
    - 幂等：已存在结算单自动跳过
    """
    request_id = get_request_id(request)
    limit = body.limit if body.limit is not None else TASK_SETTLEMENT_FREEZE_BATCH_SIZE
    logger.info(
        "[request_id=%s] 手动触发批量冻结 admin=%s limit=%s",
        request_id,
        admin_user_id,
        limit,
    )
    try:
        result = await svc.batch_freeze_settlable(limit=limit)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 8. 手动触发单笔冻结
# ══════════════════════════════════════════════════════


@router.post("/settle/freeze/single")
async def freeze_single(
    body: SettlementSingleFreezeRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
):
    """8. 手动触发单笔冻结入账（补发漏单）

    - 适用于定时任务因异常漏单时手动补冻结
    - 幂等：已存在结算单自动跳过
    - 订单状态必须为 SETTLABLE(30)，否则返回 400
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发单笔冻结 admin=%s order_id=%s",
        request_id,
        admin_user_id,
        body.order_id,
    )
    try:
        result = await svc.freeze_on_settlable(
            order_id=body.order_id,
            delay_days=(
                body.delay_days
                if body.delay_days is not None
                else SETTLEMENT_DELAY_DAYS_DEFAULT
            ),
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 9. 手动触发批量解冻转可用
# ══════════════════════════════════════════════════════


@router.post("/settle/unfreeze/batch")
async def batch_unfreeze(
    body: SettlementBatchUnfreezeRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
):
    """9. 手动触发批量解冻转可用

    - 拉取订单已 SETTLED(40) 但结算单仍 SETTLABLE 态的记录
    - 解冻 frozen → available + PENDING→SUCCESS 流水
    - 逐单 try/except，单条失败不阻断整体，返回 partial 状态
    """
    request_id = get_request_id(request)
    limit = (
        body.limit if body.limit is not None else TASK_SETTLEMENT_UNFREEZE_BATCH_SIZE
    )
    logger.info(
        "[request_id=%s] 手动触发批量解冻 admin=%s limit=%s",
        request_id,
        admin_user_id,
        limit,
    )
    try:
        result = await svc.batch_unfreeze_settled(limit=limit)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 10. 手动触发单笔解冻
# ══════════════════════════════════════════════════════


@router.post("/settle/unfreeze/single")
async def unfreeze_single(
    body: SettlementSingleUnfreezeRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementB12Service = Depends(get_settlement_b12_service),
):
    """10. 手动触发单笔解冻转可用（补发漏单）

    - 适用于定时任务因异常漏单时手动补解冻
    - 状态机守护：结算单必须为 SETTLABLE 态，非 SETTLABLE 抛 ValueError
    - 订单状态必须为 SETTLED(40)，否则返回 400
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发单笔解冻 admin=%s order_id=%s",
        request_id,
        admin_user_id,
        body.order_id,
    )
    try:
        result = await svc.unfreeze_on_settled(
            order_id=body.order_id,
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

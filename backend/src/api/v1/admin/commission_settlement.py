# @ai-generated
"""
后台佣金结算管理接口层（B07）
路由前缀：/api/v1/admin/commission-settlement
职责：管理员身份识别 → 参数校验 → 调用 CommissionSettlementService → 统一响应封装
不包含任何业务逻辑，业务规则（规则引擎/原子结算/退款扣减/锁定保护）全部在 Service 层

接口清单：
1. POST /settle/batch           手动触发批量佣金结算（可指定 limit）
2. POST /settle/single          手动触发单订单结算（补发漏单）
3. POST /refund-deduct/batch    手动触发批量退款扣减
4. POST /refund-deduct/single   手动触发单订单退款扣减（补发漏单）
5. POST /recalculate            佣金重算（锁定保护，已结算订单拒绝）
6. GET  /flows                  佣金流水查询（多条件筛选 + 分页）
7. GET  /orders                 结算状态订单查询（多条件筛选 + 分页）

身份识别：
- 强制 JWT（Authorization: Bearer <token>）+ RBAC commission:settle 权限校验；
- require_any_permission 完成：HTTPBearer 解析 token → JWT 校验 → RbacUtil 权限校验
  （含 "*" 通配符的超管直接放行；无权限→403；缺 token→401）。
"""
import logging

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
from src.common.redis_client import RedisClient
from src.config.b07_constants import (
    CACHE_TTL_COMMISSION_RULE,
    TASK_BATCH_SETTLE_BATCH_SIZE,
    TASK_REFUND_DEDUCT_BATCH_SIZE,
)
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig
from src.schemas.commission_settlement import (
    CommissionFlowQuery,
    CommissionRecalculateRequest,
    CommissionSettleRequest,
    RefundDeductRequest,
    SettlementOrderQuery,
)
from src.services.commission_rule_engine import CommissionRuleEngine
from src.services.commission_settlement_service import CommissionSettlementService
from sqlalchemy import select

logger = logging.getLogger("api.admin.commission_settlement")

router = APIRouter(
    prefix="/api/v1/admin/commission-settlement",
    tags=["后台-佣金结算"],
)


# ── 依赖注入：管理员身份识别 + 数据库会话 + Service 实例 ──────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["commission:settle"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC commission:settle 权限校验）

    依赖 require_any_permission(["commission:settle"]) 完成：
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


async def _make_config_loader(db_session: AsyncSession):
    """构造规则引擎配置加载器（与 commission_settlement_jobs._make_config_loader 一致）

    读取 SystemConfig 表 + Redis 缓存（5min TTL），空值防穿透（60s）
    """

    async def loader(config_key: str):
        # 1. Redis 缓存优先
        cached = await RedisClient.get(config_key)
        if cached is not None:
            if cached == "__EMPTY__":
                return None
            return cached

        # 2. 查库
        try:
            stmt = select(SystemConfig.config_value).where(
                SystemConfig.config_key == config_key,
                SystemConfig.is_delete == False,  # noqa: E712
            )
            result = await db_session.execute(stmt)
            row = result.first()
            if row is None:
                await RedisClient.set_empty_cache(config_key)
                return None
            value = row[0]
            await RedisClient.set(config_key, value, expire=CACHE_TTL_COMMISSION_RULE)
            return value
        except Exception as e:
            logger.warning(
                "[config_loader] 读取 SystemConfig 失败 key=%s error=%s",
                config_key,
                e,
            )
            return None

    return loader


async def get_settlement_service(
    db: AsyncSession = Depends(get_db),
) -> CommissionSettlementService:
    """构造 CommissionSettlementService 实例（注入 4 个依赖）"""
    order_dao = OrderDAO(db)
    flow_dao = CommissionFlowDAO(db)
    settlement_dao = CommissionSettlementDAO(db)
    config_loader = await _make_config_loader(db)
    rule_engine = CommissionRuleEngine(config_loader=config_loader)
    return CommissionSettlementService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        settlement_dao=settlement_dao,
        rule_engine=rule_engine,
    )


# ══════════════════════════════════════════════════════
# 1. 批量结算
# ══════════════════════════════════════════════════════


@router.post("/settle/batch")
async def batch_settle(
    body: CommissionSettleRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
):
    """1. 手动触发批量佣金结算

    - 拉取 SETTLED 状态无 ORDER 流水的订单
    - 规则引擎计算佣金 → 原子入账（FOR UPDATE + 流水 + 余额）
    - 逐单 try/except，单条失败不阻断整体，返回 partial 状态
    - 幂等：已有 SUCCESS 流水自动跳过
    """
    request_id = get_request_id(request)
    limit = body.limit if body.limit is not None else TASK_BATCH_SETTLE_BATCH_SIZE
    logger.info(
        "[request_id=%s] 手动触发批量结算 admin=%s limit=%s",
        request_id,
        admin_user_id,
        limit,
    )
    try:
        result = await svc.batch_settle_orders(limit=limit)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/settle/single")
async def settle_single(
    body: CommissionRecalculateRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
):
    """2. 手动触发单订单结算（补发漏单）

    - 适用于定时任务因异常漏单时手动补结算
    - 幂等：已有 SUCCESS 流水自动跳过
    - 订单状态必须为 SETTLED，否则返回 400
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发单笔结算 admin=%s order_id=%s",
        request_id,
        admin_user_id,
        body.order_id,
    )
    try:
        result = await svc.settle_single_order(body.order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 退款扣减
# ══════════════════════════════════════════════════════


@router.post("/refund-deduct/batch")
async def batch_refund_deduct(
    body: RefundDeductRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
):
    """3. 手动触发批量退款佣金扣减

    - 拉取 REFUNDED 状态无 DEDUCT 流水的订单
    - 分支处理：PENDING→FAILED / SUCCESS→扣余额+DEDUCT 流水
    - 逐单 try/except，单条失败不阻断整体
    - 幂等：已有 DEDUCT 流水自动跳过
    """
    request_id = get_request_id(request)
    # order_id 非空：单笔扣减；为空：批量扣减
    if body.order_id is not None:
        logger.info(
            "[request_id=%s] 手动触发单笔退款扣减 admin=%s order_id=%s",
            request_id,
            admin_user_id,
            body.order_id,
        )
        try:
            result = await svc.process_single_refund(body.order_id)
            return success_response(data=result, request_id=request_id)
        except Exception as exc:
            return handle_service_exception(exc, request_id)

    limit = body.limit if body.limit is not None else TASK_REFUND_DEDUCT_BATCH_SIZE
    logger.info(
        "[request_id=%s] 手动触发批量退款扣减 admin=%s limit=%s",
        request_id,
        admin_user_id,
        limit,
    )
    try:
        result = await svc.process_refund_deductions(limit=limit)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/refund-deduct/single")
async def refund_deduct_single(
    body: CommissionRecalculateRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
):
    """4. 手动触发单订单退款扣减（补发漏单）

    - 适用于定时任务因异常漏单时手动补扣减
    - 幂等：已有 DEDUCT 流水自动跳过
    - 订单状态必须为 REFUNDED，否则返回 400
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 手动触发单笔退款扣减 admin=%s order_id=%s",
        request_id,
        admin_user_id,
        body.order_id,
    )
    try:
        result = await svc.process_single_refund(body.order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 佣金重算
# ══════════════════════════════════════════════════════


@router.post("/recalculate")
async def recalculate(
    body: CommissionRecalculateRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
):
    """5. 佣金重算（锁定保护）

    - 已有 ORDER 类型流水 → 锁定拒绝（返回 400）
    - 无 ORDER 流水 → 按规则引擎重算并更新订单佣金字段
    - 用于后台修正比例配置后对未结算订单的佣金校准
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 佣金重算 admin=%s order_id=%s",
        request_id,
        admin_user_id,
        body.order_id,
    )
    try:
        result = await svc.recalculate_order_commission(body.order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 查询接口
# ══════════════════════════════════════════════════════


@router.get("/flows")
async def list_flows(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    flow_type: str = Query(
        default=None, description="流水类型：ORDER/SUPPLEMENT/DEDUCT"
    ),
    transfer_status: str = Query(
        default=None, description="转账状态：PENDING/PROCESSING/SUCCESS/FAILED"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """6. 佣金流水查询（多条件筛选 + 分页）

    支持按 user_id / order_id / flow_type / transfer_status 筛选
    返回流水列表 + 总数 + 分页信息
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询佣金流水 admin=%s user_id=%s order_id=%s flow_type=%s status=%s page=%s",
        request_id,
        admin_user_id,
        user_id,
        order_id,
        flow_type,
        transfer_status,
        page,
    )
    # 参数校验（与 schema 一致，捕获 ValidationError 返回 422）
    try:
        query = CommissionFlowQuery(
            user_id=user_id,
            order_id=order_id,
            flow_type=flow_type,
            transfer_status=transfer_status,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_settlement_flows(
            user_id=query.user_id,
            order_id=query.order_id,
            flow_type=query.flow_type,
            transfer_status=query.transfer_status,
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/orders")
async def list_orders(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionSettlementService = Depends(get_settlement_service),
    order_status: int = Query(
        default=None, ge=10, le=60, description="订单状态：10/30/40/50/60"
    ),
    channel_code: str = Query(default=None, description="渠道标识：myq/orderx/dta"),
    has_flow: bool = Query(
        default=None, description="True=有流水(已结算), False=无流水(待结算)"
    ),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """7. 结算状态订单查询（多条件筛选 + 分页）

    支持按 order_status / channel_code / has_flow 筛选
    返回订单列表 + 总数 + 分页信息
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 查询结算订单 admin=%s status=%s channel=%s has_flow=%s page=%s",
        request_id,
        admin_user_id,
        order_status,
        channel_code,
        has_flow,
        page,
    )
    # 参数校验（与 schema 一致，捕获 ValidationError 返回 422）
    try:
        query = SettlementOrderQuery(
            order_status=order_status,
            channel_code=channel_code,
            has_flow=has_flow,
            page=page,
            page_size=page_size,
        )
    except ValidationError as ve:
        msg = ve.errors()[0]["msg"] if ve.errors() else "参数校验失败"
        return error_response(code=422, msg=msg, request_id=request_id, http_status=422)
    try:
        result = await svc.list_settlement_orders(
            order_status=query.order_status,
            channel_code=query.channel_code,
            has_flow=query.has_flow,
            page=query.page,
            page_size=query.page_size,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

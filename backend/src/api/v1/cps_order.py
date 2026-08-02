# @ai-generated
"""
CPS 订单接口层
路由前缀：/api/v1/cps/order
职责：参数校验 → 调用 OrderService → 统一响应封装
不包含任何业务逻辑，业务规则全部在 Service 层
"""
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.api.v1.response_util import (
    get_request_id,
    success_response,
    handle_service_exception,
)
from src.dao.order_dao import OrderDAO
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.db.init_db import DatabaseManager
from src.schemas.cps import (
    OrderCreateRequest,
    OrderStatusUpdateRequest,
)
from src.services.order_service import OrderService

logger = logging.getLogger("api.cps_order")

router = APIRouter(prefix="/api/v1/cps/order", tags=["CPS订单"])


# ── 依赖注入：数据库会话 + Service 实例 ──────────────────


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    """构造 OrderService 实例（注入 OrderDAO + CommissionFlowDAO）"""
    return OrderService(OrderDAO(db), CommissionFlowDAO(db))


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.post("")
async def create_order(
    body: OrderCreateRequest,
    request: Request,
    svc: OrderService = Depends(get_order_service),
):
    """1. 渠道订单推送入库接口（幂等防重复）

    - out_order_no 渠道订单号唯一校验，重复入库返回已有订单
    - 金额校验、佣金一致性校验
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 渠道订单入库: out_order_no=%s, user_id=%s",
        request_id,
        body.out_order_no,
        body.user_id,
    )
    try:
        result = await svc.create_order_from_channel(
            out_order_no=body.out_order_no,
            internal_order_no=body.internal_order_no,
            user_id=body.user_id,
            goods_title=body.goods_title,
            goods_img=body.goods_img,
            pay_amount=body.pay_amount,
            total_commission=body.total_commission,
            user_commission=body.user_commission,
            platform_commission=body.platform_commission,
            channel_code=body.channel_code,
            pay_time=body.pay_time,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/status")
async def update_order_status(
    body: OrderStatusUpdateRequest,
    request: Request,
    svc: OrderService = Depends(get_order_service),
):
    """2. 订单状态手动变更接口

    - 校验前置状态合法性，非法流转返回 400
    - SETTLED 状态自动记录结算时间
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 订单状态变更: order_id=%s, target_status=%s",
        request_id,
        body.order_id,
        body.target_status,
    )
    try:
        result = await svc.transition_order_status(
            order_id=body.order_id,
            target_status=body.target_status,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("")
async def list_orders(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    channel_code: Optional[str] = Query(None, description="渠道标识筛选"),
    order_status: Optional[int] = Query(None, description="订单状态筛选"),
    user_id: Optional[int] = Query(None, gt=0, description="用户ID筛选"),
    svc: OrderService = Depends(get_order_service),
):
    """3. 订单分页列表查询（多条件筛选：渠道/状态/用户）"""
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 订单列表查询: page=%s, size=%s, channel=%s, status=%s, user=%s",
        request_id,
        page,
        page_size,
        channel_code,
        order_status,
        user_id,
    )
    try:
        result = await svc.list_orders(
            page=page,
            page_size=page_size,
            channel_code=channel_code,
            order_status=order_status,
            user_id=user_id,
        )
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{order_id}")
async def get_order_detail(
    order_id: int,
    request: Request,
    svc: OrderService = Depends(get_order_service),
):
    """4. 订单详情（含佣金流水）查询

    - 使用 selectinload 预加载佣金流水，避免 N+1
    - 返回订单完整信息 + 关联流水列表
    """
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 订单详情查询: order_id=%s", request_id, order_id)
    try:
        result = await svc.get_order_detail(order_id=order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)

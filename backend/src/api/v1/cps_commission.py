# @ai-generated
"""
CPS 佣金接口层（C 端历史兼容路由）
路由前缀：/api/v1/cps/commission
职责：参数校验 → 调用 CommissionService → 统一响应封装
不包含任何业务逻辑，业务规则全部在 Service 层

⚠️ B07 整改说明（2026-08-02）：
- 写入接口（/generate、/settle）保留用于 C 端历史兼容，生成的是 PENDING 流水。
- 新业务（批量结算/退款扣减/重算）必须使用 B07 后台接口：
  路由前缀 /api/v1/admin/commission-settlement（需 commission:settle 权限），
  B07 的 settle_single_order 在结算时直接生成 SUCCESS 流水并原子更新余额。
- 查询接口（/summary、/serialize）B07 暂无等价 C 端方法，保留本路由。
- 后续 C 端登录体系完善后，写入接口将统一迁移至 B07。
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
    CommissionGenerateRequest,
    CommissionSettleRequest,
    CommissionFlowSerializeRequest,
)
from src.services.commission_service import CommissionService

logger = logging.getLogger("api.cps_commission")

router = APIRouter(prefix="/api/v1/cps/commission", tags=["CPS佣金"])


# ── 依赖注入：数据库会话 + Service 实例 ──────────────────


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_commission_service(db: AsyncSession = Depends(get_db)) -> CommissionService:
    """构造 CommissionService 实例（注入 OrderDAO + CommissionFlowDAO）"""
    return CommissionService(OrderDAO(db), CommissionFlowDAO(db))


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.post("/generate")
async def generate_commission_flows(
    body: CommissionGenerateRequest,
    request: Request,
    svc: CommissionService = Depends(get_commission_service),
):
    """1. 订单佣金流水生成触发接口（历史兼容，生成 PENDING 流水）

    ⚠️ @deprecated 新业务请使用 B07 后台接口：
    POST /api/v1/admin/commission-settlement/settle/single
    （B07 在结算时直接生成 SUCCESS 流水并原子更新余额，无需两步式生成+标记）

    - 根据订单拆分生成佣金流水记录（transfer_status=PENDING）
    - 幂等：已存在 ORDER 类型流水则跳过
    """
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 佣金流水生成: order_id=%s", request_id, body.order_id)
    try:
        result = await svc.generate_commission_flows(order_id=body.order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/summary/{order_id}")
async def get_commission_summary(
    order_id: int,
    request: Request,
    svc: CommissionService = Depends(get_commission_service),
):
    """2. 订单佣金汇总金额查询

    - SQL SUM 聚合查询单订单总佣金金额
    - 返回总金额和流水条数
    """
    request_id = get_request_id(request)
    logger.info("[request_id=%s] 佣金汇总查询: order_id=%s", request_id, order_id)
    try:
        result = await svc.summarize_order_commission(order_id=order_id)
        return success_response(data=result, request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/settle")
async def batch_settle_commission(
    body: CommissionSettleRequest,
    request: Request,
    svc: CommissionService = Depends(get_commission_service),
):
    """3. 批量标记佣金结算完成接口（历史兼容，PENDING→SUCCESS 标记）

    ⚠️ @deprecated 新业务请使用 B07 后台接口：
    POST /api/v1/admin/commission-settlement/settle/batch
    （B07 的 batch_settle_orders 直接拉取 SETTLED 订单并原子结算入账，
    无需先生成 PENDING 流水再标记 SUCCESS 的两步式流程）

    - 将多条 PENDING 流水标记为 SUCCESS
    - 绑定微信转账批次ID
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 批量结算: flow_ids=%s, batch_id=%s",
        request_id,
        body.flow_ids,
        body.transfer_batch_id,
    )
    try:
        count = await svc.batch_mark_settled(
            flow_ids=body.flow_ids,
            transfer_batch_id=body.transfer_batch_id,
        )
        return success_response(
            data={"settled_count": count, "total": len(body.flow_ids)},
            msg=f"成功结算 {count} 条流水",
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.post("/serialize")
async def serialize_commission_flows(
    body: CommissionFlowSerializeRequest,
    request: Request,
    svc: CommissionService = Depends(get_commission_service),
):
    """4. 流水明细批量导出序列化接口

    - 按流水ID列表批量查询并序列化
    - 自动处理 Decimal→float、datetime→str
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 流水序列化: flow_ids count=%s",
        request_id,
        len(body.flow_ids),
    )
    try:
        result = await svc.serialize_flow_by_ids(flow_ids=body.flow_ids)
        return success_response(
            data={"list": result, "count": len(result)},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)

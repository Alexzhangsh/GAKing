# @ai-generated
"""
后台佣金流水结算前置校验管理接口层（B05-5）
路由前缀：/api/v1/admin/commission-flow-validation
职责：管理员身份识别 → 参数校验 → 调用 CommissionFlowValidationService → 统一响应封装
不包含任何业务逻辑，业务规则全部在 Service 层

接口清单：
1. POST /pre-validate             单订单结算前置校验
2. POST /pre-validate/batch       批量结算前置校验
3. GET  /logs/{order_id}          按订单ID查询校验日志
4. GET  /logs                     多条件查询校验日志（后台审计）

身份识别：
- 强制 JWT（Authorization: Bearer <token>）+ RBAC commission:settle 权限校验；
"""
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.response_util import (
    get_request_id,
    handle_service_exception,
    success_response,
    error_response,
)
from src.common.auth_util import require_any_permission
from src.dao.commission_flow_dao import CommissionFlowDAO
from src.dao.commission_flow_validation_log_dao import CommissionFlowValidationLogDAO
from src.dao.order_dao import OrderDAO
from src.db.init_db import DatabaseManager
from src.schemas.commission_flow_validation import (
    CommissionFlowPreValidateRequest,
    CommissionFlowValidationLogItem,
    CommissionFlowValidationLogListResponse,
)
from src.services.commission_flow_validation_service import (
    CommissionFlowValidationService,
)

logger = logging.getLogger("api.admin.commission_flow_validation")

router = APIRouter(
    prefix="/api/v1/admin/commission-flow-validation",
    tags=["后台-佣金流水前置校验"],
)


# ── 依赖注入 ──────────────────────────────────────────


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["commission:settle"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC commission:settle 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_validation_service(
    db: AsyncSession = Depends(get_db),
) -> CommissionFlowValidationService:
    """构造 CommissionFlowValidationService 实例"""
    order_dao = OrderDAO(db)
    flow_dao = CommissionFlowDAO(db)
    validation_log_dao = CommissionFlowValidationLogDAO(db)
    return CommissionFlowValidationService(
        order_dao=order_dao,
        flow_dao=flow_dao,
        validation_log_dao=validation_log_dao,
    )


# ══════════════════════════════════════════════════════
# 1. 单订单结算前置校验
# ══════════════════════════════════════════════════════


@router.post("/pre-validate")
async def pre_validate_settle(
    body: CommissionFlowPreValidateRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionFlowValidationService = Depends(get_validation_service),
):
    """1. 单订单结算前置校验

    校验项：
    - 订单存在性
    - 订单状态（必须为 SETTLED）
    - 佣金金额合法性（user_commission > 0）
    - 佣金金额超限校验（user_commission <= total_commission）
    - 重复流水拦截（已有 ORDER 类型流水拦截）
    - 用户归属校验（user_id > 0）

    返回各项校验明细（passed/failed），支持前端逐项展示。
    """
    request_id = get_request_id(request)
    logger.info(
        "[request_id=%s] 结算前置校验 admin=%s order_id=%s",
        request_id, admin_user_id, body.order_id,
    )
    try:
        result = await svc.pre_validate_settle(
            order_id=body.order_id,
            operator_id=admin_user_id,
        )
        # 如果校验失败，返回 400 以便前端感知
        if result.validation_result == "FAIL":
            return error_response(
                code=400,
                msg=result.error_message or "结算前置校验未通过",
                request_id=request_id,
                data=result.model_dump(),
            )
        return success_response(data=result.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 2. 批量结算前置校验
# ══════════════════════════════════════════════════════


@router.post("/pre-validate/batch")
async def batch_pre_validate(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    svc: CommissionFlowValidationService = Depends(get_validation_service),
    order_ids: str = Query(..., description="订单ID列表，逗号分隔，如'1,2,3'"),
):
    """2. 批量结算前置校验

    对多个订单执行前置校验，返回通过/失败统计。

    Args:
        order_ids: 订单ID列表，逗号分隔，最多50个
    """
    request_id = get_request_id(request)
    try:
        id_list = [int(x.strip()) for x in order_ids.split(",") if x.strip()]
        if len(id_list) > 50:
            return error_response(
                code=400, msg="批量校验最多支持50个订单",
                request_id=request_id,
            )
        result = await svc.batch_pre_validate(
            order_ids=id_list,
            operator_id=admin_user_id,
        )
        return success_response(data=result, request_id=request_id)
    except ValueError:
        return error_response(
            code=400, msg="订单ID列表格式错误，需为逗号分隔的数字",
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 3. 按订单查询校验日志
# ══════════════════════════════════════════════════════


@router.get("/logs/{order_id}")
async def list_validation_logs_by_order(
    order_id: int,
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
):
    """3. 按订单ID查询校验日志（B05-5 新增）

    查询指定订单的结算前置校验历史记录，按时间降序排列。
    """
    request_id = get_request_id(request)
    try:
        log_dao = CommissionFlowValidationLogDAO(db)
        items, total = await log_dao.list_by_order_id(
            order_id=order_id,
            page=page,
            page_size=page_size,
        )
        log_items = [
            CommissionFlowValidationLogItem(
                id=item.id,
                order_id=item.order_id,
                user_id=item.user_id,
                validation_type=item.validation_type,
                validation_result=item.validation_result,
                check_items=item.check_items or "",
                error_message=item.error_message or "",
                operator_id=item.operator_id or 0,
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = CommissionFlowValidationLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


# ══════════════════════════════════════════════════════
# 4. 多条件查询校验日志
# ══════════════════════════════════════════════════════


@router.get("/logs")
async def list_validation_logs(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    db: AsyncSession = Depends(get_db),
    order_id: int = Query(default=None, gt=0, description="订单ID筛选"),
    user_id: int = Query(default=None, gt=0, description="用户ID筛选"),
    validation_type: str = Query(default=None, description="校验类型：PRE_SETTLE/PRE_DEDUCT"),
    validation_result: str = Query(default=None, description="校验结果：PASS/FAIL"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """4. 多条件查询校验日志（后台审计用）

    支持按订单ID、用户ID、校验类型、校验结果筛选。
    """
    request_id = get_request_id(request)
    try:
        log_dao = CommissionFlowValidationLogDAO(db)
        items, total = await log_dao.list_with_filters(
            order_id=order_id,
            user_id=user_id,
            validation_type=validation_type or None,
            validation_result=validation_result or None,
            page=page,
            page_size=page_size,
        )
        log_items = [
            CommissionFlowValidationLogItem(
                id=item.id,
                order_id=item.order_id,
                user_id=item.user_id,
                validation_type=item.validation_type,
                validation_result=item.validation_result,
                check_items=item.check_items or "",
                error_message=item.error_message or "",
                operator_id=item.operator_id or 0,
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = CommissionFlowValidationLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
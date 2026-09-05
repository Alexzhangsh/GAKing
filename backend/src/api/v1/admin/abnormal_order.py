# @ai-generated
"""
后台异常订单管理接口层（B05-4 / B05-4-3）
路由前缀：/api/v1/admin/abnormal-orders
职责：管理员身份识别 → 参数校验 → 调用 AbnormalOrderDAO → 统一响应封装
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
from src.dao.abnormal_order_dao import AbnormalOrderDAO
from src.dao.abnormal_order_operation_log_dao import AbnormalOrderOperationLogDAO
from src.db.init_db import DatabaseManager
from src.schemas.short_link import (
    AbnormalOrderEditRequest,
    AbnormalOrderItem,
    AbnormalOrderListResponse,
    AbnormalOrderOperationLogItem,
    AbnormalOrderOperationLogListResponse,
    AbnormalOrderReviewRequest,
    AbnormalOrderStatsResponse,
)

logger = logging.getLogger("api.admin.abnormal_order")

router = APIRouter(prefix="/api/v1/admin/abnormal-orders", tags=["后台-异常订单管理"])


async def get_admin_user_id(
    payload: dict = Depends(require_any_permission(["order:manage"])),
) -> int:
    """获取后台管理员ID（强制 JWT + RBAC order:manage 权限校验）"""
    return int(payload["user_id"])


async def get_db():
    """异步数据库会话依赖"""
    async with DatabaseManager.get_session() as session:
        yield session


def get_abnormal_order_dao(
    db: AsyncSession = Depends(get_db),
) -> AbnormalOrderDAO:
    return AbnormalOrderDAO(db)


def get_operation_log_dao(
    db: AsyncSession = Depends(get_db),
) -> AbnormalOrderOperationLogDAO:
    return AbnormalOrderOperationLogDAO(db)


# ══════════════════════════════════════════════════════
# 接口实现
# ══════════════════════════════════════════════════════


@router.get("/list")
async def list_abnormal_orders(
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    review_status: str = Query(default="", description="复核状态筛选（PENDING/REVIEWED/IGNORED）"),
    channel_code: str = Query(default="", description="渠道筛选（myq/orderx/dta）"),
    keyword: str = Query(default="", description="搜索关键词（商品标题/订单号）"),
    admin_user_id: int = Depends(get_admin_user_id),
    dao: AbnormalOrderDAO = Depends(get_abnormal_order_dao),
):
    """1. 异常订单分页列表

    支持按复核状态、渠道、关键词筛选。
    """
    request_id = get_request_id(request)
    try:
        items, total = await dao.paginate_list(
            page=page,
            page_size=page_size,
            review_status=review_status or None,
            channel_code=channel_code or None,
            keyword=keyword or None,
        )
        order_items = [
            AbnormalOrderItem(
                id=item.id,
                out_order_no=item.out_order_no,
                channel_code=item.channel_code or "",
                goods_id=item.goods_id or "",
                goods_title=item.goods_title or "",
                pay_amount=float(item.pay_amount) if item.pay_amount else 0.0,
                total_commission=float(item.total_commission) if item.total_commission else 0.0,
                order_status=item.order_status or "",
                pay_time=item.pay_time.strftime("%Y-%m-%d %H:%M:%S") if item.pay_time else None,
                abnormal_reason=item.abnormal_reason or "",
                matched_click_key=item.matched_click_key or "",
                matched_user_id=item.matched_user_id or 0,
                assigned_user_id=item.assigned_user_id or 0,
                review_status=item.review_status or "PENDING",
                review_remark=item.review_remark or "",
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = AbnormalOrderListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=order_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{item_id}/review")
async def review_abnormal_order(
    item_id: int,
    body: AbnormalOrderReviewRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    dao: AbnormalOrderDAO = Depends(get_abnormal_order_dao),
    log_dao: AbnormalOrderOperationLogDAO = Depends(get_operation_log_dao),
):
    """2. 复核异常订单（支持手动指定归属用户）

    将异常订单标记为 REVIEWED（已复核）或 IGNORED（已忽略）。
    可通过 assigned_user_id 手动指定归属用户。
    自动记录归属操作日志。
    """
    request_id = get_request_id(request)
    try:
        if body.review_status not in ("REVIEWED", "IGNORED"):
            return error_response(
                code=400, msg="复核状态必须为 REVIEWED 或 IGNORED",
                request_id=request_id,
            )

        # 读取变更前快照
        before = await dao.get_by_id(item_id)
        if before is None:
            return error_response(
                code=404, msg="异常订单不存在",
                request_id=request_id,
            )

        # 执行复核
        result = await dao.review(
            item_id=item_id,
            review_status=body.review_status,
            review_remark=body.review_remark,
            reviewed_by=admin_user_id,
            assigned_user_id=body.assigned_user_id,
        )
        if result is None:
            return error_response(
                code=404, msg="异常订单不存在",
                request_id=request_id,
            )

        # 写入归属操作日志
        await log_dao.create_log(
            abnormal_order_id=item_id,
            operator_id=admin_user_id,
            operation_type="REVIEW",
            old_assigned_user_id=before.assigned_user_id or 0,
            new_assigned_user_id=body.assigned_user_id if body.assigned_user_id > 0 else (before.assigned_user_id or 0),
            old_review_remark=before.review_remark or "",
            new_review_remark=body.review_remark,
            old_review_status=before.review_status or "",
            new_review_status=body.review_status,
            remark=f"复核操作：{body.review_status}",
        )

        logger.info(
            "异常订单复核完成: id=%s status=%s admin=%s remark=%s assigned_user=%s",
            item_id, body.review_status, admin_user_id,
            body.review_remark, body.assigned_user_id,
        )
        return success_response(
            data={"id": item_id, "review_status": body.review_status},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.put("/{item_id}/edit")
async def edit_abnormal_order(
    item_id: int,
    body: AbnormalOrderEditRequest,
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    dao: AbnormalOrderDAO = Depends(get_abnormal_order_dao),
    log_dao: AbnormalOrderOperationLogDAO = Depends(get_operation_log_dao),
):
    """2.1 编辑异常订单（复核后修改归属/备注）

    支持修改已复核订单的归属用户和复核备注。
    自动记录归属操作日志。
    """
    request_id = get_request_id(request)
    try:
        # 读取变更前快照
        before = await dao.get_by_id(item_id)
        if before is None:
            return error_response(
                code=404, msg="异常订单不存在",
                request_id=request_id,
            )

        result = await dao.update_review(
            item_id=item_id,
            assigned_user_id=body.assigned_user_id,
            review_remark=body.review_remark,
        )
        if result is None:
            return error_response(
                code=404, msg="异常订单不存在",
                request_id=request_id,
            )

        # 写入归属操作日志
        await log_dao.create_log(
            abnormal_order_id=item_id,
            operator_id=admin_user_id,
            operation_type="EDIT",
            old_assigned_user_id=before.assigned_user_id or 0,
            new_assigned_user_id=body.assigned_user_id if body.assigned_user_id > 0 else (before.assigned_user_id or 0),
            old_review_remark=before.review_remark or "",
            new_review_remark=body.review_remark,
            old_review_status=before.review_status or "",
            new_review_status=before.review_status or "",
            remark="编辑操作：修改归属/备注",
        )

        logger.info(
            "异常订单编辑完成: id=%s admin=%s assigned_user=%s remark=%s",
            item_id, admin_user_id,
            body.assigned_user_id, body.review_remark,
        )
        return success_response(
            data={"id": item_id, "assigned_user_id": body.assigned_user_id},
            request_id=request_id,
        )
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/stats")
async def get_abnormal_order_stats(
    request: Request,
    admin_user_id: int = Depends(get_admin_user_id),
    dao: AbnormalOrderDAO = Depends(get_abnormal_order_dao),
):
    """3. 异常订单统计（各复核状态数量）"""
    request_id = get_request_id(request)
    try:
        counts = await dao.count_by_review_status()
        stats = AbnormalOrderStatsResponse(
            total=sum(counts.values()),
            pending=counts.get("PENDING", 0),
            reviewed=counts.get("REVIEWED", 0),
            ignored=counts.get("IGNORED", 0),
        )
        return success_response(data=stats.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)


@router.get("/{item_id}/operation-logs")
async def list_abnormal_order_operation_logs(
    item_id: int,
    request: Request,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    admin_user_id: int = Depends(get_admin_user_id),
    log_dao: AbnormalOrderOperationLogDAO = Depends(get_operation_log_dao),
):
    """4. 查询异常订单归属操作记录（B05-4-3 新增）

    按异常订单ID查询人工修改归属、备注的操作流水，按时间降序排列。
    """
    request_id = get_request_id(request)
    try:
        items, total = await log_dao.list_by_abnormal_order_id(
            abnormal_order_id=item_id,
            page=page,
            page_size=page_size,
        )
        log_items = [
            AbnormalOrderOperationLogItem(
                id=item.id,
                abnormal_order_id=item.abnormal_order_id,
                operator_id=item.operator_id,
                operation_type=item.operation_type,
                old_assigned_user_id=item.old_assigned_user_id or 0,
                new_assigned_user_id=item.new_assigned_user_id or 0,
                old_review_remark=item.old_review_remark or "",
                new_review_remark=item.new_review_remark or "",
                old_review_status=item.old_review_status or "",
                new_review_status=item.new_review_status or "",
                remark=item.remark or "",
                create_time=item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else None,
            )
            for item in items
        ]
        resp = AbnormalOrderOperationLogListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=log_items,
        )
        return success_response(data=resp.model_dump(), request_id=request_id)
    except Exception as exc:
        return handle_service_exception(exc, request_id)
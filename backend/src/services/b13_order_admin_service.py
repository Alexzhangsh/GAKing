# @ai-generated
"""
B13-1 订单管理后台 Service
业务逻辑层：订单列表查询、详情查看、状态流转校验与执行、操作日志查询
所有写操作自动记录审计日志（通过 AuditLogger）
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select

from src.common.b14_audit_util import AuditLogger
from src.config.b12_constants import (
    ORDER_OPERATION_TYPE_LABELS,
    ORDER_STATUS_LABELS,
    OrderOperationType,
)
# 审计动作常量（与 B13B14AuditAction 风格一致，独立定义避免修改存量文件）
AUDIT_ACTION_ORDER_TRANSITION = "ORDER_TRANSITION"  # 订单状态流转
AUDIT_ACTION_ORDER_QUERY = "ORDER_QUERY"  # 订单查询
from src.dao.b12_order_operation_log_dao import OrderOperationLogDAO
from src.dao.order_dao import OrderDAO
from src.db.base import DatabaseManager
from src.models.business.b12_order_operation_log import OrderOperationLog
from src.models.business.order_model import Order
from src.services.b12_order_state_machine_service import B12OrderStateMachineService

logger = logging.getLogger("services.b13_order_admin")


class B13OrderAdminService:
    """订单管理后台 Service"""

    # ── 工具序列化方法 ──────────────────────────────────────

    @staticmethod
    def _serialize_order_brief(order: Order) -> Dict[str, Any]:
        """序列化订单摘要"""
        return {
            "id": order.id,
            "out_order_no": order.out_order_no,
            "internal_order_no": order.internal_order_no,
            "goods_title": order.goods_title or "",
            "goods_img": order.goods_img or "",
            "user_id": order.user_id,
            "channel_code": order.channel_code or "",
            "order_status": int(order.order_status),
            "pay_amount": str(order.pay_amount) if order.pay_amount else "0.00",
            "total_commission": str(order.total_commission) if order.total_commission else "0.00",
            "user_commission": str(order.user_commission) if order.user_commission else "0.00",
            "platform_commission": str(order.platform_commission) if order.platform_commission else "0.00",
            "transfer_status": order.transfer_status or "PENDING",
            "create_time": order.create_time.strftime("%Y-%m-%d %H:%M:%S") if order.create_time else None,
            "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else None,
            "settle_time": order.settle_time.strftime("%Y-%m-%d %H:%M:%S") if order.settle_time else None,
        }

    @staticmethod
    def _serialize_order_detail(order_dict: Dict[str, Any]) -> Dict[str, Any]:
        """序列化订单详情（从缓存 dict 转前台格式）"""
        flows = order_dict.pop("commission_flows", [])
        result = {
            "id": order_dict.get("id"),
            "out_order_no": order_dict.get("out_order_no", ""),
            "internal_order_no": order_dict.get("internal_order_no", ""),
            "goods_title": order_dict.get("goods_title", ""),
            "goods_img": order_dict.get("goods_img", ""),
            "user_id": order_dict.get("user_id"),
            "channel_code": order_dict.get("channel_code", ""),
            "order_status": int(order_dict.get("order_status", 0)),
            "pay_amount": str(order_dict.get("pay_amount", "0.00")),
            "total_commission": str(order_dict.get("total_commission", "0.00")),
            "user_commission": str(order_dict.get("user_commission", "0.00")),
            "platform_commission": str(order_dict.get("platform_commission", "0.00")),
            "transfer_status": order_dict.get("transfer_status", "PENDING"),
            "wx_batch_id": order_dict.get("wx_batch_id", ""),
            "create_time": order_dict.get("create_time"),
            "pay_time": order_dict.get("pay_time"),
            "settle_time": order_dict.get("settle_time"),
            "commission_flows": [
                {
                    "id": f.get("id"),
                    "order_id": f.get("order_id"),
                    "user_id": f.get("user_id"),
                    "flow_type": f.get("flow_type", ""),
                    "amount": str(f.get("amount", "0.00")),
                    "before_balance": str(f.get("before_balance", "0.00")),
                    "after_balance": str(f.get("after_balance", "0.00")),
                    "transfer_status": f.get("transfer_status", "PENDING"),
                    "remark": f.get("remark", ""),
                    "create_time": f.get("create_time").strftime("%Y-%m-%d %H:%M:%S") if isinstance(f.get("create_time"), datetime) else f.get("create_time"),
                }
                for f in flows
            ],
        }
        return result

    @staticmethod
    def _serialize_operation_log(log: OrderOperationLog) -> Dict[str, Any]:
        """序列化操作日志"""
        return {
            "id": log.id,
            "order_id": log.order_id,
            "out_order_no": log.out_order_no or "",
            "internal_order_no": log.internal_order_no or "",
            "order_status_from": log.order_status_from,
            "order_status_to": log.order_status_to,
            "status_from_label": log.status_from_label or "",
            "status_to_label": log.status_to_label or "",
            "operation_type": log.operation_type,
            "operation_type_label": ORDER_OPERATION_TYPE_LABELS.get(log.operation_type, log.operation_type or ""),
            "operator_id": log.operator_id or 0,
            "operator_name": log.operator_name or "",
            "remark": log.remark or "",
            "create_time": log.create_time.strftime("%Y-%m-%d %H:%M:%S") if log.create_time else None,
        }

    # ── 1. 订单列表查询 ─────────────────────────────────────

    @classmethod
    async def list_orders(
        cls,
        keyword: Optional[str] = None,
        order_status: Optional[int] = None,
        channel_code: Optional[str] = None,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """多条件分页查询订单列表"""
        async with DatabaseManager.get_session() as session:
            # 构建查询条件
            conditions = [Order.is_delete == False]  # noqa: E712

            if keyword:
                keyword_filter = or_(
                    Order.goods_title.ilike(f"%{keyword}%"),
                    Order.out_order_no.ilike(f"%{keyword}%"),
                    Order.internal_order_no.ilike(f"%{keyword}%"),
                )
                conditions.append(keyword_filter)

            if order_status is not None:
                conditions.append(Order.order_status == order_status)

            if channel_code:
                conditions.append(Order.channel_code == channel_code)

            if user_id is not None:
                conditions.append(Order.user_id == user_id)

            if start_time:
                conditions.append(Order.create_time >= start_time)

            if end_time:
                conditions.append(Order.create_time <= end_time)

            # 总数查询
            count_stmt = select(func.count()).select_from(Order).where(and_(*conditions))
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            if total == 0:
                return [], 0

            # 分页查询
            offset = (page - 1) * page_size
            query_stmt = (
                select(Order)
                .where(and_(*conditions))
                .order_by(Order.create_time.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(query_stmt)
            items = list(result.scalars().all())

            return [cls._serialize_order_brief(o) for o in items], total

    # ── 2. 订单详情 ─────────────────────────────────────────

    @classmethod
    async def get_order_detail(cls, order_id: int) -> Optional[Dict[str, Any]]:
        """获取订单详情（含佣金流水，走缓存读穿）"""
        async with DatabaseManager.get_session() as session:
            dao = OrderDAO(session)
            order_dict = await dao.get_order_detail_cached(order_id)
            if order_dict is None:
                return None
            return cls._serialize_order_detail(order_dict)

    # ── 3. 状态流转校验 ─────────────────────────────────────

    @classmethod
    async def validate_transition(
        cls,
        order_id: int,
        target_status: int,
        is_manual_override: bool = False,
    ) -> Dict[str, Any]:
        """校验单个订单状态流转是否合法"""
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            state_machine = B12OrderStateMachineService(order_dao, log_dao)

            # 查询订单获取当前状态
            order = await order_dao.get_by_id(order_id)
            if order is None:
                return {
                    "valid": False,
                    "message": f"订单不存在: order_id={order_id}",
                    "current_status": 0,
                    "current_status_label": "",
                    "allowed_targets": [],
                }

            current_status = int(order.order_status)
            validation = state_machine.validate_transition(
                current_status, target_status, is_manual_override=is_manual_override,
            )

            return {
                "order_id": order_id,
                "out_order_no": order.out_order_no or "",
                "current_status": current_status,
                "current_status_label": ORDER_STATUS_LABELS.get(current_status, "未知"),
                "valid": validation["valid"],
                "message": validation["message"],
                "allowed_targets": validation["allowed_targets"],
                "condition": validation.get("condition", ""),
            }

    # ── 4. 批量校验 ─────────────────────────────────────────

    @classmethod
    async def batch_validate_transition(
        cls,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """批量校验多个订单的状态流转

        Args:
            items: [{"order_id": int, "target_status": int, "is_manual_override": bool}, ...]
        Returns:
            {"total": int, "valid_count": int, "invalid_count": int, "items": [...]}
        """
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            state_machine = B12OrderStateMachineService(order_dao, log_dao)

            result_items = []
            for item in items:
                order_id = item["order_id"]
                target_status = item["target_status"]
                is_manual_override = item.get("is_manual_override", False)

                try:
                    order = await order_dao.get_by_id(order_id)
                    if order is None:
                        result_items.append({
                            "order_id": order_id,
                            "out_order_no": "",
                            "current_status": 0,
                            "current_status_label": "",
                            "valid": False,
                            "message": "订单不存在",
                            "allowed_targets": [],
                        })
                        continue

                    current_status = int(order.order_status)
                    validation = state_machine.validate_transition(
                        current_status, target_status, is_manual_override=is_manual_override,
                    )
                    result_items.append({
                        "order_id": order_id,
                        "out_order_no": order.out_order_no or "",
                        "current_status": current_status,
                        "current_status_label": ORDER_STATUS_LABELS.get(current_status, "未知"),
                        "valid": validation["valid"],
                        "message": validation["message"],
                        "allowed_targets": validation["allowed_targets"],
                    })
                except Exception as e:
                    result_items.append({
                        "order_id": order_id,
                        "out_order_no": "",
                        "current_status": 0,
                        "current_status_label": "",
                        "valid": False,
                        "message": f"校验异常: {str(e)}",
                        "allowed_targets": [],
                    })

            valid_count = sum(1 for r in result_items if r["valid"])
            return {
                "total": len(result_items),
                "valid_count": valid_count,
                "invalid_count": len(result_items) - valid_count,
                "items": result_items,
            }

    # ── 5. 执行状态流转 ─────────────────────────────────────

    @classmethod
    async def execute_transition(
        cls,
        order_id: int,
        target_status: int,
        operation_type: str = OrderOperationType.STATUS_TRANSITION,
        operator_id: int = 0,
        operator_name: str = "",
        remark: str = "",
    ) -> Dict[str, Any]:
        """执行订单状态流转

        委托 B12OrderStateMachineService 完成：
        1. 状态流转校验
        2. 订单状态变更
        3. 写入操作日志
        4. 审计日志（本层负责）
        """
        async with DatabaseManager.get_session() as session:
            order_dao = OrderDAO(session)
            log_dao = OrderOperationLogDAO(session)
            state_machine = B12OrderStateMachineService(order_dao, log_dao)

            # 执行状态流转（内部包含校验、变更、操作日志写入）
            result = await state_machine.transition_order_status(
                order_id=order_id,
                target_status=target_status,
                operation_type=operation_type,
                operator_id=operator_id,
                operator_name=operator_name,
                remark=remark,
            )

            # 审计日志
            await AuditLogger.log(
                action=AUDIT_ACTION_ORDER_TRANSITION,
                target_type="order",
                target_id=order_id,
                details={
                    "order_id": order_id,
                    "target_status": target_status,
                    "operation_type": operation_type,
                    "remark": remark,
                },
                user_id=operator_id,
                user_name=operator_name,
            )

            logger.info(
                "订单状态流转执行成功: order_id=%s, target_status=%s, operator=%s",
                order_id, target_status, operator_name or "system",
            )

            return result

    # ── 6. 查询操作日志 ─────────────────────────────────────

    @classmethod
    async def list_operation_logs(
        cls,
        order_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询指定订单的操作日志（分页）"""
        async with DatabaseManager.get_session() as session:
            dao = OrderOperationLogDAO(session)
            items, total = await dao.list_by_order_id(
                order_id=order_id,
                page=page,
                page_size=page_size,
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [cls._serialize_operation_log(item) for item in items],
            }
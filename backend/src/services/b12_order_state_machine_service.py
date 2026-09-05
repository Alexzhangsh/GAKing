# @ai-generated
"""
B12-1 订单状态机管控服务

职责：
1. 状态流转校验（基于状态机规则，拦截非法状态变更）
2. 状态流转执行（原子化操作 + 自动写入操作日志）
3. 状态批量校验
4. 异常订单巡检逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select

from src.config.b12_constants import (
    MANUAL_OVERRIDEABLE_STATUSES,
    ORDER_OPERATION_TYPE_LABELS,
    ORDER_STATUS_LABELS,
    ORDER_STATUS_TRANSITIONS,
    ORDER_STATUS_TRANSITION_CONDITIONS,
    OrderOperationType,
    TERMINAL_STATUSES,
)
from src.config.constants import OrderStatus
from src.dao.b12_order_operation_log_dao import OrderOperationLogDAO
from src.dao.order_dao import OrderDAO
from src.models.business.b12_order_operation_log import OrderOperationLog
from src.models.business.order_model import Order

logger = logging.getLogger("service.b12_state_machine")


# ════════════════════════════════════════════════════════════
# 序列化工具
# ════════════════════════════════════════════════════════════


def _serialize_order_brief(order: Order) -> Dict[str, Any]:
    """序列化订单摘要"""
    return {
        "id": order.id,
        "out_order_no": order.out_order_no,
        "internal_order_no": order.internal_order_no,
        "order_status": int(order.order_status),
        "order_status_label": ORDER_STATUS_LABELS.get(int(order.order_status), "未知"),
        "channel_code": order.channel_code,
        "user_id": order.user_id,
        "pay_amount": str(order.pay_amount) if order.pay_amount else "0.00",
        "total_commission": str(order.total_commission) if order.total_commission else "0.00",
        "create_time": order.create_time.strftime("%Y-%m-%d %H:%M:%S") if order.create_time else None,
        "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else None,
        "settle_time": order.settle_time.strftime("%Y-%m-%d %H:%M:%S") if order.settle_time else None,
    }


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


# ════════════════════════════════════════════════════════════
# 状态机校验
# ════════════════════════════════════════════════════════════


class B12OrderStateMachineService:
    """订单状态机服务"""

    def __init__(self, order_dao: OrderDAO, log_dao: OrderOperationLogDAO):
        self.order_dao = order_dao
        self.log_dao = log_dao

    # ── 1. 状态流转校验 ──────────────────────────────────

    def validate_transition(
        self,
        current_status: int,
        target_status: int,
        is_manual_override: bool = False,
    ) -> Dict[str, Any]:
        """校验状态流转是否合法

        Args:
            current_status: 当前状态
            target_status: 目标状态
            is_manual_override: 是否人工干预（人工干预可跳过部分终态检查）
        Returns:
            {"valid": bool, "message": str, "allowed_targets": List[int], "condition": str}
        """
        # 检查目标状态是否有效
        if target_status not in OrderStatus._value2member_map_:
            return {
                "valid": False,
                "message": f"非法目标状态值: {target_status}",
                "allowed_targets": list(ORDER_STATUS_TRANSITIONS.get(current_status, set())),
                "condition": "",
            }

        # 获取当前状态允许的目标集合
        allowed_targets = ORDER_STATUS_TRANSITIONS.get(current_status, set())

        # 终态检查
        if current_status in TERMINAL_STATUSES and not is_manual_override:
            return {
                "valid": False,
                "message": f"当前状态为终态({ORDER_STATUS_LABELS.get(current_status, '未知')})，不可再流转",
                "allowed_targets": [],
                "condition": "",
            }

        # 目标状态是否在允许集合中
        if target_status not in allowed_targets:
            allowed_labels = [ORDER_STATUS_LABELS.get(s, str(s)) for s in allowed_targets] if allowed_targets else ["无（终态）"]
            return {
                "valid": False,
                "message": (
                    f"状态流转非法: {ORDER_STATUS_LABELS.get(current_status, str(current_status))} → "
                    f"{ORDER_STATUS_LABELS.get(target_status, str(target_status))}，"
                    f"当前状态允许的目标: {', '.join(allowed_labels)}"
                ),
                "allowed_targets": list(allowed_targets),
                "condition": "",
            }

        # 获取流转条件描述
        condition = ORDER_STATUS_TRANSITION_CONDITIONS.get(
            (OrderStatus(current_status), OrderStatus(target_status)), ""
        )

        return {
            "valid": True,
            "message": (
                f"状态流转合法: {ORDER_STATUS_LABELS.get(current_status, str(current_status))} → "
                f"{ORDER_STATUS_LABELS.get(target_status, str(target_status))}"
            ),
            "allowed_targets": list(allowed_targets),
            "condition": condition,
        }

    # ── 2. 执行状态流转 ──────────────────────────────────

    async def transition_order_status(
        self,
        order_id: int,
        target_status: int,
        operation_type: str = OrderOperationType.STATUS_TRANSITION,
        operator_id: int = 0,
        operator_name: str = "",
        remark: str = "",
    ) -> Dict[str, Any]:
        """执行订单状态流转（原子化操作 + 自动写入操作日志）

        Args:
            order_id: 订单ID
            target_status: 目标状态值
            operation_type: 操作类型
            operator_id: 操作人ID
            operator_name: 操作人名称
            remark: 操作原因
        Returns:
            更新后的订单信息
        Raises:
            ValueError: 订单不存在或状态流转非法
        """
        # 1. 查询订单
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            raise ValueError(f"订单不存在: order_id={order_id}")

        current_status = int(order.order_status)
        target = int(target_status)

        # 2. 状态流转校验
        is_manual = operation_type == OrderOperationType.MANUAL_OVERRIDE
        validation = self.validate_transition(current_status, target, is_manual_override=is_manual)
        if not validation["valid"]:
            raise ValueError(validation["message"])

        # 3. 相同状态不重复操作
        if current_status == target:
            logger.info(
                "订单状态无变化，跳过: order_id=%s, status=%s",
                order_id, current_status,
            )
            return _serialize_order_brief(order)

        # 4. 执行状态变更
        update_data: Dict[str, Any] = {"order_status": target}
        if target == OrderStatus.SETTLED:
            update_data["settle_time"] = datetime.now()
        if target == OrderStatus.FROZEN:
            update_data["pay_time"] = datetime.now()

        updated = await self.order_dao.update_by_id(order_id, update_data)

        # 5. 写入操作日志
        log_data = {
            "order_id": order_id,
            "out_order_no": order.out_order_no or "",
            "internal_order_no": order.internal_order_no or "",
            "order_status_from": current_status,
            "order_status_to": target,
            "status_from_label": ORDER_STATUS_LABELS.get(current_status, ""),
            "status_to_label": ORDER_STATUS_LABELS.get(target, ""),
            "operation_type": operation_type,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "remark": remark or validation["condition"],
        }
        await self.log_dao.create_log(log_data)

        logger.info(
            "订单状态流转成功: order_id=%s, %s(%s) → %s(%s), operator=%s",
            order_id,
            ORDER_STATUS_LABELS.get(current_status, str(current_status)),
            current_status,
            ORDER_STATUS_LABELS.get(target, str(target)),
            target,
            operator_name or "system",
        )

        return _serialize_order_brief(updated)

    # ── 3. 批量校验状态流转 ──────────────────────────────

    async def batch_validate_transitions(
        self,
        order_ids: List[int],
        target_status: int,
    ) -> List[Dict[str, Any]]:
        """批量校验多个订单的状态流转

        Returns:
            [{"order_id": int, "out_order_no": str, "current_status": int,
              "valid": bool, "message": str, "allowed_targets": List[int]}, ...]
        """
        results = []
        for order_id in order_ids:
            try:
                order = await self.order_dao.get_by_id(order_id)
                if order is None:
                    results.append({
                        "order_id": order_id,
                        "out_order_no": "",
                        "current_status": 0,
                        "valid": False,
                        "message": "订单不存在",
                        "allowed_targets": [],
                    })
                    continue

                current_status = int(order.order_status)
                validation = self.validate_transition(current_status, target_status)
                results.append({
                    "order_id": order_id,
                    "out_order_no": order.out_order_no or "",
                    "current_status": current_status,
                    "current_status_label": ORDER_STATUS_LABELS.get(current_status, "未知"),
                    "valid": validation["valid"],
                    "message": validation["message"],
                    "allowed_targets": validation["allowed_targets"],
                })
            except Exception as e:
                results.append({
                    "order_id": order_id,
                    "out_order_no": "",
                    "current_status": 0,
                    "valid": False,
                    "message": f"校验异常: {str(e)}",
                    "allowed_targets": [],
                })
        return results

    # ── 4. 查询订单当前状态信息 ──────────────────────────

    async def get_order_status_info(self, order_id: int) -> Optional[Dict[str, Any]]:
        """查询订单当前状态信息（含合法流转目标）"""
        order = await self.order_dao.get_by_id(order_id)
        if order is None:
            return None

        current_status = int(order.order_status)
        allowed_targets = ORDER_STATUS_TRANSITIONS.get(current_status, set())
        allowed_labels = [
            {"status": s, "label": ORDER_STATUS_LABELS.get(s, str(s))}
            for s in sorted(allowed_targets)
        ]

        result = _serialize_order_brief(order)
        result["allowed_targets"] = allowed_labels
        result["is_terminal"] = current_status in TERMINAL_STATUSES
        result["can_manual_override"] = current_status in MANUAL_OVERRIDEABLE_STATUSES
        return result

    # ── 5. 查询操作日志 ──────────────────────────────────

    async def list_operation_logs(
        self,
        order_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        order_status_from: Optional[int] = None,
        order_status_to: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """多条件分页查询操作日志"""
        items, total = await self.log_dao.list_logs(
            order_id=order_id,
            operation_type=operation_type,
            operator_id=operator_id,
            start_time=start_time,
            end_time=end_time,
            order_status_from=order_status_from,
            order_status_to=order_status_to,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_operation_log(item) for item in items],
        }

    # ── 6. 异常订单巡检逻辑 ──────────────────────────────

    async def patrol_anomaly_orders(
        self,
    ) -> Dict[str, Any]:
        """订单异常巡检

        检查项：
        1. 统计当日新增异常状态订单（INVALID/REFUNDED）
        2. 检查状态异常的订单（长时间停留在非终态但应流转的订单）
        3. 按异常原因分组统计

        Returns:
            {"status": str, "today_anomaly_count": int,
             "pending_frozen_count": int, "pending_settled_count": int,
             "details": Dict[str, int]}
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            # 统计当日新增的异常状态订单（INVALID + REFUNDED）
            invalid_count = 0
            refunded_count = 0
            invalid_stmt = (
                select(Order)
                .where(
                    Order.order_status == int(OrderStatus.INVALID),
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time >= today_start,
                )
            )
            result = await self.order_dao.session.execute(invalid_stmt)
            invalid_count = len(result.scalars().all())

            refunded_stmt = (
                select(Order)
                .where(
                    Order.order_status == int(OrderStatus.REFUNDED),
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time >= today_start,
                )
            )
            result = await self.order_dao.session.execute(refunded_stmt)
            refunded_count = len(result.scalars().all())

            today_anomaly = invalid_count + refunded_count

            # 统计当前待处理的冻结订单（FROZEN状态超过3天）
            three_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            three_days_ago = three_days_ago.replace(day=three_days_ago.day - 3) if three_days_ago.day > 3 else three_days_ago
            # 简单处理：使用 timedelta
            three_days_ago = datetime.now() - timedelta(days=3)

            frozen_stmt = (
                select(func.count())
                .select_from(Order)
                .where(
                    Order.order_status == int(OrderStatus.FROZEN),
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time < three_days_ago,
                )
            )
            result = await self.order_dao.session.execute(frozen_stmt)
            pending_frozen_count = result.scalar() or 0

            # 统计当前待结算的订单（SETTLABLE状态超过7天）
            seven_days_ago = datetime.now() - timedelta(days=7)
            settlable_stmt = (
                select(func.count())
                .select_from(Order)
                .where(
                    Order.order_status == int(OrderStatus.SETTLABLE),
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time < seven_days_ago,
                )
            )
            result = await self.order_dao.session.execute(settlable_stmt)
            pending_settled_count = result.scalar() or 0

            # 构建异常详情
            details = {
                "invalid_count": invalid_count,
                "refunded_count": refunded_count,
                "pending_frozen_count": pending_frozen_count,
                "pending_settled_count": pending_settled_count,
            }

            logger.info(
                "订单异常巡检完成: 当日新增异常=%s, 超时冻结=%s, 超时可结算=%s",
                today_anomaly, pending_frozen_count, pending_settled_count,
            )

            return {
                "status": "success",
                "today_anomaly_count": today_anomaly,
                "pending_frozen_count": pending_frozen_count,
                "pending_settled_count": pending_settled_count,
                "details": details,
            }

        except Exception as e:
            logger.error("订单异常巡检失败: %s", e)
            return {
                "status": "failed",
                "today_anomaly_count": 0,
                "pending_frozen_count": 0,
                "pending_settled_count": 0,
                "details": {},
                "error": str(e),
            }
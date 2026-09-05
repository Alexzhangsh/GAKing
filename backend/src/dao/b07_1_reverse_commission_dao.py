# @ai-generated
"""
B07-1 逆向佣金冲减 DAO（新建文件，不修改 B01-B15 及 B06 任何基线 DAO）

包含：
1. ReverseCommissionRecordDAO - 冲减记录数据访问
2. ReverseCommissionQueryDAO - 退款订单查询（只读）
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.config.b07_1_constants import (
    MAX_RETRY_COUNT,
    ReverseCommissionStatus,
)
from src.config.constants import OrderStatus
from src.dao.base_dao import BaseDAO
from src.models.business.b07_1_reverse_commission_record import ReverseCommissionRecord
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order

logger = logging.getLogger("dao.b07_1_reverse_commission")


# ════════════════════════════════════════════════════════════
# 1. 冲减记录 DAO
# ════════════════════════════════════════════════════════════


class ReverseCommissionRecordDAO(BaseDAO):
    """逆向佣金冲减记录 DAO"""

    model_class = ReverseCommissionRecord

    async def create_record(
        self,
        order_id: int,
        out_order_no: str,
        user_id: int,
        channel_code: str,
        original_commission: Decimal,
        flow_type: str,
        flow_transfer_status: str,
        operator_id: int = 0,
        operator_name: str = "",
        remark: str = "",
    ) -> ReverseCommissionRecord:
        """创建逆向冲减记录（初始状态 IDENTIFIED）"""
        data = {
            "order_id": order_id,
            "out_order_no": out_order_no,
            "user_id": user_id,
            "channel_code": channel_code,
            "original_commission": original_commission,
            "deducted_amount": Decimal("0.00"),
            "flow_type": flow_type,
            "flow_transfer_status": flow_transfer_status,
            "status": ReverseCommissionStatus.IDENTIFIED.value,
            "retry_count": 0,
            "max_retry": MAX_RETRY_COUNT,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "remark": remark,
        }
        return await self.create(data)

    async def update_status(
        self,
        record_id: int,
        status: str,
        deducted_amount: Optional[Decimal] = None,
        deduct_flow_id: Optional[int] = None,
        error_message: str = "",
        operator_id: Optional[int] = None,
        operator_name: str = "",
        remark: str = "",
    ) -> Optional[ReverseCommissionRecord]:
        """更新冲减记录状态"""
        update_data = {
            "status": status,
        }
        if deducted_amount is not None:
            update_data["deducted_amount"] = deducted_amount
        if deduct_flow_id is not None:
            update_data["deduct_flow_id"] = deduct_flow_id
        if error_message:
            update_data["error_message"] = error_message[:2000] if error_message else ""
        if operator_id is not None:
            update_data["operator_id"] = operator_id
        if operator_name:
            update_data["operator_name"] = operator_name
        if remark:
            update_data["remark"] = remark

        # 设置时间戳
        now = datetime.now()
        if status == ReverseCommissionStatus.FROZEN.value:
            update_data["frozen_at"] = now
        elif status in (ReverseCommissionStatus.CLAWBACK_DONE.value, ReverseCommissionStatus.FAILED.value):
            update_data["clawback_at"] = now

        return await self.update_by_id(record_id, update_data)

    async def increment_retry(
        self, record_id: int, error_message: str,
    ) -> Optional[ReverseCommissionRecord]:
        """递增重试次数"""
        record = await self.get_by_id(record_id)
        if record is None:
            return None
        new_retry = (record.retry_count or 0) + 1
        return await self.update_by_id(record_id, {
            "retry_count": new_retry,
            "error_message": error_message[:2000] if error_message else "",
            "clawback_at": datetime.now(),
        })

    async def list_by_status(
        self,
        status: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReverseCommissionRecord]:
        """按状态查询冲减记录"""
        stmt = (
            self._active_query()
            .where(ReverseCommissionRecord.status == status)
            .order_by(ReverseCommissionRecord.create_time.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_retryable(
        self,
        limit: int = 50,
    ) -> List[ReverseCommissionRecord]:
        """查询可重试的失败记录（重试次数未超限）"""
        stmt = (
            self._active_query()
            .where(
                and_(
                    ReverseCommissionRecord.status == ReverseCommissionStatus.FAILED.value,
                    ReverseCommissionRecord.retry_count < ReverseCommissionRecord.max_retry,
                )
            )
            .order_by(ReverseCommissionRecord.create_time.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_filters(
        self,
        status: Optional[str] = None,
        channel_code: Optional[str] = None,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReverseCommissionRecord], int]:
        """多条件分页查询冲减记录"""
        conditions = [ReverseCommissionRecord.is_delete == False]  # noqa: E712
        if status:
            conditions.append(ReverseCommissionRecord.status == status)
        if channel_code:
            conditions.append(ReverseCommissionRecord.channel_code == channel_code)
        if user_id is not None:
            conditions.append(ReverseCommissionRecord.user_id == user_id)
        if order_id is not None:
            conditions.append(ReverseCommissionRecord.order_id == order_id)
        if start_time:
            conditions.append(ReverseCommissionRecord.create_time >= start_time)
        if end_time:
            conditions.append(ReverseCommissionRecord.create_time < end_time)

        stmt = select(ReverseCommissionRecord).where(and_(*conditions))

        # 总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(ReverseCommissionRecord.create_time.desc())
            .offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def exists_by_order_id(self, order_id: int) -> bool:
        """检查订单是否已有冲减记录"""
        stmt = self._active_query().where(
            and_(
                ReverseCommissionRecord.order_id == order_id,
                ReverseCommissionRecord.status != ReverseCommissionStatus.FAILED.value,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count_by_status(self, status: str) -> int:
        """统计指定状态的记录数"""
        stmt = select(func.count()).select_from(ReverseCommissionRecord).where(
            and_(
                ReverseCommissionRecord.is_delete == False,  # noqa: E712
                ReverseCommissionRecord.status == status,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


# ════════════════════════════════════════════════════════════
# 2. 退款订单查询 DAO（只读）
# ════════════════════════════════════════════════════════════


class ReverseCommissionQueryDAO:
    """退款订单查询 DAO（只读）"""

    def __init__(self, session):
        self.session = session

    async def list_refunded_orders_without_record(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """查询已退款但尚未生成冲减记录的订单

        LEFT JOIN 排除已有冲减记录的订单，避免重复处理。
        """
        stmt = (
            select(Order)
            .outerjoin(
                ReverseCommissionRecord,
                and_(
                    Order.id == ReverseCommissionRecord.order_id,
                    ReverseCommissionRecord.is_delete == False,  # noqa: E712
                ),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.order_status == int(OrderStatus.REFUNDED),
                    Order.user_commission > 0,
                    ReverseCommissionRecord.id.is_(None),
                )
            )
            .order_by(Order.create_time.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_refunded_orders_without_record(self) -> int:
        """统计待处理的退款订单数"""
        stmt = (
            select(func.count())
            .select_from(Order)
            .outerjoin(
                ReverseCommissionRecord,
                and_(
                    Order.id == ReverseCommissionRecord.order_id,
                    ReverseCommissionRecord.is_delete == False,  # noqa: E712
                ),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.order_status == int(OrderStatus.REFUNDED),
                    Order.user_commission > 0,
                    ReverseCommissionRecord.id.is_(None),
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_commission_flows_by_order_id(
        self, order_id: int,
    ) -> List[CommissionFlow]:
        """查询订单关联的佣金流水"""
        stmt = (
            select(CommissionFlow)
            .where(
                and_(
                    CommissionFlow.is_delete == False,  # noqa: E712
                    CommissionFlow.order_id == order_id,
                )
            )
            .order_by(CommissionFlow.create_time.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
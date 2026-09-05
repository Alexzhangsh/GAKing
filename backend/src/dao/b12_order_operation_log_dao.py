# @ai-generated
"""
B12-1 订单操作日志 DAO
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.b12_order_operation_log import OrderOperationLog

logger = logging.getLogger("dao.b12_order_operation_log")


class OrderOperationLogDAO(BaseDAO):
    """订单操作日志 DAO"""

    model_class = OrderOperationLog

    async def create_log(self, data: Dict[str, Any]) -> OrderOperationLog:
        """创建操作日志"""
        return await self.create(data)

    async def list_by_order_id(
        self,
        order_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[OrderOperationLog], int]:
        """按订单ID查询操作日志（分页）"""
        conditions = [OrderOperationLog.order_id == order_id]

        count_stmt = select(func.count()).select_from(OrderOperationLog).where(
            and_(OrderOperationLog.is_delete == False, *conditions)  # noqa: E712
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size
        stmt = (
            self._active_query()
            .where(and_(*conditions))
            .order_by(OrderOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def list_logs(
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
    ) -> Tuple[List[OrderOperationLog], int]:
        """多条件分页查询操作日志"""
        conditions = []
        if order_id:
            conditions.append(OrderOperationLog.order_id == order_id)
        if operation_type:
            conditions.append(OrderOperationLog.operation_type == operation_type)
        if operator_id:
            conditions.append(OrderOperationLog.operator_id == operator_id)
        if start_time:
            conditions.append(OrderOperationLog.create_time >= start_time)
        if end_time:
            conditions.append(OrderOperationLog.create_time < end_time)
        if order_status_from:
            conditions.append(OrderOperationLog.order_status_from == order_status_from)
        if order_status_to:
            conditions.append(OrderOperationLog.order_status_to == order_status_to)

        count_stmt = select(func.count()).select_from(OrderOperationLog).where(
            and_(OrderOperationLog.is_delete == False, *conditions)  # noqa: E712
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size
        stmt = (
            self._active_query()
            .where(and_(*conditions))
            .order_by(OrderOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def count_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        operation_type: Optional[str] = None,
    ) -> int:
        """统计指定时间范围内的操作日志数量"""
        conditions = [
            OrderOperationLog.create_time >= start_time,
            OrderOperationLog.create_time < end_time,
        ]
        if operation_type:
            conditions.append(OrderOperationLog.operation_type == operation_type)

        stmt = select(func.count()).select_from(OrderOperationLog).where(
            and_(OrderOperationLog.is_delete == False, *conditions)  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
# @ai-generated
"""
退款操作日志 DAO（B05-6 新建）
继承 BaseDAO；提供创建日志、按订单查询、多条件筛选能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.order_refund_operation_log_model import (
    OrderRefundOperationLog,
)

logger = logging.getLogger("dao.order_refund_operation_log")


class OrderRefundOperationLogDAO(BaseDAO):
    """退款操作日志 DAO"""

    model_class = OrderRefundOperationLog

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 创建日志 ────────────────────────────────────────

    async def create_log(
        self,
        order_id: int,
        operator_id: int,
        operation_type: str,
        order_status_before: int,
        order_status_after: int,
        deduct_amount: Decimal,
        flow_type: str,
        flow_transfer_status: str,
        old_available_balance: Decimal,
        new_available_balance: Decimal,
        old_total_balance: Decimal,
        new_total_balance: Decimal,
        deduct_flow_id: Optional[int] = None,
        remark: str = "",
    ) -> OrderRefundOperationLog:
        """创建退款操作日志记录

        Args:
            order_id: 订单ID
            operator_id: 操作人管理员ID
            operation_type: 操作类型（DEDUCT）
            order_status_before: 变更前订单状态
            order_status_after: 变更后订单状态
            deduct_amount: 扣减金额(元)
            flow_type: 原始流水类型
            flow_transfer_status: 原始流水转账状态
            old_available_balance: 变更前可用余额
            new_available_balance: 变更后可用余额
            old_total_balance: 变更前累计佣金
            new_total_balance: 变更后累计佣金
            deduct_flow_id: 关联扣减流水ID
            remark: 备注说明
        Returns:
            新建的 OrderRefundOperationLog 实例
        """
        log = OrderRefundOperationLog(
            order_id=order_id,
            operator_id=operator_id,
            operation_type=operation_type,
            order_status_before=order_status_before,
            order_status_after=order_status_after,
            deduct_amount=deduct_amount,
            flow_type=flow_type,
            flow_transfer_status=flow_transfer_status,
            old_available_balance=old_available_balance,
            new_available_balance=new_available_balance,
            old_total_balance=old_total_balance,
            new_total_balance=new_total_balance,
            deduct_flow_id=deduct_flow_id,
            remark=remark,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    # ── 按订单查询 ──────────────────────────────────────

    async def list_by_order_id(
        self,
        order_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[OrderRefundOperationLog], int]:
        """按订单ID查询退款操作日志（按创建时间降序）

        Args:
            order_id: 订单ID
            page: 页码
            page_size: 每页条数
        Returns:
            (日志列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        stmt = (
            self._active_query()
            .where(OrderRefundOperationLog.order_id == order_id)
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(OrderRefundOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── 多条件查询 ──────────────────────────────────────

    async def list_with_filters(
        self,
        *,
        order_id: Optional[int] = None,
        operator_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[OrderRefundOperationLog], int]:
        """多条件分页查询退款操作日志（后台审计用）

        Args:
            order_id: 订单ID筛选
            operator_id: 操作人ID筛选
            operation_type: 操作类型筛选（DEDUCT）
            start_time: 创建时间起始
            end_time: 创建时间截止
            page: 页码
            page_size: 每页条数
        Returns:
            (日志列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if order_id is not None:
            conditions.append(OrderRefundOperationLog.order_id == order_id)
        if operator_id is not None:
            conditions.append(OrderRefundOperationLog.operator_id == operator_id)
        if operation_type is not None:
            conditions.append(
                OrderRefundOperationLog.operation_type == operation_type
            )
        if start_time is not None:
            conditions.append(OrderRefundOperationLog.create_time >= start_time)
        if end_time is not None:
            conditions.append(OrderRefundOperationLog.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(OrderRefundOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total
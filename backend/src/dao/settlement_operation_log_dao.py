# @ai-generated
"""
佣金结算操作日志 DAO（B12 新建）
继承 BaseDAO；提供按结算单查询操作历史、多条件筛选分页能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.settlement_operation_log_model import SettlementOperationLog

logger = logging.getLogger("dao.settlement_operation_log")


class SettlementOperationLogDAO(BaseDAO):
    """佣金结算操作日志 DAO"""

    model_class = SettlementOperationLog

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 操作历史查询 ────────────────────────────────────

    async def list_by_settlement_id(
        self,
        settlement_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SettlementOperationLog], int]:
        """按结算单ID查询操作历史（按创建时间升序，便于追溯流程）

        Args:
            settlement_id: 结算单ID
            page: 页码
            page_size: 每页条数
        Returns:
            (日志列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        stmt = self._active_query().where(
            SettlementOperationLog.settlement_id == settlement_id
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(SettlementOperationLog.create_time.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_with_filters(
        self,
        *,
        settlement_id: Optional[int] = None,
        order_id: Optional[int] = None,
        action: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[SettlementOperationLog], int]:
        """多条件分页查询结算操作日志（后台审计/导出用）

        Args:
            settlement_id: 结算单ID筛选
            order_id: 订单ID筛选
            action: 操作类型筛选（CREATE_SETTLEMENT/FREEZE/UNFREEZE/MARK_PAID）
            operator_id: 操作人ID筛选
            start_time: 创建时间起始（含）
            end_time: 创建时间截止（不含）
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
        if settlement_id is not None:
            conditions.append(SettlementOperationLog.settlement_id == settlement_id)
        if order_id is not None:
            conditions.append(SettlementOperationLog.order_id == order_id)
        if action is not None:
            conditions.append(SettlementOperationLog.action == action)
        if operator_id is not None:
            conditions.append(SettlementOperationLog.operator_id == operator_id)
        if start_time is not None:
            conditions.append(SettlementOperationLog.create_time >= start_time)
        if end_time is not None:
            conditions.append(SettlementOperationLog.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(SettlementOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

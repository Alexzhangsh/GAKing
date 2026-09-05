# @ai-generated
"""
佣金结算单 DAO（B12 新建）
继承 BaseDAO；提供按订单/单号查询、定时任务待处理查询、后台分页筛选、超期预警、汇总能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.b12_constants import SettlementStatus
from src.config.constants import OrderStatus
from src.dao.base_dao import BaseDAO
from src.models.business.order_model import Order
from src.models.business.settlement_record_model import SettlementRecord

logger = logging.getLogger("dao.settlement_record")


class SettlementRecordDAO(BaseDAO):
    """佣金结算单 DAO"""

    model_class = SettlementRecord

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 基础查询 ────────────────────────────────────────

    async def get_by_order_id(self, order_id: int) -> Optional[SettlementRecord]:
        """按订单ID查询结算单（自动过滤软删除）

        Args:
            order_id: 订单ID
        Returns:
            结算单实例 或 None
        """
        stmt = self._active_query().where(SettlementRecord.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_settlement_no(
        self, settlement_no: str
    ) -> Optional[SettlementRecord]:
        """按结算单号查询"""
        stmt = self._active_query().where(
            SettlementRecord.settlement_no == settlement_no
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, item_id: int) -> Optional[SettlementRecord]:
        """按主键ID查询结算单"""
        return await super().get_by_id(item_id)

    # ── 定时任务待处理查询 ────────────────────────────────

    async def list_settlable_orders_without_settlement(
        self,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Order], int]:
        """查询 SETTLABLE(30) 状态且无结算单的订单（定时任务冻结入账用）

        SQL 语义：
            SELECT o.* FROM orders o
            WHERE o.order_status = 30 AND o.is_delete = 0
              AND NOT EXISTS (SELECT 1 FROM settlement_record s
                              WHERE s.order_id = o.id AND s.is_delete = 0)
            ORDER BY o.update_time ASC

        Args:
            page: 页码
            page_size: 每页条数
        Returns:
            (订单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 200

        has_settlement = (
            select(SettlementRecord.id)
            .where(
                and_(
                    SettlementRecord.order_id == Order.id,
                    SettlementRecord.is_delete == False,  # noqa: E712
                )
            )
            .exists()
        )

        stmt = (
            select(Order)
            .where(
                and_(
                    Order.order_status == int(OrderStatus.SETTLABLE),
                    Order.is_delete == False,  # noqa: E712
                    ~has_settlement,  # NOT EXISTS：无结算单
                )
            )
            .order_by(Order.update_time.asc())
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def list_settled_pending_unfreeze(
        self,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[SettlementRecord], int]:
        """查询订单已 SETTLED(40) 但结算单仍 SETTLABLE 态的记录（定时任务解冻转可用用）

        SQL 语义：
            SELECT s.* FROM settlement_record s
            JOIN orders o ON o.id = s.order_id
            WHERE o.order_status = 40 AND s.settlement_status = 'SETTLABLE'
              AND s.is_delete = 0 AND o.is_delete = 0
            ORDER BY o.settle_time ASC NULLS LAST

        Args:
            page: 页码
            page_size: 每页条数
        Returns:
            (结算单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 200

        stmt = (
            select(SettlementRecord)
            .join(Order, Order.id == SettlementRecord.order_id)
            .where(
                and_(
                    Order.order_status == int(OrderStatus.SETTLED),
                    Order.is_delete == False,  # noqa: E712
                    SettlementRecord.settlement_status
                    == SettlementStatus.SETTLABLE.value,
                    SettlementRecord.is_delete == False,  # noqa: E712
                )
            )
            .order_by(Order.settle_time.asc())
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    # ── 后台分页筛选查询 ────────────────────────────────

    async def list_with_filters(
        self,
        *,
        settlement_no: Optional[str] = None,
        order_id: Optional[int] = None,
        user_id: Optional[int] = None,
        channel_code: Optional[str] = None,
        settlement_status: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[SettlementRecord], int]:
        """多条件分页查询结算单（后台审计/导出用）

        Args:
            settlement_no: 结算单号筛选
            order_id: 订单ID筛选
            user_id: 用户ID筛选
            channel_code: 渠道筛选
            settlement_status: 结算单状态筛选
            min_amount: 用户佣金下限
            max_amount: 用户佣金上限
            start_time: 创建时间起始（含）
            end_time: 创建时间截止（不含）
            page: 页码
            page_size: 每页条数
        Returns:
            (结算单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if settlement_no is not None:
            conditions.append(SettlementRecord.settlement_no == settlement_no)
        if order_id is not None:
            conditions.append(SettlementRecord.order_id == order_id)
        if user_id is not None:
            conditions.append(SettlementRecord.user_id == user_id)
        if channel_code is not None:
            conditions.append(SettlementRecord.channel_code == channel_code)
        if settlement_status is not None:
            conditions.append(SettlementRecord.settlement_status == settlement_status)
        if min_amount is not None:
            conditions.append(SettlementRecord.user_commission >= min_amount)
        if max_amount is not None:
            conditions.append(SettlementRecord.user_commission <= max_amount)
        if start_time is not None:
            conditions.append(SettlementRecord.create_time >= start_time)
        if end_time is not None:
            conditions.append(SettlementRecord.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(SettlementRecord.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    # ── 超期预警查询 ────────────────────────────────────

    async def list_overdue_settlable(
        self,
        delay_days: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SettlementRecord], int]:
        """查询超期未解冻的结算单（SETTLABLE 态超过 delay_days 天未转 SETTLED）

        用于后台预警：渠道返佣长期未到账的订单，提醒运营人工核查。
        判定条件：settlement_status=SETTLABLE 且 confirm_time < now - delay_days

        Args:
            delay_days: 超期阈值天数
            page: 页码
            page_size: 每页条数
        Returns:
            (结算单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        cutoff = datetime.now() - timedelta(days=delay_days)
        stmt = self._active_query().where(
            and_(
                SettlementRecord.settlement_status == SettlementStatus.SETTLABLE.value,
                SettlementRecord.confirm_time.isnot(None),
                SettlementRecord.confirm_time < cutoff,
            )
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(SettlementRecord.confirm_time.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    # ── 汇总查询 ────────────────────────────────────────

    async def sum_commission_by_status(
        self,
        settlement_status: Optional[str] = None,
    ) -> Decimal:
        """按状态汇总用户佣金总额（SQL SUM 聚合）

        Args:
            settlement_status: 结算单状态筛选，None 表示全部
        Returns:
            聚合金额 (Decimal)，无记录返回 Decimal("0")
        """
        stmt = select(
            func.coalesce(func.sum(SettlementRecord.user_commission), 0)
        ).where(
            SettlementRecord.is_delete == False  # noqa: E712
        )
        if settlement_status is not None:
            stmt = stmt.where(SettlementRecord.settlement_status == settlement_status)
        result = await self.session.execute(stmt)
        total = result.scalar()
        return Decimal(str(total)) if total is not None else Decimal("0")

    async def sum_commission_by_user(
        self,
        user_id: int,
        settlement_status: Optional[str] = None,
    ) -> Decimal:
        """按用户汇总佣金总额

        Args:
            user_id: 用户ID
            settlement_status: 结算单状态筛选，None 表示全部
        Returns:
            聚合金额 (Decimal)
        """
        stmt = select(
            func.coalesce(func.sum(SettlementRecord.user_commission), 0)
        ).where(
            and_(
                SettlementRecord.user_id == user_id,
                SettlementRecord.is_delete == False,  # noqa: E712
            )
        )
        if settlement_status is not None:
            stmt = stmt.where(SettlementRecord.settlement_status == settlement_status)
        result = await self.session.execute(stmt)
        total = result.scalar()
        return Decimal(str(total)) if total is not None else Decimal("0")

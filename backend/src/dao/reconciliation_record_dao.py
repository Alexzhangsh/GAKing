# @ai-generated
"""
全链路对账批次 DAO（B13 新建）
继承 BaseDAO；提供对账批次 CRUD、分页筛选、按日期查询、状态更新能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.reconciliation_record_model import ReconciliationRecord

logger = logging.getLogger("dao.reconciliation_record")


class ReconciliationRecordDAO(BaseDAO):
    """全链路对账批次 DAO"""

    model_class = ReconciliationRecord

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 基础查询 ────────────────────────────────────────

    async def get_by_id(self, item_id: int) -> Optional[ReconciliationRecord]:
        """按主键ID查询对账批次"""
        return await super().get_by_id(item_id)

    async def get_by_reconciliation_no(
        self, reconciliation_no: str
    ) -> Optional[ReconciliationRecord]:
        """按对账批次号查询"""
        stmt = self._active_query().where(
            ReconciliationRecord.reconciliation_no == reconciliation_no
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_date(self, reconcile_date: date) -> Optional[ReconciliationRecord]:
        """按对账日期查询最近一次对账记录（用于幂等判断）"""
        stmt = (
            self._active_query()
            .where(ReconciliationRecord.reconcile_date == reconcile_date)
            .order_by(ReconciliationRecord.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 写操作 ────────────────────────────────────────

    async def create(self, data: Dict[str, Any]) -> ReconciliationRecord:
        """创建对账批次记录"""
        return await super().create(data)

    async def update_by_id(
        self, item_id: int, data: Dict[str, Any]
    ) -> Optional[ReconciliationRecord]:
        """按ID更新对账批次"""
        return await super().update_by_id(item_id, data)

    # ── 后台分页查询 ────────────────────────────────────

    async def list_with_filters(
        self,
        reconciliation_no: Optional[str] = None,
        reconcile_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReconciliationRecord], int]:
        """多条件分页查询对账批次

        Args:
            reconciliation_no: 批次号筛选
            reconcile_type: 对账类型 DAILY/MANUAL
            status: 对账状态 PENDING/RUNNING/SUCCESS/PARTIAL/FAILED
            start_date: 对账日期起始（含）
            end_date: 对账日期截止（含）
            page: 页码
            page_size: 每页条数
        Returns:
            (records, total)
        """
        conditions = []
        if reconciliation_no:
            conditions.append(
                ReconciliationRecord.reconciliation_no == reconciliation_no
            )
        if reconcile_type:
            conditions.append(ReconciliationRecord.reconcile_type == reconcile_type)
        if status:
            conditions.append(ReconciliationRecord.status == status)
        if start_date:
            conditions.append(ReconciliationRecord.reconcile_date >= start_date)
        if end_date:
            conditions.append(ReconciliationRecord.reconcile_date <= end_date)

        base = self._active_query()
        if conditions:
            base = base.where(and_(*conditions))

        # 总数
        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # 分页数据
        stmt = (
            base.order_by(ReconciliationRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        return records, total

    # ── 告警统计 ────────────────────────────────────────

    async def list_recent_unresolved(
        self, days: int = 7, limit: int = 10
    ) -> List[ReconciliationRecord]:
        """查询近 N 天有差异的对账批次（告警面板用）"""
        from sqlalchemy import func

        cutoff = datetime.now()
        stmt = (
            self._active_query()
            .where(
                and_(
                    ReconciliationRecord.create_time <= cutoff,
                    ReconciliationRecord.diff_count > 0,
                )
            )
            .order_by(ReconciliationRecord.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

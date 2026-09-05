# @ai-generated
"""
全链路对账差异明细 DAO（B13 新建）
继承 BaseDAO；提供差异明细 CRUD、分页筛选、按批次/用户查询、复核状态更新能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.reconciliation_diff_model import ReconciliationDiff

logger = logging.getLogger("dao.reconciliation_diff")


class ReconciliationDiffDAO(BaseDAO):
    """全链路对账差异明细 DAO"""

    model_class = ReconciliationDiff

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 基础查询 ────────────────────────────────────────

    async def get_by_id(self, item_id: int) -> Optional[ReconciliationDiff]:
        """按主键ID查询差异明细"""
        return await super().get_by_id(item_id)

    async def list_by_reconciliation_id(
        self,
        reconciliation_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ReconciliationDiff], int]:
        """按对账批次ID分页查询差异明细"""
        base = self._active_query().where(
            ReconciliationDiff.reconciliation_id == reconciliation_id
        )
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            base.order_by(ReconciliationDiff.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        return records, total

    async def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[ReconciliationDiff], int]:
        """按用户ID分页查询差异明细"""
        base = self._active_query().where(ReconciliationDiff.user_id == user_id)
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            base.order_by(ReconciliationDiff.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        return records, total

    # ── 写操作 ────────────────────────────────────────

    async def create(self, data: Dict[str, Any]) -> ReconciliationDiff:
        """创建差异明细"""
        return await super().create(data)

    async def batch_create(
        self, data_list: List[Dict[str, Any]]
    ) -> List[ReconciliationDiff]:
        """批量创建差异明细"""
        return await super().batch_create(data_list)

    async def update_by_id(
        self, item_id: int, data: Dict[str, Any]
    ) -> Optional[ReconciliationDiff]:
        """按ID更新差异明细（复核调平用）"""
        return await super().update_by_id(item_id, data)

    # ── 后台多条件分页查询 ────────────────────────────────

    async def list_with_filters(
        self,
        reconciliation_id: Optional[int] = None,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        diff_type: Optional[str] = None,
        status: Optional[str] = None,
        alert_level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReconciliationDiff], int]:
        """多条件分页查询差异明细（后台筛选/导出用）

        Args:
            reconciliation_id: 对账批次ID筛选
            user_id: 用户ID筛选
            order_id: 订单ID筛选
            diff_type: 差异类型筛选
            status: 复核状态筛选 PENDING/REVIEWING/RESOLVED/IGNORED
            alert_level: 告警级别筛选 INFO/WARNING/CRITICAL
            start_time: 创建时间起始（含）
            end_time: 创建时间截止（不含）
            page: 页码
            page_size: 每页条数
        Returns:
            (diffs, total)
        """
        conditions = []
        if reconciliation_id:
            conditions.append(ReconciliationDiff.reconciliation_id == reconciliation_id)
        if user_id:
            conditions.append(ReconciliationDiff.user_id == user_id)
        if order_id:
            conditions.append(ReconciliationDiff.order_id == order_id)
        if diff_type:
            conditions.append(ReconciliationDiff.diff_type == diff_type)
        if status:
            conditions.append(ReconciliationDiff.status == status)
        if alert_level:
            conditions.append(ReconciliationDiff.alert_level == alert_level)
        if start_time:
            conditions.append(ReconciliationDiff.create_time >= start_time)
        if end_time:
            conditions.append(ReconciliationDiff.create_time < end_time)

        base = self._active_query()
        if conditions:
            base = base.where(and_(*conditions))

        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            base.order_by(ReconciliationDiff.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        return records, total

    # ── 统计 ────────────────────────────────────────

    async def count_by_reconciliation(self, reconciliation_id: int) -> Dict[str, int]:
        """统计指定对账批次的差异分布（按状态/告警级别）"""
        base = self._active_query().where(
            ReconciliationDiff.reconciliation_id == reconciliation_id
        )
        # 按状态统计
        status_stmt = (
            select(ReconciliationDiff.status, func.count())
            .where(
                and_(
                    ReconciliationDiff.reconciliation_id == reconciliation_id,
                    ReconciliationDiff.is_delete == False,  # noqa: E712
                )
            )
            .group_by(ReconciliationDiff.status)
        )
        status_result = await self.session.execute(status_stmt)
        status_map = {row[0]: row[1] for row in status_result.fetchall()}

        # 按告警级别统计
        level_stmt = (
            select(ReconciliationDiff.alert_level, func.count())
            .where(
                and_(
                    ReconciliationDiff.reconciliation_id == reconciliation_id,
                    ReconciliationDiff.is_delete == False,  # noqa: E712
                )
            )
            .group_by(ReconciliationDiff.alert_level)
        )
        level_result = await self.session.execute(level_stmt)
        level_map = {row[0]: row[1] for row in level_result.fetchall()}

        return {
            "total": sum(status_map.values()),
            "by_status": status_map,
            "by_alert_level": level_map,
            "pending": status_map.get("PENDING", 0),
            "critical": level_map.get("CRITICAL", 0),
        }

    # ── B17 渠道对账差异查询 ────────────────────────

    async def list_channel_diffs(
        self,
        channel_code: Optional[str] = None,
        diff_type: Optional[str] = None,
        status: Optional[str] = None,
        alert_level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """渠道对账差异分页查询（按渠道筛选）

        仅查询 CHANNEL_* 类型差异（B17 渠道对账产生的差异）。
        """
        conditions = [
            ReconciliationDiff.is_delete == False,  # noqa: E712
            ReconciliationDiff.diff_type.like("CHANNEL_%"),
        ]
        if channel_code:
            conditions.append(ReconciliationDiff.channel_code == channel_code)
        if diff_type:
            conditions.append(ReconciliationDiff.diff_type == diff_type)
        if status:
            conditions.append(ReconciliationDiff.status == status)
        if alert_level:
            conditions.append(ReconciliationDiff.alert_level == alert_level)

        base = self._active_query().where(and_(*conditions))

        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            base.order_by(ReconciliationDiff.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        return {
            "list": [r.to_dict() for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def summary_channel_diffs(
        self,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """渠道对账差异汇总（按渠道分组统计）

        Returns:
            {
                "channels": {
                    "myq": {"diff_count": 5, "pending_count": 3,
                            "critical_count": 1, "diff_amount": "12.34"},
                    "orderx": {...}
                },
                "total": {"diff_count": 8, "pending_count": 5,
                          "critical_count": 2, "diff_amount": "20.00"}
            }
        """
        conditions = [
            ReconciliationDiff.is_delete == False,  # noqa: E712
            ReconciliationDiff.diff_type.like("CHANNEL_%"),
        ]
        if start_date:
            conditions.append(ReconciliationDiff.create_time >= datetime.combine(
                start_date, datetime.min.time()
            ))
        if end_date:
            conditions.append(ReconciliationDiff.create_time < datetime.combine(
                end_date + timedelta(days=1),
                datetime.min.time(),
            ))

        # 按渠道统计差异数量/金额/状态
        stmt = (
            select(
                ReconciliationDiff.channel_code,
                func.count(ReconciliationDiff.id),
                func.coalesce(func.sum(ReconciliationDiff.diff_amount), 0),
                func.sum(
                    func.if_(ReconciliationDiff.status == "PENDING", 1, 0)
                ),
                func.sum(
                    func.if_(ReconciliationDiff.alert_level == "CRITICAL", 1, 0)
                ),
            )
            .where(and_(*conditions))
            .group_by(ReconciliationDiff.channel_code)
        )
        result = await self.session.execute(stmt)
        rows = result.fetchall()

        channels: Dict[str, Any] = {}
        totals = {
            "diff_count": 0, "pending_count": 0,
            "critical_count": 0, "diff_amount": 0,
        }
        for row in rows:
            code = row[0] or "unknown"
            channels[code] = {
                "channel_code": code,
                "diff_count": int(row[1] or 0),
                "diff_amount": str(round(float(row[2] or 0), 2)),
                "pending_count": int(row[3] or 0),
                "critical_count": int(row[4] or 0),
            }
            totals["diff_count"] += int(row[1] or 0)
            totals["pending_count"] += int(row[3] or 0)
            totals["critical_count"] += int(row[4] or 0)
            totals["diff_amount"] += float(row[2] or 0)

        return {
            "channels": channels,
            "total": {
                "diff_count": totals["diff_count"],
                "pending_count": totals["pending_count"],
                "critical_count": totals["critical_count"],
                "diff_amount": str(round(totals["diff_amount"], 2)),
            },
        }

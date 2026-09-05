# @ai-generated
"""
数据大盘聚合查询 DAO（只读，不继承 BaseDAO，无写操作）
聚合查询 orders / commission_flow / user_commission_account / user_withdraw_apply 四张表
专为 B14-补全 数据大盘接口服务
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select

from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.business.user_commission_account_model import UserCommissionAccount
from src.models.business.user_withdraw_apply_model import UserWithdrawApply

logger = logging.getLogger("dao.dashboard_query")


class DashboardQueryDAO:
    """数据大盘聚合查询 DAO（只读）"""

    def __init__(self, session):
        self.session = session

    # ── 1. 首页卡片聚合数据 ────────────────────────────

    async def get_cards_data(self) -> Dict[str, Any]:
        """获取首页 5 张卡片聚合数据

        Returns:
            {
                "total_orders": 累计订单数,
                "pending_settle_commission": 待结算佣金(SETTLABLE 状态订单的 user_commission 之和),
                "settled_commission": 已结算佣金(用户累计已结算佣金 total_balance 之和),
                "total_withdrawn": 提现总额(用户累计成功提现 cumulative_withdrawn 之和),
                "pending_review_withdraws": 待审核提现数量(PENDING 状态),
            }
        """
        # 1. 累计订单数
        total_orders = await self._count_orders()

        # 2. 待结算佣金（order_status=SETTLABLE=30 的 user_commission 之和）
        pending_settle = await self._sum_pending_settle_commission()

        # 3. 已结算佣金（用户累计已结算佣金 total_balance 之和）
        settled = await self._sum_settled_commission()

        # 4. 提现总额（用户累计成功提现 cumulative_withdrawn 之和）
        total_withdrawn = await self._sum_total_withdrawn()

        # 5. 待审核提现数量（status=PENDING）
        pending_review = await self._count_pending_withdraws()

        return {
            "total_orders": total_orders,
            "pending_settle_commission": str(pending_settle),
            "settled_commission": str(settled),
            "total_withdrawn": str(total_withdrawn),
            "pending_review_withdraws": pending_review,
        }

    async def _count_orders(self) -> int:
        """累计订单数（非软删除）"""
        stmt = select(func.count()).select_from(Order).where(
            Order.is_delete == False  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _sum_pending_settle_commission(self) -> float:
        """待结算佣金（order_status=30 SETTLABLE）"""
        stmt = select(
            func.coalesce(func.sum(Order.user_commission), 0)
        ).where(
            and_(
                Order.is_delete == False,  # noqa: E712
                Order.order_status == 30,  # SETTLABLE
            )
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def _sum_settled_commission(self) -> float:
        """已结算佣金（用户累计已结算佣金 total_balance 之和）"""
        stmt = select(
            func.coalesce(func.sum(UserCommissionAccount.total_balance), 0)
        ).where(
            UserCommissionAccount.is_delete == False  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def _sum_total_withdrawn(self) -> float:
        """提现总额（用户累计成功提现 cumulative_withdrawn 之和）"""
        stmt = select(
            func.coalesce(func.sum(UserCommissionAccount.cumulative_withdrawn), 0)
        ).where(
            UserCommissionAccount.is_delete == False  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def _count_pending_withdraws(self) -> int:
        """待审核提现数量（status=PENDING）"""
        stmt = select(func.count()).select_from(UserWithdrawApply).where(
            and_(
                UserWithdrawApply.is_delete == False,  # noqa: E712
                UserWithdrawApply.status == "PENDING",
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ── 2. 多维度佣金统计 ────────────────────────────

    async def get_commission_stats_by_date(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """按日期分组佣金统计

        Returns:
            [{"date": "2026-08-01", "total_commission": "123.45", "order_count": 10}, ...]
        """
        stmt = (
            select(
                func.date(Order.create_time).label("stat_date"),
                func.coalesce(func.sum(Order.user_commission), 0).label("total_commission"),
                func.count(Order.id).label("order_count"),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time >= start_date,
                    Order.create_time < end_date,
                )
            )
            .group_by(func.date(Order.create_time))
            .order_by(func.date(Order.create_time).asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "date": str(row.stat_date),
                "total_commission": str(row.total_commission),
                "order_count": row.order_count,
            }
            for row in rows
        ]

    async def get_commission_stats_by_channel(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """按渠道分组佣金统计

        Returns:
            [{"channel_code": "myq", "total_commission": "123.45", "order_count": 10}, ...]
        """
        stmt = (
            select(
                Order.channel_code.label("channel_code"),
                func.coalesce(func.sum(Order.user_commission), 0).label("total_commission"),
                func.count(Order.id).label("order_count"),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time >= start_date,
                    Order.create_time < end_date,
                )
            )
            .group_by(Order.channel_code)
            .order_by(func.sum(Order.user_commission).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "channel_code": row.channel_code,
                "total_commission": str(row.total_commission),
                "order_count": row.order_count,
            }
            for row in rows
        ]

    async def get_commission_stats_by_user(
        self,
        start_date: datetime,
        end_date: datetime,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """按用户分组佣金统计（分页）

        Returns:
            {"total": 100, "page": 1, "page_size": 20, "items": [...]}
        """
        # 构建基础查询
        base_filter = and_(
            Order.is_delete == False,  # noqa: E712
            Order.create_time >= start_date,
            Order.create_time < end_date,
        )

        # 统计总数（去重 user_id）
        count_stmt = (
            select(func.count(func.distinct(Order.user_id)))
            .where(base_filter)
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        stmt = (
            select(
                Order.user_id.label("user_id"),
                func.coalesce(func.sum(Order.user_commission), 0).label("total_commission"),
                func.count(Order.id).label("order_count"),
            )
            .where(base_filter)
            .group_by(Order.user_id)
            .order_by(func.sum(Order.user_commission).desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        items = [
            {
                "user_id": row.user_id,
                "total_commission": str(row.total_commission),
                "order_count": row.order_count,
            }
            for row in rows
        ]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    # ── 3. 订单趋势折线数据 ────────────────────────────

    async def get_order_trend(
        self, start_date: datetime, end_date: datetime, group_by: str = "day"
    ) -> List[Dict[str, Any]]:
        """订单趋势折线数据（按天/周/月分组）

        Args:
            group_by: day / week / month
        Returns:
            [{"date": "2026-08-01", "order_count": 10, "total_commission": "123.45"}, ...]
        """
        # 选择分组函数
        if group_by == "week":
            date_func = func.yearweek(Order.create_time)
        elif group_by == "month":
            date_func = func.date_format(Order.create_time, "%Y-%m")
        else:
            date_func = func.date(Order.create_time)

        stmt = (
            select(
                date_func.label("stat_date"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.user_commission), 0).label("total_commission"),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.create_time >= start_date,
                    Order.create_time < end_date,
                )
            )
            .group_by(date_func)
            .order_by(date_func.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "date": str(row.stat_date),
                "order_count": row.order_count,
                "total_commission": str(row.total_commission),
            }
            for row in rows
        ]

    # ── 5. 提现趋势折线数据 ──────────────────────────────

    async def get_withdraw_trend(
        self, start_date: datetime, end_date: datetime, group_by: str = "day"
    ) -> List[Dict[str, Any]]:
        """提现趋势折线数据（按天/周/月分组）

        Args:
            group_by: day / week / month
        Returns:
            [{"date": "2026-08-01", "apply_count": 5, "withdraw_amount": "50.00", "success_amount": "45.00"}, ...]
        """
        # 选择分组函数
        if group_by == "week":
            date_func = func.yearweek(UserWithdrawApply.create_time)
        elif group_by == "month":
            date_func = func.date_format(UserWithdrawApply.create_time, "%Y-%m")
        else:
            date_func = func.date(UserWithdrawApply.create_time)

        # 提现申请金额统计（所有申请）
        apply_stmt = (
            select(
                date_func.label("stat_date"),
                func.count(UserWithdrawApply.id).label("apply_count"),
                func.coalesce(func.sum(UserWithdrawApply.apply_amount), 0).label("withdraw_amount"),
            )
            .where(
                and_(
                    UserWithdrawApply.is_delete == False,  # noqa: E712
                    UserWithdrawApply.create_time >= start_date,
                    UserWithdrawApply.create_time < end_date,
                )
            )
            .group_by(date_func)
            .order_by(date_func.asc())
        )
        apply_result = await self.session.execute(apply_stmt)
        apply_rows = {str(row.stat_date): row for row in apply_result.all()}

        # 成功到账金额统计（status = SUCCESS）
        success_stmt = (
            select(
                date_func.label("stat_date"),
                func.coalesce(func.sum(UserWithdrawApply.actual_amount), 0).label("success_amount"),
            )
            .where(
                and_(
                    UserWithdrawApply.is_delete == False,  # noqa: E712
                    UserWithdrawApply.status == "SUCCESS",
                    UserWithdrawApply.transfer_time >= start_date,
                    UserWithdrawApply.transfer_time < end_date,
                )
            )
            .group_by(date_func)
            .order_by(date_func.asc())
        )
        success_result = await self.session.execute(success_stmt)
        success_rows = {str(row.stat_date): row for row in success_result.all()}

        # 合并结果
        all_dates = sorted(set(list(apply_rows.keys()) + list(success_rows.keys())))
        return [
            {
                "date": d,
                "apply_count": getattr(apply_rows.get(d), "apply_count", 0),
                "withdraw_amount": str(getattr(apply_rows.get(d), "withdraw_amount", 0)),
                "success_amount": str(getattr(success_rows.get(d), "success_amount", 0)),
            }
            for d in all_dates
        ]

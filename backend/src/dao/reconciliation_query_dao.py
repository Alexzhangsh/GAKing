# @ai-generated
"""
全链路对账四方汇总查询 DAO（B13 新建）
只读查询 DAO，不继承 BaseDAO（跨表聚合，无单一 model）
跨表聚合：Order ↔ SettlementRecord ↔ UserCommissionAccount ↔ UserWithdrawApply
仅做数据查询，不含业务逻辑；所有查询自动过滤软删除
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.b12_constants import SettlementStatus
from src.config.constants import OrderStatus
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.business.reconciliation_diff_model import ReconciliationDiff
from src.models.business.settlement_record_model import SettlementRecord
from src.models.business.user_commission_account_model import (
    UserCommissionAccount,
)
from src.models.business.user_withdraw_apply_model import UserWithdrawApply

logger = logging.getLogger("dao.reconciliation_query")


class ReconciliationQueryDAO:
    """全链路对账四方汇总查询 DAO（只读）"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ════════════════════════════════════════════════════
    # 1. 订单原始佣金汇总（第一方）
    # ════════════════════════════════════════════════════

    async def aggregate_order_commission_by_user(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[int, Dict[str, Decimal]]:
        """按用户汇总订单佣金（SETTLABLE/SETTLED 状态订单）

        Args:
            start_time: 查询起始时间（含）
            end_time: 查询截止时间（不含）
        Returns:
            {user_id: {"user_commission": Decimal, "total_commission": Decimal, "order_count": int}}
        """
        stmt = (
            select(
                Order.user_id,
                func.sum(Order.user_commission),
                func.sum(Order.total_commission),
                func.count(Order.id),
            )
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.order_status.in_(
                        [int(OrderStatus.SETTLABLE), int(OrderStatus.SETTLED)]
                    ),
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                )
            )
            .group_by(Order.user_id)
        )
        result = await self.session.execute(stmt)
        agg: Dict[int, Dict[str, Any]] = {}
        for row in result.fetchall():
            agg[row[0]] = {
                "user_commission": row[1] or Decimal("0.00"),
                "total_commission": row[2] or Decimal("0.00"),
                "order_count": int(row[3] or 0),
            }
        return agg

    async def list_orders_by_user(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Order]:
        """查询用户在时间范围内的订单列表（逐单核对用）"""
        stmt = (
            select(Order)
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.user_id == user_id,
                    Order.order_status.in_(
                        [int(OrderStatus.SETTLABLE), int(OrderStatus.SETTLED)]
                    ),
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                )
            )
            .order_by(Order.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ════════════════════════════════════════════════════
    # 2. B12 结算入账汇总（第二方）
    # ════════════════════════════════════════════════════

    async def aggregate_settlement_by_user(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[int, Dict[str, Decimal]]:
        """按用户汇总结算入账金额（SETTLABLE/SETTLED/PAID 状态结算单）

        Returns:
            {user_id: {"user_commission": Decimal, "total_commission": Decimal, "count": int}}
        """
        stmt = (
            select(
                SettlementRecord.user_id,
                func.sum(SettlementRecord.user_commission),
                func.sum(SettlementRecord.total_commission),
                func.count(SettlementRecord.id),
            )
            .where(
                and_(
                    SettlementRecord.is_delete == False,  # noqa: E712
                    SettlementRecord.settlement_status.in_(
                        [
                            SettlementStatus.SETTLABLE.value,
                            SettlementStatus.SETTLED.value,
                            SettlementStatus.PAID.value,
                        ]
                    ),
                    SettlementRecord.create_time >= start_time,
                    SettlementRecord.create_time < end_time,
                )
            )
            .group_by(SettlementRecord.user_id)
        )
        result = await self.session.execute(stmt)
        agg: Dict[int, Dict[str, Any]] = {}
        for row in result.fetchall():
            agg[row[0]] = {
                "user_commission": row[1] or Decimal("0.00"),
                "total_commission": row[2] or Decimal("0.00"),
                "count": int(row[3] or 0),
            }
        return agg

    async def get_settlement_by_order_id(
        self, order_id: int
    ) -> Optional[SettlementRecord]:
        """按订单ID查询结算单（逐单核对用）"""
        stmt = select(SettlementRecord).where(
            and_(
                SettlementRecord.is_delete == False,  # noqa: E712
                SettlementRecord.order_id == order_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ════════════════════════════════════════════════════
    # 3. B08 资产账户余额（第三方）
    # ════════════════════════════════════════════════════

    async def list_all_accounts(self) -> List[UserCommissionAccount]:
        """查询全部用户佣金账户（当前快照）"""
        stmt = (
            select(UserCommissionAccount)
            .where(UserCommissionAccount.is_delete == False)  # noqa: E712
            .order_by(UserCommissionAccount.user_id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_account_by_user(
        self, user_id: int
    ) -> Optional[UserCommissionAccount]:
        """按用户ID查询佣金账户"""
        stmt = select(UserCommissionAccount).where(
            and_(
                UserCommissionAccount.is_delete == False,  # noqa: E712
                UserCommissionAccount.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def aggregate_account_totals(self) -> Dict[str, Decimal]:
        """汇总全部账户余额总额（对账批次汇总用）"""
        stmt = select(
            func.sum(UserCommissionAccount.total_balance),
            func.sum(UserCommissionAccount.available_balance),
            func.sum(UserCommissionAccount.frozen_balance),
            func.sum(UserCommissionAccount.cumulative_withdrawn),
            func.sum(UserCommissionAccount.cumulative_fee),
            func.count(UserCommissionAccount.id),
        ).where(
            UserCommissionAccount.is_delete == False
        )  # noqa: E712
        result = await self.session.execute(stmt)
        row = result.fetchone()
        return {
            "total_balance": row[0] or Decimal("0.00"),
            "available_balance": row[1] or Decimal("0.00"),
            "frozen_balance": row[2] or Decimal("0.00"),
            "cumulative_withdrawn": row[3] or Decimal("0.00"),
            "cumulative_fee": row[4] or Decimal("0.00"),
            "account_count": int(row[5] or 0),
        }

    # ════════════════════════════════════════════════════
    # 4. B10 微信打款流水汇总（第四方）
    # ════════════════════════════════════════════════════

    async def aggregate_withdraw_by_user(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[int, Dict[str, Decimal]]:
        """按用户汇总成功提现金额（SUCCESS 状态）

        Returns:
            {user_id: {"actual_amount": Decimal, "fee": Decimal, "apply_amount": Decimal, "count": int}}
        """
        stmt = (
            select(
                UserWithdrawApply.user_id,
                func.sum(UserWithdrawApply.actual_amount),
                func.sum(UserWithdrawApply.fee),
                func.sum(UserWithdrawApply.apply_amount),
                func.count(UserWithdrawApply.id),
            )
            .where(
                and_(
                    UserWithdrawApply.is_delete == False,  # noqa: E712
                    UserWithdrawApply.status == "SUCCESS",
                    UserWithdrawApply.create_time >= start_time,
                    UserWithdrawApply.create_time < end_time,
                )
            )
            .group_by(UserWithdrawApply.user_id)
        )
        result = await self.session.execute(stmt)
        agg: Dict[int, Dict[str, Any]] = {}
        for row in result.fetchall():
            agg[row[0]] = {
                "actual_amount": row[1] or Decimal("0.00"),
                "fee": row[2] or Decimal("0.00"),
                "apply_amount": row[3] or Decimal("0.00"),
                "count": int(row[4] or 0),
            }
        return agg

    async def list_withdraws_by_user(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> List[UserWithdrawApply]:
        """查询用户在时间范围内的提现记录（逐单核对用）"""
        stmt = (
            select(UserWithdrawApply)
            .where(
                and_(
                    UserWithdrawApply.is_delete == False,  # noqa: E712
                    UserWithdrawApply.user_id == user_id,
                    UserWithdrawApply.create_time >= start_time,
                    UserWithdrawApply.create_time < end_time,
                )
            )
            .order_by(UserWithdrawApply.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_withdraw_totals(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Decimal]:
        """汇总全部成功提现总额（对账批次汇总用）"""
        stmt = select(
            func.sum(UserWithdrawApply.actual_amount),
            func.sum(UserWithdrawApply.fee),
            func.count(UserWithdrawApply.id),
        ).where(
            and_(
                UserWithdrawApply.is_delete == False,  # noqa: E712
                UserWithdrawApply.status == "SUCCESS",
                UserWithdrawApply.create_time >= start_time,
                UserWithdrawApply.create_time < end_time,
            )
        )
        result = await self.session.execute(stmt)
        row = result.fetchone()
        return {
            "total_withdrawn": row[0] or Decimal("0.00"),
            "total_fee": row[1] or Decimal("0.00"),
            "withdraw_count": int(row[2] or 0),
        }

    # ════════════════════════════════════════════════════
    # 5. 跨表单边账检测
    # ════════════════════════════════════════════════════

    async def find_orders_without_settlement(
        self, start_time: datetime, end_time: datetime
    ) -> List[Order]:
        """查询有佣金但无结算单的订单（单边账-订单侧）

        SQL 语义：SETTLABLE/SETTLED 订单 LEFT JOIN 结算单 WHERE 结算单 IS NULL
        """
        # 子查询：有结算单的 order_id 集合
        settled_order_ids = (
            select(SettlementRecord.order_id)
            .where(SettlementRecord.is_delete == False)  # noqa: E712
            .distinct()
            .subquery()
        )
        stmt = (
            select(Order)
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.order_status.in_(
                        [int(OrderStatus.SETTLABLE), int(OrderStatus.SETTLED)]
                    ),
                    Order.user_commission > 0,
                    Order.create_time >= start_time,
                    Order.create_time < end_time,
                    ~Order.id.in_(select(settled_order_ids.c.order_id)),
                )
            )
            .order_by(Order.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_settlements_without_order(
        self, start_time: datetime, end_time: datetime
    ) -> List[SettlementRecord]:
        """查询结算单存在但订单缺失/失效的记录（单边账-结算侧）"""
        # 子查询：有效订单 ID 集合
        valid_order_ids = (
            select(Order.id)
            .where(
                and_(
                    Order.is_delete == False,  # noqa: E712
                    Order.order_status.in_(
                        [int(OrderStatus.SETTLABLE), int(OrderStatus.SETTLED)]
                    ),
                )
            )
            .distinct()
            .subquery()
        )
        stmt = (
            select(SettlementRecord)
            .where(
                and_(
                    SettlementRecord.is_delete == False,  # noqa: E712
                    SettlementRecord.create_time >= start_time,
                    SettlementRecord.create_time < end_time,
                    ~SettlementRecord.order_id.in_(select(valid_order_ids.c.id)),
                )
            )
            .order_by(SettlementRecord.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

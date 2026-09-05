# @ai-generated
"""
B08-1 资金流水 DAO（新建文件，不修改 B01-B15 及 B06/B07 任何基线 DAO）

包含：
1. FundFlowDAO - 资金流水记录数据访问
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.b08_1_fund_flow_model import FundFlow

logger = logging.getLogger("dao.b08_1_fund_flow")


class FundFlowDAO(BaseDAO):
    """资金流水记录 DAO"""

    model_class = FundFlow

    async def create_flow(
        self,
        user_id: int,
        flow_type: str,
        amount: Decimal,
        before_balance: Decimal,
        after_balance: Decimal,
        before_frozen: Decimal,
        after_frozen: Decimal,
        biz_id: str,
        order_id: Optional[int] = None,
        withdraw_apply_id: Optional[int] = None,
        remark: str = "",
        operator_id: int = 0,
        operator_name: str = "",
    ) -> FundFlow:
        """创建资金流水记录

        Args:
            user_id: 用户ID
            flow_type: 流水类型
            amount: 变动金额（正入负出）
            before_balance: 变动前可用余额
            after_balance: 变动后可用余额
            before_frozen: 变动前冻结余额
            after_frozen: 变动后冻结余额
            biz_id: 业务流水号（唯一幂等键）
            order_id: 关联订单ID
            withdraw_apply_id: 关联提现申请ID
            remark: 备注
            operator_id: 操作人ID
            operator_name: 操作人姓名
        Returns:
            创建的流水记录
        """
        data = {
            "user_id": user_id,
            "flow_type": flow_type,
            "amount": amount,
            "before_balance": before_balance,
            "after_balance": after_balance,
            "before_frozen": before_frozen,
            "after_frozen": after_frozen,
            "biz_id": biz_id,
            "order_id": order_id,
            "withdraw_apply_id": withdraw_apply_id,
            "remark": remark,
            "operator_id": operator_id,
            "operator_name": operator_name,
        }
        return await self.create(data)

    async def get_by_biz_id(self, biz_id: str) -> Optional[FundFlow]:
        """按业务流水号查询（幂等校验）

        Args:
            biz_id: 业务流水号
        Returns:
            流水记录 或 None
        """
        stmt = self._active_query().where(FundFlow.biz_id == biz_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, item_id: int) -> Optional[FundFlow]:
        """按主键ID查询流水记录"""
        stmt = self._active_query().where(FundFlow.id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        user_id: Optional[int] = None,
        flow_type: Optional[str] = None,
        order_id: Optional[int] = None,
        withdraw_apply_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "-create_time",
    ) -> Tuple[List[FundFlow], int]:
        """多条件分页查询资金流水

        Args:
            user_id: 用户ID筛选
            flow_type: 流水类型筛选
            order_id: 关联订单ID筛选
            withdraw_apply_id: 关联提现申请ID筛选
            start_time: 起始时间
            end_time: 截止时间
            min_amount: 最小金额
            max_amount: 最大金额
            page: 页码
            page_size: 每页条数
            order_by: 排序字段，默认按创建时间降序
        Returns:
            (流水记录列表, 总记录数)
        """
        conditions = [FundFlow.is_delete == False]  # noqa: E712

        if user_id is not None:
            conditions.append(FundFlow.user_id == user_id)
        if flow_type:
            conditions.append(FundFlow.flow_type == flow_type)
        if order_id is not None:
            conditions.append(FundFlow.order_id == order_id)
        if withdraw_apply_id is not None:
            conditions.append(FundFlow.withdraw_apply_id == withdraw_apply_id)
        if start_time:
            conditions.append(FundFlow.create_time >= start_time)
        if end_time:
            conditions.append(FundFlow.create_time < end_time)
        if min_amount is not None:
            conditions.append(FundFlow.amount >= min_amount)
        if max_amount is not None:
            conditions.append(FundFlow.amount <= max_amount)

        stmt = select(FundFlow).where(and_(*conditions))

        # 总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 排序
        if order_by.startswith("-"):
            col = getattr(FundFlow, order_by[1:])
            stmt = stmt.order_by(col.desc())
        else:
            col = getattr(FundFlow, order_by)
            stmt = stmt.order_by(col.asc())

        # 分页
        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def count_by_user_and_type(
        self,
        user_id: int,
        flow_type: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计用户指定类型的流水数量

        Args:
            user_id: 用户ID
            flow_type: 流水类型
            start_time: 起始时间
            end_time: 截止时间
        Returns:
            流水记录数
        """
        conditions = [
            FundFlow.is_delete == False,  # noqa: E712
            FundFlow.user_id == user_id,
            FundFlow.flow_type == flow_type,
        ]
        if start_time:
            conditions.append(FundFlow.create_time >= start_time)
        if end_time:
            conditions.append(FundFlow.create_time < end_time)

        stmt = select(func.count()).select_from(FundFlow).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def sum_amount_by_user_and_type(
        self,
        user_id: int,
        flow_type: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Decimal:
        """统计用户指定类型的金额汇总

        Args:
            user_id: 用户ID
            flow_type: 流水类型
            start_time: 起始时间
            end_time: 截止时间
        Returns:
            金额汇总
        """
        conditions = [
            FundFlow.is_delete == False,  # noqa: E712
            FundFlow.user_id == user_id,
            FundFlow.flow_type == flow_type,
        ]
        if start_time:
            conditions.append(FundFlow.create_time >= start_time)
        if end_time:
            conditions.append(FundFlow.create_time < end_time)

        stmt = select(func.coalesce(func.sum(FundFlow.amount), 0)).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return Decimal(str(result.scalar() or 0))
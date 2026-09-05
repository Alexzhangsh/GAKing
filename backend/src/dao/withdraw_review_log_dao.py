# @ai-generated
"""
提现审批状态流转日志 DAO（B11 新建）
继承 BaseDAO；提供按申请ID查询操作历史、按条件筛选日志能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.withdraw_review_log_model import WithdrawReviewLog

logger = logging.getLogger("dao.withdraw_review_log")


class WithdrawReviewLogDAO(BaseDAO):
    """提现审批状态流转日志 DAO"""

    model_class = WithdrawReviewLog

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def list_by_apply_id(
        self,
        apply_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[WithdrawReviewLog], int]:
        """按提现申请ID查询操作历史（按创建时间升序，便于追溯流程）

        Args:
            apply_id: 提现申请ID
            page: 页码
            page_size: 每页条数
        Returns:
            (日志列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        stmt = self._active_query().where(WithdrawReviewLog.apply_id == apply_id)

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        # 升序排列，便于按时间顺序追溯完整流程
        page_query = (
            stmt.order_by(WithdrawReviewLog.create_time.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_with_filters(
        self,
        *,
        apply_id: Optional[int] = None,
        action: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[WithdrawReviewLog], int]:
        """多条件分页查询审批日志（后台审计/导出用）

        Args:
            apply_id: 提现申请ID筛选
            action: 操作类型筛选（APPROVE/REJECT/TRANSFER等）
            operator_id: 操作人ID筛选
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
        if apply_id is not None:
            conditions.append(WithdrawReviewLog.apply_id == apply_id)
        if action is not None:
            conditions.append(WithdrawReviewLog.action == action)
        if operator_id is not None:
            conditions.append(WithdrawReviewLog.operator_id == operator_id)
        if start_time is not None:
            conditions.append(WithdrawReviewLog.create_time >= start_time)
        if end_time is not None:
            conditions.append(WithdrawReviewLog.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(WithdrawReviewLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

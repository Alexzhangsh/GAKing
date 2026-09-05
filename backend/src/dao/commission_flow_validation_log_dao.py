# @ai-generated
"""
佣金流水结算前置校验日志 DAO（B05-5 新建）
继承 BaseDAO；提供按订单ID查询校验记录、多条件筛选能力
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.commission_flow_validation_log_model import (
    CommissionFlowValidationLog,
)

logger = logging.getLogger("dao.commission_flow_validation_log")


class CommissionFlowValidationLogDAO(BaseDAO):
    """佣金流水结算前置校验日志 DAO"""

    model_class = CommissionFlowValidationLog

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def create_log(
        self,
        order_id: int,
        user_id: int,
        validation_type: str,
        validation_result: str,
        check_items: str,
        error_message: str = "",
        operator_id: int = 0,
    ) -> CommissionFlowValidationLog:
        """创建校验日志记录

        Args:
            order_id: 订单ID
            user_id: 用户ID
            validation_type: 校验类型（PRE_SETTLE/PRE_DEDUCT）
            validation_result: 校验结果（PASS/FAIL）
            check_items: 各项校验明细JSON
            error_message: 总体错误信息
            operator_id: 操作人管理员ID（0=系统自动）
        Returns:
            新建的 CommissionFlowValidationLog 实例
        """
        log = CommissionFlowValidationLog(
            order_id=order_id,
            user_id=user_id,
            validation_type=validation_type,
            validation_result=validation_result,
            check_items=check_items,
            error_message=error_message,
            operator_id=operator_id,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_by_order_id(
        self,
        order_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CommissionFlowValidationLog], int]:
        """按订单ID查询校验记录（按创建时间降序）

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
            .where(CommissionFlowValidationLog.order_id == order_id)
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(CommissionFlowValidationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_with_filters(
        self,
        *,
        order_id: Optional[int] = None,
        user_id: Optional[int] = None,
        validation_type: Optional[str] = None,
        validation_result: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CommissionFlowValidationLog], int]:
        """多条件分页查询校验日志（后台审计用）

        Args:
            order_id: 订单ID筛选
            user_id: 用户ID筛选
            validation_type: 校验类型筛选
            validation_result: 校验结果筛选（PASS/FAIL）
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
            conditions.append(CommissionFlowValidationLog.order_id == order_id)
        if user_id is not None:
            conditions.append(CommissionFlowValidationLog.user_id == user_id)
        if validation_type is not None:
            conditions.append(
                CommissionFlowValidationLog.validation_type == validation_type
            )
        if validation_result is not None:
            conditions.append(
                CommissionFlowValidationLog.validation_result == validation_result
            )
        if start_time is not None:
            conditions.append(CommissionFlowValidationLog.create_time >= start_time)
        if end_time is not None:
            conditions.append(CommissionFlowValidationLog.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(CommissionFlowValidationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total
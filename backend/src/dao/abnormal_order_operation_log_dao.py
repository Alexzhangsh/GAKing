# @ai-generated
"""
订单归属操作日志 DAO（B05-4-3 新建）
继承 BaseDAO；提供按异常订单ID查询操作历史能力
仅做数据存取，不含业务逻辑
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.models.business.abnormal_order_operation_log_model import (
    AbnormalOrderOperationLog,
)

logger = logging.getLogger("dao.abnormal_order_operation_log")


class AbnormalOrderOperationLogDAO(BaseDAO):
    """订单归属操作日志 DAO"""

    model_class = AbnormalOrderOperationLog

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def create_log(
        self,
        abnormal_order_id: int,
        operator_id: int,
        operation_type: str,
        old_assigned_user_id: int = 0,
        new_assigned_user_id: int = 0,
        old_review_remark: str = "",
        new_review_remark: str = "",
        old_review_status: str = "",
        new_review_status: str = "",
        remark: str = "",
    ) -> AbnormalOrderOperationLog:
        """创建归属操作日志记录

        Args:
            abnormal_order_id: 异常订单ID
            operator_id: 操作人管理员ID
            operation_type: 操作类型（REVIEW/EDIT）
            old_assigned_user_id: 变更前归属用户ID
            new_assigned_user_id: 变更后归属用户ID
            old_review_remark: 变更前复核备注
            new_review_remark: 变更后复核备注
            old_review_status: 变更前复核状态
            new_review_status: 变更后复核状态
            remark: 操作补充说明
        Returns:
            新建的 AbnormalOrderOperationLog 实例
        """
        log = AbnormalOrderOperationLog(
            abnormal_order_id=abnormal_order_id,
            operator_id=operator_id,
            operation_type=operation_type,
            old_assigned_user_id=old_assigned_user_id,
            new_assigned_user_id=new_assigned_user_id,
            old_review_remark=old_review_remark,
            new_review_remark=new_review_remark,
            old_review_status=old_review_status,
            new_review_status=new_review_status,
            remark=remark,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_by_abnormal_order_id(
        self,
        abnormal_order_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AbnormalOrderOperationLog], int]:
        """按异常订单ID查询操作历史（按创建时间降序）

        Args:
            abnormal_order_id: 异常订单ID
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
            .where(AbnormalOrderOperationLog.abnormal_order_id == abnormal_order_id)
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        # 降序排列，最新操作排最前
        page_query = (
            stmt.order_by(AbnormalOrderOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_with_filters(
        self,
        *,
        abnormal_order_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        operator_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AbnormalOrderOperationLog], int]:
        """多条件分页查询操作日志（后台审计用）

        Args:
            abnormal_order_id: 异常订单ID筛选
            operation_type: 操作类型筛选（REVIEW/EDIT）
            operator_id: 操作人ID筛选
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
        if abnormal_order_id is not None:
            conditions.append(
                AbnormalOrderOperationLog.abnormal_order_id == abnormal_order_id
            )
        if operation_type is not None:
            conditions.append(
                AbnormalOrderOperationLog.operation_type == operation_type
            )
        if operator_id is not None:
            conditions.append(
                AbnormalOrderOperationLog.operator_id == operator_id
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(AbnormalOrderOperationLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total
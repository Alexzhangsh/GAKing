# @ai-generated
"""
审计日志 DAO（B14 新建，不修改 B01-B13 基线）
继承 BaseDAO；操作 src/db/models.py 中的 AuditLogs 模型
提供审计日志写入 + 多条件分页查询
仅做数据存取，不含业务逻辑
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.base_dao import BaseDAO
from src.db.models import AuditLogs

logger = logging.getLogger("dao.audit_log")


class AuditLogDAO(BaseDAO):
    """审计日志 DAO"""

    model_class = AuditLogs

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create_log(
        self,
        user_id: int,
        user_name: str,
        action: str,
        target_type: str = "",
        target_id: int = 0,
        details: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> AuditLogs:
        """写入一条审计日志

        Args:
            user_id: 操作人ID（0 表示匿名/未认证）
            user_name: 操作人姓名
            action: 操作描述（AuditAction 枚举值）
            target_type: 目标类型（AuditTargetType 枚举值）
            target_id: 目标ID
            details: 脱敏后的操作内容
            ip_address: IP 地址
            user_agent: User Agent
        Returns:
            创建的审计日志实例
        """
        data = {
            "user_id": user_id,
            "user_name": user_name,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        return await self.create(data)

    async def paginate_by_actions(
        self,
        actions: List[str],
        target_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AuditLogs], int]:
        """按动作集合分页查询审计日志（AuditLogs 无软删除字段，直接查询）

        F04-2 新增：佣金策略变更审计记录查询。
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = select(AuditLogs)
        conditions = [AuditLogs.action.in_(actions)]
        if target_type:
            conditions.append(AuditLogs.target_type == target_type)
        stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(AuditLogs.create_time.desc()).offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def list_with_filters(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AuditLogs], int]:
        """多条件分页查询审计日志

        Args:
            user_id: 操作人ID筛选
            action: 动作类型筛选
            target_type: 目标类型筛选
            start_time: 创建时间起始（含）
            end_time: 创建时间截止（不含）
            page: 页码
            page_size: 每页条数
        Returns:
            (审计日志列表, 总数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query()
        conditions = []
        if user_id is not None:
            conditions.append(AuditLogs.user_id == user_id)
        if action is not None:
            conditions.append(AuditLogs.action == action)
        if target_type is not None:
            conditions.append(AuditLogs.target_type == target_type)
        if start_time is not None:
            conditions.append(AuditLogs.create_time >= start_time)
        if end_time is not None:
            conditions.append(AuditLogs.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页（按创建时间降序）
        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(AuditLogs.create_time.desc()).offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

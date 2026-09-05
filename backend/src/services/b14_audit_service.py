# @ai-generated
"""
B14 审计日志查询 Service（列表 / 详情 / 统计）
新建独立文件，不修改 B01-B13 任何基线 service

业务说明：
- 审计日志写入由 AuditLogger / B14AuditMiddleware 自动完成，本 Service 仅负责查询
- 多条件分页查询：user_id / action / target_type / 时间范围
- 统计接口：按 action / target_type / user 聚合（前端报表用）
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select

from src.dao.audit_log_dao import AuditLogDAO
from src.db.init_db import DatabaseManager
from src.db.models import AuditLogs

logger = logging.getLogger("service.b14_audit")


class B14AuditService:
    """审计日志查询服务（B14 新建）"""

    @classmethod
    async def list_audit_logs(
        cls,
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
            page: 页码（1 开始）
            page_size: 每页条数
        Returns:
            (审计日志列表, 总数)
        """
        async with DatabaseManager.get_session() as session:
            dao = AuditLogDAO(session)
            return await dao.list_with_filters(
                user_id=user_id,
                action=action,
                target_type=target_type,
                start_time=start_time,
                end_time=end_time,
                page=page,
                page_size=page_size,
            )

    @classmethod
    async def get_audit_log(cls, log_id: int) -> Optional[AuditLogs]:
        """按 ID 查询审计日志详情

        Args:
            log_id: 日志ID
        Returns:
            日志实例 或 None
        """
        async with DatabaseManager.get_session() as session:
            dao = AuditLogDAO(session)
            return await dao.get_by_id(log_id)

    @classmethod
    async def get_audit_stats(
        cls,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """审计日志统计（按 action / target_type / user 聚合）

        Args:
            start_time: 创建时间起始（含）
            end_time: 创建时间截止（不含）
        Returns:
            {total, by_action, by_target_type, by_user}
        """
        async with DatabaseManager.get_session() as session:
            stmt = select(AuditLogs).where(AuditLogs.is_delete == False)  # noqa: E712
            if start_time is not None:
                stmt = stmt.where(AuditLogs.create_time >= start_time)
            if end_time is not None:
                stmt = stmt.where(AuditLogs.create_time < end_time)

            # 总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            # 按 action 聚合
            action_stmt = (
                select(AuditLogs.action, func.count())
                .where(AuditLogs.is_delete == False)  # noqa: E712
                .group_by(AuditLogs.action)
            )
            if start_time is not None:
                action_stmt = action_stmt.where(AuditLogs.create_time >= start_time)
            if end_time is not None:
                action_stmt = action_stmt.where(AuditLogs.create_time < end_time)
            action_result = await session.execute(action_stmt)
            by_action = {row[0]: row[1] for row in action_result.all()}

            # 按 target_type 聚合
            target_stmt = (
                select(AuditLogs.target_type, func.count())
                .where(AuditLogs.is_delete == False)  # noqa: E712
                .group_by(AuditLogs.target_type)
            )
            if start_time is not None:
                target_stmt = target_stmt.where(AuditLogs.create_time >= start_time)
            if end_time is not None:
                target_stmt = target_stmt.where(AuditLogs.create_time < end_time)
            target_result = await session.execute(target_stmt)
            by_target_type = {row[0]: row[1] for row in target_result.all()}

            # 按 user_id 聚合
            user_stmt = (
                select(AuditLogs.user_id, func.count())
                .where(AuditLogs.is_delete == False)  # noqa: E712
                .group_by(AuditLogs.user_id)
            )
            if start_time is not None:
                user_stmt = user_stmt.where(AuditLogs.create_time >= start_time)
            if end_time is not None:
                user_stmt = user_stmt.where(AuditLogs.create_time < end_time)
            user_result = await session.execute(user_stmt)
            by_user = {str(row[0]): row[1] for row in user_result.all()}

            return {
                "total": total,
                "by_action": by_action,
                "by_target_type": by_target_type,
                "by_user": by_user,
            }

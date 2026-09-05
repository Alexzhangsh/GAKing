# @ai-generated
"""
定时任务运行日志 DAO（B05-7 新建）
继承 BaseDAO；提供创建日志、分页查询、按ID查询、清理过期日志能力
仅做数据存取，不含业务逻辑
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.scheduled_task_run_log_model import ScheduledTaskRunLog

logger = logging.getLogger("dao.scheduled_task_run_log")


class ScheduledTaskRunLogDAO(BaseDAO):
    """定时任务运行日志 DAO"""

    model_class = ScheduledTaskRunLog

    # ── 创建日志 ────────────────────────────────────────

    async def create_run_log(
        self,
        task_name: str,
        run_id: str,
        status: str,
        started_at: datetime,
        finished_at: Optional[datetime] = None,
        duration_seconds: int = 0,
        total_orders: int = 0,
        success_count: int = 0,
        failed_count: int = 0,
        skipped_count: int = 0,
        error_message: str = "",
        detail_json: str = "",
    ) -> ScheduledTaskRunLog:
        """创建任务运行日志记录

        Args:
            task_name: 任务名称
            run_id: 运行批次ID
            status: 运行状态
            started_at: 开始时间
            finished_at: 结束时间
            duration_seconds: 耗时(秒)
            total_orders: 总处理订单数
            success_count: 成功数
            failed_count: 失败数
            skipped_count: 跳过数
            error_message: 错误信息
            detail_json: 详细结果JSON
        Returns:
            新建的 ScheduledTaskRunLog 实例
        """
        log = ScheduledTaskRunLog(
            task_name=task_name,
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            total_orders=total_orders,
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            error_message=error_message,
            detail_json=detail_json,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    # ── 更新日志状态 ────────────────────────────────────

    async def update_run_log(
        self,
        log_id: int,
        **kwargs,
    ) -> Optional[ScheduledTaskRunLog]:
        """更新任务运行日志

        Args:
            log_id: 日志ID
            **kwargs: 要更新的字段
        Returns:
            更新后的 ScheduledTaskRunLog 实例
        """
        log = await self.get_by_id(log_id)
        if log is None:
            return None
        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    # ── 分页查询 ────────────────────────────────────────

    async def list_with_filters(
        self,
        *,
        task_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ScheduledTaskRunLog], int]:
        """多条件分页查询运行日志

        Args:
            task_name: 任务名称筛选
            status: 运行状态筛选
            start_time: 开始时间起始
            end_time: 开始时间截止
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
        if task_name is not None:
            conditions.append(ScheduledTaskRunLog.task_name == task_name)
        if status is not None:
            conditions.append(ScheduledTaskRunLog.status == status)
        if start_time is not None:
            conditions.append(ScheduledTaskRunLog.started_at >= start_time)
        if end_time is not None:
            conditions.append(ScheduledTaskRunLog.started_at < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(ScheduledTaskRunLog.started_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    # ── M07-2 运维监控统计 ────────────────────────────────

    async def get_task_summary_stats(
        self,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """获取各任务概览统计

        按 task_name 分组，统计近 N 天内的总运行次数、成功/失败/部分成功次数、成功率。
        """
        cutoff = datetime.now() - timedelta(days=days)
        stmt = (
            select(
                ScheduledTaskRunLog.task_name,
                func.count().label("total_runs"),
                func.sum(
                    case((ScheduledTaskRunLog.status == "success", 1), else_=0)
                ).label("success_count"),
                func.sum(
                    case((ScheduledTaskRunLog.status == "failed", 1), else_=0)
                ).label("failed_count"),
                func.sum(
                    case((ScheduledTaskRunLog.status == "partial", 1), else_=0)
                ).label("partial_count"),
                func.max(ScheduledTaskRunLog.started_at).label("last_run_at"),
            )
            .where(
                and_(
                    ScheduledTaskRunLog.is_delete == False,  # noqa: E712
                    ScheduledTaskRunLog.started_at >= cutoff,
                )
            )
            .group_by(ScheduledTaskRunLog.task_name)
            .order_by(func.max(ScheduledTaskRunLog.started_at).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        summary = []
        for row in rows:
            total = int(row.total_runs or 0)
            success = int(row.success_count or 0)
            failed = int(row.failed_count or 0)
            partial = int(row.partial_count or 0)
            non_failed = total - failed
            success_rate = round(non_failed / total * 100, 1) if total > 0 else 0.0
            last_run = row.last_run_at
            summary.append({
                "task_name": row.task_name,
                "total_runs": total,
                "success_count": success,
                "failed_count": failed,
                "partial_count": partial,
                "success_rate": success_rate,
                "last_run_at": last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else "",
            })
        return summary

    async def get_recent_failed_logs(
        self,
        limit: int = 20,
    ) -> List[ScheduledTaskRunLog]:
        """获取最近失败的运行日志"""
        stmt = (
            self._active_query()
            .where(ScheduledTaskRunLog.status == "failed")
            .order_by(ScheduledTaskRunLog.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_run_per_task(self) -> List[Dict[str, Any]]:
        """获取每个任务的最新一次运行状态

        返回每个 task_name 最近一条运行日志的状态。
        """
        # 子查询：每个 task_name 的最大 started_at
        subq = (
            select(
                ScheduledTaskRunLog.task_name,
                func.max(ScheduledTaskRunLog.started_at).label("max_started_at"),
            )
            .where(ScheduledTaskRunLog.is_delete == False)  # noqa: E712
            .group_by(ScheduledTaskRunLog.task_name)
            .subquery()
        )
        stmt = (
            select(ScheduledTaskRunLog)
            .join(
                subq,
                and_(
                    ScheduledTaskRunLog.task_name == subq.c.task_name,
                    ScheduledTaskRunLog.started_at == subq.c.max_started_at,
                ),
            )
            .order_by(ScheduledTaskRunLog.started_at.desc())
        )
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())
        return [
            {
                "task_name": log.task_name,
                "status": log.status,
                "started_at": log.started_at.strftime("%Y-%m-%d %H:%M:%S") if log.started_at else "",
                "duration_seconds": log.duration_seconds or 0,
                "error_message": log.error_message or "",
            }
            for log in logs
        ]

    # ── 清理过期日志 ────────────────────────────────────

    async def delete_expired_logs(
        self,
        retention_days: int = 30,
    ) -> int:
        """软删除过期日志记录

        Args:
            retention_days: 保留天数
        Returns:
            删除的记录数
        """
        cutoff = datetime.now() - timedelta(days=retention_days)
        stmt = (
            select(ScheduledTaskRunLog)
            .where(
                and_(
                    ScheduledTaskRunLog.is_delete == False,  # noqa: E712
                    ScheduledTaskRunLog.started_at < cutoff,
                )
            )
        )
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())

        for log in logs:
            log.is_delete = True

        if logs:
            await self.session.commit()
            logger.info(
                "[dao] 清理过期运行日志 count=%s cutoff=%s", len(logs), cutoff
            )

        return len(logs)
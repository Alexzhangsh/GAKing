# @ai-generated
"""
B06-2 渠道订单报表导出与佣金账单对账 DAO（新建文件，不修改 B01-B15 及 B06-1 任何基线 DAO）

包含：
1. ChannelExportTaskLogDAO - 导出任务日志数据访问
2. ChannelOrderExportQueryDAO - 订单报表导出查询（只读）
3. ChannelCommissionBillQueryDAO - 佣金账单对账查询（只读）
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.system.b06_2_export_task_log import ChannelExportTaskLog

logger = logging.getLogger("dao.b06_2_channel")


# ════════════════════════════════════════════════════════════
# 1. 导出任务日志 DAO
# ════════════════════════════════════════════════════════════


class ChannelExportTaskLogDAO(BaseDAO):
    """导出任务日志 DAO"""

    model_class = ChannelExportTaskLog

    async def create_task_log(
        self,
        task_type: str,
        operator_id: int,
        operator_name: str,
        channel_code: str = "",
        params: Optional[dict] = None,
    ) -> ChannelExportTaskLog:
        """创建导出任务日志（初始状态 PROCESSING）"""
        data = {
            "task_type": task_type,
            "channel_code": channel_code,
            "status": "PROCESSING",
            "operator_id": operator_id,
            "operator_name": operator_name,
            "params": json.dumps(params or {}, ensure_ascii=False),
            "started_at": datetime.now(),
        }
        return await self.create(data)

    async def mark_success(
        self,
        log_id: int,
        file_path: str,
        file_name: str,
        file_size: int,
        row_count: int,
    ) -> Optional[ChannelExportTaskLog]:
        """标记任务成功"""
        return await self.update_by_id(log_id, {
            "status": "SUCCESS",
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "row_count": row_count,
            "finished_at": datetime.now(),
        })

    async def mark_failed(
        self, log_id: int, error_message: str
    ) -> Optional[ChannelExportTaskLog]:
        """标记任务失败"""
        return await self.update_by_id(log_id, {
            "status": "FAILED",
            "error_message": error_message[:2000] if error_message else "",
            "finished_at": datetime.now(),
        })

    async def list_with_filters(
        self,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        operator_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ChannelExportTaskLog], int]:
        """多条件分页查询导出任务日志"""
        stmt = self._active_query()
        conditions = []
        if task_type:
            conditions.append(ChannelExportTaskLog.task_type == task_type)
        if status:
            conditions.append(ChannelExportTaskLog.status == status)
        if operator_id is not None:
            conditions.append(ChannelExportTaskLog.operator_id == operator_id)
        if start_time:
            conditions.append(ChannelExportTaskLog.create_time >= start_time)
        if end_time:
            conditions.append(ChannelExportTaskLog.create_time < end_time)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页（按创建时间降序）
        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(ChannelExportTaskLog.create_time.desc())
            .offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def check_running_task(self, operator_id: int) -> Optional[ChannelExportTaskLog]:
        """检查用户是否有正在进行的导出任务"""
        stmt = self._active_query().where(
            and_(
                ChannelExportTaskLog.operator_id == operator_id,
                ChannelExportTaskLog.status == "PROCESSING",
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clean_expired_logs(self, before: datetime) -> int:
        """清理过期日志（软删除）"""
        stmt = select(ChannelExportTaskLog).where(
            and_(
                ChannelExportTaskLog.is_delete == False,  # noqa: E712
                ChannelExportTaskLog.create_time < before,
            )
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        for item in items:
            item.is_delete = True
            item.update_time = datetime.now()
        await self.session.flush()
        await self.session.commit()
        return len(items)


# ════════════════════════════════════════════════════════════
# 2. 订单报表导出查询 DAO（只读）
# ════════════════════════════════════════════════════════════


class ChannelOrderExportQueryDAO:
    """订单报表导出查询 DAO（只读）"""

    def __init__(self, session):
        self.session = session

    async def query_orders(
        self,
        channel_code: Optional[str] = None,
        order_status: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10000,
        offset: int = 0,
    ) -> List[Order]:
        """查询订单列表（用于导出）

        Args:
            channel_code: 渠道编码筛选
            order_status: 订单状态筛选
            start_time: 创建时间起始
            end_time: 创建时间截止
            limit: 最大返回行数
            offset: 偏移量
        Returns:
            订单列表
        """
        conditions = [Order.is_delete == False]  # noqa: E712
        if channel_code:
            conditions.append(Order.channel_code == channel_code)
        if order_status is not None:
            conditions.append(Order.order_status == order_status)
        if start_time:
            conditions.append(Order.create_time >= start_time)
        if end_time:
            conditions.append(Order.create_time < end_time)

        stmt = (
            select(Order)
            .where(and_(*conditions))
            .order_by(Order.create_time.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_orders(
        self,
        channel_code: Optional[str] = None,
        order_status: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计符合条件的订单数"""
        conditions = [Order.is_delete == False]  # noqa: E712
        if channel_code:
            conditions.append(Order.channel_code == channel_code)
        if order_status is not None:
            conditions.append(Order.order_status == order_status)
        if start_time:
            conditions.append(Order.create_time >= start_time)
        if end_time:
            conditions.append(Order.create_time < end_time)

        stmt = select(func.count()).select_from(Order).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar() or 0


# ════════════════════════════════════════════════════════════
# 3. 佣金账单对账查询 DAO（只读）
# ════════════════════════════════════════════════════════════


class ChannelCommissionBillQueryDAO:
    """佣金账单对账查询 DAO（只读）"""

    def __init__(self, session):
        self.session = session

    async def query_commission_flows(
        self,
        channel_code: Optional[str] = None,
        flow_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10000,
        offset: int = 0,
    ) -> List[Any]:
        """查询佣金流水列表（需关联 orders 表获取渠道信息）

        Returns:
            包含 orders 和 commission_flow 联合数据的列表
        """
        conditions = [
            CommissionFlow.is_delete == False,  # noqa: E712
            Order.is_delete == False,  # noqa: E712
        ]
        if channel_code:
            conditions.append(Order.channel_code == channel_code)
        if flow_type:
            conditions.append(CommissionFlow.flow_type == flow_type)
        if start_time:
            conditions.append(CommissionFlow.create_time >= start_time)
        if end_time:
            conditions.append(CommissionFlow.create_time < end_time)

        stmt = (
            select(
                Order.internal_order_no,
                Order.out_order_no,
                Order.channel_code,
                CommissionFlow.user_id,
                CommissionFlow.flow_type,
                CommissionFlow.amount,
                CommissionFlow.before_balance,
                CommissionFlow.after_balance,
                CommissionFlow.transfer_status,
                CommissionFlow.create_time,
            )
            .join(Order, CommissionFlow.order_id == Order.id, isouter=True)
            .where(and_(*conditions))
            .order_by(CommissionFlow.create_time.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def count_commission_flows(
        self,
        channel_code: Optional[str] = None,
        flow_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计符合条件的佣金流水数"""
        conditions = [
            CommissionFlow.is_delete == False,  # noqa: E712
            Order.is_delete == False,  # noqa: E712
        ]
        if channel_code:
            conditions.append(Order.channel_code == channel_code)
        if flow_type:
            conditions.append(CommissionFlow.flow_type == flow_type)
        if start_time:
            conditions.append(CommissionFlow.create_time >= start_time)
        if end_time:
            conditions.append(CommissionFlow.create_time < end_time)

        stmt = (
            select(func.count())
            .select_from(CommissionFlow)
            .join(Order, CommissionFlow.order_id == Order.id, isouter=True)
            .where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_reconciliation_summary(
        self,
        channel_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """佣金账单对账汇总

        Returns:
            {
                "total_order_count": 订单总数,
                "total_commission": 总佣金,
                "total_user_commission": 用户佣金,
                "total_platform_commission": 平台佣金,
                "total_flow_count": 流水总数,
                "total_flow_amount": 流水总金额,
                "channel_summary": [{channel_code, order_count, total_commission}, ...]
            }
        """
        # 订单汇总
        order_conditions = [Order.is_delete == False]  # noqa: E712
        if channel_code:
            order_conditions.append(Order.channel_code == channel_code)
        if start_time:
            order_conditions.append(Order.create_time >= start_time)
        if end_time:
            order_conditions.append(Order.create_time < end_time)

        order_stmt = (
            select(
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("total_user_commission"),
                func.coalesce(func.sum(Order.platform_commission), 0).label("total_platform_commission"),
            )
            .where(and_(*order_conditions))
        )
        order_result = await self.session.execute(order_stmt)
        order_row = order_result.one()

        # 佣金流水汇总
        flow_conditions = [CommissionFlow.is_delete == False]  # noqa: E712
        if start_time:
            flow_conditions.append(CommissionFlow.create_time >= start_time)
        if end_time:
            flow_conditions.append(CommissionFlow.create_time < end_time)

        flow_stmt = (
            select(
                func.count(CommissionFlow.id).label("flow_count"),
                func.coalesce(func.sum(CommissionFlow.amount), 0).label("flow_amount"),
            )
            .where(and_(*flow_conditions))
        )
        flow_result = await self.session.execute(flow_stmt)
        flow_row = flow_result.one()

        # 按渠道分组汇总
        channel_conditions = [Order.is_delete == False]  # noqa: E712
        if start_time:
            channel_conditions.append(Order.create_time >= start_time)
        if end_time:
            channel_conditions.append(Order.create_time < end_time)

        channel_stmt = (
            select(
                Order.channel_code.label("channel_code"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
            )
            .where(and_(*channel_conditions))
            .group_by(Order.channel_code)
            .order_by(func.sum(Order.total_commission).desc())
        )
        channel_result = await self.session.execute(channel_stmt)
        channel_rows = channel_result.all()

        return {
            "total_order_count": order_row.order_count,
            "total_commission": str(round(float(order_row.total_commission), 2)),
            "total_user_commission": str(round(float(order_row.total_user_commission), 2)),
            "total_platform_commission": str(round(float(order_row.total_platform_commission), 2)),
            "total_flow_count": flow_row.flow_count,
            "total_flow_amount": str(round(float(flow_row.flow_amount), 2)),
            "channel_summary": [
                {
                    "channel_code": r.channel_code or "unknown",
                    "order_count": r.order_count,
                    "total_commission": str(round(float(r.total_commission), 2)),
                }
                for r in channel_rows
            ],
        }
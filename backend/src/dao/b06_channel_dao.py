# @ai-generated
"""
B06 渠道管理 DAO（新建文件，不修改 B01-B15 任何基线 DAO）

包含：
1. ChannelCommissionConfigDAO - 渠道佣金比例配置数据访问
2. ChannelDashboardQueryDAO - 渠道数据看板查询（只读）
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.business.order_model import Order
from src.models.system.b06_channel_config import ChannelCommissionConfig

logger = logging.getLogger("dao.b06_channel")


class ChannelCommissionConfigDAO(BaseDAO):
    """渠道佣金比例配置 DAO"""

    model_class = ChannelCommissionConfig

    async def get_by_channel_and_user_type(
        self, channel_code: str, user_type: int
    ) -> Optional[ChannelCommissionConfig]:
        """按渠道编码和用户类型查询佣金配置"""
        stmt = self._active_query().where(
            and_(
                ChannelCommissionConfig.channel_code == channel_code,
                ChannelCommissionConfig.user_type == user_type,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_channel(
        self, channel_code: str
    ) -> List[ChannelCommissionConfig]:
        """查询指定渠道的所有佣金配置"""
        stmt = self._active_query().where(
            ChannelCommissionConfig.channel_code == channel_code
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_commission_config(
        self,
        channel_code: str,
        user_type: int,
        user_commission_rate: float,
        platform_retention_rate: float,
        remark: str = "",
    ) -> ChannelCommissionConfig:
        """新增或更新渠道佣金比例配置

        Args:
            channel_code: 渠道标识
            user_type: 用户类型
            user_commission_rate: 用户返利比例
            platform_retention_rate: 平台留存比例
            remark: 备注
        Returns:
            更新后的配置实例
        """
        existing = await self.get_by_channel_and_user_type(channel_code, user_type)
        if existing:
            existing.user_commission_rate = user_commission_rate
            existing.platform_retention_rate = platform_retention_rate
            existing.remark = remark
            await self.session.flush()
            await self.session.commit()
            return existing
        else:
            data = {
                "channel_code": channel_code,
                "user_type": user_type,
                "user_commission_rate": user_commission_rate,
                "platform_retention_rate": platform_retention_rate,
                "remark": remark,
            }
            return await self.create(data)

    async def delete_by_channel(self, channel_code: str) -> int:
        """删除指定渠道的所有佣金配置"""
        stmt = (
            select(ChannelCommissionConfig)
            .where(
                and_(
                    ChannelCommissionConfig.channel_code == channel_code,
                    ChannelCommissionConfig.is_delete == False,  # noqa: E712
                )
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


class ChannelDashboardQueryDAO:
    """渠道数据看板查询 DAO（只读）

    基于 orders 表聚合查询各渠道的订单和佣金数据
    """

    def __init__(self, session):
        self.session = session

    async def get_channel_summary(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """渠道数据看板汇总

        按渠道维度聚合：订单数、总佣金、用户佣金、平台佣金
        Returns:
            [{"channel_code": "myq", "channel_name": "喵有券",
              "order_count": 100, "total_commission": "1234.56",
              "user_commission": "617.28", "platform_commission": "617.28"}, ...]
        """
        conditions = [Order.is_delete == False]  # noqa: E712
        if start_date:
            conditions.append(Order.create_time >= start_date)
        if end_date:
            conditions.append(Order.create_time < end_date)

        stmt = (
            select(
                Order.channel_code.label("channel_code"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
                func.count(Order.id).label("order_count"),
            )
            .where(and_(*conditions))
            .group_by(Order.channel_code)
            .order_by(func.sum(Order.total_commission).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        items = []
        for row in rows:
            total = float(row.total_commission)
            user_part = float(row.user_commission)
            platform_part = total - user_part
            items.append({
                "channel_code": row.channel_code or "unknown",
                "order_count": row.order_count,
                "total_commission": str(round(total, 2)),
                "user_commission": str(round(user_part, 2)),
                "platform_commission": str(round(platform_part, 2)),
            })
        return items

    async def get_channel_detail(
        self,
        channel_code: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """单个渠道的详细统计数据

        Returns:
            {"channel_code": "myq", "order_count": 100,
             "total_commission": "1234.56", "user_commission": "617.28",
             "platform_commission": "617.28", "avg_commission": "12.35"}
        """
        conditions = [
            Order.is_delete == False,  # noqa: E712
            Order.channel_code == channel_code,
        ]
        if start_date:
            conditions.append(Order.create_time >= start_date)
        if end_date:
            conditions.append(Order.create_time < end_date)

        stmt = (
            select(
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
                func.coalesce(func.avg(Order.total_commission), 0).label("avg_commission"),
            )
            .where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        row = result.one()

        total = float(row.total_commission)
        user_part = float(row.user_commission)
        platform_part = total - user_part

        return {
            "channel_code": channel_code,
            "order_count": row.order_count,
            "total_commission": str(round(total, 2)),
            "user_commission": str(round(user_part, 2)),
            "platform_commission": str(round(platform_part, 2)),
            "avg_commission": str(round(float(row.avg_commission), 2)),
        }

    async def get_channel_trend(
        self,
        channel_code: str,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "day",
    ) -> List[Dict[str, Any]]:
        """渠道趋势数据（按天/周/月分组）

        Args:
            channel_code: 渠道标识
            start_date: 起始日期
            end_date: 截止日期
            group_by: 分组维度 day/week/month
        Returns:
            [{"date": "2026-08-01", "order_count": 10, "total_commission": "123.45"}, ...]
        """
        conditions = [
            Order.is_delete == False,  # noqa: E712
            Order.channel_code == channel_code,
            Order.create_time >= start_date,
            Order.create_time < end_date,
        ]

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
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
            )
            .where(and_(*conditions))
            .group_by(date_func)
            .order_by(date_func.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "date": str(row.stat_date),
                "order_count": row.order_count,
                "total_commission": str(round(float(row.total_commission), 2)),
                "user_commission": str(round(float(row.user_commission), 2)),
            }
            for row in rows
        ]

    async def get_all_channels_summary_trend(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "day",
    ) -> List[Dict[str, Any]]:
        """全渠道汇总趋势数据（按天/周/月分组）

        Returns:
            [{"date": "2026-08-01", "order_count": 50, "total_commission": "1234.56",
              "user_commission": "617.28"}, ...]
        """
        conditions = [
            Order.is_delete == False,  # noqa: E712
            Order.create_time >= start_date,
            Order.create_time < end_date,
        ]

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
                func.coalesce(func.sum(Order.total_commission), 0).label("total_commission"),
                func.coalesce(func.sum(Order.user_commission), 0).label("user_commission"),
            )
            .where(and_(*conditions))
            .group_by(date_func)
            .order_by(date_func.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "date": str(row.stat_date),
                "order_count": row.order_count,
                "total_commission": str(round(float(row.total_commission), 2)),
                "user_commission": str(round(float(row.user_commission), 2)),
            }
            for row in rows
        ]
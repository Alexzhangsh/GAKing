# @ai-generated
"""
B11-1 渠道管理 DAO（新建文件，不修改 B01-B15 任何基线 DAO）

包含：
1. ChannelBlacklistDAO - 渠道黑名单数据访问
2. ChannelDailyStatDAO - 渠道每日统计数据访问
3. ChannelConfigLogDAO - 渠道配置变更日志数据访问
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select

from src.dao.base_dao import BaseDAO
from src.models.system.b11_channel_blacklist import ChannelBlacklist
from src.models.system.b11_channel_daily_stat import ChannelDailyStat
from src.models.system.b11_channel_config_log import ChannelConfigLog

logger = logging.getLogger("dao.b11_channel")


class ChannelBlacklistDAO(BaseDAO):
    """渠道黑名单 DAO"""

    model_class = ChannelBlacklist

    async def get_by_value(self, channel_code: str, blacklist_type: str, blacklist_value: str) -> Optional[ChannelBlacklist]:
        """按渠道、类型和值查询黑名单记录"""
        stmt = self._active_query().where(
            and_(
                ChannelBlacklist.channel_code == channel_code,
                ChannelBlacklist.blacklist_type == blacklist_type,
                ChannelBlacklist.blacklist_value == blacklist_value,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_channel(
        self,
        channel_code: Optional[str] = None,
        blacklist_type: Optional[str] = None,
        status: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ChannelBlacklist], int]:
        """分页查询黑名单列表

        Args:
            channel_code: 渠道标识（可选）
            blacklist_type: 黑名单类型（可选）
            status: 状态（可选）
            keyword: 搜索关键词（可选，匹配黑名单值）
            page: 页码
            page_size: 每页条数
        Returns:
            (items, total)
        """
        conditions = []
        if channel_code:
            conditions.append(ChannelBlacklist.channel_code == channel_code)
        if blacklist_type:
            conditions.append(ChannelBlacklist.blacklist_type == blacklist_type)
        if status is not None:
            conditions.append(ChannelBlacklist.status == status)
        if keyword:
            conditions.append(ChannelBlacklist.blacklist_value.like(f"%{keyword}%"))

        # 总数
        count_stmt = select(func.count()).select_from(ChannelBlacklist).where(
            and_(ChannelBlacklist.is_delete == False, *conditions)  # noqa: E712
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total == 0:
            return [], 0

        # 列表
        offset = (page - 1) * page_size
        stmt = (
            self._active_query()
            .where(and_(*conditions))
            .order_by(ChannelBlacklist.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def is_blacklisted(self, channel_code: str, blacklist_type: str, blacklist_value: str) -> bool:
        """检查指定值是否在黑名单中（仅检查启用状态）"""
        stmt = self._active_query().where(
            and_(
                ChannelBlacklist.channel_code == channel_code,
                ChannelBlacklist.blacklist_type == blacklist_type,
                ChannelBlacklist.blacklist_value == blacklist_value,
                ChannelBlacklist.status == 1,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_blacklist(self, data: Dict[str, Any]) -> ChannelBlacklist:
        """新增黑名单记录"""
        return await self.create(data)

    async def remove_blacklist(self, item_id: int) -> bool:
        """移除黑名单（软删除）"""
        item = await self.get_by_id(item_id)
        if item is None:
            return False
        item.is_delete = True
        await self.session.flush()
        await self.session.commit()
        return True

    async def toggle_status(self, item_id: int, status: int) -> Optional[ChannelBlacklist]:
        """启停黑名单"""
        item = await self.get_by_id(item_id)
        if item is None:
            return None
        item.status = status
        await self.session.flush()
        await self.session.commit()
        return item


class ChannelDailyStatDAO(BaseDAO):
    """渠道每日统计 DAO"""

    model_class = ChannelDailyStat

    async def get_by_date_and_channel(self, stat_date: date, channel_code: str) -> Optional[ChannelDailyStat]:
        """按日期和渠道查询统计记录"""
        stmt = self._active_query().where(
            and_(
                ChannelDailyStat.stat_date == stat_date,
                ChannelDailyStat.channel_code == channel_code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_stat(
        self,
        stat_date: date,
        channel_code: str,
        order_count: int,
        total_pay_amount: float,
        total_commission: float,
        user_commission: float,
        platform_commission: float,
        settled_count: int,
        refund_count: int,
        refund_amount: float,
    ) -> ChannelDailyStat:
        """新增或更新渠道每日统计"""
        existing = await self.get_by_date_and_channel(stat_date, channel_code)
        if existing:
            existing.order_count = order_count
            existing.total_pay_amount = total_pay_amount
            existing.total_commission = total_commission
            existing.user_commission = user_commission
            existing.platform_commission = platform_commission
            existing.settled_count = settled_count
            existing.refund_count = refund_count
            existing.refund_amount = refund_amount
            await self.session.flush()
            await self.session.commit()
            return existing
        else:
            data = {
                "stat_date": stat_date,
                "channel_code": channel_code,
                "order_count": order_count,
                "total_pay_amount": total_pay_amount,
                "total_commission": total_commission,
                "user_commission": user_commission,
                "platform_commission": platform_commission,
                "settled_count": settled_count,
                "refund_count": refund_count,
                "refund_amount": refund_amount,
            }
            return await self.create(data)

    async def list_by_date_range(
        self,
        start_date: date,
        end_date: date,
        channel_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ChannelDailyStat], int]:
        """按日期范围查询统计列表"""
        conditions = [
            ChannelDailyStat.stat_date >= start_date,
            ChannelDailyStat.stat_date <= end_date,
        ]
        if channel_code:
            conditions.append(ChannelDailyStat.channel_code == channel_code)

        count_stmt = select(func.count()).select_from(ChannelDailyStat).where(
            and_(ChannelDailyStat.is_delete == False, *conditions)  # noqa: E712
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size
        stmt = (
            self._active_query()
            .where(and_(*conditions))
            .order_by(ChannelDailyStat.stat_date.desc(), ChannelDailyStat.channel_code.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_summary_by_date_range(
        self, start_date: date, end_date: date, channel_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """按渠道汇总日期范围内的统计数据"""
        conditions = [
            ChannelDailyStat.stat_date >= start_date,
            ChannelDailyStat.stat_date <= end_date,
        ]
        if channel_code:
            conditions.append(ChannelDailyStat.channel_code == channel_code)

        stmt = (
            select(
                ChannelDailyStat.channel_code,
                func.sum(ChannelDailyStat.order_count).label("total_order_count"),
                func.sum(ChannelDailyStat.total_pay_amount).label("total_pay_amount"),
                func.sum(ChannelDailyStat.total_commission).label("total_commission"),
                func.sum(ChannelDailyStat.user_commission).label("user_commission"),
                func.sum(ChannelDailyStat.platform_commission).label("platform_commission"),
                func.sum(ChannelDailyStat.settled_count).label("total_settled_count"),
                func.sum(ChannelDailyStat.refund_count).label("total_refund_count"),
                func.sum(ChannelDailyStat.refund_amount).label("total_refund_amount"),
            )
            .where(and_(ChannelDailyStat.is_delete == False, *conditions))  # noqa: E712
            .group_by(ChannelDailyStat.channel_code)
            .order_by(ChannelDailyStat.channel_code.asc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "channel_code": row.channel_code,
                "total_order_count": int(row.total_order_count or 0),
                "total_pay_amount": str(round(float(row.total_pay_amount or 0), 2)),
                "total_commission": str(round(float(row.total_commission or 0), 2)),
                "user_commission": str(round(float(row.user_commission or 0), 2)),
                "platform_commission": str(round(float(row.platform_commission or 0), 2)),
                "total_settled_count": int(row.total_settled_count or 0),
                "total_refund_count": int(row.total_refund_count or 0),
                "total_refund_amount": str(round(float(row.total_refund_amount or 0), 2)),
            }
            for row in rows
        ]


class ChannelConfigLogDAO(BaseDAO):
    """渠道配置变更日志 DAO"""

    model_class = ChannelConfigLog

    async def create_log(self, data: Dict[str, Any]) -> ChannelConfigLog:
        """创建变更日志"""
        return await self.create(data)

    async def list_by_channel(
        self,
        channel_code: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ChannelConfigLog], int]:
        """分页查询变更日志"""
        conditions = []
        if channel_code:
            conditions.append(ChannelConfigLog.channel_code == channel_code)
        if operation_type:
            conditions.append(ChannelConfigLog.operation_type == operation_type)
        if start_time:
            conditions.append(ChannelConfigLog.create_time >= start_time)
        if end_time:
            conditions.append(ChannelConfigLog.create_time < end_time)

        count_stmt = select(func.count()).select_from(ChannelConfigLog).where(
            and_(ChannelConfigLog.is_delete == False, *conditions)  # noqa: E712
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size
        stmt = (
            self._active_query()
            .where(and_(*conditions))
            .order_by(ChannelConfigLog.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total
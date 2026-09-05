# @ai-generated
"""
点击行为日志表 DAO
继承 BaseDAO 通用能力，扩展点击日志专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, func

from src.dao.base_dao import BaseDAO
from src.models.business.click_log_model import ClickLog

logger = logging.getLogger("dao.click_log")


class ClickLogDAO(BaseDAO):
    """点击行为日志 DAO"""

    model_class = ClickLog

    def __init__(self, session):
        super().__init__(session)

    async def find_recent_clicks(
        self,
        goods_id: str,
        hours: int = 72,
        channel_code: str = "",
    ) -> List[ClickLog]:
        """查找某商品最近 N 小时内的点击记录（按访问时间倒序）

        用于跟单匹配：按 goods_id 查找 72h 窗口内的所有点击记录，
        按 last-click 规则取最新一条。

        Args:
            goods_id: 商品ID
            hours: 时间窗口（小时），默认 72
            channel_code: 渠道标识（可选过滤）
        Returns:
            点击记录列表（按 access_time DESC）
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        conditions = [
            ClickLog.goods_id == goods_id,
            ClickLog.access_time >= cutoff,
            ClickLog.is_delete == False,  # noqa: E712
        ]
        if channel_code:
            conditions.append(ClickLog.source_channel == channel_code)

        stmt = (
            select(ClickLog)
            .where(and_(*conditions))
            .order_by(ClickLog.access_time.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_recent_clicks_by_user(
        self,
        user_id: int,
        goods_id: str,
        hours: int = 72,
    ) -> List[ClickLog]:
        """查找某用户对某商品最近 N 小时内的点击记录

        Args:
            user_id: 用户ID
            goods_id: 商品ID
            hours: 时间窗口（小时），默认 72
        Returns:
            点击记录列表（按 access_time DESC）
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        conditions = [
            ClickLog.user_id == user_id,
            ClickLog.goods_id == goods_id,
            ClickLog.access_time >= cutoff,
            ClickLog.is_delete == False,  # noqa: E712
        ]
        stmt = (
            select(ClickLog)
            .where(and_(*conditions))
            .order_by(ClickLog.access_time.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_recent_clicks_by_user(
        self, user_id: int, hours: int = 72
    ) -> int:
        """统计某用户最近 N 小时内的点击总次数

        Args:
            user_id: 用户ID
            hours: 时间窗口（小时）
        Returns:
            点击总次数
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        stmt = select(func.count()).where(
            and_(
                ClickLog.user_id == user_id,
                ClickLog.access_time >= cutoff,
                ClickLog.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
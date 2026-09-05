# @ai-generated
"""
F04-2 渠道佣金策略 DAO（新建文件，不修改 B01-B15 任何基线 DAO）

包含：
1. ChannelCommissionStrategyDAO - 佣金策略主表数据访问
2. ChannelCommissionTierDAO     - 阶梯佣金明细数据访问
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select

from src.dao.base_dao import BaseDAO
from src.models.system.f04_channel_commission import (
    ChannelCommissionStrategy,
    ChannelCommissionTier,
)

logger = logging.getLogger("dao.f04_channel_commission")


class ChannelCommissionStrategyDAO(BaseDAO):
    """渠道佣金策略主表 DAO"""

    model_class = ChannelCommissionStrategy

    async def get_by_channel_code(self, channel_code: str) -> Optional[ChannelCommissionStrategy]:
        """按渠道标识查询策略（未软删除）"""
        stmt = self._active_query().where(
            ChannelCommissionStrategy.channel_code == channel_code
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate_strategies(
        self,
        page: int = 1,
        page_size: int = 20,
        channel_code: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Tuple[List[ChannelCommissionStrategy], int]:
        """分页查询策略列表（支持渠道/生效状态筛选）"""
        stmt = self._active_query()
        if channel_code:
            stmt = stmt.where(ChannelCommissionStrategy.channel_code == channel_code)
        if enabled is not None:
            stmt = stmt.where(ChannelCommissionStrategy.enabled == enabled)

        # 统计总数
        from sqlalchemy import func

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(ChannelCommissionStrategy.create_time.desc())
        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        return list(result.scalars().all()), total


class ChannelCommissionTierDAO(BaseDAO):
    """渠道佣金阶梯明细 DAO"""

    model_class = ChannelCommissionTier

    async def list_by_strategy(self, strategy_id: int) -> List[ChannelCommissionTier]:
        """查询策略下的全部阶梯明细（按用户类型+排序号）"""
        stmt = (
            self._active_query()
            .where(ChannelCommissionTier.strategy_id == strategy_id)
            .order_by(
                ChannelCommissionTier.user_type.asc(),
                ChannelCommissionTier.sort_order.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_strategy(self, strategy_id: int) -> int:
        """软删除策略下的全部阶梯明细"""
        stmt = (
            select(ChannelCommissionTier)
            .where(
                and_(
                    ChannelCommissionTier.strategy_id == strategy_id,
                    ChannelCommissionTier.is_delete == False,  # noqa: E712
                )
            )
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        now = datetime.now()
        for item in items:
            item.is_delete = True
            item.update_time = now
        await self.session.flush()
        await self.session.commit()
        return len(items)

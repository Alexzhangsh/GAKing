# @ai-generated
"""
短链映射表 DAO
继承 BaseDAO 通用能力，扩展短链专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_

from src.dao.base_dao import BaseDAO
from src.models.business.short_link_model import ShortLink

logger = logging.getLogger("dao.short_link")


class ShortLinkDAO(BaseDAO):
    """短链映射 DAO"""

    model_class = ShortLink

    def __init__(self, session):
        super().__init__(session)

    async def get_by_short_key(self, short_key: str) -> Optional[ShortLink]:
        """按短链 key 唯一查询（自动过滤软删除）

        Args:
            short_key: 短链唯一标识
        Returns:
            ShortLink 实例 或 None
        """
        stmt = self._active_query().where(ShortLink.short_key == short_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_by_user_and_goods(
        self, user_id: int, goods_id: str, channel_code: str = ""
    ) -> List[ShortLink]:
        """查询某用户对某商品的未过期短链

        Args:
            user_id: 用户ID
            goods_id: 商品ID
            channel_code: 渠道标识（可选）
        Returns:
            未过期的短链列表
        """
        now = datetime.now()
        conditions = [
            ShortLink.user_id == user_id,
            ShortLink.goods_id == goods_id,
            ShortLink.expire_at > now,
            ShortLink.is_delete == False,  # noqa: E712
        ]
        if channel_code:
            conditions.append(ShortLink.channel_code == channel_code)

        stmt = select(ShortLink).where(and_(*conditions)).order_by(ShortLink.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_click_count(self, link_id: int) -> None:
        """递增短链点击次数（原子更新）

        Args:
            link_id: 短链 ID
        """
        link = await self.get_by_id(link_id)
        if link is None:
            return
        link.click_count = (link.click_count or 0) + 1
        link.last_click_at = datetime.now()
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning("increment_click_count 提交失败: short_link_id=%s", link_id)
            raise
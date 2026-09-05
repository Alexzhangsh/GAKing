# @ai-generated
"""
商品管理扩展表 DAO
继承 BaseDAO 通用能力，扩展商品管理业务专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update

from src.dao.base_dao import BaseDAO
from src.models.business.goods_management_model import GoodsManagement

logger = logging.getLogger("dao.goods_management")


class GoodsManagementDAO(BaseDAO):
    """商品管理扩展表 DAO"""

    model_class = GoodsManagement

    def __init__(self, session):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def get_by_goods_id_channel(
        self, goods_id: str, source_channel: str
    ) -> Optional[GoodsManagement]:
        """按 CPS 商品ID + 渠道码查询（联合唯一）"""
        stmt = (
            self._active_query()
            .where(
                and_(
                    GoodsManagement.goods_id == goods_id,
                    GoodsManagement.source_channel == source_channel,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        keyword: Optional[str] = None,
        source_channel: Optional[str] = None,
        shelf_status: Optional[str] = None,
        category: Optional[str] = None,
        sync_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[GoodsManagement], int]:
        """多条件筛选分页查询（支持 keyword 模糊搜索商品标题）"""
        stmt = self._active_query()

        if keyword:
            stmt = stmt.where(GoodsManagement.goods_title.like(f"%{keyword}%"))
        if source_channel:
            stmt = stmt.where(GoodsManagement.source_channel == source_channel)
        if shelf_status:
            stmt = stmt.where(GoodsManagement.shelf_status == shelf_status)
        if category:
            stmt = stmt.where(GoodsManagement.category == category)
        if sync_status:
            stmt = stmt.where(GoodsManagement.sync_status == sync_status)

        # 统计总数
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询（按 sort_order 升序 + create_time 降序）
        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(
                GoodsManagement.sort_order.asc(),
                GoodsManagement.create_time.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def count_by_shelf_status(
        self,
        keyword: Optional[str] = None,
        source_channel: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, int]:
        """按上下架状态统计商品总数（不含 shelf_status 过滤，保证上架/下架两数都有意义）

        与 list_with_filters 共用 keyword/source_channel/category 过滤条件，
        但不应用 shelf_status 过滤，避免筛选上架时下架数恒为 0。
        """
        conditions = [GoodsManagement.is_delete == False]  # noqa: E712
        if keyword:
            conditions.append(GoodsManagement.goods_title.like(f"%{keyword}%"))
        if source_channel:
            conditions.append(GoodsManagement.source_channel == source_channel)
        if category:
            conditions.append(GoodsManagement.category == category)

        stmt = (
            select(
                GoodsManagement.shelf_status,
                func.count(GoodsManagement.id).label("cnt"),
            )
            .where(and_(*conditions))
            .group_by(GoodsManagement.shelf_status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        stats = {"on_shelf": 0, "off_shelf": 0}
        for row in rows:
            if row.shelf_status in stats:
                stats[row.shelf_status] = row.cnt
        return stats

    async def list_by_goods_ids(
        self, goods_ids: List[str], source_channel: str
    ) -> List[GoodsManagement]:
        """按 goods_id 列表 + 渠道批量查询本地管理记录（用于 CPS 搜索结果覆盖）"""
        if not goods_ids:
            return []
        stmt = self._active_query().where(
            and_(
                GoodsManagement.goods_id.in_(goods_ids),
                GoodsManagement.source_channel == source_channel,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_by_goods_channel(
        self, goods_id: str, source_channel: str, data: Dict[str, Any]
    ) -> GoodsManagement:
        """按 goods_id + source_channel upsert（存在则更新，不存在则创建）"""
        existing = await self.get_by_goods_id_channel(goods_id, source_channel)
        if existing:
            # 更新（仅刷新动态字段，静态资料不覆盖）
            return await self.update_by_id(existing.id, data)
        else:
            # 创建
            data["goods_id"] = goods_id
            data["source_channel"] = source_channel
            data["last_sync_time"] = data.get("last_sync_time", datetime.now())
            return await self.create(data)

    async def batch_update_shelf_status(
        self, goods_ids: List[str], source_channel: str, shelf_status: str
    ) -> int:
        """批量更新上下架状态（同渠道下多个商品）"""
        stmt = (
            update(GoodsManagement)
            .where(
                and_(
                    GoodsManagement.goods_id.in_(goods_ids),
                    GoodsManagement.source_channel == source_channel,
                    GoodsManagement.is_delete == False,  # noqa: E712
                )
            )
            .values(shelf_status=shelf_status)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    # ── B16 预热任务专用查询方法 ─────────────────────────

    async def list_hot_products(
        self, source_channel: Optional[str] = None, limit: int = 1000
    ) -> List[GoodsManagement]:
        """查询热门商品（popularity > 0 且 sync_status=normal）

        用于热门商品定时刷新（每 6 小时）
        """
        stmt = self._active_query().where(
            and_(
                GoodsManagement.popularity > 0,
                GoodsManagement.sync_status == "normal",
            )
        )
        if source_channel:
            stmt = stmt.where(GoodsManagement.source_channel == source_channel)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_normal_products(
        self, source_channel: Optional[str] = None, limit: int = 5000
    ) -> List[GoodsManagement]:
        """查询普通商品（popularity = 0 且 sync_status=normal）

        用于普通商品每日刷新（每日 02:00）
        """
        stmt = self._active_query().where(
            and_(
                GoodsManagement.popularity == 0,
                GoodsManagement.sync_status == "normal",
            )
        )
        if source_channel:
            stmt = stmt.where(GoodsManagement.source_channel == source_channel)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_expired_products(
        self, expiry_days: int = 30
    ) -> List[GoodsManagement]:
        """查询连续 expiry_days 天无浏览记录的过期商品（sync_status=normal 且 last_visit_time 超期）

        用于冷品清理：标记为 expired
        """
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff - timedelta(days=expiry_days)
        stmt = self._active_query().where(
            and_(
                GoodsManagement.sync_status == "normal",
                GoodsManagement.last_visit_time < cutoff,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_soft_delete_candidates(
        self, grace_days: int = 7
    ) -> List[GoodsManagement]:
        """查询已过期且超过 grace_days 宽限期仍未浏览的商品

        用于冷品清理：执行软删除
        """
        cutoff = datetime.now() - timedelta(days=grace_days)
        stmt = self._active_query().where(
            and_(
                GoodsManagement.sync_status == "expired",
                GoodsManagement.last_visit_time < cutoff,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def batch_update_sync_status(
        self, ids: List[int], sync_status: str
    ) -> int:
        """批量更新同步状态"""
        if not ids:
            return 0
        stmt = (
            update(GoodsManagement)
            .where(
                and_(
                    GoodsManagement.id.in_(ids),
                    GoodsManagement.is_delete == False,  # noqa: E712
                )
            )
            .values(sync_status=sync_status, update_time=datetime.now())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def batch_soft_delete(self, ids: List[int]) -> int:
        """批量软删除"""
        if not ids:
            return 0
        stmt = (
            update(GoodsManagement)
            .where(GoodsManagement.id.in_(ids))
            .values(is_delete=True, update_time=datetime.now())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def count_by_category(
        self, source_channel: str
    ) -> List[Dict[str, Any]]:
        """按类目统计商品数量（用于预热任务轮换类目选择）"""
        stmt = (
            select(
                GoodsManagement.category,
                func.count(GoodsManagement.id).label("cnt"),
            )
            .where(
                and_(
                    GoodsManagement.source_channel == source_channel,
                    GoodsManagement.is_delete == False,  # noqa: E712
                    GoodsManagement.sync_status == "normal",
                )
            )
            .group_by(GoodsManagement.category)
            .order_by(func.count(GoodsManagement.id).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [{"category": row.category, "count": row.cnt} for row in rows]

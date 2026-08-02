# @ai-generated
"""
订单主表 DAO
继承 BaseDAO 通用能力，扩展订单业务专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.redis_client import RedisClient
from src.config.constants import (
    CacheTTL,
    OrderStatus,
    CACHE_KEY_COMMISSION_SUM,
    CACHE_KEY_ORDER_DETAIL,
)
from src.dao.base_dao import BaseDAO
from src.models.business.order_model import Order
from src.models.business.commission_flow_model import CommissionFlow

logger = logging.getLogger("dao.order")


class OrderDAO(BaseDAO):
    """导购订单 DAO"""

    model_class = Order

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def get_by_order_no(
        self, order_no: str
    ) -> Optional[Order]:
        """通过外部渠道订单号唯一查询（自动过滤软删除）

        Args:
            order_no: 渠道订单号 (out_order_no)
        Returns:
            订单实例 或 None
        """
        stmt = self._active_query().where(Order.out_order_no == order_no)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_channel_code(
        self,
        channel_code: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Order], int]:
        """按渠道编码分页查询订单

        Args:
            channel_code: 渠道标识 (myq / orderx)
            page: 页码
            page_size: 每页条数
        Returns:
            (订单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(Order.channel_code == channel_code)

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def list_by_order_status(
        self,
        order_status: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Order], int]:
        """按订单状态筛选查询

        Args:
            order_status: 订单状态值 (对应 OrderStatus 枚举)
            page: 页码
            page_size: 每页条数
        Returns:
            (订单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(Order.order_status == order_status)

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def get_order_with_commission_flows(
        self, order_id: int
    ) -> Optional[Order]:
        """预加载查询订单及其全部佣金流水（一对多关联）

        使用 selectinload 避免 N+1 查询，一次性获取订单和关联流水
        Args:
            order_id: 订单 ID
        Returns:
            订单实例 (commission_flows 已预加载) 或 None
        """
        stmt = (
            self._active_query()
            .options(selectinload(Order.commission_flows))
            .where(Order.id == order_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 订单详情缓存（读穿 + 主动失效） ──────────────────
    #
    # 缓存策略：
    # 1. key = gaking:prod:order:{order_id}，TTL=10min（CacheTTL.ORDER_DETAIL + ±20% 抖动）
    # 2. 读穿：未命中查库后回填；命中直接返回序列化 dict
    # 3. 防穿透：订单不存在时写入 __EMPTY__ 空标记，TTL=60s（防同一不存在的 ID 击穿）
    # 4. 失效：订单状态/字段变更（update_by_id、batch_update_order_status）主动 DEL
    #    佣金流水变更（生成/结算）由 CommissionFlowDAO 失效时一并 DEL 本 key
    # 5. 缓存值为订单 dict + commission_flows 列表（与 OrderService.get_order_detail 输出一致）
    async def get_order_detail_cached(self, order_id: int) -> Optional[Dict[str, Any]]:
        """按订单 ID 查询详情（含佣金流水），带 Redis 读穿缓存

        Args:
            order_id: 订单 ID
        Returns:
            订单详情 dict（含 commission_flows），订单不存在返回 None
        """
        key = f"{CACHE_KEY_ORDER_DETAIL}{order_id}"

        # 单次 GET 同时识别空标记与正常缓存，减少一次 round-trip
        raw = await RedisClient.get(key)
        if raw is not None:
            if raw == "__EMPTY__":
                logger.info("[cache_hit_empty] order detail order_id=%s", order_id)
                return None
            try:
                logger.info("[cache_hit] order detail order_id=%s", order_id)
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("[cache_corrupt] order detail order_id=%s, 回查库", order_id)

        # 未命中：查库并回填
        order = await self.get_order_with_commission_flows(order_id)
        if order is None:
            await RedisClient.set_empty_cache(key)  # 60s 空标记防穿透
            logger.info("[cache_miss_empty] order detail order_id=%s", order_id)
            return None

        order_dict = order.to_dict()
        flows = order.commission_flows or []
        order_dict["commission_flows"] = [
            f.to_dict() for f in flows if not f.is_delete
        ]
        await RedisClient.set_json(key, order_dict, expire=CacheTTL.ORDER_DETAIL)
        logger.info(
            "[cache_miss_set] order detail order_id=%s, flows=%s",
            order_id,
            len(order_dict["commission_flows"]),
        )
        return order_dict

    async def _invalidate_order_cache(self, order_id: int) -> None:
        """失效订单详情缓存（订单字段变更后调用）"""
        await RedisClient.delete(f"{CACHE_KEY_ORDER_DETAIL}{order_id}")
        logger.info("[cache_invalidate] order detail order_id=%s", order_id)

    async def update_by_id(
        self,
        item_id: int,
        data: Dict[str, Any],
    ) -> Optional[Order]:
        """覆写基类方法：订单字段更新后主动失效详情缓存

        item_id 即 order_id，故直接按其失效 order:{item_id}
        """
        result = await super().update_by_id(item_id, data)
        if result is not None:
            await self._invalidate_order_cache(item_id)
        return result

    async def batch_update_order_status(
        self,
        order_ids: List[int],
        order_status: int,
    ) -> int:
        """批量修改订单状态

        Args:
            order_ids: 订单 ID 列表
            order_status: 目标状态值
        Returns:
            实际更新的记录数
        """
        stmt = (
            update(Order)
            .where(
                and_(
                    Order.id.in_(order_ids),
                    Order.is_delete == False,  # noqa: E712
                )
            )
            .values(
                order_status=order_status,
                update_time=datetime.now(),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # 批量失效受影响订单的详情缓存
        for oid in order_ids:
            await self._invalidate_order_cache(oid)
        return result.rowcount or 0

    async def close_expired_unpaid_orders(
        self,
        cutoff: datetime,
    ) -> Tuple[List[int], int]:
        """关闭超时未支付订单：待支付(PENDING) 且 create_time < cutoff → 失效(INVALID)

        供定时任务调用，单次完成「查询 + 批量更新 + 提交 + 缓存失效」：
        1. 查询所有 order_status=PENDING 且 create_time<cutoff 的订单 ID；
        2. 批量更新为 INVALID（写操作自动 commit）；
        3. commit 成功后再失效各订单详情缓存（保证读不到旧状态的脏缓存）。

        Args:
            cutoff: 超时截止时间，create_time 早于该时间的待支付单将被关闭
        Returns:
            (被关闭的订单 ID 列表, 实际更新行数)；无符合条件的订单返回 ([], 0)
        """
        # 1. 查询超时待支付订单 ID（只取 id，避免加载整行）
        select_stmt = select(Order.id).where(
            and_(
                Order.order_status == int(OrderStatus.PENDING),
                Order.is_delete == False,  # noqa: E712
                Order.create_time < cutoff,
            )
        )
        result = await self.session.execute(select_stmt)
        order_ids: List[int] = [row[0] for row in result.all()]

        if not order_ids:
            return [], 0

        # 2. 批量更新为失效状态
        update_stmt = (
            update(Order)
            .where(
                and_(
                    Order.id.in_(order_ids),
                    Order.is_delete == False,  # noqa: E712
                )
            )
            .values(
                order_status=int(OrderStatus.INVALID),
                update_time=datetime.now(),
            )
        )
        update_result = await self.session.execute(update_stmt)
        affected = update_result.rowcount or 0
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "close_expired_unpaid_orders 提交失败已回滚 cutoff=%s",
                cutoff,
                exc_info=True,
            )
            raise

        # 3. commit 成功后失效各订单详情缓存（顺序：先持久化再失效，避免并发回填脏数据）
        for oid in order_ids:
            await self._invalidate_order_cache(oid)

        logger.info(
            "[dao] close_expired_unpaid_orders cutoff=%s closed_ids=%s affected=%s",
            cutoff,
            order_ids,
            affected,
        )
        return order_ids, affected

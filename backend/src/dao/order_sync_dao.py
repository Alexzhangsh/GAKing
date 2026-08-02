# @ai-generated
"""
订单同步专属 DAO（B05）

职责：
- 批量查重：按 out_order_no 列表 IN 查询已存在的渠道订单号
- user_id 反查：按 channel_pid + channel_code 查最近一条历史订单的 user_id
- 批量幂等插入：先查重过滤，再批量插入，IntegrityError 兜底回退逐条插入
- 批量状态更新：按 out_order_no 批量更新 order_status/pay_time/settle_time

设计约定：
1. 继承 BaseDAO 通用能力（_active_query / batch_create / commit 等），不修改 BaseDAO；
2. 仅做数据存取，业务逻辑（状态映射/游标推进/重试）在 OrderSyncService；
3. 写操作自动 commit（BaseDAO.batch_create 已实现）；
4. 批量插入失败时（IntegrityError 唯一索引冲突）回退逐条插入，保证部分成功；
5. 状态更新后失效订单详情缓存（复用 OrderDAO._invalidate_order_cache 的 Redis key 约定）。
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.redis_client import RedisClient
from src.config.constants import CACHE_KEY_ORDER_DETAIL
from src.dao.base_dao import BaseDAO
from src.models.business.order_model import Order

logger = logging.getLogger("dao.order_sync")


class OrderSyncDAO(BaseDAO):
    """订单同步专属 DAO

    与 OrderDAO 区别：
    - OrderDAO 面向 C 端订单详情/列表查询（带缓存读穿）
    - OrderSyncDAO 面向 B05 批量同步场景（批量查重/插入/状态更新，无详情缓存读穿）
    两者共用 Order 模型，互不修改。
    """

    model_class = Order

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 1. 批量查重：按 out_order_no 列表查询已存在的渠道订单号 ──────────

    async def list_existing_out_order_nos(self, out_order_nos: List[str]) -> Set[str]:
        """批量查询已存在的渠道订单号（自动过滤软删除）

        用于幂等入库前的查重过滤，避免重复插入触发唯一索引冲突。

        Args:
            out_order_nos: 渠道订单号列表
        Returns:
            已存在于数据库的渠道订单号集合；入参为空返回空集合
        """
        if not out_order_nos:
            return set()

        stmt = select(Order.out_order_no).where(
            and_(
                Order.out_order_no.in_(out_order_nos),
                Order.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result.all()}

    # ── 2. user_id 反查：按 channel_pid + channel_code 查历史订单 ────────

    async def find_user_id_by_channel_pid(
        self,
        channel_pid: str,
        channel_code: str,
    ) -> int:
        """按 channel_pid + channel_code 反查历史订单的 user_id

        业务背景：OrderDTO 只有 channel_pid（relation_id 推广位），无 user_id。
        通过同渠道同 pid 的历史订单反查 user_id（最近一条）。
        找不到返回 0（标记为待认领订单，由 OrderSyncService 日志告警）。

        Args:
            channel_pid: 渠道推广位 PID（relation_id）
            channel_code: 渠道标识（myq/orderx/dta）
        Returns:
            user_id（找不到返回 0）
        """
        if not channel_pid or not channel_code:
            return 0

        # 查最近一条同渠道同 pid 且 user_id>0 的订单
        stmt = (
            select(Order.user_id)
            .where(
                and_(
                    Order.channel_code == channel_code,
                    Order.user_id > 0,
                    Order.is_delete == False,  # noqa: E712
                )
            )
            .order_by(Order.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        return int(row[0]) if row else 0

    # ── 3. 批量幂等插入：先查重过滤，再批量插入 ──────────────────────────

    async def batch_upsert_orders(
        self,
        orders_data: List[Dict[str, Any]],
    ) -> Tuple[List[Order], int]:
        """批量幂等插入订单（out_order_no 唯一索引防重）

        流程：
        1. 提取所有 out_order_no，批量查重；
        2. 过滤掉已存在的订单，仅插入新订单；
        3. 批量插入（BaseDAO.batch_create 自动 commit）；
        4. IntegrityError 兜底：批量失败时回退逐条插入，保证部分成功。

        Args:
            orders_data: 订单字段数据字典列表（每个 dict 含 out_order_no 等字段）
        Returns:
            (成功插入的 Order 实例列表, 插入条数)
        """
        if not orders_data:
            return [], 0

        # 1. 批量查重
        out_order_nos = [
            d["out_order_no"] for d in orders_data if d.get("out_order_no")
        ]
        existing_nos = await self.list_existing_out_order_nos(out_order_nos)

        # 2. 过滤新订单
        new_orders_data = [
            d for d in orders_data if d.get("out_order_no") not in existing_nos
        ]
        skipped = len(orders_data) - len(new_orders_data)
        if skipped > 0:
            logger.info(
                "批量入库查重：%s 条订单中 %s 条已存在，跳过插入，新订单 %s 条",
                len(orders_data),
                skipped,
                len(new_orders_data),
            )

        if not new_orders_data:
            return [], 0

        # 3. 批量插入（自动 commit）
        try:
            inserted = await self.batch_create(new_orders_data)
            logger.info(
                "批量插入订单成功：%s 条（跳过已存在 %s 条）",
                len(inserted),
                skipped,
            )
            return list(inserted), len(inserted)
        except IntegrityError as e:
            # 并发场景下唯一索引冲突（查重时不存在，插入时已被其他进程写入）
            # 回退逐条插入，跳过冲突项
            logger.warning(
                "批量插入遭遇唯一索引冲突，回退逐条插入: %s",
                str(e)[:200],
            )
            await self.session.rollback()
            return await self._fallback_single_insert(new_orders_data)

    async def _fallback_single_insert(
        self, orders_data: List[Dict[str, Any]]
    ) -> Tuple[List[Order], int]:
        """逐条插入兜底（批量插入 IntegrityError 时使用）

        每条独立事务，单条失败不阻断其他订单。
        """
        inserted: List[Order] = []
        for data in orders_data:
            try:
                obj = Order(**data)
                self.session.add(obj)
                await self.session.flush()
                await self.session.commit()
                inserted.append(obj)
            except IntegrityError:
                # 单条冲突（并发写入），跳过
                await self.session.rollback()
                logger.debug(
                    "单条插入跳过（已存在）: out_order_no=%s",
                    data.get("out_order_no"),
                )
            except Exception as e:
                await self.session.rollback()
                logger.warning(
                    "单条插入失败: out_order_no=%s err=%s",
                    data.get("out_order_no"),
                    e,
                )
        logger.info("逐条插入兜底完成：成功 %s 条", len(inserted))
        return inserted, len(inserted)

    # ── 4. 批量状态更新：按 out_order_no 批量更新订单状态 ───────────────

    async def batch_update_status(
        self,
        updates: List[Dict[str, Any]],
    ) -> int:
        """按 out_order_no 批量更新订单状态

        每条 update dict 包含：
        - out_order_no: 渠道订单号（定位条件）
        - order_status: 目标状态值（OrderStatus 枚举 int）
        - pay_time: 支付时间（可选，None 不更新）
        - settle_time: 结算时间（可选，None 不更新）

        单条独立事务，单条失败不阻断其他订单，commit 后失效订单详情缓存。

        Args:
            updates: 更新数据列表
        Returns:
            实际更新成功的条数
        """
        if not updates:
            return 0

        affected = 0
        for u in updates:
            out_order_no = u.get("out_order_no")
            if not out_order_no:
                continue

            update_data: Dict[str, Any] = {
                "order_status": int(u["order_status"]),
                "update_time": datetime.now(),
            }
            # 仅更新非空时间字段
            if u.get("pay_time") is not None:
                update_data["pay_time"] = u["pay_time"]
            if u.get("settle_time") is not None:
                update_data["settle_time"] = u["settle_time"]

            try:
                stmt = (
                    update(Order)
                    .where(
                        and_(
                            Order.out_order_no == out_order_no,
                            Order.is_delete == False,  # noqa: E712
                        )
                    )
                    .values(**update_data)
                )
                result = await self.session.execute(stmt)
                await self.session.flush()
                await self.session.commit()
                rowcount = result.rowcount or 0
                affected += rowcount

                # 失效订单详情缓存（按 order_id 失效，需先查 id）
                if rowcount > 0:
                    await self._invalidate_cache_by_out_order_no(out_order_no)

            except Exception as e:
                await self.session.rollback()
                logger.warning(
                    "批量状态更新单条失败: out_order_no=%s err=%s",
                    out_order_no,
                    e,
                )
        logger.info("批量状态更新完成：成功 %s 条", affected)
        return affected

    async def _invalidate_cache_by_out_order_no(self, out_order_no: str) -> None:
        """按 out_order_no 查询 order_id 并失效订单详情缓存

        复用 OrderDAO 的缓存 key 约定：gaking:prod:order:{order_id}
        """
        try:
            stmt = select(Order.id).where(
                and_(
                    Order.out_order_no == out_order_no,
                    Order.is_delete == False,  # noqa: E712
                )
            )
            result = await self.session.execute(stmt)
            row = result.first()
            if row:
                order_id = int(row[0])
                await RedisClient.delete(f"{CACHE_KEY_ORDER_DETAIL}{order_id}")
                logger.debug(
                    "[cache_invalidate] order detail order_id=%s (out_order_no=%s)",
                    order_id,
                    out_order_no,
                )
        except Exception as e:
            logger.warning(
                "失效订单详情缓存失败（不影响主流程）: out_order_no=%s err=%s",
                out_order_no,
                e,
            )

    # ── 5. 查询失败补发用：按 out_order_no 列表查订单当前状态 ─────────────

    async def list_orders_by_out_order_nos(
        self, out_order_nos: List[str]
    ) -> List[Order]:
        """按 out_order_no 列表查询订单（自动过滤软删除）

        用于状态对比：拉取到的渠道订单与本地订单状态对比，决定是否需要更新。

        Args:
            out_order_nos: 渠道订单号列表
        Returns:
            订单实例列表
        """
        if not out_order_nos:
            return []

        stmt = self._active_query().where(Order.out_order_no.in_(out_order_nos))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

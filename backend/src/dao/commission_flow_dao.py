# @ai-generated
"""
佣金流水明细表 DAO
继承 BaseDAO 通用能力，扩展佣金流水业务专属查询方法
仅做数据存取，不包含任何业务计算逻辑
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func, update

from src.common.redis_client import RedisClient
from src.config.constants import (
    CacheTTL,
    CACHE_KEY_COMMISSION_SUM,
    CACHE_KEY_ORDER_DETAIL,
)
from src.dao.base_dao import BaseDAO
from src.models.business.commission_flow_model import CommissionFlow

logger = logging.getLogger("dao.commission_flow")


class CommissionFlowDAO(BaseDAO):
    """佣金发放流水 DAO"""

    model_class = CommissionFlow

    def __init__(self, session):
        super().__init__(session)

    # ── 专属扩展方法 ────────────────────────────────────

    async def list_by_order_id(self, order_id: int) -> List[CommissionFlow]:
        """查询单个订单的全部佣金流水（自动过滤软删除）

        Args:
            order_id: 订单 ID
        Returns:
            佣金流水列表
        """
        stmt = (
            self._active_query()
            .where(CommissionFlow.order_id == order_id)
            .order_by(CommissionFlow.create_time.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def sum_commission_by_order_id(self, order_id: int) -> Decimal:
        """聚合查询单订单总佣金金额（SQL SUM 聚合），带 Redis 读穿缓存

        缓存策略：
        1. key = gaking:prod:commission_sum:{order_id}，TTL=10min（±20% 抖动）
        2. 缓存值为金额字符串；总额为 0 时写 __EMPTY__ 空标记（60s 防穿透）
        3. 失效：流水生成(batch_create)/结算(update_by_id)/绑定(batch_bind_order)主动 DEL
        Args:
            order_id: 订单 ID
        Returns:
            聚合总金额 (Decimal)，无记录返回 Decimal("0")
        """
        key = f"{CACHE_KEY_COMMISSION_SUM}{order_id}"

        # 单次 GET 识别空标记与正常缓存
        cached = await RedisClient.get(key)
        if cached is not None:
            if cached == "__EMPTY__":
                logger.info("[cache_hit_empty] commission_sum order_id=%s", order_id)
                return Decimal("0")
            logger.info("[cache_hit] commission_sum order_id=%s", order_id)
            return Decimal(cached)

        # 未命中：聚合查库
        stmt = select(func.coalesce(func.sum(CommissionFlow.amount), 0)).where(
            and_(
                CommissionFlow.order_id == order_id,
                CommissionFlow.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        total = Decimal(str(total)) if total is not None else Decimal("0")

        # 回填：0 写空标记防穿透，非 0 写金额字符串
        if total == Decimal("0"):
            await RedisClient.set_empty_cache(key)
            logger.info("[cache_miss_empty] commission_sum order_id=%s", order_id)
        else:
            await RedisClient.set(key, str(total), expire=CacheTTL.COMMISSION_SUM)
            logger.info(
                "[cache_miss_set] commission_sum order_id=%s total=%s", order_id, total
            )
        return total

    # ── 佣金缓存失效 ─────────────────────────────────────
    async def _invalidate_flow_cache(self, order_id: int) -> None:
        """失效订单的佣金汇总缓存 + 订单详情缓存

        佣金流水变更同时影响：commission_sum:{order_id}（金额）与
        order:{order_id}（详情含 flows 列表），故两者一并 DEL
        """
        await RedisClient.delete(f"{CACHE_KEY_COMMISSION_SUM}{order_id}")
        await RedisClient.delete(f"{CACHE_KEY_ORDER_DETAIL}{order_id}")
        logger.info("[cache_invalidate] flows order_id=%s", order_id)

    async def batch_create(
        self, data_list: List[Dict[str, Any]]
    ) -> List[CommissionFlow]:
        """覆写基类方法：佣金流水生成后失效对应订单缓存

        生成场景对应 OrderService 佣金拆分入库，流水 amount 影响汇总、
        流水条数影响订单详情，故按 data_list 中的 order_id 失效
        """
        objects = await super().batch_create(data_list)
        for obj in objects:
            await self._invalidate_flow_cache(obj.order_id)
        return objects

    async def create(self, data: Dict[str, Any]) -> CommissionFlow:
        """覆写基类方法：单条佣金流水创建后失效对应订单缓存

        与 batch_create 语义一致：单条 INSERT 后也需失效 order_id 相关缓存。
        """
        obj = await super().create(data)
        await self._invalidate_flow_cache(obj.order_id)
        return obj

    async def update_by_id(
        self,
        item_id: int,
        data: Dict[str, Any],
    ) -> Optional[CommissionFlow]:
        """覆写基类方法：佣金流水更新（如结算标记）后失效对应订单缓存

        结算场景更新 transfer_status，流水对象返回后取其 order_id 失效
        """
        result = await super().update_by_id(item_id, data)
        if result is not None:
            order_id = data.get("order_id") or result.order_id
            await self._invalidate_flow_cache(order_id)
        return result

    async def list_by_settle_status(
        self,
        transfer_status: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CommissionFlow], int]:
        """按转账状态筛选流水

        Args:
            transfer_status: 转账状态 (PENDING / PROCESSING / SUCCESS / FAILED)
            page: 页码
            page_size: 每页条数
        Returns:
            (流水列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(
            CommissionFlow.transfer_status == transfer_status
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(CommissionFlow.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = result.scalars().all()

        return list(items), total

    async def batch_bind_order(self, order_id: int, flow_ids: List[int]) -> int:
        """批量绑定流水归属订单（更新 order_id）

        Args:
            order_id: 目标订单 ID
            flow_ids: 佣金流水 ID 列表
        Returns:
            实际更新的记录数
        """
        stmt = (
            update(CommissionFlow)
            .where(
                and_(
                    CommissionFlow.id.in_(flow_ids),
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .values(
                order_id=order_id,
                update_time=datetime.now(),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # 流水归属订单变更，失效目标订单的佣金汇总 + 详情缓存
        await self._invalidate_flow_cache(order_id)
        return result.rowcount or 0

    # ── 每日佣金对账统计（定时任务调用，只读聚合 + 缓存失效） ──────────

    async def aggregate_settled_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        transfer_status: str,
    ) -> List[Dict[str, Any]]:
        """按推广员(user_id)聚合指定时间范围内、指定转账状态的佣金流水

        SQL 语义：
            SELECT user_id,
                   COALESCE(SUM(amount), 0)   AS total_amount,
                   COUNT(DISTINCT order_id)   AS order_count
            FROM commission_flow
            WHERE transfer_status = :status
              AND create_time >= :start AND create_time < :end
              AND is_delete = 0
            GROUP BY user_id

        Args:
            start_time: 区间起点（含）
            end_time: 区间终点（不含）
            transfer_status: 转账状态值（一般传 TransferStatus.SUCCESS）
        Returns:
            [{"user_id": int, "total_amount": Decimal, "order_count": int}, ...]
        """
        stmt = (
            select(
                CommissionFlow.user_id,
                func.coalesce(func.sum(CommissionFlow.amount), 0).label("total_amount"),
                func.count(func.distinct(CommissionFlow.order_id)).label("order_count"),
            )
            .where(
                and_(
                    CommissionFlow.transfer_status == transfer_status,
                    CommissionFlow.create_time >= start_time,
                    CommissionFlow.create_time < end_time,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .group_by(CommissionFlow.user_id)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "user_id": row.user_id,
                "total_amount": Decimal(str(row.total_amount)),
                "order_count": int(row.order_count),
            }
            for row in result.all()
        ]

    async def list_settled_order_ids_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        transfer_status: str,
    ) -> List[int]:
        """查询指定时间范围内、指定转账状态流水涉及的 order_id 列表（去重，排除 NULL）

        用于对账后失效 commission_sum:{order_id} / order:{order_id} 缓存。

        Args:
            start_time: 区间起点（含）
            end_time: 区间终点（不含）
            transfer_status: 转账状态值
        Returns:
            order_id 列表（去重）
        """
        stmt = select(func.distinct(CommissionFlow.order_id)).where(
            and_(
                CommissionFlow.transfer_status == transfer_status,
                CommissionFlow.create_time >= start_time,
                CommissionFlow.create_time < end_time,
                CommissionFlow.order_id.isnot(None),
                CommissionFlow.is_delete == False,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all() if row[0] is not None]

    async def batch_invalidate_commission_cache(self, order_ids: List[int]) -> None:
        """批量失效佣金汇总缓存 + 订单详情缓存（对账/结算后调用）

        复用 _invalidate_flow_cache：同时 DEL commission_sum:{oid} 与 order:{oid}。
        Args:
            order_ids: 需失效缓存的订单 ID 列表
        """
        for oid in order_ids:
            await self._invalidate_flow_cache(oid)

    # ══════════════════════════════════════════════════════
    # B08 补全：用户维度流水查询（C 端「我的佣金」+ 后台流水审计）
    # ══════════════════════════════════════════════════════

    async def list_by_user_id(
        self,
        user_id: int,
        *,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CommissionFlow], int]:
        """按用户筛选佣金流水 + 分页（C 端「我的佣金流水」列表 + 后台用户流水审计）

        所有筛选条件可叠加；时间范围左闭右开 [start_time, end_time)。
        默认按 create_time 降序（最新在前）。

        Args:
            user_id: 平台用户 ID（必填）
            flow_type: 流水类型筛选（ORDER-订单佣金/SUPPLEMENT-补发/DEDUCT-扣减），None 表示不过滤
            transfer_status: 转账状态筛选（PENDING/PROCESSING/SUCCESS/FAILED），None 表示不过滤
            start_time: 起时间（含），None 表示无下限
            end_time: 止时间（不含），None 表示无上限
            page: 页码，从 1 开始
            page_size: 每页条数
        Returns:
            (流水列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        stmt = self._active_query().where(CommissionFlow.user_id == user_id)
        if flow_type is not None:
            stmt = stmt.where(CommissionFlow.flow_type == flow_type)
        if transfer_status is not None:
            stmt = stmt.where(CommissionFlow.transfer_status == transfer_status)
        if start_time is not None:
            stmt = stmt.where(CommissionFlow.create_time >= start_time)
        if end_time is not None:
            stmt = stmt.where(CommissionFlow.create_time < end_time)

        # 总数（子查询，避免被 offset/limit 截断）
        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(CommissionFlow.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())
        return items, total

    async def sum_commission_by_user_id(
        self,
        user_id: int,
        *,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Decimal:
        """按用户聚合佣金总额（纯 SUM，SQL 侧聚合，避免拉取多条到 Python）

        参数与 list_by_user_id 语义一致（均为可选叠加 + 时间左闭右开）。
        典型使用：
        - C 端「我的累计佣金」：transfer_status=SUCCESS（仅统计已到账）
        - C 端「累计扣减」：flow_type=DEDUCT
        - 后台运营「按月已结算佣金总额审计」

        Returns:
            聚合金额 (Decimal)，无匹配返回 Decimal("0")
        """
        stmt = select(func.coalesce(func.sum(CommissionFlow.amount), 0)).where(
            and_(
                CommissionFlow.user_id == user_id,
                CommissionFlow.is_delete == False,  # noqa: E712
            )
        )
        if flow_type is not None:
            stmt = stmt.where(CommissionFlow.flow_type == flow_type)
        if transfer_status is not None:
            stmt = stmt.where(CommissionFlow.transfer_status == transfer_status)
        if start_time is not None:
            stmt = stmt.where(CommissionFlow.create_time >= start_time)
        if end_time is not None:
            stmt = stmt.where(CommissionFlow.create_time < end_time)

        result = await self.session.execute(stmt)
        total = result.scalar()
        if total is None:
            return Decimal("0")
        # scalar 可能来自 SQL COALESCE(SUM(...), 0) → int(0) 或 Decimal；统一 Decimal 化
        try:
            return Decimal(str(total))
        except Exception:
            return Decimal("0")

    async def list_supplement_flows_by_order_id(
        self, order_id: int
    ) -> List[CommissionFlow]:
        """查询某订单的 SUPPLEMENT（补发）类型流水

        运营后台「补发历史」场景：查询该订单是否有补发、补发了几次。
        按 create_time 升序（补发顺序）。
        """
        stmt = (
            self._active_query()
            .where(
                and_(
                    CommissionFlow.order_id == order_id,
                    CommissionFlow.flow_type == "SUPPLEMENT",
                )
            )
            .order_by(CommissionFlow.create_time.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_deduct_flows_by_order_id(
        self, order_id: int
    ) -> List[CommissionFlow]:
        """查询某订单的 DEDUCT（扣减）类型流水

        运营后台「退款扣减历史」场景，按 create_time 升序。
        """
        stmt = (
            self._active_query()
            .where(
                and_(
                    CommissionFlow.order_id == order_id,
                    CommissionFlow.flow_type == "DEDUCT",
                )
            )
            .order_by(CommissionFlow.create_time.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_user_monthly_summary(
        self,
        user_id: int,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """按用户 + 年月聚合佣金摘要（C 端「我的佣金 - 月度账单」）

        SQL 语义：
            SELECT flow_type,
                   transfer_status,
                   COALESCE(SUM(amount), 0)   AS sum_amount,
                   COUNT(DISTINCT order_id)   AS order_count
            FROM commission_flow
            WHERE user_id = :user_id
              AND create_time BETWEEN :month_start AND :month_end
              AND is_delete = 0
            GROUP BY flow_type, transfer_status

        Returns:
            {
                "year": 2026, "month": 8,
                "total_earned": Decimal(已到账 ORDER 佣金累计 + SUCCESS),
                "total_deducted": Decimal(DEDUCT 累计),
                "pending_amount": Decimal(PENDING ORDER 累计),
                "flow_count": int(该月流水总条数),
                "order_count": int(该月不同订单数),
                "details": [{"flow_type": "ORDER", "transfer_status": "SUCCESS",
                             "sum_amount": Decimal, "order_count": int}, ...]
            }
        """
        # 构造月份起止（下月 1 号 0 点为上限，左闭右开）
        from calendar import monthrange

        start = datetime(year, month, 1, 0, 0, 0)
        _, last_day = monthrange(year, month)
        next_month = 1 if month == 12 else month + 1
        next_year = year + 1 if month == 12 else year
        end = datetime(next_year, next_month, 1, 0, 0, 0)

        stmt = (
            select(
                CommissionFlow.flow_type,
                CommissionFlow.transfer_status,
                func.coalesce(func.sum(CommissionFlow.amount), 0).label("sum_amount"),
                func.count(func.distinct(CommissionFlow.order_id)).label("order_count"),
            )
            .where(
                and_(
                    CommissionFlow.user_id == user_id,
                    CommissionFlow.create_time >= start,
                    CommissionFlow.create_time < end,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .group_by(
                CommissionFlow.flow_type,
                CommissionFlow.transfer_status,
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        total_earned = Decimal("0")
        total_deducted = Decimal("0")
        pending_amount = Decimal("0")
        flow_count = 0
        distinct_orders = set()
        details: List[Dict[str, Any]] = []
        for r in rows:
            sum_amt = Decimal(str(r.sum_amount))
            order_cnt = int(r.order_count)
            flow_count += order_cnt  # 以 order_count 近似条数权重（另补精确流水条数）
            # 明细补回查询更精确的 flow_count：这里只记录 SUM
            if r.flow_type == "ORDER" and r.transfer_status == "SUCCESS":
                total_earned += sum_amt
            elif r.flow_type == "ORDER" and r.transfer_status == "PENDING":
                pending_amount += sum_amt
            elif r.flow_type == "DEDUCT":
                total_deducted += sum_amt
            if r.flow_type in ("ORDER", "SUPPLEMENT"):
                distinct_orders.add(r.flow_type + "_" + r.transfer_status)
            details.append(
                {
                    "flow_type": r.flow_type,
                    "transfer_status": r.transfer_status,
                    "sum_amount": sum_amt,
                    "order_count": order_cnt,
                }
            )

        # 精确 flow_count（该月总流水条数）
        count_stmt = select(func.count(CommissionFlow.id)).where(
            and_(
                CommissionFlow.user_id == user_id,
                CommissionFlow.create_time >= start,
                CommissionFlow.create_time < end,
                CommissionFlow.is_delete == False,  # noqa: E712
            )
        )
        count_result = await self.session.execute(count_stmt)
        flow_count_total = count_result.scalar() or 0

        # 精确总订单数（按 order_id，忽略 None）
        order_stmt = select(func.count(func.distinct(CommissionFlow.order_id))).where(
            and_(
                CommissionFlow.user_id == user_id,
                CommissionFlow.create_time >= start,
                CommissionFlow.create_time < end,
                CommissionFlow.is_delete == False,  # noqa: E712
                CommissionFlow.order_id.isnot(None),
            )
        )
        order_result = await self.session.execute(order_stmt)
        order_count_total = order_result.scalar() or 0

        logger.info(
            "[dao] monthly_summary user_id=%s y=%s m=%s earned=%s deducted=%s pending=%s",
            user_id,
            year,
            month,
            total_earned,
            total_deducted,
            pending_amount,
        )
        return {
            "year": year,
            "month": month,
            "total_earned": total_earned,
            "total_deducted": total_deducted,
            "pending_amount": pending_amount,
            "flow_count": int(flow_count_total),
            "order_count": int(order_count_total),
            "details": details,
        }

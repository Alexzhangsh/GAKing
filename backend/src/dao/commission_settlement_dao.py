# @ai-generated
"""
B07 佣金结算专属 DAO
继承 BaseDAO，复用 Order / CommissionFlow / UserCommissionAccount 模型
不修改任何现有 DAO，仅新增 B07 所需的原子操作和复合查询

核心方法：
1. list_settled_orders_without_flow —— LEFT JOIN 查 SETTLED 订单无 ORDER 流水
2. list_refunded_orders_without_deduct —— 查 REFUNDED 订单需退款扣减
3. settle_order_commission_atomic —— 单事务原子结算入账（FOR UPDATE + 插入流水 + 更新余额）
4. deduct_on_refund_atomic —— 单事务原子退款扣减（PENDING→FAILED / SUCCESS→扣余额）
5. list_flows_with_filters —— 多条件分页查询流水
6. list_settlement_orders_with_filters —— 结算状态查询
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_COMMISSION_SUM,
    CACHE_KEY_ORDER_DETAIL,
    CACHE_KEY_USER_ACCOUNT,
    OrderStatus,
)
from src.dao.base_dao import BaseDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.business.user_commission_account_model import UserCommissionAccount

logger = logging.getLogger("dao.commission_settlement")

# 流水类型常量（与 commission_service.py 一致，避免跨模块导入）
FLOW_TYPE_ORDER = "ORDER"
FLOW_TYPE_DEDUCT = "DEDUCT"

# 转账状态常量
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"
TRANSFER_STATUS_FAILED = "FAILED"


class CommissionSettlementDAO(BaseDAO):
    """佣金结算专属 DAO"""

    model_class = CommissionFlow

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── 1. 查询待结算/待扣减订单 ──────────────────────────────

    async def list_settled_orders_without_flow(
        self,
        page: int = 1,
        page_size: int = 200,
    ) -> Tuple[List[Order], int]:
        """查询 SETTLED 状态且无 ORDER 类型流水的订单

        SQL 语义：
            SELECT o.* FROM orders o
            LEFT JOIN commission_flow f
              ON f.order_id = o.id AND f.flow_type = 'ORDER' AND f.is_delete = 0
            WHERE o.order_status = 40 AND o.is_delete = 0 AND f.id IS NULL
            ORDER BY o.settle_time ASC NULLS LAST

        Args:
            page: 页码
            page_size: 每页条数
        Returns:
            (订单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 200

        # LEFT JOIN 子查询：该订单的 ORDER 类型流水
        flow_subq = (
            select(CommissionFlow.id.label("flow_id"))
            .where(
                and_(
                    CommissionFlow.order_id == Order.id,
                    CommissionFlow.flow_type == FLOW_TYPE_ORDER,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .exists()
        )

        stmt = (
            select(Order)
            .where(
                and_(
                    Order.order_status == int(OrderStatus.SETTLED),
                    Order.is_delete == False,  # noqa: E712
                    ~flow_subq,  # NOT EXISTS：无 ORDER 流水
                )
            )
            .order_by(Order.settle_time.asc())
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    async def list_refunded_orders_without_deduct(
        self,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[Order], int]:
        """查询 REFUNDED 状态且有 ORDER+SUCCESS 流水但无 DEDUCT 流水的订单

        SQL 语义：
            SELECT o.* FROM orders o
            WHERE o.order_status = 60 AND o.is_delete = 0
              AND EXISTS (SELECT 1 FROM commission_flow f
                          WHERE f.order_id = o.id AND f.flow_type = 'ORDER'
                                AND f.transfer_status = 'SUCCESS' AND f.is_delete = 0)
              AND NOT EXISTS (SELECT 1 FROM commission_flow f
                              WHERE f.order_id = o.id AND f.flow_type = 'DEDUCT'
                                    AND f.is_delete = 0)

        Args:
            page: 页码
            page_size: 每页条数
        Returns:
            (订单列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 100

        # EXISTS：有 ORDER+SUCCESS 流水
        has_order_success = (
            select(CommissionFlow.id)
            .where(
                and_(
                    CommissionFlow.order_id == Order.id,
                    CommissionFlow.flow_type == FLOW_TYPE_ORDER,
                    CommissionFlow.transfer_status == TRANSFER_STATUS_SUCCESS,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .exists()
        )

        # NOT EXISTS：无 DEDUCT 流水
        no_deduct = (
            select(CommissionFlow.id)
            .where(
                and_(
                    CommissionFlow.order_id == Order.id,
                    CommissionFlow.flow_type == FLOW_TYPE_DEDUCT,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .exists()
        )

        stmt = (
            select(Order)
            .where(
                and_(
                    Order.order_status == int(OrderStatus.REFUNDED),
                    Order.is_delete == False,  # noqa: E712
                    has_order_success,
                    ~no_deduct,
                )
            )
            .order_by(Order.update_time.asc())
        )

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(page_query)
        items = list(result.scalars().all())

        return items, total

    # ── 2. 原子结算入账 ────────────────────────────────────────

    async def settle_order_commission_atomic(
        self,
        order: Order,
        user_commission: Decimal,
        transfer_batch_id: str,
    ) -> CommissionFlow:
        """单事务原子结算入账

        流程：
        1. SELECT ... FOR UPDATE 锁定用户佣金账户
        2. 账户不存在则创建（初始余额全 0）
        3. 插入 CommissionFlow（ORDER, SUCCESS, before/after_balance）
        4. 更新账户：available_balance += amount, total_balance += amount, version += 1
        5. flush + commit
        6. commit 后失效缓存（user_account, commission_sum, order_detail）

        Args:
            order: 订单实例（需含 user_id, id, internal_order_no）
            user_commission: 用户佣金金额
            transfer_batch_id: 转账批次 ID
        Returns:
            创建的 CommissionFlow 实例
        Raises:
            ValueError: 金额 <= 0
        """
        if user_commission <= 0:
            raise ValueError(
                f"结算金额必须大于 0: order_id={order.id}, amount={user_commission}"
            )

        user_id = order.user_id

        # 1. FOR UPDATE 锁定账户
        account = await self._get_or_create_account_for_update(user_id)

        # 2. 计算变更前后余额
        before_balance = Decimal(str(account.available_balance))
        after_balance = before_balance + user_commission

        # 3. 插入佣金流水
        flow = CommissionFlow(
            order_id=order.id,
            user_id=user_id,
            flow_type=FLOW_TYPE_ORDER,
            amount=user_commission,
            before_balance=before_balance,
            after_balance=after_balance,
            transfer_batch_id=transfer_batch_id,
            transfer_status=TRANSFER_STATUS_SUCCESS,
            remark=f"订单佣金结算入账: {order.internal_order_no}",
        )
        self.session.add(flow)

        # 4. 更新账户余额
        account.available_balance = after_balance
        account.total_balance = Decimal(str(account.total_balance)) + user_commission
        account.version = (account.version or 0) + 1

        # 5. 提交事务
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "settle_order_commission_atomic 提交失败已回滚 order_id=%s user_id=%s",
                order.id,
                user_id,
                exc_info=True,
            )
            raise

        # 6. 失效缓存（commit 后）
        await self._invalidate_settlement_cache(user_id, order.id)

        logger.info(
            "[dao] settle_atomic order_id=%s user_id=%s amount=%s before=%s after=%s flow_id=%s",
            order.id,
            user_id,
            user_commission,
            before_balance,
            after_balance,
            flow.id,
        )
        return flow

    # ── 3. 原子退款扣减 ────────────────────────────────────────

    async def deduct_on_refund_atomic(
        self,
        order: Order,
        original_flow: CommissionFlow,
    ) -> Optional[CommissionFlow]:
        """单事务原子退款扣减

        分支逻辑：
        - original_flow.transfer_status == 'PENDING'：在途扣减，标记 FAILED，不动余额
        - original_flow.transfer_status == 'SUCCESS'：已到账扣减，FOR UPDATE 锁账户，
          透支校验，插入 DEDUCT 流水，扣减 available_balance + total_balance

        Args:
            order: 订单实例
            original_flow: 原始 ORDER 类型流水
        Returns:
            PENDING 分支返回 None；SUCCESS 分支返回 DEDUCT 流水实例
        Raises:
            ValueError: 透支（available_balance < 扣减金额）
        """
        deduct_amount = Decimal(str(original_flow.amount))
        user_id = order.user_id

        if original_flow.transfer_status == TRANSFER_STATUS_PENDING:
            # 在途扣减：佣金未入账，直接标记 FAILED
            original_flow.transfer_status = TRANSFER_STATUS_FAILED
            original_flow.remark = (
                f"退款冲减（在途标记失败）: {order.internal_order_no}"
            )
            try:
                await self.session.flush()
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                logger.warning(
                    "deduct_on_refund_atomic PENDING 分支提交失败 order_id=%s",
                    order.id,
                    exc_info=True,
                )
                raise
            await self._invalidate_settlement_cache(user_id, order.id)
            logger.info(
                "[dao] deduct_atomic PENDING→FAILED order_id=%s flow_id=%s",
                order.id,
                original_flow.id,
            )
            return None

        # SUCCESS 分支：已入账，需扣减余额
        account = await self._get_or_create_account_for_update(user_id)
        before_balance = Decimal(str(account.available_balance))
        after_balance = before_balance - deduct_amount

        if after_balance < 0:
            raise ValueError(
                f"退款扣减透支: user_id={user_id}, 可用余额={before_balance}, 扣减={deduct_amount}"
            )

        # 插入 DEDUCT 流水
        deduct_flow = CommissionFlow(
            order_id=order.id,
            user_id=user_id,
            flow_type=FLOW_TYPE_DEDUCT,
            amount=deduct_amount,
            before_balance=before_balance,
            after_balance=after_balance,
            transfer_batch_id="",
            transfer_status=TRANSFER_STATUS_SUCCESS,
            remark=f"退款佣金冲减: {order.internal_order_no}",
        )
        self.session.add(deduct_flow)

        # 更新账户余额
        account.available_balance = after_balance
        account.total_balance = Decimal(str(account.total_balance)) - deduct_amount
        account.version = (account.version or 0) + 1

        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "deduct_on_refund_atomic SUCCESS 分支提交失败 order_id=%s",
                order.id,
                exc_info=True,
            )
            raise

        await self._invalidate_settlement_cache(user_id, order.id)
        logger.info(
            "[dao] deduct_atomic SUCCESS order_id=%s user_id=%s amount=%s before=%s after=%s flow_id=%s",
            order.id,
            user_id,
            deduct_amount,
            before_balance,
            after_balance,
            deduct_flow.id,
        )
        return deduct_flow

    # ── 4. 多条件查询 ──────────────────────────────────────────

    async def list_flows_with_filters(
        self,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        flow_type: Optional[str] = None,
        transfer_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CommissionFlow], int]:
        """多条件分页查询佣金流水

        Args:
            user_id: 用户ID筛选
            order_id: 订单ID筛选
            flow_type: 流水类型筛选 (ORDER/SUPPLEMENT/DEDUCT)
            transfer_status: 转账状态筛选 (PENDING/PROCESSING/SUCCESS/FAILED)
            page: 页码
            page_size: 每页条数
        Returns:
            (流水列表, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        conditions = [CommissionFlow.is_delete == False]  # noqa: E712
        if user_id is not None:
            conditions.append(CommissionFlow.user_id == user_id)
        if order_id is not None:
            conditions.append(CommissionFlow.order_id == order_id)
        if flow_type is not None:
            conditions.append(CommissionFlow.flow_type == flow_type)
        if transfer_status is not None:
            conditions.append(CommissionFlow.transfer_status == transfer_status)

        stmt = self._active_query().where(and_(*conditions))

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

    async def list_settlement_orders_with_filters(
        self,
        order_status: Optional[int] = None,
        channel_code: Optional[str] = None,
        has_flow: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """结算状态查询：支持按 has_flow 筛选

        Args:
            order_status: 订单状态筛选
            channel_code: 渠道筛选
            has_flow: True=有ORDER流水(已结算), False=无ORDER流水(待结算), None=不筛选
            page: 页码
            page_size: 每页条数
        Returns:
            (订单dict列表含has_flow标记, 总记录数)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        conditions = [Order.is_delete == False]  # noqa: E712
        if order_status is not None:
            conditions.append(Order.order_status == order_status)
        if channel_code is not None:
            conditions.append(Order.channel_code == channel_code)

        # has_flow 筛选
        order_flow_exists = (
            select(CommissionFlow.id)
            .where(
                and_(
                    CommissionFlow.order_id == Order.id,
                    CommissionFlow.flow_type == FLOW_TYPE_ORDER,
                    CommissionFlow.is_delete == False,  # noqa: E712
                )
            )
            .exists()
        )

        if has_flow is True:
            conditions.append(order_flow_exists)
        elif has_flow is False:
            conditions.append(~order_flow_exists)

        stmt = select(Order).where(and_(*conditions))

        count_query = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        page_query = (
            stmt.order_by(Order.create_time.desc()).offset(offset).limit(page_size)
        )
        result = await self.session.execute(page_query)
        orders = list(result.scalars().all())

        # 批量查 has_flow 标记
        order_ids = [o.id for o in orders]
        flow_order_ids: set = set()
        if order_ids:
            flow_stmt = (
                select(CommissionFlow.order_id)
                .where(
                    and_(
                        CommissionFlow.order_id.in_(order_ids),
                        CommissionFlow.flow_type == FLOW_TYPE_ORDER,
                        CommissionFlow.is_delete == False,  # noqa: E712
                    )
                )
                .distinct()
            )
            flow_result = await self.session.execute(flow_stmt)
            flow_order_ids = {row[0] for row in flow_result.all() if row[0] is not None}

        items = []
        for o in orders:
            d = o.to_dict()
            d["has_commission_flow"] = o.id in flow_order_ids
            items.append(d)

        return items, total

    # ── 内部工具方法 ────────────────────────────────────────────

    async def _get_or_create_account_for_update(
        self,
        user_id: int,
    ) -> UserCommissionAccount:
        """FOR UPDATE 锁定用户账户，不存在则创建

        Args:
            user_id: 平台用户ID
        Returns:
            锁定的账户实例
        """
        stmt = (
            select(UserCommissionAccount)
            .where(
                and_(
                    UserCommissionAccount.user_id == user_id,
                    UserCommissionAccount.is_delete == False,  # noqa: E712
                )
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()

        if account is not None:
            return account

        # 不存在则创建（初始余额全 0）
        account = UserCommissionAccount(
            user_id=user_id,
            total_balance=Decimal("0.00"),
            available_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            cumulative_withdrawn=Decimal("0.00"),
            cumulative_fee=Decimal("0.00"),
            last_settle_date=None,
            version=0,
        )
        self.session.add(account)
        await self.session.flush()  # 获取 id，不 commit（由调用方控制事务）
        logger.info("[dao] 创建用户佣金账户 user_id=%s", user_id)
        return account

    async def _invalidate_settlement_cache(
        self,
        user_id: int,
        order_id: int,
    ) -> None:
        """失效结算相关缓存（commit 后调用）

        3 个 key：
        - gaking:prod:user_account:{user_id}
        - gaking:prod:commission_sum:{order_id}
        - gaking:prod:order:{order_id}
        """
        await RedisClient.delete(f"{CACHE_KEY_USER_ACCOUNT}{user_id}")
        await RedisClient.delete(f"{CACHE_KEY_COMMISSION_SUM}{order_id}")
        await RedisClient.delete(f"{CACHE_KEY_ORDER_DETAIL}{order_id}")
        logger.info(
            "[cache_invalidate] settlement user_id=%s order_id=%s", user_id, order_id
        )

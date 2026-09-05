# @ai-generated
"""
佣金结算原子操作 DAO（B12 新建）
实现单事务原子冻结入账 / 解冻转可用，保证结算单+佣金流水+账户余额三者一致性
参照 B07 CommissionSettlementDAO.settle_order_commission_atomic 模式，但入账目标为冻结余额

核心方法：
1. freeze_atomic —— SETTLABLE 订单冻结入账（创建结算单+写PENDING流水+frozen+=amount）
2. unfreeze_atomic —— SETTLED 订单解冻转可用（更新结算单+PENDING→SUCCESS流水+frozen→available）
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import and_, select

from src.common.redis_client import RedisClient
from src.config.b12_constants import SettlementStatus
from src.config.constants import (
    CACHE_KEY_COMMISSION_SUM,
    CACHE_KEY_ORDER_DETAIL,
    CACHE_KEY_USER_ACCOUNT,
)
from src.dao.base_dao import BaseDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.settlement_record_model import SettlementRecord
from src.models.business.user_commission_account_model import UserCommissionAccount

logger = logging.getLogger("dao.settlement_atomic")

# 流水类型/转账状态常量（与 B07 commission_settlement_dao 一致，避免跨模块导入）
FLOW_TYPE_ORDER = "ORDER"
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_SUCCESS = "SUCCESS"


class SettlementAtomicDAO(BaseDAO):
    """佣金结算原子操作 DAO（单事务保证一致性）"""

    model_class = SettlementRecord

    def __init__(self, session):
        super().__init__(session)

    # ── 1. 原子冻结入账 ────────────────────────────────────────

    async def freeze_atomic(
        self,
        order,
        user_commission: Decimal,
        platform_commission: Decimal,
        settlement_no: str,
        delay_days: int,
    ) -> Tuple[SettlementRecord, CommissionFlow]:
        """单事务原子冻结入账（SETTLABLE 阶段）

        流程：
        1. SELECT ... FOR UPDATE 锁定用户佣金账户（不存在则创建）
        2. 创建 SettlementRecord（SETTLABLE 态，confirm_time=now）
        3. 插入 CommissionFlow（ORDER, PENDING，before/after=available 不变）
        4. 回填 SettlementRecord.flow_id
        5. 更新账户：frozen_balance += amount, total_balance += amount, version += 1
        6. flush + commit
        7. commit 后失效缓存（user_account, commission_sum, order_detail）

        Args:
            order: 订单实例（需含 user_id, id, internal_order_no, channel_code, total_commission）
            user_commission: 用户佣金金额
            platform_commission: 平台佣金金额
            settlement_no: 结算单号
            delay_days: 延迟天数配置快照
        Returns:
            (结算单实例, 佣金流水实例)
        Raises:
            ValueError: 金额 <= 0
        """
        if user_commission <= 0:
            raise ValueError(
                f"冻结金额必须大于 0: order_id={order.id}, amount={user_commission}"
            )

        user_id = order.user_id

        # 1. FOR UPDATE 锁定账户
        account = await self._get_or_create_account_for_update(user_id)
        before_available = Decimal(str(account.available_balance))

        # 2. 创建结算单（SETTLABLE 态）
        settlement = SettlementRecord(
            settlement_no=settlement_no,
            order_id=order.id,
            user_id=user_id,
            channel_code=order.channel_code or "",
            total_commission=Decimal(str(order.total_commission)),
            user_commission=user_commission,
            platform_commission=platform_commission,
            settlement_status=SettlementStatus.SETTLABLE.value,
            flow_id=None,
            confirm_time=datetime.now(),
            settle_time=None,
            paid_time=None,
            delay_days=delay_days,
            remark=f"确认收货冻结入账: {order.internal_order_no}",
        )
        self.session.add(settlement)
        await self.session.flush()  # 获取 settlement.id，不 commit

        # 3. 插入佣金流水（PENDING：渠道返利未到账，已承诺冻结）
        flow = CommissionFlow(
            order_id=order.id,
            user_id=user_id,
            flow_type=FLOW_TYPE_ORDER,
            amount=user_commission,
            before_balance=before_available,
            after_balance=before_available,  # 冻结不影响可用余额
            transfer_batch_id=settlement_no,
            transfer_status=TRANSFER_STATUS_PENDING,
            remark=f"确认收货冻结佣金(渠道未到账): {order.internal_order_no}",
        )
        self.session.add(flow)
        await self.session.flush()  # 获取 flow.id

        # 4. 回填结算单 flow_id
        settlement.flow_id = flow.id

        # 5. 更新账户余额（冻结 += amount，累计 += amount）
        account.frozen_balance = Decimal(str(account.frozen_balance)) + user_commission
        account.total_balance = Decimal(str(account.total_balance)) + user_commission
        account.version = (account.version or 0) + 1

        # 6. 提交事务
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "freeze_atomic 提交失败已回滚 order_id=%s user_id=%s",
                order.id,
                user_id,
                exc_info=True,
            )
            raise

        # 7. 失效缓存（commit 后）
        await self._invalidate_settlement_cache(user_id, order.id)

        logger.info(
            "[dao] freeze_atomic order_id=%s user_id=%s amount=%s "
            "frozen=%s settlement_id=%s flow_id=%s",
            order.id,
            user_id,
            user_commission,
            account.frozen_balance,
            settlement.id,
            flow.id,
        )
        return settlement, flow

    # ── 2. 原子解冻转可用 ────────────────────────────────────────

    async def unfreeze_atomic(
        self,
        settlement: SettlementRecord,
        order,
    ) -> Tuple[SettlementRecord, CommissionFlow]:
        """单事务原子解冻转可用（SETTLED 阶段，渠道返利到账）

        流程：
        1. SELECT ... FOR UPDATE 锁定用户佣金账户
        2. 查原始 CommissionFlow（settlement.flow_id）
        3. 透支校验：frozen_balance >= amount
        4. 更新账户：frozen -= amount, available += amount, version += 1
        5. 更新 CommissionFlow：PENDING→SUCCESS, before/after=available 变化
        6. 更新 SettlementRecord：SETTLED 态, settle_time=now
        7. flush + commit
        8. commit 后失效缓存

        Args:
            settlement: 结算单实例（需为 SETTLABLE 态，含 flow_id）
            order: 订单实例
        Returns:
            (更新后的结算单实例, 更新后的佣金流水实例)
        Raises:
            ValueError: 流水不存在 / 冻结余额不足
        """
        user_id = settlement.user_id
        amount = Decimal(str(settlement.user_commission))

        # 1. FOR UPDATE 锁定账户
        account = await self._get_or_create_account_for_update(user_id)
        before_frozen = Decimal(str(account.frozen_balance))
        before_available = Decimal(str(account.available_balance))

        # 2. 查原始流水
        if settlement.flow_id is None:
            raise ValueError(
                f"结算单无关联流水: settlement_id={settlement.id}, flow_id=None"
            )
        flow_stmt = select(CommissionFlow).where(
            and_(
                CommissionFlow.id == settlement.flow_id,
                CommissionFlow.is_delete == False,  # noqa: E712
            )
        )
        flow_result = await self.session.execute(flow_stmt)
        flow = flow_result.scalar_one_or_none()
        if flow is None:
            raise ValueError(f"佣金流水不存在: flow_id={settlement.flow_id}")

        # 3. 透支校验
        if before_frozen < amount:
            raise ValueError(
                f"冻结余额不足: user_id={user_id}, 当前冻结={before_frozen}, 需解冻={amount}"
            )

        # 4. 更新账户余额（冻结 → 可用）
        account.frozen_balance = before_frozen - amount
        account.available_balance = before_available + amount
        account.version = (account.version or 0) + 1

        # 5. 更新流水（PENDING→SUCCESS，记录可用余额变化）
        flow.transfer_status = TRANSFER_STATUS_SUCCESS
        flow.before_balance = before_available
        flow.after_balance = before_available + amount
        flow.remark = f"渠道返利到账解冻转可用: {order.internal_order_no}"

        # 6. 更新结算单（SETTLABLE → SETTLED）
        settlement.settlement_status = SettlementStatus.SETTLED.value
        settlement.settle_time = datetime.now()
        settlement.remark = f"渠道结算到账，解冻转可用: {order.internal_order_no}"

        # 7. 提交事务
        try:
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.warning(
                "unfreeze_atomic 提交失败已回滚 settlement_id=%s order_id=%s",
                settlement.id,
                order.id,
                exc_info=True,
            )
            raise

        # 8. 失效缓存
        await self._invalidate_settlement_cache(user_id, order.id)

        logger.info(
            "[dao] unfreeze_atomic settlement_id=%s order_id=%s user_id=%s "
            "amount=%s frozen=%s available=%s",
            settlement.id,
            order.id,
            user_id,
            amount,
            account.frozen_balance,
            account.available_balance,
        )
        return settlement, flow

    # ── 内部工具方法 ────────────────────────────────────────────

    async def _get_or_create_account_for_update(
        self,
        user_id: int,
    ) -> UserCommissionAccount:
        """FOR UPDATE 锁定用户账户，不存在则创建（与 B07 模式一致）

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
            "[cache_invalidate] settlement_b12 user_id=%s order_id=%s",
            user_id,
            order_id,
        )

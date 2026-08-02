# @ai-generated
"""
B07 佣金结算 DAO 单元测试
覆盖：list_settled_orders_without_flow / list_refunded_orders_without_deduct /
      settle_order_commission_atomic / deduct_on_refund_atomic /
      list_flows_with_filters / list_settlement_orders_with_filters
使用 AsyncMock 模拟 session，不依赖真实 DB/Redis
"""
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.constants import OrderStatus
from src.dao.commission_settlement_dao import CommissionSettlementDAO
from src.models.business.commission_flow_model import CommissionFlow
from src.models.business.order_model import Order
from src.models.business.user_commission_account_model import UserCommissionAccount


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    order_status: int = int(OrderStatus.SETTLED),
    total_commission: str = "100.00",
    channel_code: str = "myq",
) -> Order:
    """构造 Order mock 对象"""
    order = MagicMock(spec=Order)
    order.id = order_id
    order.user_id = user_id
    order.order_status = order_status
    order.total_commission = Decimal(total_commission)
    order.user_commission = Decimal("80.00")
    order.platform_commission = Decimal("20.00")
    order.channel_code = channel_code
    order.internal_order_no = f"GAK{order_id}"
    order.out_order_no = f"TB_{order_id}"
    order.settle_time = datetime.now()
    order.to_dict = MagicMock(
        return_value={
            "id": order_id,
            "user_id": user_id,
            "order_status": order_status,
            "total_commission": total_commission,
            "channel_code": channel_code,
        }
    )
    return order


def _make_flow(
    flow_id: int = 1,
    order_id: int = 1,
    user_id: int = 100,
    flow_type: str = "ORDER",
    amount: str = "80.00",
    transfer_status: str = "SUCCESS",
) -> CommissionFlow:
    """构造 CommissionFlow mock 对象"""
    flow = MagicMock(spec=CommissionFlow)
    flow.id = flow_id
    flow.order_id = order_id
    flow.user_id = user_id
    flow.flow_type = flow_type
    flow.amount = Decimal(amount)
    flow.transfer_status = transfer_status
    flow.before_balance = Decimal("0.00")
    flow.after_balance = Decimal("80.00")
    flow.transfer_batch_id = "BATCH_001"
    flow.remark = "test"
    return flow


def _make_account(
    user_id: int = 100,
    available: str = "500.00",
    total: str = "1000.00",
) -> UserCommissionAccount:
    """构造 UserCommissionAccount mock 对象"""
    account = MagicMock(spec=UserCommissionAccount)
    account.id = 1
    account.user_id = user_id
    account.available_balance = Decimal(available)
    account.total_balance = Decimal(total)
    account.frozen_balance = Decimal("0.00")
    account.cumulative_withdrawn = Decimal("0.00")
    account.cumulative_fee = Decimal("0.00")
    account.version = 0
    return account


def _make_session_mock(scalars_result=None, scalar_result=None):
    """构造 AsyncSession mock"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    execute_result = MagicMock()
    if scalars_result is not None:
        execute_result.scalars.return_value.all.return_value = scalars_result
        execute_result.scalars.return_value.one_or_none.return_value = (
            scalars_result[0] if scalars_result else None
        )
    if scalar_result is not None:
        execute_result.scalar.return_value = scalar_result
        execute_result.scalar_one_or_none.return_value = scalar_result
    # all() 返回空列表（flow_order_ids 查询的默认返回，支持 row[0] 索引）
    execute_result.all.return_value = []

    session.execute = AsyncMock(return_value=execute_result)
    return session


# ══════════════════════════════════════════════════════
# 1. list_settled_orders_without_flow 测试
# ══════════════════════════════════════════════════════


class TestListSettledOrdersWithoutFlow:
    """查询 SETTLED 订单无 ORDER 流水"""

    @pytest.mark.asyncio
    async def test_has_orders(self):
        """有符合条件的订单"""
        orders = [_make_order(1), _make_order(2)]
        session = _make_session_mock(scalars_result=orders, scalar_result=2)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_settled_orders_without_flow(
            page=1, page_size=200
        )
        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """无符合条件的订单"""
        session = _make_session_mock(scalars_result=[], scalar_result=0)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_settled_orders_without_flow()
        assert result == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_pagination(self):
        """分页参数"""
        session = _make_session_mock(scalars_result=[], scalar_result=0)
        dao = CommissionSettlementDAO(session)
        await dao.list_settled_orders_without_flow(page=2, page_size=50)
        # 验证 execute 被调用（count + page 两次）
        assert session.execute.call_count >= 2


# ══════════════════════════════════════════════════════
# 2. list_refunded_orders_without_deduct 测试
# ══════════════════════════════════════════════════════


class TestListRefundedOrdersWithoutDeduct:
    """查询 REFUNDED 订单需退款扣减"""

    @pytest.mark.asyncio
    async def test_has_orders(self):
        """有需退款扣减的订单"""
        orders = [_make_order(1, order_status=int(OrderStatus.REFUNDED))]
        session = _make_session_mock(scalars_result=orders, scalar_result=1)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_refunded_orders_without_deduct()
        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """无需退款扣减"""
        session = _make_session_mock(scalars_result=[], scalar_result=0)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_refunded_orders_without_deduct()
        assert result == []
        assert total == 0


# ══════════════════════════════════════════════════════
# 3. settle_order_commission_atomic 测试
# ══════════════════════════════════════════════════════


class TestSettleOrderCommissionAtomic:
    """原子结算入账测试"""

    @pytest.mark.asyncio
    async def test_normal_settle(self):
        """正常结算入账"""
        order = _make_order(1, user_id=100)
        account = _make_account(100, available="500.00", total="1000.00")

        session = _make_session_mock(scalar_result=account)
        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ) as mock_delete:
            flow = await dao.settle_order_commission_atomic(
                order, Decimal("80.00"), "BATCH_001"
            )
        assert flow.flow_type == "ORDER"
        assert flow.transfer_status == "SUCCESS"
        assert flow.amount == Decimal("80.00")
        assert flow.before_balance == Decimal("500.00")
        assert flow.after_balance == Decimal("580.00")
        # 验证账户更新
        assert account.available_balance == Decimal("580.00")
        assert account.total_balance == Decimal("1080.00")
        assert account.version == 1
        # 验证缓存失效 3 次
        assert mock_delete.call_count == 3
        # 验证事务提交
        session.flush.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_account_not_exist_creates_new(self):
        """账户不存在 → 自动创建"""
        order = _make_order(1, user_id=200)

        # 第一次查询返回 None（不存在），flush 后返回新账户
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=execute_result)

        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ):
            flow = await dao.settle_order_commission_atomic(
                order, Decimal("80.00"), "BATCH_001"
            )
        assert flow.amount == Decimal("80.00")
        # session.add 应被调用两次（flow + account）
        assert session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_zero_amount_raises(self):
        """金额 <= 0 → 抛 ValueError"""
        order = _make_order(1)
        session = _make_session_mock()
        dao = CommissionSettlementDAO(session)
        with pytest.raises(ValueError, match="大于 0"):
            await dao.settle_order_commission_atomic(order, Decimal("0"), "BATCH")

    @pytest.mark.asyncio
    async def test_commit_failure_rollback(self):
        """commit 失败 → rollback + raise"""
        order = _make_order(1, user_id=100)
        account = _make_account(100)

        session = _make_session_mock(scalar_result=account)
        session.commit = AsyncMock(side_effect=RuntimeError("DB 超时"))

        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ):
            with pytest.raises(RuntimeError, match="DB 超时"):
                await dao.settle_order_commission_atomic(
                    order, Decimal("80.00"), "BATCH"
                )
        session.rollback.assert_called_once()


# ══════════════════════════════════════════════════════
# 4. deduct_on_refund_atomic 测试
# ══════════════════════════════════════════════════════


class TestDeductOnRefundAtomic:
    """原子退款扣减测试"""

    @pytest.mark.asyncio
    async def test_pending_flow_marked_failed(self):
        """PENDING 流水 → 标记 FAILED，不动余额"""
        order = _make_order(1, order_status=int(OrderStatus.REFUNDED))
        original_flow = _make_flow(
            1, flow_type="ORDER", transfer_status="PENDING", amount="80.00"
        )

        session = _make_session_mock()
        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ):
            result = await dao.deduct_on_refund_atomic(order, original_flow)

        assert result is None  # PENDING 分支返回 None
        assert original_flow.transfer_status == "FAILED"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_flow_deducts_balance(self):
        """SUCCESS 流水 → 扣减余额 + DEDUCT 流水"""
        order = _make_order(1, user_id=100, order_status=int(OrderStatus.REFUNDED))
        original_flow = _make_flow(
            1, flow_type="ORDER", transfer_status="SUCCESS", amount="80.00"
        )
        account = _make_account(100, available="500.00", total="1000.00")

        session = _make_session_mock(scalar_result=account)
        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ):
            deduct_flow = await dao.deduct_on_refund_atomic(order, original_flow)

        assert deduct_flow is not None
        assert deduct_flow.flow_type == "DEDUCT"
        assert deduct_flow.amount == Decimal("80.00")
        assert deduct_flow.before_balance == Decimal("500.00")
        assert deduct_flow.after_balance == Decimal("420.00")
        # 验证账户扣减
        assert account.available_balance == Decimal("420.00")
        assert account.total_balance == Decimal("920.00")
        assert account.version == 1

    @pytest.mark.asyncio
    async def test_overdraft_raises(self):
        """透支 → 抛 ValueError"""
        order = _make_order(1, user_id=100, order_status=int(OrderStatus.REFUNDED))
        original_flow = _make_flow(1, transfer_status="SUCCESS", amount="600.00")
        account = _make_account(100, available="500.00")

        session = _make_session_mock(scalar_result=account)
        dao = CommissionSettlementDAO(session)

        with pytest.raises(ValueError, match="透支"):
            await dao.deduct_on_refund_atomic(order, original_flow)

    @pytest.mark.asyncio
    async def test_deduct_commit_failure_rollback(self):
        """SUCCESS 分支 commit 失败 → rollback"""
        order = _make_order(1, user_id=100, order_status=int(OrderStatus.REFUNDED))
        original_flow = _make_flow(1, transfer_status="SUCCESS", amount="80.00")
        account = _make_account(100, available="500.00")

        session = _make_session_mock(scalar_result=account)
        session.commit = AsyncMock(side_effect=RuntimeError("DB 死锁"))

        dao = CommissionSettlementDAO(session)

        with patch(
            "src.dao.commission_settlement_dao.RedisClient.delete",
            new_callable=AsyncMock,
        ):
            with pytest.raises(RuntimeError, match="DB 死锁"):
                await dao.deduct_on_refund_atomic(order, original_flow)
        session.rollback.assert_called_once()


# ══════════════════════════════════════════════════════
# 5. list_flows_with_filters 测试
# ══════════════════════════════════════════════════════


class TestListFlowsWithFilters:
    """多条件查询流水测试"""

    @pytest.mark.asyncio
    async def test_no_filters(self):
        """无筛选条件"""
        flows = [_make_flow(1), _make_flow(2)]
        session = _make_session_mock(scalars_result=flows, scalar_result=2)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_flows_with_filters()
        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_with_filters(self):
        """多条件筛选"""
        flows = [_make_flow(1, user_id=100, flow_type="ORDER")]
        session = _make_session_mock(scalars_result=flows, scalar_result=1)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_flows_with_filters(
            user_id=100, flow_type="ORDER", transfer_status="SUCCESS"
        )
        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """空结果"""
        session = _make_session_mock(scalars_result=[], scalar_result=0)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_flows_with_filters(user_id=999)
        assert result == []
        assert total == 0


# ══════════════════════════════════════════════════════
# 6. list_settlement_orders_with_filters 测试
# ══════════════════════════════════════════════════════


class TestListSettlementOrdersWithFilters:
    """结算状态查询测试"""

    @pytest.mark.asyncio
    async def test_no_filters(self):
        """无筛选"""
        orders = [_make_order(1), _make_order(2)]
        session = _make_session_mock(scalars_result=orders, scalar_result=2)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_settlement_orders_with_filters()
        assert len(result) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self):
        """按状态筛选"""
        orders = [_make_order(1, order_status=40)]
        session = _make_session_mock(scalars_result=orders, scalar_result=1)
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_settlement_orders_with_filters(order_status=40)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filter_has_flow(self):
        """筛选有流水的订单"""
        order = _make_order(1)
        session = _make_session_mock(scalars_result=[order], scalar_result=1)
        # 第二次 execute 返回 flow_order_ids
        flow_result = MagicMock()
        flow_result.all.return_value = [(1,)]
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=MagicMock(return_value=1)),  # count
                MagicMock(
                    scalars=MagicMock(
                        return_value=MagicMock(all=MagicMock(return_value=[order]))
                    )
                ),  # orders
                flow_result,  # flow_order_ids
            ]
        )
        dao = CommissionSettlementDAO(session)
        result, total = await dao.list_settlement_orders_with_filters(has_flow=True)
        assert len(result) == 1
        assert result[0]["has_commission_flow"] is True

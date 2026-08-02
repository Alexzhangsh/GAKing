# @ai-generated
"""
B07 佣金结算 Service 单元测试
覆盖：batch_settle_orders / settle_single_order / process_refund_deductions /
      process_single_refund / recalculate_order_commission / list_settlement_flows /
      list_settlement_orders
"""
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, ".")

from src.config.b07_constants import UserType
from src.config.constants import OrderStatus
from src.services.commission_rule_engine import CommissionResult, CommissionSplit
from src.services.commission_settlement_service import CommissionSettlementService


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    order_status: int = int(OrderStatus.SETTLED),
    total_commission: str = "100.00",
    user_commission: str = "80.00",
    channel_code: str = "myq",
):
    order = MagicMock()
    order.id = order_id
    order.user_id = user_id
    order.order_status = order_status
    order.total_commission = Decimal(total_commission)
    order.user_commission = Decimal(user_commission)
    order.platform_commission = Decimal("20.00")
    order.channel_code = channel_code
    order.internal_order_no = f"GAK{order_id}"
    return order


def _make_flow(
    flow_id: int = 1,
    order_id: int = 1,
    user_id: int = 100,
    flow_type: str = "ORDER",
    amount: str = "80.00",
    transfer_status: str = "SUCCESS",
):
    flow = MagicMock()
    flow.id = flow_id
    flow.order_id = order_id
    flow.user_id = user_id
    flow.flow_type = flow_type
    flow.amount = Decimal(amount)
    flow.transfer_status = transfer_status
    flow.transfer_batch_id = "BATCH_001"
    flow.to_dict = MagicMock(
        return_value={
            "id": flow_id,
            "order_id": order_id,
            "user_id": user_id,
            "flow_type": flow_type,
            "amount": float(amount),
            "transfer_status": transfer_status,
        }
    )
    return flow


def _make_service(
    order_dao=None,
    flow_dao=None,
    settlement_dao=None,
    rule_engine=None,
):
    """构造 CommissionSettlementService with mocks"""
    order_dao = order_dao or MagicMock()
    flow_dao = flow_dao or MagicMock()
    settlement_dao = settlement_dao or MagicMock()
    rule_engine = rule_engine or MagicMock()

    svc = CommissionSettlementService(order_dao, flow_dao, settlement_dao, rule_engine)
    return svc


def _make_rule_engine_mock(
    user_rate="0.80",
    platform_rate="0.20",
    user_commission="80.00",
    platform_commission="20.00",
):
    """构造 rule_engine mock"""
    engine = MagicMock()
    engine.get_rates = AsyncMock(
        return_value=CommissionSplit(Decimal(user_rate), Decimal(platform_rate))
    )
    engine.calculate = MagicMock(
        return_value=CommissionResult(
            total_commission=Decimal("100.00"),
            user_commission=Decimal(user_commission),
            platform_commission=Decimal(platform_commission),
            user_rate=Decimal(user_rate),
            platform_rate=Decimal(platform_rate),
        )
    )
    return engine


# ══════════════════════════════════════════════════════
# 1. batch_settle_orders 测试
# ══════════════════════════════════════════════════════


class TestBatchSettleOrders:
    """批量结算测试"""

    @pytest.mark.asyncio
    async def test_empty_orders(self):
        """无待结算订单"""
        settlement_dao = MagicMock()
        settlement_dao.list_settled_orders_without_flow = AsyncMock(
            return_value=([], 0)
        )
        svc = _make_service(settlement_dao=settlement_dao)
        result = await svc.batch_settle_orders()
        assert result["status"] == "success"
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_all_success(self):
        """全部成功"""
        orders = [_make_order(1), _make_order(2)]
        settlement_dao = MagicMock()
        settlement_dao.list_settled_orders_without_flow = AsyncMock(
            return_value=(orders, 2)
        )
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(side_effect=orders)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        settlement_dao.settle_order_commission_atomic = AsyncMock(
            side_effect=[_make_flow(1), _make_flow(2)]
        )
        rule_engine = _make_rule_engine_mock()

        svc = _make_service(order_dao, flow_dao, settlement_dao, rule_engine)
        result = await svc.batch_settle_orders()
        assert result["success_count"] == 2
        assert result["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """部分失败不阻断"""
        orders = [_make_order(1), _make_order(2)]
        settlement_dao = MagicMock()
        settlement_dao.list_settled_orders_without_flow = AsyncMock(
            return_value=(orders, 2)
        )
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(side_effect=orders)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        # 第一笔成功，第二笔抛异常
        settlement_dao.settle_order_commission_atomic = AsyncMock(
            side_effect=[_make_flow(1), RuntimeError("DB 超时")]
        )
        rule_engine = _make_rule_engine_mock()

        svc = _make_service(order_dao, flow_dao, settlement_dao, rule_engine)
        result = await svc.batch_settle_orders()
        assert result["status"] == "partial"
        assert result["success_count"] == 1
        assert result["failed_count"] == 1


# ══════════════════════════════════════════════════════
# 2. settle_single_order 测试
# ══════════════════════════════════════════════════════


class TestSettleSingleOrder:
    """单笔结算测试"""

    @pytest.mark.asyncio
    async def test_order_not_found(self):
        """订单不存在"""
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(order_dao=order_dao)
        with pytest.raises(ValueError, match="订单不存在"):
            await svc.settle_single_order(999)

    @pytest.mark.asyncio
    async def test_wrong_status(self):
        """非 SETTLED 状态"""
        order = _make_order(1, order_status=int(OrderStatus.SETTLABLE))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        svc = _make_service(order_dao=order_dao)
        with pytest.raises(ValueError, match="非 SETTLED"):
            await svc.settle_single_order(1)

    @pytest.mark.asyncio
    async def test_already_settled_skipped(self):
        """已有 SUCCESS 流水 → 幂等跳过"""
        order = _make_order(1)
        existing_flow = _make_flow(1, transfer_status="SUCCESS")
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[existing_flow])
        svc = _make_service(order_dao=order_dao, flow_dao=flow_dao)
        result = await svc.settle_single_order(1)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_normal_settle(self):
        """正常结算"""
        order = _make_order(1)
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        settlement_dao = MagicMock()
        settlement_dao.settle_order_commission_atomic = AsyncMock(
            return_value=_make_flow(1)
        )
        rule_engine = _make_rule_engine_mock()
        svc = _make_service(order_dao, flow_dao, settlement_dao, rule_engine)
        result = await svc.settle_single_order(1)
        assert result["status"] == "success"
        assert result["flow_id"] == 1

    @pytest.mark.asyncio
    async def test_commission_recalibration(self):
        """佣金校准（规则变更导致金额不一致）"""
        order = _make_order(1, user_commission="70.00")  # 落库值 70
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        order_dao.update_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        settlement_dao = MagicMock()
        settlement_dao.settle_order_commission_atomic = AsyncMock(
            return_value=_make_flow(1)
        )
        # 规则引擎返回 80（与落库 70 不一致）
        rule_engine = _make_rule_engine_mock(user_commission="80.00")
        svc = _make_service(order_dao, flow_dao, settlement_dao, rule_engine)
        result = await svc.settle_single_order(1)
        # 验证调用了 update_by_id 校准
        order_dao.update_by_id.assert_called_once()
        assert result["status"] == "success"


# ══════════════════════════════════════════════════════
# 3. process_refund_deductions 测试
# ══════════════════════════════════════════════════════


class TestProcessRefundDeductions:
    """批量退款扣减测试"""

    @pytest.mark.asyncio
    async def test_empty_orders(self):
        """无待扣减订单"""
        settlement_dao = MagicMock()
        settlement_dao.list_refunded_orders_without_deduct = AsyncMock(
            return_value=([], 0)
        )
        svc = _make_service(settlement_dao=settlement_dao)
        result = await svc.process_refund_deductions()
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_all_success(self):
        """全部成功"""
        orders = [_make_order(1, order_status=int(OrderStatus.REFUNDED))]
        settlement_dao = MagicMock()
        settlement_dao.list_refunded_orders_without_deduct = AsyncMock(
            return_value=(orders, 1)
        )
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=orders[0])
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(
            return_value=[_make_flow(1, transfer_status="SUCCESS")]
        )
        settlement_dao.deduct_on_refund_atomic = AsyncMock(
            return_value=_make_flow(2, flow_type="DEDUCT")
        )
        svc = _make_service(order_dao, flow_dao, settlement_dao)
        result = await svc.process_refund_deductions()
        assert result["success_count"] == 1


# ══════════════════════════════════════════════════════
# 4. process_single_refund 测试
# ══════════════════════════════════════════════════════


class TestProcessSingleRefund:
    """单笔退款扣减测试"""

    @pytest.mark.asyncio
    async def test_no_order_flow_skipped(self):
        """无 ORDER 流水 → 跳过"""
        order = _make_order(1, order_status=int(OrderStatus.REFUNDED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        svc = _make_service(order_dao=order_dao, flow_dao=flow_dao)
        result = await svc.process_single_refund(1)
        assert result["status"] == "skipped"
        assert result["reason"] == "no_order_flow"

    @pytest.mark.asyncio
    async def test_already_deducted_skipped(self):
        """已有 DEDUCT 流水 → 幂等跳过"""
        order = _make_order(1, order_status=int(OrderStatus.REFUNDED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(
            return_value=[
                _make_flow(1, flow_type="ORDER"),
                _make_flow(2, flow_type="DEDUCT"),
            ]
        )
        svc = _make_service(order_dao=order_dao, flow_dao=flow_dao)
        result = await svc.process_single_refund(1)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_deducted"

    @pytest.mark.asyncio
    async def test_pending_flow_marked_failed(self):
        """PENDING 流水 → 标记 FAILED"""
        order = _make_order(1, order_status=int(OrderStatus.REFUNDED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(
            return_value=[_make_flow(1, transfer_status="PENDING")]
        )
        settlement_dao = MagicMock()
        settlement_dao.deduct_on_refund_atomic = AsyncMock(return_value=None)
        svc = _make_service(order_dao, flow_dao, settlement_dao)
        result = await svc.process_single_refund(1)
        assert result["status"] == "success"
        assert result["deduct_flow_id"] is None

    @pytest.mark.asyncio
    async def test_success_flow_deducted(self):
        """SUCCESS 流水 → 扣减余额"""
        order = _make_order(1, order_status=int(OrderStatus.REFUNDED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(
            return_value=[_make_flow(1, transfer_status="SUCCESS")]
        )
        settlement_dao = MagicMock()
        settlement_dao.deduct_on_refund_atomic = AsyncMock(
            return_value=_make_flow(2, flow_type="DEDUCT")
        )
        svc = _make_service(order_dao, flow_dao, settlement_dao)
        result = await svc.process_single_refund(1)
        assert result["status"] == "success"
        assert result["deduct_flow_id"] == 2

    @pytest.mark.asyncio
    async def test_wrong_status(self):
        """非 REFUNDED 状态"""
        order = _make_order(1, order_status=int(OrderStatus.SETTLED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        svc = _make_service(order_dao=order_dao)
        with pytest.raises(ValueError, match="非 REFUNDED"):
            await svc.process_single_refund(1)


# ══════════════════════════════════════════════════════
# 5. recalculate_order_commission 测试
# ══════════════════════════════════════════════════════


class TestRecalculateOrderCommission:
    """佣金重算测试"""

    @pytest.mark.asyncio
    async def test_locked_order_rejected(self):
        """已有 ORDER 流水 → 锁定拒绝"""
        order = _make_order(1)
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(
            return_value=[_make_flow(1, flow_type="ORDER")]
        )
        svc = _make_service(order_dao=order_dao, flow_dao=flow_dao)
        with pytest.raises(ValueError, match="锁定不可重算"):
            await svc.recalculate_order_commission(1)

    @pytest.mark.asyncio
    async def test_normal_recalculate(self):
        """正常重算"""
        order = _make_order(1, user_commission="70.00")
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        order_dao.update_by_id = AsyncMock(return_value=order)
        flow_dao = MagicMock()
        flow_dao.list_by_order_id = AsyncMock(return_value=[])
        rule_engine = _make_rule_engine_mock(user_commission="80.00")
        svc = _make_service(order_dao, flow_dao, rule_engine=rule_engine)
        result = await svc.recalculate_order_commission(1)
        assert result["old_user_commission"] == 70.0
        assert result["new_user_commission"] == 80.0

    @pytest.mark.asyncio
    async def test_order_not_found(self):
        """订单不存在"""
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(order_dao=order_dao)
        with pytest.raises(ValueError, match="订单不存在"):
            await svc.recalculate_order_commission(999)


# ══════════════════════════════════════════════════════
# 6. 查询接口测试
# ══════════════════════════════════════════════════════


class TestListSettlementFlows:
    """查询佣金流水测试"""

    @pytest.mark.asyncio
    async def test_list_flows(self):
        """查询流水"""
        flows = [_make_flow(1), _make_flow(2)]
        settlement_dao = MagicMock()
        settlement_dao.list_flows_with_filters = AsyncMock(return_value=(flows, 2))
        svc = _make_service(settlement_dao=settlement_dao)
        result = await svc.list_settlement_flows(user_id=100, page=1, page_size=20)
        assert len(result["list"]) == 2
        assert result["total"] == 2


class TestListSettlementOrders:
    """查询结算状态订单测试"""

    @pytest.mark.asyncio
    async def test_list_orders(self):
        """查询订单"""
        orders = [{"id": 1, "has_commission_flow": True}]
        settlement_dao = MagicMock()
        settlement_dao.list_settlement_orders_with_filters = AsyncMock(
            return_value=(orders, 1)
        )
        svc = _make_service(settlement_dao=settlement_dao)
        result = await svc.list_settlement_orders(order_status=40, has_flow=True)
        assert len(result["list"]) == 1
        assert result["total"] == 1

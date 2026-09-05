# @ai-generated
"""
B12 佣金结算状态机单元测试
覆盖：
1. SettlementStateMachine 状态流转守护（合法/非法/终态/未知状态）
2. CommissionSettlementB12Service 冻结/解冻/标记打款/批量/查询/日志
3. settlement_b12_jobs 定时任务触发/开关/异常兜底/配置加载
4. 幂等锁拦截、熔断拦截、状态非法流转拦截、批量事务单条失败不阻断

覆盖率目标：单文件 ≥90%
"""
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b12_constants import (
    ACTION_CREATE_SETTLEMENT,
    ACTION_FREEZE,
    ACTION_MARK_PAID,
    ACTION_UNFREEZE,
    SETTLEMENT_DELAY_DAYS_DEFAULT,
    SETTLEMENT_BREAKER_CHANNEL,
    SettlementStatus,
)
from src.config.constants import OrderStatus
from src.services.commission_settlement_b12_service import (
    CommissionSettlementB12Service,
)
from src.services.settlement_state_machine import SettlementStateMachine


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    order_status: int = int(OrderStatus.SETTLABLE),
    total_commission: str = "100.00",
    user_commission: str = "80.00",
    platform_commission: str = "20.00",
    channel_code: str = "myq",
):
    order = MagicMock()
    order.id = order_id
    order.user_id = user_id
    order.order_status = order_status
    order.total_commission = Decimal(total_commission)
    order.user_commission = Decimal(user_commission)
    order.platform_commission = Decimal(platform_commission)
    order.channel_code = channel_code
    order.internal_order_no = f"GAK{order_id}"
    return order


def _make_settlement(
    settlement_id: int = 1,
    order_id: int = 1,
    user_id: int = 100,
    settlement_status: str = SettlementStatus.SETTLABLE.value,
    user_commission: str = "80.00",
    flow_id: int = 1,
    settlement_no: str = "GAKS20260802000001_1",
):
    s = MagicMock()
    s.id = settlement_id
    s.order_id = order_id
    s.user_id = user_id
    s.settlement_status = settlement_status
    s.user_commission = Decimal(user_commission)
    s.platform_commission = Decimal("20.00")
    s.total_commission = Decimal("100.00")
    s.flow_id = flow_id
    s.settlement_no = settlement_no
    s.channel_code = "myq"
    s.confirm_time = datetime.now() - timedelta(days=5)
    s.settle_time = None
    s.paid_time = None
    s.delay_days = 30
    s.remark = ""
    s.to_dict = MagicMock(
        return_value={
            "id": settlement_id,
            "order_id": order_id,
            "user_id": user_id,
            "settlement_status": settlement_status,
            "user_commission": user_commission,
            "settlement_no": settlement_no,
        }
    )
    return s


def _make_flow(flow_id: int = 1, order_id: int = 1, transfer_status: str = "PENDING"):
    flow = MagicMock()
    flow.id = flow_id
    flow.order_id = order_id
    flow.transfer_status = transfer_status
    flow.amount = Decimal("80.00")
    return flow


def _make_log(log_id: int = 1, settlement_id: int = 1, action: str = ACTION_FREEZE):
    log = MagicMock()
    log.id = log_id
    log.settlement_id = settlement_id
    log.action = action
    log.to_dict = MagicMock(
        return_value={"id": log_id, "settlement_id": settlement_id, "action": action}
    )
    return log


def _make_service(
    order_dao=None,
    settlement_dao=None,
    atomic_dao=None,
    log_dao=None,
    circuit_breaker=None,
):
    """构造 CommissionSettlementB12Service with mocks"""
    return CommissionSettlementB12Service(
        order_dao=order_dao or MagicMock(),
        settlement_dao=settlement_dao or MagicMock(),
        atomic_dao=atomic_dao or MagicMock(),
        log_dao=log_dao or MagicMock(),
        circuit_breaker=circuit_breaker,
    )


def _make_breaker(allowed: bool = True):
    """构造熔断器 mock"""
    breaker = AsyncMock()
    breaker.allow_request = AsyncMock(return_value=allowed)
    breaker.record_success = AsyncMock()
    breaker.record_failure = AsyncMock()
    return breaker


# ══════════════════════════════════════════════════════
# 1. SettlementStateMachine 状态机守护测试
# ══════════════════════════════════════════════════════


class TestSettlementStateMachine:
    """状态机流转守护测试"""

    def test_legal_transitions(self):
        """合法正向流转全部通过"""
        SettlementStateMachine.validate_transition(
            SettlementStatus.ORDERED.value, SettlementStatus.SETTLABLE.value
        )
        SettlementStateMachine.validate_transition(
            SettlementStatus.SETTLABLE.value, SettlementStatus.SETTLED.value
        )
        SettlementStateMachine.validate_transition(
            SettlementStatus.SETTLED.value, SettlementStatus.PAID.value
        )

    def test_illegal_rollback_transition(self):
        """回退流转被拦截"""
        with pytest.raises(ValueError, match="非法状态流转"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.SETTLED.value, SettlementStatus.SETTLABLE.value
            )
        with pytest.raises(ValueError, match="非法状态流转"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.PAID.value, SettlementStatus.SETTLED.value
            )

    def test_illegal_skip_transition(self):
        """跨状态跳跃流转被拦截"""
        with pytest.raises(ValueError, match="非法状态流转"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.ORDERED.value, SettlementStatus.SETTLED.value
            )
        with pytest.raises(ValueError, match="非法状态流转"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.SETTLABLE.value, SettlementStatus.PAID.value
            )

    def test_same_status_transition(self):
        """相同状态不算流转，被拦截"""
        with pytest.raises(ValueError, match="状态未变更"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.SETTLABLE.value, SettlementStatus.SETTLABLE.value
            )

    def test_unknown_status(self):
        """未知状态被拦截"""
        with pytest.raises(ValueError, match="未知结算单状态"):
            SettlementStateMachine.validate_transition(
                "UNKNOWN", SettlementStatus.SETTLABLE.value
            )
        with pytest.raises(ValueError, match="未知结算单状态"):
            SettlementStateMachine.validate_transition(
                SettlementStatus.ORDERED.value, "UNKNOWN"
            )

    def test_is_terminal(self):
        """PAID 为终态，其他非终态"""
        assert SettlementStateMachine.is_terminal(SettlementStatus.PAID.value) is True
        assert (
            SettlementStateMachine.is_terminal(SettlementStatus.SETTLED.value) is False
        )
        assert (
            SettlementStateMachine.is_terminal(SettlementStatus.SETTLABLE.value)
            is False
        )
        assert (
            SettlementStateMachine.is_terminal(SettlementStatus.ORDERED.value) is False
        )

    def test_get_allowed_next(self):
        """获取允许的下一状态"""
        assert SettlementStateMachine.get_allowed_next(
            SettlementStatus.ORDERED.value
        ) == {SettlementStatus.SETTLABLE.value}
        assert (
            SettlementStateMachine.get_allowed_next(SettlementStatus.PAID.value)
            == set()
        )

    def test_can_freeze(self):
        assert SettlementStateMachine.can_freeze(SettlementStatus.ORDERED.value) is True
        assert (
            SettlementStateMachine.can_freeze(SettlementStatus.SETTLABLE.value) is False
        )

    def test_can_unfreeze(self):
        assert (
            SettlementStateMachine.can_unfreeze(SettlementStatus.SETTLABLE.value)
            is True
        )
        assert (
            SettlementStateMachine.can_unfreeze(SettlementStatus.ORDERED.value) is False
        )

    def test_can_mark_paid(self):
        assert (
            SettlementStateMachine.can_mark_paid(SettlementStatus.SETTLED.value) is True
        )
        assert (
            SettlementStateMachine.can_mark_paid(SettlementStatus.SETTLABLE.value)
            is False
        )


# ══════════════════════════════════════════════════════
# 2. CommissionSettlementB12Service 冻结入账测试
# ══════════════════════════════════════════════════════


class TestFreezeOnSettlable:
    """冻结入账（ORDERED → SETTLABLE）测试"""

    @pytest.mark.asyncio
    async def test_freeze_success(self):
        """正常冻结入账成功"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLABLE))
        settlement = _make_settlement(settlement_id=10, order_id=1)
        flow = _make_flow(flow_id=20, order_id=1)

        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=None)
        atomic_dao = MagicMock()
        atomic_dao.freeze_atomic = AsyncMock(return_value=(settlement, flow))
        log_dao = MagicMock()
        log_dao.create = AsyncMock(return_value=_make_log())

        svc = _make_service(
            order_dao, settlement_dao, atomic_dao, log_dao, _make_breaker()
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            result = await svc.freeze_on_settlable(order_id=1, delay_days=30)

        assert result["status"] == "success"
        assert result["order_id"] == 1
        assert result["settlement_id"] == 10
        assert result["flow_id"] == 20
        atomic_dao.freeze_atomic.assert_called_once()
        # 操作日志记录两次（FREEZE + CREATE_SETTLEMENT）
        assert log_dao.create.call_count == 2

    @pytest.mark.asyncio
    async def test_freeze_idempotent_skip(self):
        """已存在结算单，幂等跳过"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLABLE))
        existing = _make_settlement(settlement_id=10, order_id=1)

        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=existing)
        atomic_dao = MagicMock()
        log_dao = MagicMock()

        svc = _make_service(
            order_dao, settlement_dao, atomic_dao, log_dao, _make_breaker()
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            result = await svc.freeze_on_settlable(order_id=1)

        assert result["status"] == "skipped"
        assert result["settlement_id"] == 10
        atomic_dao.freeze_atomic.assert_not_called()

    @pytest.mark.asyncio
    async def test_freeze_order_not_found(self):
        """订单不存在"""
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(order_dao=order_dao, circuit_breaker=_make_breaker())

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="订单不存在"):
                await svc.freeze_on_settlable(order_id=999)

    @pytest.mark.asyncio
    async def test_freeze_wrong_order_status(self):
        """订单状态非 SETTLABLE 被拦截"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLED))
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        svc = _make_service(order_dao=order_dao, circuit_breaker=_make_breaker())

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="订单状态非 SETTLABLE"):
                await svc.freeze_on_settlable(order_id=1)

    @pytest.mark.asyncio
    async def test_freeze_lock_interception(self):
        """幂等锁获取失败被拦截（重复执行拦截）"""
        svc = _make_service(circuit_breaker=_make_breaker())

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="正在处理中"):
                await svc.freeze_on_settlable(order_id=1)

    @pytest.mark.asyncio
    async def test_freeze_breaker_open(self):
        """熔断中被拦截"""
        svc = _make_service(circuit_breaker=_make_breaker(allowed=False))

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="结算熔断中"):
                await svc.freeze_on_settlable(order_id=1)

    @pytest.mark.asyncio
    async def test_freeze_no_breaker(self):
        """无熔断器（None）不报错，正常执行"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLABLE))
        settlement = _make_settlement(settlement_id=10, order_id=1)
        flow = _make_flow(flow_id=20, order_id=1)

        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=None)
        atomic_dao = MagicMock()
        atomic_dao.freeze_atomic = AsyncMock(return_value=(settlement, flow))
        log_dao = MagicMock()
        log_dao.create = AsyncMock()

        svc = _make_service(
            order_dao, settlement_dao, atomic_dao, log_dao, circuit_breaker=None
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            result = await svc.freeze_on_settlable(order_id=1)

        assert result["status"] == "success"


# ══════════════════════════════════════════════════════
# 3. CommissionSettlementB12Service 解冻转可用测试
# ══════════════════════════════════════════════════════


class TestUnfreezeOnSettled:
    """解冻转可用（SETTLABLE → SETTLED）测试"""

    @pytest.mark.asyncio
    async def test_unfreeze_success(self):
        """正常解冻成功"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLED))
        settlement = _make_settlement(
            settlement_id=10,
            order_id=1,
            settlement_status=SettlementStatus.SETTLABLE.value,
        )
        flow = _make_flow(flow_id=20, order_id=1)

        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=settlement)
        atomic_dao = MagicMock()
        atomic_dao.unfreeze_atomic = AsyncMock(return_value=(settlement, flow))
        log_dao = MagicMock()
        log_dao.create = AsyncMock()

        svc = _make_service(
            order_dao, settlement_dao, atomic_dao, log_dao, _make_breaker()
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            result = await svc.unfreeze_on_settled(order_id=1)

        assert result["status"] == "success"
        assert result["settlement_id"] == 10
        atomic_dao.unfreeze_atomic.assert_called_once()

    @pytest.mark.asyncio
    async def test_unfreeze_settlement_not_found(self):
        """结算单不存在"""
        order_dao = MagicMock()
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=None)
        svc = _make_service(
            order_dao=order_dao,
            settlement_dao=settlement_dao,
            circuit_breaker=_make_breaker(),
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="结算单不存在"):
                await svc.unfreeze_on_settled(order_id=1)

    @pytest.mark.asyncio
    async def test_unfreeze_illegal_state_transition(self):
        """状态非法流转被拦截（PAID → SETTLED 回退被拦截）"""
        settlement = _make_settlement(
            settlement_id=10, order_id=1, settlement_status=SettlementStatus.PAID.value
        )
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=settlement)
        svc = _make_service(
            settlement_dao=settlement_dao, circuit_breaker=_make_breaker()
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="非法状态流转"):
                await svc.unfreeze_on_settled(order_id=1)

    @pytest.mark.asyncio
    async def test_unfreeze_order_not_found(self):
        """订单不存在"""
        settlement = _make_settlement(
            settlement_id=10,
            order_id=1,
            settlement_status=SettlementStatus.SETTLABLE.value,
        )
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=None)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=settlement)
        svc = _make_service(
            order_dao=order_dao,
            settlement_dao=settlement_dao,
            circuit_breaker=_make_breaker(),
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="订单不存在"):
                await svc.unfreeze_on_settled(order_id=1)

    @pytest.mark.asyncio
    async def test_unfreeze_wrong_order_status(self):
        """订单状态非 SETTLED 被拦截"""
        order = _make_order(order_id=1, order_status=int(OrderStatus.SETTLABLE))
        settlement = _make_settlement(
            settlement_id=10,
            order_id=1,
            settlement_status=SettlementStatus.SETTLABLE.value,
        )
        order_dao = MagicMock()
        order_dao.get_by_id = AsyncMock(return_value=order)
        settlement_dao = MagicMock()
        settlement_dao.get_by_order_id = AsyncMock(return_value=settlement)
        svc = _make_service(
            order_dao=order_dao,
            settlement_dao=settlement_dao,
            circuit_breaker=_make_breaker(),
        )

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.commission_settlement_b12_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="订单状态非 SETTLED"):
                await svc.unfreeze_on_settled(order_id=1)

    @pytest.mark.asyncio
    async def test_unfreeze_lock_interception(self):
        """幂等锁获取失败被拦截"""
        svc = _make_service(circuit_breaker=_make_breaker())

        with patch(
            "src.services.commission_settlement_b12_service.LockUtil.acquire_lock",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="正在处理中"):
                await svc.unfreeze_on_settled(order_id=1)


# ══════════════════════════════════════════════════════
# 4. CommissionSettlementB12Service 标记已打款测试
# ══════════════════════════════════════════════════════


class TestMarkPaid:
    """标记已打款（SETTLED → PAID）测试"""

    @pytest.mark.asyncio
    async def test_mark_paid_success(self):
        """正常标记打款成功"""
        settlement = _make_settlement(
            settlement_id=10,
            order_id=1,
            settlement_status=SettlementStatus.SETTLED.value,
        )
        updated = _make_settlement(
            settlement_id=10, order_id=1, settlement_status=SettlementStatus.PAID.value
        )
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=settlement)
        settlement_dao.update_by_id = AsyncMock(return_value=updated)
        log_dao = MagicMock()
        log_dao.create = AsyncMock()

        svc = _make_service(settlement_dao=settlement_dao, log_dao=log_dao)

        result = await svc.mark_paid(settlement_id=10, operator_id=200)

        assert result["status"] == "success"
        assert result["settlement_id"] == 10
        settlement_dao.update_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_paid_terminal_skip(self):
        """终态幂等跳过"""
        settlement = _make_settlement(
            settlement_id=10, order_id=1, settlement_status=SettlementStatus.PAID.value
        )
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=settlement)

        svc = _make_service(settlement_dao=settlement_dao)

        result = await svc.mark_paid(settlement_id=10)

        assert result["status"] == "skipped"
        settlement_dao.update_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_paid_not_found(self):
        """结算单不存在"""
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(settlement_dao=settlement_dao)

        with pytest.raises(ValueError, match="结算单不存在"):
            await svc.mark_paid(settlement_id=999)

    @pytest.mark.asyncio
    async def test_mark_paid_illegal_transition(self):
        """非法流转被拦截（SETTLABLE → PAID 跳跃）"""
        settlement = _make_settlement(
            settlement_id=10,
            order_id=1,
            settlement_status=SettlementStatus.SETTLABLE.value,
        )
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=settlement)
        svc = _make_service(settlement_dao=settlement_dao)

        with pytest.raises(ValueError, match="非法状态流转"):
            await svc.mark_paid(settlement_id=10)


# ══════════════════════════════════════════════════════
# 5. 批量任务测试（含单条失败不阻断/批量回滚场景）
# ══════════════════════════════════════════════════════


class TestBatchFreeze:
    """批量冻结任务测试"""

    @pytest.mark.asyncio
    async def test_batch_freeze_empty(self):
        """无待冻结订单"""
        settlement_dao = MagicMock()
        settlement_dao.list_settlable_orders_without_settlement = AsyncMock(
            return_value=([], 0)
        )
        svc = _make_service(settlement_dao=settlement_dao)

        result = await svc.batch_freeze_settlable(limit=200, delay_days=30)

        assert result["status"] == "success"
        assert result["total"] == 0
        assert result["success_count"] == 0

    @pytest.mark.asyncio
    async def test_batch_freeze_mixed_success_failure(self):
        """批量冻结：部分成功部分失败（单条失败不阻断整体）"""
        orders = [
            _make_order(order_id=1, order_status=int(OrderStatus.SETTLABLE)),
            _make_order(order_id=2, order_status=int(OrderStatus.SETTLABLE)),
            _make_order(order_id=3, order_status=int(OrderStatus.SETTLABLE)),
        ]
        settlement_dao = MagicMock()
        settlement_dao.list_settlable_orders_without_settlement = AsyncMock(
            return_value=(orders, 3)
        )
        svc = _make_service(
            settlement_dao=settlement_dao, circuit_breaker=_make_breaker()
        )

        call_count = [0]

        async def mock_freeze(order_id, **kwargs):
            call_count[0] += 1
            if order_id == 2:
                raise ValueError("模拟单笔失败")
            return {
                "status": "success",
                "order_id": order_id,
                "settlement_id": call_count[0],
            }

        svc.freeze_on_settlable = mock_freeze

        result = await svc.batch_freeze_settlable(limit=200, delay_days=30)

        assert result["status"] == "partial"
        assert result["total"] == 3
        assert result["success_count"] == 2
        assert result["failed_count"] == 1
        assert len(result["details"]) == 3


class TestBatchUnfreeze:
    """批量解冻任务测试"""

    @pytest.mark.asyncio
    async def test_batch_unfreeze_empty(self):
        """无待解冻结算单"""
        settlement_dao = MagicMock()
        settlement_dao.list_settled_pending_unfreeze = AsyncMock(return_value=([], 0))
        svc = _make_service(settlement_dao=settlement_dao)

        result = await svc.batch_unfreeze_settled(limit=200)

        assert result["status"] == "success"
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_batch_unfreeze_mixed_success_failure(self):
        """批量解冻：部分成功部分失败（批量事务回滚场景模拟）"""
        settlements = [
            _make_settlement(settlement_id=1, order_id=1),
            _make_settlement(settlement_id=2, order_id=2),
        ]
        settlement_dao = MagicMock()
        settlement_dao.list_settled_pending_unfreeze = AsyncMock(
            return_value=(settlements, 2)
        )
        svc = _make_service(
            settlement_dao=settlement_dao, circuit_breaker=_make_breaker()
        )

        async def mock_unfreeze(order_id, **kwargs):
            if order_id == 2:
                raise ValueError("模拟解冻失败（冻结余额不足）")
            return {"status": "success", "order_id": order_id, "settlement_id": 1}

        svc.unfreeze_on_settled = mock_unfreeze

        result = await svc.batch_unfreeze_settled(limit=200)

        assert result["status"] == "partial"
        assert result["success_count"] == 1
        assert result["failed_count"] == 1


# ══════════════════════════════════════════════════════
# 6. 后台查询接口测试
# ══════════════════════════════════════════════════════


class TestQueryInterfaces:
    """后台查询接口测试"""

    @pytest.mark.asyncio
    async def test_list_settlements_with_filters(self):
        """分页查询结算单"""
        items = [_make_settlement(settlement_id=1), _make_settlement(settlement_id=2)]
        settlement_dao = MagicMock()
        settlement_dao.list_with_filters = AsyncMock(return_value=(items, 2))
        svc = _make_service(settlement_dao=settlement_dao)

        result = await svc.list_settlements_with_filters(
            settlement_status=SettlementStatus.SETTLABLE.value, page=1, page_size=20
        )

        assert result["total"] == 2
        assert len(result["list"]) == 2
        assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_list_overdue_settlable(self):
        """超期预警查询"""
        items = [_make_settlement(settlement_id=1)]
        settlement_dao = MagicMock()
        settlement_dao.list_overdue_settlable = AsyncMock(return_value=(items, 1))
        svc = _make_service(settlement_dao=settlement_dao)

        result = await svc.list_overdue_settlable(delay_days=30, page=1, page_size=50)

        assert result["total"] == 1
        assert len(result["list"]) == 1

    @pytest.mark.asyncio
    async def test_get_settlement_detail_success(self):
        """结算单详情含操作历史"""
        settlement = _make_settlement(settlement_id=1)
        logs = [_make_log(log_id=1), _make_log(log_id=2)]
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=settlement)
        log_dao = MagicMock()
        log_dao.list_by_settlement_id = AsyncMock(return_value=(logs, 2))
        svc = _make_service(settlement_dao=settlement_dao, log_dao=log_dao)

        result = await svc.get_settlement_detail(settlement_id=1)

        assert result["settlement"]["id"] == 1
        assert result["log_total"] == 2
        assert len(result["logs"]) == 2

    @pytest.mark.asyncio
    async def test_get_settlement_detail_not_found(self):
        """结算单不存在"""
        settlement_dao = MagicMock()
        settlement_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(settlement_dao=settlement_dao)

        with pytest.raises(ValueError, match="结算单不存在"):
            await svc.get_settlement_detail(settlement_id=999)

    @pytest.mark.asyncio
    async def test_get_settlement_logs(self):
        """操作历史分页查询"""
        logs = [_make_log(log_id=1)]
        log_dao = MagicMock()
        log_dao.list_by_settlement_id = AsyncMock(return_value=(logs, 1))
        svc = _make_service(log_dao=log_dao)

        result = await svc.get_settlement_logs(settlement_id=1, page=1, page_size=50)

        assert result["total"] == 1
        assert len(result["list"]) == 1

    @pytest.mark.asyncio
    async def test_list_operation_logs_with_filters(self):
        """操作日志多条件查询"""
        logs = [_make_log(log_id=1, action=ACTION_FREEZE)]
        log_dao = MagicMock()
        log_dao.list_with_filters = AsyncMock(return_value=(logs, 1))
        svc = _make_service(log_dao=log_dao)

        result = await svc.list_operation_logs_with_filters(
            action=ACTION_FREEZE, page=1, page_size=20
        )

        assert result["total"] == 1
        assert len(result["list"]) == 1


# ══════════════════════════════════════════════════════
# 7. 内部工具方法测试
# ══════════════════════════════════════════════════════


class TestInternalUtils:
    """内部工具方法测试"""

    def test_generate_settlement_no(self):
        """结算单号生成格式校验"""
        no = CommissionSettlementB12Service._generate_settlement_no(order_id=123)
        assert no.startswith("GAKS")
        assert no.endswith("_123")
        assert len(no) > 10

    def test_empty_batch_result(self):
        """空批次结果结构校验"""
        result = CommissionSettlementB12Service._empty_batch_result()
        assert result["status"] == "success"
        assert result["total"] == 0
        assert result["success_count"] == 0
        assert result["failed_count"] == 0
        assert result["skipped_count"] == 0
        assert result["details"] == []

    @pytest.mark.asyncio
    async def test_log_operation_failure_not_blocking(self):
        """操作日志记录失败不阻断主流程"""
        log_dao = MagicMock()
        log_dao.create = AsyncMock(side_effect=Exception("DB 异常"))
        svc = _make_service(log_dao=log_dao)

        # 不抛异常即说明未阻断
        await svc._log_operation(
            settlement_id=1,
            order_id=1,
            from_status=SettlementStatus.ORDERED.value,
            to_status=SettlementStatus.SETTLABLE.value,
            action=ACTION_FREEZE,
            amount=Decimal("80.00"),
        )

    @pytest.mark.asyncio
    async def test_record_success_no_breaker(self):
        """无熔断器时 record_success 不报错"""
        svc = _make_service(circuit_breaker=None)
        await svc._record_success()

    @pytest.mark.asyncio
    async def test_record_failure_no_breaker(self):
        """无熔断器时 record_failure 不报错"""
        svc = _make_service(circuit_breaker=None)
        await svc._record_failure()

    @pytest.mark.asyncio
    async def test_record_success_breaker_exception_not_blocking(self):
        """熔断器 record_success 异常不阻断"""
        breaker = AsyncMock()
        breaker.record_success = AsyncMock(side_effect=Exception("Redis 异常"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._record_success()  # 不抛异常

    @pytest.mark.asyncio
    async def test_release_op_lock_none_owner(self):
        """lock_owner 为 None 时直接返回"""
        svc = _make_service()
        await svc._release_op_lock(order_id=1, action=ACTION_FREEZE, lock_owner=None)


# ══════════════════════════════════════════════════════
# 8. 定时任务测试（settlement_b12_jobs）
# ══════════════════════════════════════════════════════


class TestSettlementB12Jobs:
    """定时任务触发/开关/异常兜底测试"""

    @pytest.mark.asyncio
    async def test_batch_freeze_job_disabled(self):
        """任务开关关闭时跳过"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_FREEZE_ENABLE", False
        ):
            from src.scheduler.settlement_b12_jobs import batch_freeze_settlable_job

            result = await batch_freeze_settlable_job()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_batch_unfreeze_job_disabled(self):
        """任务开关关闭时跳过"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_UNFREEZE_ENABLE", False
        ):
            from src.scheduler.settlement_b12_jobs import batch_unfreeze_settled_job

            result = await batch_unfreeze_settled_job()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_batch_freeze_job_success(self):
        """批量冻结任务正常执行"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_FREEZE_ENABLE", True
        ), patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.settlement_b12_jobs._load_settlement_delay_days",
            return_value=30,
        ), patch(
            "src.scheduler.settlement_b12_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.batch_freeze_settlable = AsyncMock(
                return_value={
                    "status": "success",
                    "total": 1,
                    "success_count": 1,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "details": [],
                }
            )
            mock_build.return_value = mock_svc

            from src.scheduler.settlement_b12_jobs import batch_freeze_settlable_job

            result = await batch_freeze_settlable_job()

        assert result["status"] == "success"
        assert result["delay_days"] == 30

    @pytest.mark.asyncio
    async def test_batch_freeze_job_exception(self):
        """批量冻结任务异常兜底"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_FREEZE_ENABLE", True
        ), patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session",
            side_effect=Exception("DB 连接失败"),
        ):
            from src.scheduler.settlement_b12_jobs import batch_freeze_settlable_job

            result = await batch_freeze_settlable_job()

        assert result["status"] == "failed"
        assert "DB 连接失败" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_unfreeze_job_success(self):
        """批量解冻任务正常执行"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_UNFREEZE_ENABLE", True
        ), patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.settlement_b12_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.batch_unfreeze_settled = AsyncMock(
                return_value={
                    "status": "success",
                    "total": 1,
                    "success_count": 1,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "details": [],
                }
            )
            mock_build.return_value = mock_svc

            from src.scheduler.settlement_b12_jobs import batch_unfreeze_settled_job

            result = await batch_unfreeze_settled_job()

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_freeze_single_order_job_success(self):
        """单笔冻结手动补发成功"""
        with patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.settlement_b12_jobs._load_settlement_delay_days",
            return_value=30,
        ), patch(
            "src.scheduler.settlement_b12_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.freeze_on_settlable = AsyncMock(
                return_value={"status": "success", "order_id": 1, "settlement_id": 10}
            )
            mock_build.return_value = mock_svc

            from src.scheduler.settlement_b12_jobs import freeze_single_order_job

            result = await freeze_single_order_job(order_id=1)

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_unfreeze_single_order_job_success(self):
        """单笔解冻手动补发成功"""
        with patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.settlement_b12_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.unfreeze_on_settled = AsyncMock(
                return_value={"status": "success", "order_id": 1, "settlement_id": 10}
            )
            mock_build.return_value = mock_svc

            from src.scheduler.settlement_b12_jobs import unfreeze_single_order_job

            result = await unfreeze_single_order_job(order_id=1)

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_freeze_single_order_job_exception(self):
        """单笔冻结异常兜底"""
        with patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session",
            side_effect=Exception("连接超时"),
        ):
            from src.scheduler.settlement_b12_jobs import freeze_single_order_job

            result = await freeze_single_order_job(order_id=1)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_unfreeze_single_order_job_exception(self):
        """单笔解冻异常兜底"""
        with patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session",
            side_effect=Exception("连接超时"),
        ):
            from src.scheduler.settlement_b12_jobs import unfreeze_single_order_job

            result = await unfreeze_single_order_job(order_id=1)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_batch_unfreeze_job_exception(self):
        """批量解冻任务异常兜底"""
        with patch(
            "src.scheduler.settlement_b12_jobs.TASK_SETTLEMENT_UNFREEZE_ENABLE", True
        ), patch(
            "src.scheduler.settlement_b12_jobs.DatabaseManager.get_session",
            side_effect=Exception("DB 连接失败"),
        ):
            from src.scheduler.settlement_b12_jobs import batch_unfreeze_settled_job

            result = await batch_unfreeze_settled_job()

        assert result["status"] == "failed"
        assert "DB 连接失败" in result["message"]

    @pytest.mark.asyncio
    async def test_build_service_constructs_all_dependencies(self):
        """_build_service 正确注入 4 个 DAO + 熔断器"""
        from src.scheduler.settlement_b12_jobs import _build_service

        db_session = MagicMock()
        svc = await _build_service(db_session)
        assert svc.order_dao is not None
        assert svc.settlement_dao is not None
        assert svc.atomic_dao is not None
        assert svc.log_dao is not None
        assert svc.circuit_breaker is not None

    def test_register_settlement_b12_jobs(self):
        """register_settlement_b12_jobs 注册两个定时任务"""
        from src.scheduler.settlement_b12_jobs import register_settlement_b12_jobs

        with patch(
            "src.scheduler.settlement_b12_jobs.TaskScheduler.add_cron_task"
        ) as mock_add:
            register_settlement_b12_jobs()

        assert mock_add.call_count == 2
        # 校验任务名称（name 为关键字参数）
        task_names = [call.kwargs["name"] for call in mock_add.call_args_list]
        assert "batch_freeze_settlable" in task_names
        assert "batch_unfreeze_settled" in task_names


# ══════════════════════════════════════════════════════
# 9. 配置加载器测试（_load_settlement_delay_days）
# ══════════════════════════════════════════════════════


class TestLoadSettlementDelayDays:
    """延迟结算天数配置加载测试"""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Redis 缓存命中"""
        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value="45"
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(MagicMock())
        assert result == 45

    @pytest.mark.asyncio
    async def test_cache_empty_value(self):
        """Redis 缓存空值标记，回退默认"""
        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get",
            return_value="__EMPTY__",
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(MagicMock())
        assert result == SETTLEMENT_DELAY_DAYS_DEFAULT

    @pytest.mark.asyncio
    async def test_cache_invalid_value(self):
        """Redis 缓存值非法，回退默认"""
        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value="abc"
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(MagicMock())
        assert result == SETTLEMENT_DELAY_DAYS_DEFAULT

    @pytest.mark.asyncio
    async def test_db_hit(self):
        """缓存未命中，查库命中"""
        db_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=("60",))
        db_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value=None
        ), patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.set", return_value=True
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(db_session)
        assert result == 60

    @pytest.mark.asyncio
    async def test_db_miss_fallback_default(self):
        """缓存未命中，查库也无记录，回退默认"""
        db_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)
        db_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value=None
        ), patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.set_empty_cache",
            return_value=None,
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(db_session)
        assert result == SETTLEMENT_DELAY_DAYS_DEFAULT

    @pytest.mark.asyncio
    async def test_db_exception_fallback_default(self):
        """查库异常，回退默认"""
        db_session = MagicMock()
        db_session.execute = AsyncMock(side_effect=Exception("DB 异常"))

        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value=None
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(db_session)
        assert result == SETTLEMENT_DELAY_DAYS_DEFAULT

    @pytest.mark.asyncio
    async def test_db_invalid_value_fallback_default(self):
        """查库值非法，回退默认"""
        db_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=("abc",))
        db_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.get", return_value=None
        ), patch(
            "src.scheduler.settlement_b12_jobs.RedisClient.set", return_value=True
        ):
            from src.scheduler.settlement_b12_jobs import _load_settlement_delay_days

            result = await _load_settlement_delay_days(db_session)
        assert result == SETTLEMENT_DELAY_DAYS_DEFAULT

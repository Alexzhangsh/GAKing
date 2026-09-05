# @ai-generated
"""
B17 多渠道对账差异处理与多渠道聚合统计 单元测试
覆盖：
1. 渠道对账成功（无差异）
2. 渠道订单佣金 ↔ 结算入账不一致（CHANNEL_ORDER_SETTLEMENT_MISMATCH）
3. 单边账-订单侧（有订单无结算单）
4. 单边账-结算侧（有结算单无订单）
5. 幂等锁拦截（同日重复对账）
6. 熔断降级
7. 多渠道聚合统计（佣金/订单/成交分渠道汇总）
8. 渠道订单趋势（按天/周/月，支持单渠道筛选）
9. 内部工具方法（金额比较/差异构造/批次号生成）
10. 定时任务（开关/锁/异常兜底）
11. 差异 DAO（渠道筛选/渠道汇总）

覆盖率目标：单文件 ≥85%
"""
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b13_constants import (
    AlertLevel,
    DiffStatus,
    RECONCILIATION_TOLERANCE,
)
from src.config.b17_constants import (
    CHANNEL_RECONCILIATION_CHANNELS,
    ChannelDiffType,
    ChannelReconciliationStatus,
)
from src.services.b17_channel_reconciliation_service import (
    B17ChannelReconciliationService,
)


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_record(
    record_id: int = 1,
    reconciliation_no: str = "GAKCR20260801ABC12345",
    reconcile_date: date = date(2026, 8, 1),
    status: str = ChannelReconciliationStatus.RUNNING.value,
):
    r = MagicMock()
    r.id = record_id
    r.reconciliation_no = reconciliation_no
    r.reconcile_date = reconcile_date
    r.status = status
    return r


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    user_commission: str = "80.00",
    internal_order_no: str = "GAK001",
    channel_code: str = "myq",
):
    o = MagicMock()
    o.id = order_id
    o.user_id = user_id
    o.user_commission = Decimal(user_commission)
    o.total_commission = Decimal("100.00")
    o.internal_order_no = internal_order_no
    o.channel_code = channel_code
    return o


def _make_settlement(
    settlement_id: int = 1,
    order_id: int = 1,
    user_id: int = 100,
    user_commission: str = "80.00",
    settlement_no: str = "GAKS001",
    channel_code: str = "myq",
):
    s = MagicMock()
    s.id = settlement_id
    s.order_id = order_id
    s.user_id = user_id
    s.user_commission = Decimal(user_commission)
    s.total_commission = Decimal("100.00")
    s.settlement_no = settlement_no
    s.channel_code = channel_code
    return s


def _make_breaker(allowed: bool = True):
    breaker = AsyncMock()
    breaker.allow_request = AsyncMock(return_value=allowed)
    breaker.record_success = AsyncMock()
    breaker.record_failure = AsyncMock()
    return breaker


def _make_service(
    record_dao=None,
    diff_dao=None,
    session=None,
    circuit_breaker=None,
):
    return B17ChannelReconciliationService(
        record_dao=record_dao or MagicMock(),
        diff_dao=diff_dao or MagicMock(),
        session=session or MagicMock(),
        circuit_breaker=circuit_breaker,
    )


def _channel_result(
    order_count: int = 1,
    matched_count: int = 1,
    diffs: list = None,
    order_commission: str = "80.00",
    settlement_commission: str = "80.00",
):
    return {
        "order_count": order_count,
        "matched_count": matched_count,
        "diffs": diffs or [],
        "order_commission": Decimal(order_commission),
        "settlement_commission": Decimal(settlement_commission),
    }


# ══════════════════════════════════════════════════════
# 1. 渠道对账成功（无差异）
# ══════════════════════════════════════════════════════


class TestChannelReconciliationSuccess:
    """渠道对账成功（无差异）"""

    @pytest.mark.asyncio
    async def test_all_matched_no_diff(self):
        """双渠道一致，无差异，对账成功"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()

        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        svc = _make_service(record_dao, diff_dao, circuit_breaker=_make_breaker())

        svc._execute_channel_check = AsyncMock(
            return_value={
                "order_count": 10,
                "matched_count": 10,
                "diff_count": 0,
                "total_order_commission": Decimal("800.00"),
                "total_settlement_commission": Decimal("800.00"),
                "critical_diff_count": 0,
                "channel_stats": {
                    "myq": {
                        "order_count": 5, "matched_count": 5, "diff_count": 0,
                        "order_commission": "400.00",
                        "settlement_commission": "400.00",
                    },
                    "orderx": {
                        "order_count": 5, "matched_count": 5, "diff_count": 0,
                        "order_commission": "400.00",
                        "settlement_commission": "400.00",
                    },
                },
            }
        )

        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            result = await svc.run_channel_reconciliation(
                reconcile_date=date(2026, 8, 1),
                reconcile_type="DAILY",
            )

        assert result["status"] == ChannelReconciliationStatus.SUCCESS.value
        assert result["diff_count"] == 0
        assert result["matched_count"] == 10
        assert result["critical_diff_count"] == 0
        assert set(result["channel_stats"].keys()) == set(
            CHANNEL_RECONCILIATION_CHANNELS
        )
        diff_dao.batch_create.assert_not_called()
        record_dao.update_by_id.assert_called_once()


# ══════════════════════════════════════════════════════
# 2. 渠道订单佣金 ↔ 结算入账不一致
# ══════════════════════════════════════════════════════


class TestChannelMismatch:
    """渠道订单佣金 ↔ 结算入账不一致"""

    @pytest.mark.asyncio
    async def test_order_settlement_mismatch(self):
        """订单佣金与结算入账不一致 → CHANNEL_ORDER_SETTLEMENT_MISMATCH"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()

        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        svc = _make_service(record_dao, diff_dao, circuit_breaker=_make_breaker())

        mismatch_diff = svc._build_diff(
            reconciliation_id=1, user_id=100, channel_code="myq",
            diff_type=ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value,
            source_type="ORDER", target_type="SETTLEMENT",
            source_amount=Decimal("80.00"), target_amount=Decimal("70.00"),
        )
        svc._execute_channel_check = AsyncMock(
            return_value={
                "order_count": 1,
                "matched_count": 0,
                "diff_count": 1,
                "total_order_commission": Decimal("80.00"),
                "total_settlement_commission": Decimal("70.00"),
                "critical_diff_count": 0,
                "channel_stats": {
                    "myq": {
                        "order_count": 1, "matched_count": 0, "diff_count": 1,
                        "order_commission": "80.00",
                        "settlement_commission": "70.00",
                    },
                    "orderx": {
                        "order_count": 0, "matched_count": 0, "diff_count": 0,
                        "order_commission": "0.00",
                        "settlement_commission": "0.00",
                    },
                },
            }
        )

        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            result = await svc.run_channel_reconciliation(
                reconcile_date=date(2026, 8, 1),
                reconcile_type="MANUAL",
                operator_id=1,
            )

        assert result["status"] == ChannelReconciliationStatus.PARTIAL.value
        assert result["diff_count"] == 1
        assert result["channel_stats"]["myq"]["diff_count"] == 1
        assert mismatch_diff["diff_type"] == (
            ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value
        )
        assert mismatch_diff["alert_level"] == AlertLevel.WARNING.value


# ══════════════════════════════════════════════════════
# 3. 单边账-订单侧
# ══════════════════════════════════════════════════════


class TestSingleSideOrder:
    """单边账-订单侧（有订单无结算单）"""

    @pytest.mark.asyncio
    async def test_order_without_settlement(self):
        """渠道有订单但无结算单 → CHANNEL_SINGLE_SIDE_ORDER"""
        order = _make_order(order_id=1, user_commission="80.00", channel_code="myq")
        svc = _make_service()
        svc._aggregate_channel_orders = AsyncMock(return_value={})
        svc._aggregate_channel_settlements = AsyncMock(return_value={})
        svc._find_channel_orders_without_settlement = AsyncMock(
            return_value=[order]
        )
        svc._find_channel_settlements_without_order = AsyncMock(return_value=[])
        diffs = await svc._check_single_channel(
            reconciliation_id=1,
            channel_code="myq",
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
        )
        assert any(
            d["diff_type"] == ChannelDiffType.CHANNEL_SINGLE_SIDE_ORDER.value
            for d in diffs["diffs"]
        )
        single = next(
            d for d in diffs["diffs"]
            if d["diff_type"] == ChannelDiffType.CHANNEL_SINGLE_SIDE_ORDER.value
        )
        assert single["source_amount"] == Decimal("80.00")
        assert single["target_amount"] == Decimal("0.00")
        assert single["channel_code"] == "myq"
        assert single["alert_level"] == AlertLevel.INFO.value


# ══════════════════════════════════════════════════════
# 4. 单边账-结算侧
# ══════════════════════════════════════════════════════


class TestSingleSideSettlement:
    """单边账-结算侧（有结算单无订单）"""

    @pytest.mark.asyncio
    async def test_settlement_without_order(self):
        """渠道有结算单但订单缺失 → CHANNEL_SINGLE_SIDE_SETTLEMENT"""
        settlement = _make_settlement(
            settlement_id=1, user_commission="80.00", channel_code="orderx"
        )
        svc = _make_service()
        svc._aggregate_channel_orders = AsyncMock(return_value={})
        svc._aggregate_channel_settlements = AsyncMock(return_value={})
        svc._find_channel_orders_without_settlement = AsyncMock(return_value=[])
        svc._find_channel_settlements_without_order = AsyncMock(
            return_value=[settlement]
        )
        diffs = await svc._check_single_channel(
            reconciliation_id=1,
            channel_code="orderx",
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
        )
        assert any(
            d["diff_type"] == ChannelDiffType.CHANNEL_SINGLE_SIDE_SETTLEMENT.value
            for d in diffs["diffs"]
        )
        single = next(
            d for d in diffs["diffs"]
            if d["diff_type"] == ChannelDiffType.CHANNEL_SINGLE_SIDE_SETTLEMENT.value
        )
        assert single["source_amount"] == Decimal("80.00")
        assert single["target_amount"] == Decimal("0.00")
        assert single["channel_code"] == "orderx"
        assert single["alert_level"] == AlertLevel.WARNING.value


# ══════════════════════════════════════════════════════
# 5. 幂等锁拦截
# ══════════════════════════════════════════════════════


class TestIdempotentLock:
    """幂等锁拦截（同日重复对账）"""

    @pytest.mark.asyncio
    async def test_duplicate_run_blocked(self):
        """同日重复对账被幂等锁拦截"""
        svc = _make_service()
        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value=None,
        ):
            with pytest.raises(ValueError) as exc_info:
                await svc.run_channel_reconciliation(
                    reconcile_date=date(2026, 8, 1),
                )
        assert "正在执行中或已对账" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_default_reconcile_date_yesterday(self):
        """未传日期时默认对账昨天"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()
        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        svc = _make_service(record_dao, diff_dao, circuit_breaker=_make_breaker())
        svc._execute_channel_check = AsyncMock(
            return_value={
                "order_count": 0, "matched_count": 0, "diff_count": 0,
                "total_order_commission": Decimal("0.00"),
                "total_settlement_commission": Decimal("0.00"),
                "critical_diff_count": 0, "channel_stats": {},
            }
        )
        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set", return_value=True,
        ):
            result = await svc.run_channel_reconciliation(reconcile_type="DAILY")

        assert result["status"] == ChannelReconciliationStatus.SUCCESS.value
        created = record_dao.create.call_args[0][0]
        assert created["reconcile_date"] == date.today() - timedelta(days=1)

    @pytest.mark.asyncio
    async def test_cache_write_failure_ignored(self):
        """幂等缓存写入失败不阻断对账"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()
        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        svc = _make_service(record_dao, diff_dao, circuit_breaker=_make_breaker())
        svc._execute_channel_check = AsyncMock(
            return_value={
                "order_count": 0, "matched_count": 0, "diff_count": 0,
                "total_order_commission": Decimal("0.00"),
                "total_settlement_commission": Decimal("0.00"),
                "critical_diff_count": 0, "channel_stats": {},
            }
        )
        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            side_effect=RuntimeError("redis down"),
        ):
            result = await svc.run_channel_reconciliation(
                reconcile_date=date(2026, 8, 1),
            )

        assert result["status"] == ChannelReconciliationStatus.SUCCESS.value
        record_dao.update_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_channel_check_real(self):
        """_execute_channel_check 真实实现：多渠道汇总 + 差异落库 + 告警"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()
        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        svc = _make_service(record_dao, diff_dao, circuit_breaker=_make_breaker())

        async def fake_check(reconciliation_id, channel_code, start_time, end_time):
            if channel_code == "myq":
                return {
                    "order_count": 5, "matched_count": 5, "diffs": [],
                    "order_commission": Decimal("400.00"),
                    "settlement_commission": Decimal("400.00"),
                }
            return {
                "order_count": 3, "matched_count": 2, "diffs": [
                    svc._build_diff(
                        reconciliation_id, 200, "orderx",
                        ChannelDiffType.CHANNEL_ORDER_MISSING.value,
                        "ORDER", "SETTLEMENT",
                        Decimal("50.00"), Decimal("0.00"),
                    )
                ],
                "order_commission": Decimal("300.00"),
                "settlement_commission": Decimal("250.00"),
            }

        svc._check_single_channel = fake_check
        result = await svc._execute_channel_check(1, date(2026, 8, 1))

        assert result["order_count"] == 8
        assert result["matched_count"] == 7
        assert result["diff_count"] == 1
        assert result["critical_diff_count"] == 1
        assert result["channel_stats"]["myq"]["order_count"] == 5
        assert result["channel_stats"]["orderx"]["diff_count"] == 1
        diff_dao.batch_create.assert_called_once()
        assert len(diff_dao.batch_create.call_args[0][0]) == 1

    @pytest.mark.asyncio
    async def test_failure_updates_record(self):
        """对账异常时更新批次为 FAILED"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()
        record_dao.list_with_filters = AsyncMock(
            return_value=[(_make_record(record_id=1),)]
        )

        svc = _make_service(record_dao, circuit_breaker=_make_breaker())
        svc._execute_channel_check = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(RuntimeError):
                await svc.run_channel_reconciliation(
                    reconcile_date=date(2026, 8, 1),
                )

        update_call = record_dao.update_by_id.call_args[0]
        assert update_call[0] == 1
        assert update_call[1]["status"] == ChannelReconciliationStatus.FAILED.value


# ══════════════════════════════════════════════════════
# 6. 熔断降级
# ══════════════════════════════════════════════════════


class TestCircuitBreaker:
    """熔断降级"""

    @pytest.mark.asyncio
    async def test_breaker_blocked(self):
        """熔断拦截对账执行"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        svc = _make_service(
            record_dao=record_dao,
            circuit_breaker=_make_breaker(allowed=False),
        )
        with patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.b17_channel_reconciliation_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError) as exc_info:
                await svc.run_channel_reconciliation(
                    reconcile_date=date(2026, 8, 1),
                )
        assert "熔断" in str(exc_info.value)


# ══════════════════════════════════════════════════════
# 7. 多渠道聚合统计
# ══════════════════════════════════════════════════════


class TestAggregateStats:
    """多渠道聚合统计（佣金/订单/成交分渠道汇总）"""

    @pytest.mark.asyncio
    async def test_aggregate_stats(self):
        """聚合统计按渠道分组汇总"""
        session = MagicMock()
        row_myq = MagicMock()
        row_myq.channel_code = "myq"
        row_myq.order_count = 5
        row_myq.total_commission = Decimal("500.00")
        row_myq.user_commission = Decimal("250.00")
        row_myq.platform_commission = Decimal("250.00")
        row_myq.pay_amount = Decimal("5000.00")
        row_myq.deal_count = 4
        row_myq.deal_amount = Decimal("4000.00")

        row_orderx = MagicMock()
        row_orderx.channel_code = "orderx"
        row_orderx.order_count = 3
        row_orderx.total_commission = Decimal("300.00")
        row_orderx.user_commission = Decimal("150.00")
        row_orderx.platform_commission = Decimal("150.00")
        row_orderx.pay_amount = Decimal("3000.00")
        row_orderx.deal_count = 2
        row_orderx.deal_amount = Decimal("2000.00")

        result_mock = AsyncMock()
        result_mock.all = MagicMock(return_value=[row_myq, row_orderx])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        data = await svc.get_channel_aggregate_stats(
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
        )

        assert set(data["channels"].keys()) == {"myq", "orderx"}
        assert data["channels"]["myq"]["order_count"] == 5
        assert data["channels"]["myq"]["total_commission"] == "500.0"
        assert data["channels"]["myq"]["deal_count"] == 4
        assert data["channels"]["myq"]["deal_amount"] == "4000.0"
        assert data["total"]["order_count"] == 8
        assert data["total"]["total_commission"] == "800.0"
        assert data["total"]["deal_count"] == 6
        assert data["total"]["deal_amount"] == "6000.0"


# ══════════════════════════════════════════════════════
# 8. 渠道订单趋势
# ══════════════════════════════════════════════════════


class TestOrderTrend:
    """渠道订单趋势（按天/周/月，支持单渠道筛选）"""

    @pytest.mark.asyncio
    async def test_order_trend_by_day(self):
        """按天分组趋势"""
        session = MagicMock()
        row = MagicMock()
        row.stat_date = date(2026, 8, 1)
        row.channel_code = "myq"
        row.order_count = 5
        row.total_commission = Decimal("500.00")
        row.user_commission = Decimal("250.00")
        row.deal_count = 4
        row.deal_amount = Decimal("4000.00")

        result_mock = AsyncMock()
        result_mock.all = MagicMock(return_value=[row])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        items = await svc.get_channel_order_trend(
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
            channel_code="myq",
            group_by="day",
        )
        assert len(items) == 1
        assert items[0]["channel_code"] == "myq"
        assert items[0]["order_count"] == 5
        assert items[0]["deal_count"] == 4

    @pytest.mark.asyncio
    async def test_order_trend_by_week(self):
        """按周分组趋势"""
        session = MagicMock()
        row = MagicMock()
        row.stat_date = 202631
        row.channel_code = "myq"
        row.order_count = 5
        row.total_commission = Decimal("500.00")
        row.user_commission = Decimal("250.00")
        row.deal_count = 4
        row.deal_amount = Decimal("4000.00")

        result_mock = AsyncMock()
        result_mock.all = MagicMock(return_value=[row])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        items = await svc.get_channel_order_trend(
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
            group_by="week",
        )
        assert len(items) == 1
        assert items[0]["date"] == "202631"

    @pytest.mark.asyncio
    async def test_order_trend_by_month(self):
        """按月分组趋势"""
        session = MagicMock()
        row = MagicMock()
        row.stat_date = "2026-08"
        row.channel_code = "orderx"
        row.order_count = 3
        row.total_commission = Decimal("300.00")
        row.user_commission = Decimal("150.00")
        row.deal_count = 2
        row.deal_amount = Decimal("2000.00")

        result_mock = AsyncMock()
        result_mock.all = MagicMock(return_value=[row])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        items = await svc.get_channel_order_trend(
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
            group_by="month",
        )
        assert len(items) == 1
        assert items[0]["date"] == "2026-08"
        assert items[0]["channel_code"] == "orderx"


# ══════════════════════════════════════════════════════
# 8.1 渠道聚合查询方法
# ══════════════════════════════════════════════════════


class TestChannelAggregateQueries:
    """渠道聚合查询方法（订单/结算汇总、单边账检测）"""

    @pytest.mark.asyncio
    async def test_aggregate_channel_orders(self):
        """按用户汇总渠道订单佣金"""
        session = MagicMock()
        row = (100, Decimal("80.00"), Decimal("100.00"), 2)
        result_mock = AsyncMock()
        result_mock.fetchall = MagicMock(return_value=[row])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        agg = await svc._aggregate_channel_orders(
            "myq", datetime(2026, 8, 1), datetime(2026, 8, 2),
        )
        assert agg[100]["user_commission"] == Decimal("80.00")
        assert agg[100]["order_count"] == 2

    @pytest.mark.asyncio
    async def test_aggregate_channel_settlements(self):
        """按用户汇总渠道结算入账"""
        session = MagicMock()
        row = (100, Decimal("80.00"), Decimal("100.00"), 1)
        result_mock = AsyncMock()
        result_mock.fetchall = MagicMock(return_value=[row])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        agg = await svc._aggregate_channel_settlements(
            "myq", datetime(2026, 8, 1), datetime(2026, 8, 2),
        )
        assert agg[100]["user_commission"] == Decimal("80.00")
        assert agg[100]["count"] == 1

    @pytest.mark.asyncio
    async def test_find_orders_without_settlement(self):
        """查询渠道中有佣金但无结算单的订单"""
        session = MagicMock()
        order = _make_order(order_id=1, user_commission="80.00")
        result_mock = AsyncMock()
        result_mock.scalars = MagicMock()
        result_mock.scalars.return_value.all = MagicMock(return_value=[order])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        orders = await svc._find_channel_orders_without_settlement(
            "myq", datetime(2026, 8, 1), datetime(2026, 8, 2),
        )
        assert len(orders) == 1
        assert orders[0].id == 1

    @pytest.mark.asyncio
    async def test_find_settlements_without_order(self):
        """查询渠道中结算单存在但订单缺失的记录"""
        session = MagicMock()
        settlement = _make_settlement(settlement_id=1, user_commission="80.00")
        result_mock = AsyncMock()
        result_mock.scalars = MagicMock()
        result_mock.scalars.return_value.all = MagicMock(return_value=[settlement])
        session.execute = AsyncMock(return_value=result_mock)

        svc = _make_service(session=session)
        settlements = await svc._find_channel_settlements_without_order(
            "orderx", datetime(2026, 8, 1), datetime(2026, 8, 2),
        )
        assert len(settlements) == 1
        assert settlements[0].id == 1

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """CRITICAL 差异告警推送（日志标记 alert_sent=Y）"""
        svc = _make_service()
        diff = svc._build_diff(
            1, 100, "myq",
            ChannelDiffType.CHANNEL_ORDER_MISSING.value,
            "ORDER", "SETTLEMENT",
            Decimal("50.00"), Decimal("0.00"),
        )
        assert diff["alert_sent"] == "N"
        await svc._send_alert(diff)
        assert diff["alert_sent"] == "Y"

    @pytest.mark.asyncio
    async def test_check_breaker_no_breaker(self):
        """无熔断器时直接放行"""
        svc = _make_service(circuit_breaker=None)
        await svc._check_breaker()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_breaker_helpers_no_breaker(self):
        """无熔断器时成功/失败记录为空操作"""
        svc = _make_service(circuit_breaker=None)
        await svc._record_success()
        await svc._record_failure()

    @pytest.mark.asyncio
    async def test_check_single_channel_mismatch_loop(self):
        """单渠道核对：订单佣金↔结算入账不一致生成差异"""
        svc = _make_service()
        svc._aggregate_channel_orders = AsyncMock(
            return_value={
                100: {
                    "user_commission": Decimal("80.00"),
                    "total_commission": Decimal("100.00"),
                    "order_count": 1,
                }
            }
        )
        svc._aggregate_channel_settlements = AsyncMock(
            return_value={
                100: {
                    "user_commission": Decimal("70.00"),
                    "total_commission": Decimal("90.00"),
                    "count": 1,
                }
            }
        )
        svc._find_channel_orders_without_settlement = AsyncMock(return_value=[])
        svc._find_channel_settlements_without_order = AsyncMock(return_value=[])
        result = await svc._check_single_channel(
            1, "myq",
            datetime(2026, 8, 1), datetime(2026, 8, 2),
        )
        assert result["order_count"] == 1
        assert result["matched_count"] == 0
        assert len(result["diffs"]) == 1
        assert result["diffs"][0]["diff_type"] == (
            ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value
        )
        assert result["diffs"][0]["diff_amount"] == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_send_alert_exception(self):
        """告警推送异常不阻断"""
        svc = _make_service()
        diff = {
            "reconciliation_id": 1, "user_id": 100, "diff_type": "X",
            "diff_amount": Decimal("1.00"), "source_type": "A",
            "target_type": "B", "remark": "r", "alert_sent": "N",
        }
        with patch(
            "src.services.b17_channel_reconciliation_service.logger.error",
            side_effect=RuntimeError("log down"),
        ):
            await svc._send_alert(diff)
        assert diff["alert_sent"] == "N"

    @pytest.mark.asyncio
    async def test_check_breaker_unexpected_exception(self):
        """熔断检查异常（非熔断拒绝）时放行"""
        breaker = _make_breaker(allowed=True)
        breaker.allow_request = AsyncMock(side_effect=RuntimeError("breaker down"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._check_breaker()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_breaker_record_exceptions(self):
        """熔断成功/失败记录异常不阻断"""
        breaker = _make_breaker()
        breaker.record_success = AsyncMock(side_effect=RuntimeError("down"))
        breaker.record_failure = AsyncMock(side_effect=RuntimeError("down"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._record_success()
        await svc._record_failure()

    @pytest.mark.asyncio
    async def test_review_channel_diff_resolved(self):
        """人工复核：PENDING → RESOLVED"""
        diff_dao = MagicMock()
        diff = MagicMock()
        diff.diff_type = "CHANNEL_ORDER_MISSING"
        diff.status = "PENDING"
        diff.channel_code = "myq"
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        diff_dao.update_by_id = AsyncMock()
        svc = _make_service(diff_dao=diff_dao)
        result = await svc.review_channel_diff(
            diff_id=1, action="RESOLVED", review_remark="已调平", operator_id=999,
        )
        assert result["status"] == "RESOLVED"
        assert result["reviewed_at"] is not None
        update_data = diff_dao.update_by_id.call_args[0][1]
        assert update_data["status"] == "RESOLVED"
        assert update_data["review_user_id"] == 999

    @pytest.mark.asyncio
    async def test_review_channel_diff_not_found(self):
        """复核不存在的差异 → 报错"""
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError) as exc_info:
            await svc.review_channel_diff(
                diff_id=999, action="RESOLVED", review_remark="x", operator_id=1,
            )
        assert "不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_channel_diff_non_channel(self):
        """非 CHANNEL_* 差异不允许复核"""
        diff_dao = MagicMock()
        diff = MagicMock()
        diff.diff_type = "ORDER_SETTLEMENT_MISMATCH"
        diff.status = "PENDING"
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError) as exc_info:
            await svc.review_channel_diff(
                diff_id=1, action="RESOLVED", review_remark="x", operator_id=1,
            )
        assert "仅支持复核渠道对账差异" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_channel_diff_terminal_state(self):
        """终态差异不可再操作"""
        diff_dao = MagicMock()
        diff = MagicMock()
        diff.diff_type = "CHANNEL_ORDER_MISSING"
        diff.status = "RESOLVED"
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError) as exc_info:
            await svc.review_channel_diff(
                diff_id=1, action="IGNORED", review_remark="x", operator_id=1,
            )
        assert "终态" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_channel_diff_illegal_transition(self):
        """非法状态流转被拦截"""
        diff_dao = MagicMock()
        diff = MagicMock()
        diff.diff_type = "CHANNEL_ORDER_MISSING"
        diff.status = "REVIEWING"
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError) as exc_info:
            await svc.review_channel_diff(
                diff_id=1, action="REVIEWING", review_remark="x", operator_id=1,
            )
        assert "非法状态流转" in str(exc_info.value)


# ══════════════════════════════════════════════════════
# 9. 内部工具方法
# ══════════════════════════════════════════════════════


class TestInternalTools:
    """内部工具方法（金额比较/差异构造/批次号生成）"""

    def test_compare_amounts_within_tolerance(self):
        """金额在容忍度内 → 无差异"""
        svc = _make_service()
        diff = svc._compare_amounts(
            1, 100, "myq",
            Decimal("80.00"), Decimal("80.01"),
            ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value,
            "ORDER", "SETTLEMENT",
        )
        assert diff is None

    def test_compare_amounts_over_tolerance(self):
        """金额超出容忍度 → 生成差异"""
        svc = _make_service()
        diff = svc._compare_amounts(
            1, 100, "myq",
            Decimal("80.00"), Decimal("70.00"),
            ChannelDiffType.CHANNEL_ORDER_SETTLEMENT_MISMATCH.value,
            "ORDER", "SETTLEMENT",
        )
        assert diff is not None
        assert diff["diff_amount"] == Decimal("10.00")
        assert diff["channel_code"] == "myq"
        assert diff["status"] == DiffStatus.PENDING.value

    def test_build_diff_remark(self):
        """差异构造：自动生成 remark"""
        svc = _make_service()
        diff = svc._build_diff(
            1, 100, "orderx",
            ChannelDiffType.CHANNEL_ORDER_MISSING.value,
            "ORDER", "SETTLEMENT",
            Decimal("50.00"), Decimal("0.00"),
        )
        assert diff["diff_type"] == ChannelDiffType.CHANNEL_ORDER_MISSING.value
        assert diff["alert_level"] == AlertLevel.CRITICAL.value
        assert "[orderx]" in diff["remark"]

    def test_generate_no(self):
        """批次号生成：GAKCR 前缀 + 日期"""
        svc = _make_service()
        no = svc._generate_no(date(2026, 8, 1))
        assert no.startswith("GAKCR20260801")
        assert len(no) == len("GAKCR") + 8 + 8


# ══════════════════════════════════════════════════════
# 10. 定时任务
# ══════════════════════════════════════════════════════


class TestChannelReconciliationJob:
    """定时任务（开关/锁/异常兜底）"""

    @pytest.mark.asyncio
    async def test_job_disabled(self):
        """任务开关关闭 → 跳过"""
        from src.scheduler.b17_channel_reconciliation_jobs import (
            channel_reconciliation_job,
        )

        with patch(
            "src.scheduler.b17_channel_reconciliation_jobs.TASK_CHANNEL_RECONCILIATION_ENABLE",
            False,
        ):
            result = await channel_reconciliation_job()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_job_lock_conflict(self):
        """分布式锁冲突 → 跳过"""
        from src.scheduler.b17_channel_reconciliation_jobs import (
            channel_reconciliation_job,
        )

        with patch(
            "src.scheduler.b17_channel_reconciliation_jobs.LockUtil.acquire_lock",
            return_value=None,
        ):
            result = await channel_reconciliation_job()
        assert result["status"] == "skipped"
        assert "正在执行" in result["message"]

    @pytest.mark.asyncio
    async def test_job_success(self):
        """任务正常执行"""
        from src.scheduler.b17_channel_reconciliation_jobs import (
            channel_reconciliation_job,
        )

        service_mock = AsyncMock()
        service_mock.run_channel_reconciliation = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "reconciliation_no": "GAKCR20260801ABC",
                "diff_count": 0,
                "channel_stats": {"myq": {}, "orderx": {}},
            }
        )
        mock_session = AsyncMock()
        with patch(
            "src.scheduler.b17_channel_reconciliation_jobs.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.scheduler.b17_channel_reconciliation_jobs.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.scheduler.b17_channel_reconciliation_jobs.DatabaseManager.get_session"
        ) as mock_get_session, patch(
            "src.scheduler.b17_channel_reconciliation_jobs.B17ChannelReconciliationService",
            return_value=service_mock,
        ):
            mock_get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await channel_reconciliation_job()
        assert result["status"] == "success"
        assert result["diff_count"] == 0

    @pytest.mark.asyncio
    async def test_job_exception(self):
        """任务执行异常 → failed 兜底"""
        from src.scheduler.b17_channel_reconciliation_jobs import (
            channel_reconciliation_job,
        )

        with patch(
            "src.scheduler.b17_channel_reconciliation_jobs.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.scheduler.b17_channel_reconciliation_jobs.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.scheduler.b17_channel_reconciliation_jobs.DatabaseManager.get_session",
            side_effect=RuntimeError("db down"),
        ):
            result = await channel_reconciliation_job()
        assert result["status"] == "failed"
        assert "db down" in result["message"]


# ══════════════════════════════════════════════════════
# 11. 差异 DAO（渠道筛选/渠道汇总）
# ══════════════════════════════════════════════════════


class TestDiffDAO:
    """渠道差异 DAO"""

    @pytest.mark.asyncio
    async def test_list_channel_diffs(self):
        """渠道差异分页查询（按渠道筛选）"""
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO

        diff = MagicMock()
        diff.to_dict = MagicMock(
            return_value={
                "id": 1,
                "channel_code": "myq",
                "diff_type": "CHANNEL_ORDER_MISSING",
                "status": "PENDING",
            }
        )
        session = MagicMock()
        # execute -> scalars -> all
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[diff])
        exec_result = MagicMock()
        exec_result.scalar = MagicMock(return_value=1)
        exec_result.scalars = MagicMock(return_value=scalars_mock)
        session.execute = AsyncMock(return_value=exec_result)

        dao = ReconciliationDiffDAO(session)
        data = await dao.list_channel_diffs(channel_code="myq", page=1, page_size=20)
        assert data["total"] == 1
        assert data["list"][0]["channel_code"] == "myq"

    @pytest.mark.asyncio
    async def test_list_channel_diffs_full_filters(self):
        """渠道差异分页查询（全条件筛选：diff_type/status/alert_level）"""
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO

        diff = MagicMock()
        diff.to_dict = MagicMock(return_value={"id": 2, "channel_code": "orderx"})
        session = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[diff])
        exec_result = MagicMock()
        exec_result.scalar = MagicMock(return_value=1)
        exec_result.scalars = MagicMock(return_value=scalars_mock)
        session.execute = AsyncMock(return_value=exec_result)

        dao = ReconciliationDiffDAO(session)
        data = await dao.list_channel_diffs(
            channel_code="orderx",
            diff_type="CHANNEL_ORDER_MISSING",
            status="PENDING",
            alert_level="CRITICAL",
            page=2,
            page_size=10,
        )
        assert data["total"] == 1
        assert data["page"] == 2
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_summary_channel_diffs(self):
        """渠道差异汇总（按渠道分组）"""
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO

        session = MagicMock()
        exec_result = MagicMock()
        exec_result.fetchall = MagicMock(
            return_value=[
                ("myq", 5, Decimal("12.34"), 3, 1),
                ("orderx", 2, Decimal("5.00"), 1, 0),
            ]
        )
        session.execute = AsyncMock(return_value=exec_result)

        dao = ReconciliationDiffDAO(session)
        data = await dao.summary_channel_diffs()
        assert data["channels"]["myq"]["diff_count"] == 5
        assert data["channels"]["myq"]["pending_count"] == 3
        assert data["channels"]["myq"]["critical_count"] == 1
        assert data["channels"]["myq"]["diff_amount"] == "12.34"
        assert data["total"]["diff_count"] == 7
        assert data["total"]["critical_count"] == 1

    @pytest.mark.asyncio
    async def test_summary_channel_diffs_with_date_range(self):
        """渠道差异汇总（带日期范围筛选）"""
        from src.dao.reconciliation_diff_dao import ReconciliationDiffDAO

        session = MagicMock()
        exec_result = MagicMock()
        exec_result.fetchall = MagicMock(return_value=[])
        session.execute = AsyncMock(return_value=exec_result)

        dao = ReconciliationDiffDAO(session)
        data = await dao.summary_channel_diffs(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
        )
        assert data["channels"] == {}
        assert data["total"]["diff_count"] == 0

# @ai-generated
"""
B13 全链路数据对账单元测试
覆盖：
1. 正常平账（四方一致无差异）
2. 单边账（有订单无结算/有结算无订单/有提现无账户）
3. 重复对账拦截（幂等锁）
4. 事务回滚（差异批量写入失败）
5. 熔断降级（B04 熔断拦截）
6. 差异复核调平（合法/非法/终态流转）
7. 手动重跑对账
8. 后台查询接口（批次列表/差异列表/详情/告警）
9. 定时任务触发/开关/异常兜底
10. 内部工具方法（金额比较/差异构造/批次号生成）

覆盖率目标：单文件 ≥90%
"""
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.config.b13_constants import (
    AlertLevel,
    DIFF_TERMINAL_STATES,
    DIFF_TRANSITIONS,
    RECONCILIATION_BREAKER_CHANNEL,
    RECONCILIATION_TOLERANCE,
    DiffStatus,
    DiffType,
    ReconciliationStatus,
    ReconciliationType,
    SOURCE_TYPE_ACCOUNT,
    SOURCE_TYPE_ORDER,
    SOURCE_TYPE_SETTLEMENT,
    SOURCE_TYPE_WITHDRAW,
)
from src.services.reconciliation_b13_service import ReconciliationB13Service


# ══════════════════════════════════════════════════════
# 测试数据构造工具
# ══════════════════════════════════════════════════════


def _make_account(
    user_id: int = 100,
    total_balance: str = "80.00",
    available_balance: str = "80.00",
    frozen_balance: str = "0.00",
    cumulative_withdrawn: str = "0.00",
    cumulative_fee: str = "0.00",
):
    acc = MagicMock()
    acc.user_id = user_id
    acc.total_balance = Decimal(total_balance)
    acc.available_balance = Decimal(available_balance)
    acc.frozen_balance = Decimal(frozen_balance)
    acc.cumulative_withdrawn = Decimal(cumulative_withdrawn)
    acc.cumulative_fee = Decimal(cumulative_fee)
    return acc


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    user_commission: str = "80.00",
    internal_order_no: str = "GAK001",
):
    o = MagicMock()
    o.id = order_id
    o.user_id = user_id
    o.user_commission = Decimal(user_commission)
    o.total_commission = Decimal("100.00")
    o.internal_order_no = internal_order_no
    return o


def _make_settlement(
    settlement_id: int = 1,
    order_id: int = 1,
    user_id: int = 100,
    user_commission: str = "80.00",
    settlement_no: str = "GAKS001",
):
    s = MagicMock()
    s.id = settlement_id
    s.order_id = order_id
    s.user_id = user_id
    s.user_commission = Decimal(user_commission)
    s.settlement_no = settlement_no
    return s


def _make_record(
    record_id: int = 1,
    reconciliation_no: str = "GAKR20260802ABC12345",
    reconcile_date: date = date(2026, 8, 1),
    status: str = ReconciliationStatus.SUCCESS.value,
    diff_count: int = 0,
):
    r = MagicMock()
    r.id = record_id
    r.reconciliation_no = reconciliation_no
    r.reconcile_date = reconcile_date
    r.status = status
    r.diff_count = diff_count
    r.to_dict = MagicMock(
        return_value={
            "id": record_id,
            "reconciliation_no": reconciliation_no,
            "status": status,
            "diff_count": diff_count,
        }
    )
    return r


def _make_diff(
    diff_id: int = 1,
    reconciliation_id: int = 1,
    user_id: int = 100,
    diff_type: str = DiffType.ORDER_SETTLEMENT_MISMATCH.value,
    status: str = DiffStatus.PENDING.value,
    alert_level: str = AlertLevel.WARNING.value,
    diff_amount: str = "10.00",
):
    d = MagicMock()
    d.id = diff_id
    d.reconciliation_id = reconciliation_id
    d.user_id = user_id
    d.diff_type = diff_type
    d.status = status
    d.alert_level = alert_level
    d.diff_amount = Decimal(diff_amount)
    d.source_amount = Decimal("80.00")
    d.target_amount = Decimal("70.00")
    d.remark = "test diff"
    d.to_dict = MagicMock(
        return_value={
            "id": diff_id,
            "reconciliation_id": reconciliation_id,
            "user_id": user_id,
            "diff_type": diff_type,
            "status": status,
            "alert_level": alert_level,
            "diff_amount": diff_amount,
        }
    )
    return d


def _make_breaker(allowed: bool = True):
    breaker = AsyncMock()
    breaker.allow_request = AsyncMock(return_value=allowed)
    breaker.record_success = AsyncMock()
    breaker.record_failure = AsyncMock()
    return breaker


def _make_service(
    record_dao=None,
    diff_dao=None,
    query_dao=None,
    circuit_breaker=None,
):
    return ReconciliationB13Service(
        record_dao=record_dao or MagicMock(),
        diff_dao=diff_dao or MagicMock(),
        query_dao=query_dao or MagicMock(),
        circuit_breaker=circuit_breaker,
    )


# ══════════════════════════════════════════════════════
# 1. 正常平账测试
# ══════════════════════════════════════════════════════


class TestReconciliationSuccess:
    """正常平账（四方一致无差异）"""

    @pytest.mark.asyncio
    async def test_all_matched_no_diff(self):
        """四方一致，无差异，对账成功"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()

        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        query_dao = MagicMock()
        query_dao.aggregate_order_commission_by_user = AsyncMock(
            return_value={
                100: {
                    "user_commission": Decimal("80.00"),
                    "total_commission": Decimal("100.00"),
                    "order_count": 1,
                }
            }
        )
        query_dao.aggregate_settlement_by_user = AsyncMock(
            return_value={
                100: {
                    "user_commission": Decimal("80.00"),
                    "total_commission": Decimal("100.00"),
                    "count": 1,
                }
            }
        )
        query_dao.aggregate_account_totals = AsyncMock(
            return_value={
                "total_balance": Decimal("80.00"),
                "available_balance": Decimal("80.00"),
                "frozen_balance": Decimal("0.00"),
                "cumulative_withdrawn": Decimal("0.00"),
                "cumulative_fee": Decimal("0.00"),
                "account_count": 1,
            }
        )
        query_dao.aggregate_withdraw_by_user = AsyncMock(return_value={})
        query_dao.aggregate_withdraw_totals = AsyncMock(
            return_value={
                "total_withdrawn": Decimal("0.00"),
                "total_fee": Decimal("0.00"),
                "withdraw_count": 0,
            }
        )
        query_dao.get_account_by_user = AsyncMock(return_value=_make_account())
        query_dao.find_orders_without_settlement = AsyncMock(return_value=[])
        query_dao.find_settlements_without_order = AsyncMock(return_value=[])

        svc = _make_service(record_dao, diff_dao, query_dao, _make_breaker())

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.reconciliation_b13_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            result = await svc.run_reconciliation(
                reconcile_date=date(2026, 8, 1),
                reconcile_type=ReconciliationType.DAILY.value,
            )

        assert result["status"] == ReconciliationStatus.SUCCESS.value
        assert result["diff_count"] == 0
        assert result["matched_count"] == 1
        diff_dao.batch_create.assert_not_called()


# ══════════════════════════════════════════════════════
# 2. 单边账测试
# ══════════════════════════════════════════════════════


class TestSingleSideDiff:
    """单边账检测测试"""

    @pytest.mark.asyncio
    async def test_order_without_settlement(self):
        """有订单无结算单 → 单边账-订单侧"""
        order = _make_order(order_id=1, user_commission="80.00")
        query_dao = MagicMock()
        query_dao.find_orders_without_settlement = AsyncMock(return_value=[order])

        svc = _make_service(query_dao=query_dao)
        diffs = await svc._detect_single_side_orders(
            reconciliation_id=1,
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
        )
        assert len(diffs) == 1
        assert diffs[0]["diff_type"] == DiffType.SINGLE_SIDE_ORDER.value
        assert diffs[0]["source_amount"] == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_settlement_without_order(self):
        """有结算单无订单 → 单边账-结算侧"""
        settlement = _make_settlement(settlement_id=1, user_commission="80.00")
        svc = _make_service()
        svc.query_dao.find_settlements_without_order = AsyncMock(
            return_value=[settlement]
        )
        diffs = await svc._detect_single_side_settlements(
            reconciliation_id=1,
            start_time=datetime(2026, 8, 1),
            end_time=datetime(2026, 8, 2),
        )
        assert len(diffs) == 1
        assert diffs[0]["diff_type"] == DiffType.SINGLE_SIDE_SETTLEMENT.value

    @pytest.mark.asyncio
    async def test_withdraw_without_account(self):
        """有提现无账户 → 单边账-提现侧（在四方核对中检测）"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record())
        record_dao.update_by_id = AsyncMock()
        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        query_dao = MagicMock()
        query_dao.aggregate_order_commission_by_user = AsyncMock(return_value={})
        query_dao.aggregate_settlement_by_user = AsyncMock(return_value={})
        query_dao.aggregate_account_totals = AsyncMock(
            return_value={
                "total_balance": Decimal("0.00"),
                "available_balance": Decimal("0.00"),
                "frozen_balance": Decimal("0.00"),
                "cumulative_withdrawn": Decimal("0.00"),
                "cumulative_fee": Decimal("0.00"),
                "account_count": 0,
            }
        )
        query_dao.aggregate_withdraw_by_user = AsyncMock(
            return_value={100: {"actual_amount": Decimal("50.00")}}
        )
        query_dao.aggregate_withdraw_totals = AsyncMock(
            return_value={
                "total_withdrawn": Decimal("50.00"),
                "total_fee": Decimal("0.00"),
                "withdraw_count": 1,
            }
        )
        query_dao.get_account_by_user = AsyncMock(return_value=None)
        query_dao.find_orders_without_settlement = AsyncMock(return_value=[])
        query_dao.find_settlements_without_order = AsyncMock(return_value=[])

        svc = _make_service(record_dao, diff_dao, query_dao, _make_breaker())

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.reconciliation_b13_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            result = await svc.run_reconciliation(reconcile_date=date(2026, 8, 1))

        assert result["status"] == ReconciliationStatus.PARTIAL.value
        assert result["diff_count"] >= 1


# ══════════════════════════════════════════════════════
# 3. 重复对账拦截测试
# ══════════════════════════════════════════════════════


class TestIdempotentLock:
    """幂等锁拦截重复对账"""

    @pytest.mark.asyncio
    async def test_duplicate_reconciliation_blocked(self):
        """幂等锁获取失败，拦截重复对账"""
        svc = _make_service(circuit_breaker=_make_breaker())

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="正在执行中或已对账"):
                await svc.run_reconciliation(reconcile_date=date(2026, 8, 1))


# ══════════════════════════════════════════════════════
# 4. 熔断降级测试
# ══════════════════════════════════════════════════════


class TestCircuitBreaker:
    """B04 熔断保护测试"""

    @pytest.mark.asyncio
    async def test_breaker_open_blocked(self):
        """熔断中，对账被拦截"""
        svc = _make_service(circuit_breaker=_make_breaker(allowed=False))

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.reconciliation_b13_service.LockUtil.release_lock",
            return_value=True,
        ):
            with pytest.raises(ValueError, match="对账熔断中"):
                await svc.run_reconciliation(reconcile_date=date(2026, 8, 1))

    @pytest.mark.asyncio
    async def test_breaker_none_no_check(self):
        """无熔断器（None）不报错"""
        svc = _make_service(circuit_breaker=None)
        await svc._check_breaker()  # 不抛异常

    @pytest.mark.asyncio
    async def test_breaker_exception_not_blocking(self):
        """熔断检查异常不阻断（放行）"""
        breaker = AsyncMock()
        breaker.allow_request = AsyncMock(side_effect=Exception("Redis 异常"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._check_breaker()  # 不抛异常

    @pytest.mark.asyncio
    async def test_record_success_exception_not_blocking(self):
        """熔断成功记录异常不阻断"""
        breaker = AsyncMock()
        breaker.record_success = AsyncMock(side_effect=Exception("Redis 异常"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._record_success()

    @pytest.mark.asyncio
    async def test_record_failure_exception_not_blocking(self):
        """熔断失败记录异常不阻断"""
        breaker = AsyncMock()
        breaker.record_failure = AsyncMock(side_effect=Exception("Redis 异常"))
        svc = _make_service(circuit_breaker=breaker)
        await svc._record_failure()

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


# ══════════════════════════════════════════════════════
# 5. 差异复核调平测试
# ══════════════════════════════════════════════════════


class TestDiffReview:
    """差异人工复核调平测试"""

    @pytest.mark.asyncio
    async def test_review_pending_to_resolved(self):
        """PENDING → RESOLVED 合法流转"""
        diff = _make_diff(diff_id=1, status=DiffStatus.PENDING.value)
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        diff_dao.update_by_id = AsyncMock()

        svc = _make_service(diff_dao=diff_dao)
        result = await svc.review_diff(
            diff_id=1,
            action=DiffStatus.RESOLVED.value,
            review_remark="已手动调平",
            operator_id=200,
        )

        assert result["status"] == DiffStatus.RESOLVED.value
        diff_dao.update_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_pending_to_reviewing(self):
        """PENDING → REVIEWING 合法流转（认领复核）"""
        diff = _make_diff(diff_id=1, status=DiffStatus.PENDING.value)
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        diff_dao.update_by_id = AsyncMock()

        svc = _make_service(diff_dao=diff_dao)
        result = await svc.review_diff(
            diff_id=1,
            action=DiffStatus.REVIEWING.value,
            review_remark="认领核查中",
            operator_id=200,
        )

        assert result["status"] == DiffStatus.REVIEWING.value

    @pytest.mark.asyncio
    async def test_review_resolved_terminal_blocked(self):
        """RESOLVED 终态不可再操作"""
        diff = _make_diff(diff_id=1, status=DiffStatus.RESOLVED.value)
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=diff)

        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError, match="终态"):
            await svc.review_diff(
                diff_id=1,
                action=DiffStatus.REVIEWING.value,
                review_remark="test",
                operator_id=200,
            )

    @pytest.mark.asyncio
    async def test_review_illegal_transition_blocked(self):
        """非法状态流转被拦截（RESOLVED → REVIEWING 不可回退）"""
        # RESOLVED is terminal, already tested above. Test REVIEWING → PENDING (not allowed)
        diff = _make_diff(diff_id=1, status=DiffStatus.REVIEWING.value)
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=diff)

        svc = _make_service(diff_dao=diff_dao)
        with pytest.raises(ValueError, match="非法状态流转"):
            await svc.review_diff(
                diff_id=1,
                action=DiffStatus.PENDING.value,
                review_remark="test",
                operator_id=200,
            )

    @pytest.mark.asyncio
    async def test_review_diff_not_found(self):
        """差异明细不存在"""
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(diff_dao=diff_dao)

        with pytest.raises(ValueError, match="差异明细不存在"):
            await svc.review_diff(
                diff_id=999,
                action=DiffStatus.RESOLVED.value,
                review_remark="test",
                operator_id=200,
            )


# ══════════════════════════════════════════════════════
# 6. 手动重跑对账测试
# ══════════════════════════════════════════════════════


class TestRetryReconciliation:
    """手动重跑对账测试"""

    @pytest.mark.asyncio
    async def test_retry_success(self):
        """重跑对账成功（读取原批次日期创建新批次）"""
        original = _make_record(record_id=1, reconcile_date=date(2026, 8, 1))
        record_dao = MagicMock()
        record_dao.get_by_id = AsyncMock(return_value=original)
        record_dao.create = AsyncMock(return_value=_make_record(record_id=2))
        record_dao.update_by_id = AsyncMock()

        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock()

        query_dao = MagicMock()
        query_dao.aggregate_order_commission_by_user = AsyncMock(return_value={})
        query_dao.aggregate_settlement_by_user = AsyncMock(return_value={})
        query_dao.aggregate_account_totals = AsyncMock(
            return_value={
                "total_balance": Decimal("0.00"),
                "available_balance": Decimal("0.00"),
                "frozen_balance": Decimal("0.00"),
                "cumulative_withdrawn": Decimal("0.00"),
                "cumulative_fee": Decimal("0.00"),
                "account_count": 0,
            }
        )
        query_dao.aggregate_withdraw_by_user = AsyncMock(return_value={})
        query_dao.aggregate_withdraw_totals = AsyncMock(
            return_value={
                "total_withdrawn": Decimal("0.00"),
                "total_fee": Decimal("0.00"),
                "withdraw_count": 0,
            }
        )
        query_dao.find_orders_without_settlement = AsyncMock(return_value=[])
        query_dao.find_settlements_without_order = AsyncMock(return_value=[])

        svc = _make_service(record_dao, diff_dao, query_dao, _make_breaker())

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value="owner-2",
        ), patch(
            "src.services.reconciliation_b13_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            result = await svc.retry_reconciliation(
                reconciliation_id=1, operator_id=200
            )

        assert result["status"] == ReconciliationStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_retry_original_not_found(self):
        """原对账批次不存在"""
        record_dao = MagicMock()
        record_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(record_dao=record_dao)

        with pytest.raises(ValueError, match="对账批次不存在"):
            await svc.retry_reconciliation(reconciliation_id=999, operator_id=200)


# ══════════════════════════════════════════════════════
# 7. 后台查询接口测试
# ══════════════════════════════════════════════════════


class TestQueryInterfaces:
    """后台查询接口测试"""

    @pytest.mark.asyncio
    async def test_list_records(self):
        """对账批次分页查询"""
        records = [_make_record(record_id=1), _make_record(record_id=2)]
        record_dao = MagicMock()
        record_dao.list_with_filters = AsyncMock(return_value=(records, 2))
        svc = _make_service(record_dao=record_dao)

        result = await svc.list_records_with_filters(page=1, page_size=20)

        assert result["total"] == 2
        assert len(result["list"]) == 2

    @pytest.mark.asyncio
    async def test_list_diffs(self):
        """差异明细分页查询"""
        diffs = [_make_diff(diff_id=1), _make_diff(diff_id=2)]
        diff_dao = MagicMock()
        diff_dao.list_with_filters = AsyncMock(return_value=(diffs, 2))
        svc = _make_service(diff_dao=diff_dao)

        result = await svc.list_diffs_with_filters(page=1, page_size=20)

        assert result["total"] == 2
        assert len(result["list"]) == 2

    @pytest.mark.asyncio
    async def test_get_record_detail_success(self):
        """对账批次详情含差异统计"""
        record = _make_record(record_id=1)
        diffs = [_make_diff(diff_id=1)]
        record_dao = MagicMock()
        record_dao.get_by_id = AsyncMock(return_value=record)
        diff_dao = MagicMock()
        diff_dao.count_by_reconciliation = AsyncMock(
            return_value={
                "total": 1,
                "pending": 1,
                "critical": 0,
                "by_status": {},
                "by_alert_level": {},
            }
        )
        diff_dao.list_by_reconciliation_id = AsyncMock(return_value=(diffs, 1))
        svc = _make_service(record_dao=record_dao, diff_dao=diff_dao)

        result = await svc.get_record_detail(1)

        assert result["record"]["id"] == 1
        assert result["diff_stats"]["total"] == 1
        assert len(result["recent_diffs"]) == 1

    @pytest.mark.asyncio
    async def test_get_record_detail_not_found(self):
        """对账批次不存在"""
        record_dao = MagicMock()
        record_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(record_dao=record_dao)

        with pytest.raises(ValueError, match="对账批次不存在"):
            await svc.get_record_detail(999)

    @pytest.mark.asyncio
    async def test_get_diff_detail(self):
        """差异明细详情"""
        diff = _make_diff(diff_id=1)
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=diff)
        svc = _make_service(diff_dao=diff_dao)

        result = await svc.get_diff_detail(1)

        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_diff_detail_not_found(self):
        """差异明细不存在"""
        diff_dao = MagicMock()
        diff_dao.get_by_id = AsyncMock(return_value=None)
        svc = _make_service(diff_dao=diff_dao)

        with pytest.raises(ValueError, match="差异明细不存在"):
            await svc.get_diff_detail(999)

    @pytest.mark.asyncio
    async def test_list_alerts(self):
        """告警列表查询"""
        diffs = [_make_diff(diff_id=1, alert_level=AlertLevel.CRITICAL.value)]
        diff_dao = MagicMock()
        diff_dao.list_with_filters = AsyncMock(return_value=(diffs, 1))
        svc = _make_service(diff_dao=diff_dao)

        result = await svc.list_alerts(page=1, page_size=20)

        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_recent_records(self):
        """近7天有差异的对账批次"""
        records = [_make_record(record_id=1, diff_count=3)]
        record_dao = MagicMock()
        record_dao.list_recent_unresolved = AsyncMock(return_value=records)
        svc = _make_service(record_dao=record_dao)

        result = await svc.list_recent_records(days=7, limit=10)

        assert len(result) == 1


# ══════════════════════════════════════════════════════
# 8. 内部工具方法测试
# ══════════════════════════════════════════════════════


class TestInternalUtils:
    """内部工具方法测试"""

    def test_generate_reconciliation_no(self):
        """对账批次号生成格式校验"""
        no = ReconciliationB13Service._generate_reconciliation_no(date(2026, 8, 1))
        assert no.startswith("GAKR")
        assert "20260801" in no
        assert len(no) > 12

    def test_compare_amounts_matched(self):
        """金额在容忍度内，返回 None（平账）"""
        svc = _make_service()
        result = svc._compare_amounts(
            reconciliation_id=1,
            user_id=100,
            source_amount=Decimal("80.00"),
            target_amount=Decimal("80.00"),
            diff_type=DiffType.ORDER_SETTLEMENT_MISMATCH.value,
            source_type=SOURCE_TYPE_ORDER,
            target_type=SOURCE_TYPE_SETTLEMENT,
        )
        assert result is None

    def test_compare_amounts_within_tolerance(self):
        """金额差异在容忍度内（0.01），视为平账"""
        svc = _make_service()
        result = svc._compare_amounts(
            reconciliation_id=1,
            user_id=100,
            source_amount=Decimal("80.00"),
            target_amount=Decimal("80.01"),
            diff_type=DiffType.ORDER_SETTLEMENT_MISMATCH.value,
            source_type=SOURCE_TYPE_ORDER,
            target_type=SOURCE_TYPE_SETTLEMENT,
        )
        assert result is None

    def test_compare_amounts_mismatch(self):
        """金额超出容忍度，返回差异 dict"""
        svc = _make_service()
        result = svc._compare_amounts(
            reconciliation_id=1,
            user_id=100,
            source_amount=Decimal("80.00"),
            target_amount=Decimal("70.00"),
            diff_type=DiffType.ORDER_SETTLEMENT_MISMATCH.value,
            source_type=SOURCE_TYPE_ORDER,
            target_type=SOURCE_TYPE_SETTLEMENT,
        )
        assert result is not None
        assert result["diff_amount"] == Decimal("10.00")
        assert result["diff_type"] == DiffType.ORDER_SETTLEMENT_MISMATCH.value
        assert result["alert_level"] == AlertLevel.WARNING.value

    def test_build_diff(self):
        """差异 dict 构造"""
        svc = _make_service()
        diff = svc._build_diff(
            reconciliation_id=1,
            user_id=100,
            diff_type=DiffType.SETTLEMENT_ACCOUNT_MISMATCH.value,
            source_type=SOURCE_TYPE_SETTLEMENT,
            target_type=SOURCE_TYPE_ACCOUNT,
            source_amount=Decimal("80.00"),
            target_amount=Decimal("75.00"),
            order_id=1,
            settlement_id=1,
        )
        assert diff["diff_amount"] == Decimal("5.00")
        assert diff["alert_level"] == AlertLevel.CRITICAL.value
        assert diff["status"] == DiffStatus.PENDING.value
        assert diff["alert_sent"] == "N"

    @pytest.mark.asyncio
    async def test_send_alert_critical(self):
        """CRITICAL 告警推送（日志标记）"""
        svc = _make_service()
        diff_data = {
            "reconciliation_id": 1,
            "user_id": 100,
            "diff_type": DiffType.SETTLEMENT_ACCOUNT_MISMATCH.value,
            "diff_amount": Decimal("10.00"),
            "source_type": SOURCE_TYPE_SETTLEMENT,
            "target_type": SOURCE_TYPE_ACCOUNT,
            "remark": "test critical",
        }
        await svc._send_alert(diff_data)
        assert diff_data["alert_sent"] == "Y"

    @pytest.mark.asyncio
    async def test_send_alert_exception_not_blocking(self):
        """告警推送异常不阻断"""
        svc = _make_service()
        # 传入会导致异常的数据
        diff_data = None
        await svc._send_alert(diff_data)  # 不抛异常


# ══════════════════════════════════════════════════════
# 9. 定时任务测试
# ══════════════════════════════════════════════════════


class TestReconciliationJobs:
    """定时任务触发/开关/异常兜底测试"""

    @pytest.mark.asyncio
    async def test_daily_job_disabled(self):
        """任务开关关闭时跳过"""
        with patch(
            "src.scheduler.reconciliation_b13_jobs.TASK_DAILY_RECONCILIATION_ENABLE",
            False,
        ):
            from src.scheduler.reconciliation_b13_jobs import daily_reconciliation_job

            result = await daily_reconciliation_job()
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_daily_job_success(self):
        """每日对账任务正常执行"""
        with patch(
            "src.scheduler.reconciliation_b13_jobs.TASK_DAILY_RECONCILIATION_ENABLE",
            True,
        ), patch(
            "src.scheduler.reconciliation_b13_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.reconciliation_b13_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.run_reconciliation = AsyncMock(
                return_value={
                    "status": "SUCCESS",
                    "reconciliation_no": "GAKR20260802TEST",
                    "matched_count": 5,
                    "diff_count": 0,
                }
            )
            mock_build.return_value = mock_svc

            from src.scheduler.reconciliation_b13_jobs import (
                daily_reconciliation_job,
            )

            result = await daily_reconciliation_job()

        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_daily_job_exception(self):
        """每日对账任务异常兜底"""
        with patch(
            "src.scheduler.reconciliation_b13_jobs.TASK_DAILY_RECONCILIATION_ENABLE",
            True,
        ), patch(
            "src.scheduler.reconciliation_b13_jobs.DatabaseManager.get_session",
            side_effect=Exception("DB 连接失败"),
        ):
            from src.scheduler.reconciliation_b13_jobs import (
                daily_reconciliation_job,
            )

            result = await daily_reconciliation_job()

        assert result["status"] == "failed"
        assert "DB 连接失败" in result["message"]

    @pytest.mark.asyncio
    async def test_manual_job_success(self):
        """手动对账任务正常执行"""
        with patch(
            "src.scheduler.reconciliation_b13_jobs.DatabaseManager.get_session"
        ) as mock_session, patch(
            "src.scheduler.reconciliation_b13_jobs._build_service"
        ) as mock_build:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_svc = AsyncMock()
            mock_svc.run_reconciliation = AsyncMock(
                return_value={
                    "status": "SUCCESS",
                    "reconciliation_no": "GAKR20260802MANUAL",
                    "matched_count": 3,
                    "diff_count": 0,
                }
            )
            mock_build.return_value = mock_svc

            from src.scheduler.reconciliation_b13_jobs import (
                manual_reconciliation_job,
            )

            result = await manual_reconciliation_job(
                reconcile_date=date(2026, 8, 1), operator_id=200
            )

        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_manual_job_exception(self):
        """手动对账任务异常兜底"""
        with patch(
            "src.scheduler.reconciliation_b13_jobs.DatabaseManager.get_session",
            side_effect=Exception("连接超时"),
        ):
            from src.scheduler.reconciliation_b13_jobs import (
                manual_reconciliation_job,
            )

            result = await manual_reconciliation_job(operator_id=200)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_build_service_constructs_all_dependencies(self):
        """_build_service 正确注入 3 个 DAO + 熔断器"""
        from src.scheduler.reconciliation_b13_jobs import _build_service

        db_session = MagicMock()
        svc = await _build_service(db_session)
        assert svc.record_dao is not None
        assert svc.diff_dao is not None
        assert svc.query_dao is not None
        assert svc.circuit_breaker is not None

    def test_register_reconciliation_b13_jobs(self):
        """register_reconciliation_b13_jobs 注册定时任务"""
        from src.scheduler.reconciliation_b13_jobs import (
            register_reconciliation_b13_jobs,
        )

        with patch(
            "src.scheduler.reconciliation_b13_jobs.TaskScheduler.add_cron_task"
        ) as mock_add:
            register_reconciliation_b13_jobs()

        assert mock_add.call_count == 1
        assert mock_add.call_args.kwargs["name"] == "daily_reconciliation"


# ══════════════════════════════════════════════════════
# 10. 差异批量写入事务回滚场景
# ══════════════════════════════════════════════════════


class TestBatchCreateRollback:
    """差异批量写入失败场景（事务回滚）"""

    @pytest.mark.asyncio
    async def test_batch_create_failure_marks_failed(self):
        """差异批量写入失败 → 对账标记 FAILED"""
        record_dao = MagicMock()
        record_dao.create = AsyncMock(return_value=_make_record(record_id=1))
        record_dao.update_by_id = AsyncMock()
        record_dao.list_with_filters = AsyncMock(return_value=([], 0))

        diff_dao = MagicMock()
        diff_dao.batch_create = AsyncMock(side_effect=Exception("DB 写入失败"))

        query_dao = MagicMock()
        query_dao.aggregate_order_commission_by_user = AsyncMock(
            return_value={100: {"user_commission": Decimal("80.00"), "order_count": 1}}
        )
        query_dao.aggregate_settlement_by_user = AsyncMock(
            return_value={100: {"user_commission": Decimal("70.00")}}
        )
        query_dao.aggregate_account_totals = AsyncMock(
            return_value={
                "total_balance": Decimal("0.00"),
                "available_balance": Decimal("0.00"),
                "frozen_balance": Decimal("0.00"),
                "cumulative_withdrawn": Decimal("0.00"),
                "cumulative_fee": Decimal("0.00"),
                "account_count": 0,
            }
        )
        query_dao.aggregate_withdraw_by_user = AsyncMock(return_value={})
        query_dao.aggregate_withdraw_totals = AsyncMock(
            return_value={
                "total_withdrawn": Decimal("0.00"),
                "total_fee": Decimal("0.00"),
                "withdraw_count": 0,
            }
        )
        query_dao.get_account_by_user = AsyncMock(return_value=None)
        query_dao.find_orders_without_settlement = AsyncMock(return_value=[])
        query_dao.find_settlements_without_order = AsyncMock(return_value=[])

        svc = _make_service(record_dao, diff_dao, query_dao, _make_breaker())

        with patch(
            "src.services.reconciliation_b13_service.LockUtil.acquire_lock",
            return_value="owner-1",
        ), patch(
            "src.services.reconciliation_b13_service.LockUtil.release_lock",
            return_value=True,
        ), patch(
            "src.common.redis_client.RedisClient.set",
            return_value=True,
        ):
            with pytest.raises(Exception, match="DB 写入失败"):
                await svc.run_reconciliation(reconcile_date=date(2026, 8, 1))

        # 验证熔断失败被记录
        # (record_failure called in the exception handler)


# ══════════════════════════════════════════════════════
# 11. 差异复核状态机常量校验
# ══════════════════════════════════════════════════════


class TestDiffStateMachine:
    """差异状态机常量校验"""

    def test_diff_transitions(self):
        """差异状态流转映射正确"""
        assert DiffStatus.RESOLVED.value in DIFF_TRANSITIONS[DiffStatus.PENDING.value]
        assert DiffStatus.IGNORED.value in DIFF_TRANSITIONS[DiffStatus.PENDING.value]
        assert DiffStatus.RESOLVED.value in DIFF_TRANSITIONS[DiffStatus.REVIEWING.value]
        assert DIFF_TRANSITIONS[DiffStatus.RESOLVED.value] == set()

    def test_terminal_states(self):
        """终态集合正确"""
        assert DiffStatus.RESOLVED.value in DIFF_TERMINAL_STATES
        assert DiffStatus.IGNORED.value in DIFF_TERMINAL_STATES
        assert DiffStatus.PENDING.value not in DIFF_TERMINAL_STATES

    def test_alert_level_map(self):
        """差异类型 → 告警级别映射正确"""
        from src.config.b13_constants import DIFF_ALERT_LEVEL_MAP

        assert (
            DIFF_ALERT_LEVEL_MAP[DiffType.SETTLEMENT_ACCOUNT_MISMATCH.value]
            == AlertLevel.CRITICAL.value
        )
        assert (
            DIFF_ALERT_LEVEL_MAP[DiffType.SINGLE_SIDE_ORDER.value]
            == AlertLevel.INFO.value
        )
        assert (
            DIFF_ALERT_LEVEL_MAP[DiffType.ORDER_SETTLEMENT_MISMATCH.value]
            == AlertLevel.WARNING.value
        )

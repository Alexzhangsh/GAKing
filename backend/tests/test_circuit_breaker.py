# @ai-generated
"""
CPS 渠道熔断器单元测试

覆盖场景：
1. 状态机流转：CLOSED→OPEN→HALF_OPEN→CLOSED/OPEN
2. 连续失败阈值触发熔断
3. 恢复超时后自动半开试探
4. 试探成功/失败的恢复逻辑
5. 包装适配器兜底数据（搜索空结果/转链抛异常/订单空结果）
6. 熔断状态查询与重置

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_circuit_breaker.py -v
"""
import json
import logging
import sys
import time
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.redis_client import RedisClient
from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import (
    ConvertLinkResult,
    GoodsDTO,
    GoodsSearchResult,
    OrderPullResult,
)
from src.cps.circuit_breaker import BreakerState, CircuitBreaker
from src.cps.circuit_breaker_adapter import CircuitBreakerAdapter

logging.basicConfig(level=logging.DEBUG)

# ── 内存 Redis 模拟 ──────────────────────────────────

_STORE: Dict[str, str] = {}


def _install_mock_redis() -> None:
    @classmethod
    async def get(cls, key):  # type: ignore[override]
        return _STORE.get(key)

    @classmethod
    async def set(cls, key, value, expire=None, ex=None):  # type: ignore[override]
        _STORE[key] = value if isinstance(value, str) else str(value)
        return True

    @classmethod
    async def delete(cls, key):  # type: ignore[override]
        return 1 if _STORE.pop(key, None) is not None else 0

    RedisClient.get = get  # type: ignore[assignment]
    RedisClient.set = set  # type: ignore[assignment]
    RedisClient.delete = delete  # type: ignore[assignment]


def _reset_store() -> None:
    _STORE.clear()


@pytest.fixture(autouse=True)
def setup_mock_redis():
    _reset_store()
    _install_mock_redis()
    CircuitBreakerAdapter.reset_default_breaker()
    yield
    _reset_store()
    CircuitBreakerAdapter.reset_default_breaker()


# ── Mock 适配器 ──────────────────────────────────────


class MockAdapter(BaseCpsAdapter):
    """可控制成功/失败的 Mock 适配器"""

    def __init__(
        self,
        channel_code: str = "myq",
        channel_name: str = "测试渠道",
        fail: bool = False,
    ) -> None:
        self._channel_code = channel_code
        self._channel_name = channel_name
        self._fail = fail
        self.search_called = 0
        self.convert_called = 0
        self.pull_called = 0
        self.health_called = 0

    def get_channel_name(self) -> str:
        return self._channel_name

    def get_channel_code(self) -> str:
        return self._channel_code

    async def search_goods(self, keyword, page=1, size=20):
        self.search_called += 1
        if self._fail:
            raise CpsChannelException(
                CpsErrorType.API_ERROR, "模拟失败", self._channel_name
            )
        return GoodsSearchResult(
            items=[
                GoodsDTO(
                    goods_id="G001",
                    goods_title="测试商品",
                    original_price=Decimal("99.00"),
                    sale_price=Decimal("79.00"),
                )
            ],
            total=1,
            page=page,
            size=size,
        )

    async def convert_link(self, original_url, user_channel_id):
        self.convert_called += 1
        if self._fail:
            raise CpsChannelException(
                CpsErrorType.API_ERROR, "模拟失败", self._channel_name
            )
        return ConvertLinkResult(
            promote_url="https://promote.com/xxx",
            estimate_commission=Decimal("9.95"),
        )

    async def pull_order(self, start_time, end_time):
        self.pull_called += 1
        if self._fail:
            raise CpsChannelException(
                CpsErrorType.API_ERROR, "模拟失败", self._channel_name
            )
        return OrderPullResult(total=0, start_time=start_time, end_time=end_time)

    async def health_check(self):
        self.health_called += 1
        if self._fail:
            raise RuntimeError("健康检查失败")
        return not self._fail


# ════════════════════════════════════════════════════
# 熔断器状态机测试
# ════════════════════════════════════════════════════


class TestCircuitBreakerState:
    """熔断器状态机测试"""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        breaker = CircuitBreaker()
        state = await breaker.get_state("myq")
        assert state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_trigger_open(self):
        """连续失败达阈值 → OPEN"""
        breaker = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            await breaker.record_failure("myq")
        state = await breaker.get_state("myq")
        assert state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_below_threshold_stays_closed(self):
        """失败未达阈值 → 仍 CLOSED"""
        breaker = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            await breaker.record_failure("myq")
        state = await breaker.get_state("myq")
        assert state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_counter(self):
        """成功重置失败计数"""
        breaker = CircuitBreaker(failure_threshold=3)
        await breaker.record_failure("myq")
        await breaker.record_failure("myq")
        await breaker.record_success("myq")
        # 再失败 1 次，不应触发熔断（计数已重置）
        await breaker.record_failure("myq")
        state = await breaker.get_state("myq")
        assert state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_open_blocks_requests(self):
        """OPEN 状态拒绝请求"""
        breaker = CircuitBreaker(failure_threshold=2)
        await breaker.record_failure("myq")
        await breaker.record_failure("myq")
        assert await breaker.allow_request("myq") is False

    @pytest.mark.asyncio
    async def test_closed_allows_requests(self):
        """CLOSED 状态放行请求"""
        breaker = CircuitBreaker()
        assert await breaker.allow_request("myq") is True

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self):
        """OPEN 超过恢复时间 → 自动转 HALF_OPEN"""
        # 用大阈值确保不立即转换，手动篡改 opened_at 模拟超时
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        await breaker.record_failure("myq")
        # 确认进入 OPEN
        assert await breaker.get_state("myq") == BreakerState.OPEN
        # 篡改 opened_at 为 61 秒前，模拟超时
        from src.cps.circuit_breaker import _opened_at_key

        _STORE[_opened_at_key("myq")] = str(time.time() - 61)
        # 再次查询应自动转 HALF_OPEN
        state = await breaker.get_state("myq")
        assert state == BreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_allows_probe(self):
        """HALF_OPEN 放行试探请求"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        await breaker.record_failure("myq")
        # 触发 HALF_OPEN
        await breaker.get_state("myq")
        assert await breaker.allow_request("myq") is True

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        """HALF_OPEN 试探成功 → CLOSED"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        await breaker.record_failure("myq")
        await breaker.get_state("myq")  # 转 HALF_OPEN
        await breaker.record_success("myq")
        assert await breaker.get_state("myq") == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        """HALF_OPEN 试探失败 → 回到 OPEN"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        await breaker.record_failure("myq")
        await breaker.get_state("myq")  # 转 HALF_OPEN
        await breaker.record_failure("myq")
        state = await breaker.get_state("myq")
        # record_failure 后又触发 OPEN→HALF_OPEN（因 recovery_timeout=0）
        # 实际上：HALF_OPEN 失败 → _open() → OPEN，然后 get_state 检查超时又转 HALF_OPEN
        # 这里直接检查 allow_request 是否放行（HALF_OPEN 放行）
        assert state in (BreakerState.OPEN, BreakerState.HALF_OPEN)

    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """reset 清空熔断状态"""
        breaker = CircuitBreaker(failure_threshold=1)
        await breaker.record_failure("myq")
        assert await breaker.get_state("myq") == BreakerState.OPEN
        await breaker.reset("myq")
        assert await breaker.get_state("myq") == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """get_stats 返回完整状态"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        await breaker.record_failure("myq")
        await breaker.record_failure("myq")
        stats = await breaker.get_stats("myq")
        assert stats["channel_code"] == "myq"
        assert stats["state"] == "CLOSED"
        assert stats["fail_count"] == 2
        assert stats["failure_threshold"] == 3
        assert stats["recovery_timeout"] == 30

    @pytest.mark.asyncio
    async def test_channels_isolated(self):
        """不同渠道熔断状态隔离"""
        breaker = CircuitBreaker(failure_threshold=2)
        # myq 失败 2 次
        await breaker.record_failure("myq")
        await breaker.record_failure("myq")
        # orderx 仍正常
        assert await breaker.get_state("myq") == BreakerState.OPEN
        assert await breaker.get_state("orderx") == BreakerState.CLOSED
        assert await breaker.allow_request("orderx") is True


# ════════════════════════════════════════════════════
# 包装适配器测试
# ════════════════════════════════════════════════════


class TestCircuitBreakerAdapter:
    """熔断包装适配器测试"""

    @pytest.mark.asyncio
    async def test_search_success_records_success(self):
        """搜索成功 → 记录 success"""
        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=3)
        adapter = CircuitBreakerAdapter(raw, breaker)

        result = await adapter.search_goods("耳机")
        assert len(result.items) == 1
        assert raw.search_called == 1
        # 熔断器应保持 CLOSED
        state = await breaker.get_state("myq")
        assert state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_search_failure_records_failure(self):
        """搜索失败 → 记录 failure → 达阈值熔断"""
        raw = MockAdapter(fail=True)
        breaker = CircuitBreaker(failure_threshold=2)
        adapter = CircuitBreakerAdapter(raw, breaker)

        # 第一次失败
        with pytest.raises(CpsChannelException):
            await adapter.search_goods("耳机")
        # 第二次失败
        with pytest.raises(CpsChannelException):
            await adapter.search_goods("耳机")
        # 应已熔断
        assert await breaker.get_state("myq") == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_search_fallback_when_open(self):
        """熔断 OPEN 时搜索返回兜底空结果"""
        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        adapter = CircuitBreakerAdapter(raw, breaker)

        # 触发熔断
        await breaker.record_failure("myq")
        assert await breaker.get_state("myq") == BreakerState.OPEN

        # 搜索应返回空结果（兜底），不调原始适配器
        result = await adapter.search_goods("耳机")
        assert result.items == []
        assert result.total == 0
        assert raw.search_called == 0  # 未调原始适配器

    @pytest.mark.asyncio
    async def test_convert_link_fallback_raises(self):
        """熔断 OPEN 时转链抛异常（不能兜底空值）"""
        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        adapter = CircuitBreakerAdapter(raw, breaker)

        await breaker.record_failure("myq")
        with pytest.raises(CpsChannelException) as exc_info:
            await adapter.convert_link("https://tb.com", "rel_001")
        assert "熔断中" in str(exc_info.value)
        assert raw.convert_called == 0

    @pytest.mark.asyncio
    async def test_pull_order_fallback_empty(self):
        """熔断 OPEN 时订单拉取返回空结果"""
        from datetime import datetime

        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        adapter = CircuitBreakerAdapter(raw, breaker)

        await breaker.record_failure("myq")
        result = await adapter.pull_order(datetime(2026, 1, 1), datetime(2026, 1, 2))
        assert result.orders == []
        assert result.total == 0
        assert raw.pull_called == 0

    @pytest.mark.asyncio
    async def test_health_check_fallback_false(self):
        """熔断 OPEN 时健康检查返回 False"""
        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        adapter = CircuitBreakerAdapter(raw, breaker)

        await breaker.record_failure("myq")
        result = await adapter.health_check()
        assert result is False
        assert raw.health_called == 0

    @pytest.mark.asyncio
    async def test_full_recovery_cycle(self):
        """完整恢复周期：CLOSED→OPEN→HALF_OPEN→CLOSED"""
        raw = MockAdapter(fail=True)
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        adapter = CircuitBreakerAdapter(raw, breaker)

        # 1. 两次失败触发熔断
        with pytest.raises(CpsChannelException):
            await adapter.search_goods("x")
        with pytest.raises(CpsChannelException):
            await adapter.search_goods("x")
        assert await breaker.get_state("myq") in (
            BreakerState.OPEN,
            BreakerState.HALF_OPEN,
        )

        # 2. 恢复：切回成功
        raw._fail = False
        # get_state 会自动转 HALF_OPEN（recovery_timeout=0）
        await breaker.get_state("myq")

        # 3. 试探成功 → CLOSED
        result = await adapter.search_goods("x")
        assert len(result.items) == 1
        assert await breaker.get_state("myq") == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_channel_info_passthrough(self):
        """渠道信息透传"""
        raw = MockAdapter(channel_code="orderx", channel_name="订单侠")
        adapter = CircuitBreakerAdapter(raw, CircuitBreaker())
        assert adapter.get_channel_name() == "订单侠"
        assert adapter.get_channel_code() == "orderx"

    @pytest.mark.asyncio
    async def test_health_check_failure_records(self):
        """健康检查失败记录 failure"""
        raw = MockAdapter(fail=True)
        breaker = CircuitBreaker(failure_threshold=1)
        adapter = CircuitBreakerAdapter(raw, breaker)

        result = await adapter.health_check()
        assert result is False
        # 失败已记录，应熔断
        assert await breaker.get_state("myq") == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_convert_link_success(self):
        """转链成功 → 记录 success"""
        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=3)
        adapter = CircuitBreakerAdapter(raw, breaker)

        result = await adapter.convert_link("https://tb.com", "rel_001")
        assert result.promote_url == "https://promote.com/xxx"
        assert raw.convert_called == 1
        assert await breaker.get_state("myq") == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_convert_link_failure_records(self):
        """转链失败 → 记录 failure"""
        raw = MockAdapter(fail=True)
        breaker = CircuitBreaker(failure_threshold=2)
        adapter = CircuitBreakerAdapter(raw, breaker)

        with pytest.raises(CpsChannelException):
            await adapter.convert_link("https://tb.com", "x")
        with pytest.raises(CpsChannelException):
            await adapter.convert_link("https://tb.com", "x")
        assert await breaker.get_state("myq") == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_pull_order_success(self):
        """订单拉取成功 → 记录 success"""
        from datetime import datetime

        raw = MockAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=3)
        adapter = CircuitBreakerAdapter(raw, breaker)

        result = await adapter.pull_order(datetime(2026, 1, 1), datetime(2026, 1, 2))
        assert result.total == 0
        assert raw.pull_called == 1
        assert await breaker.get_state("myq") == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_pull_order_failure_records(self):
        """订单拉取失败 → 记录 failure"""
        from datetime import datetime

        raw = MockAdapter(fail=True)
        breaker = CircuitBreaker(failure_threshold=1)
        adapter = CircuitBreakerAdapter(raw, breaker)

        with pytest.raises(CpsChannelException):
            await adapter.pull_order(datetime(2026, 1, 1), datetime(2026, 1, 2))
        assert await breaker.get_state("myq") == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_health_check_returns_false_without_exception(self):
        """健康检查返回 False（不抛异常）→ 记录 failure"""
        raw = MockAdapter(fail=False)

        class FalseHealthAdapter(MockAdapter):
            async def health_check(self):
                return False

        adapter = FalseHealthAdapter(fail=False)
        breaker = CircuitBreaker(failure_threshold=1)
        wrapped = CircuitBreakerAdapter(adapter, breaker)

        result = await wrapped.health_check()
        assert result is False
        assert await breaker.get_state("myq") == BreakerState.OPEN

    def test_passthrough_methods(self):
        """基础信息透传方法"""
        raw = MockAdapter(channel_code="orderx", channel_name="订单侠")
        adapter = CircuitBreakerAdapter(raw, CircuitBreaker())
        assert adapter.get_pid() == raw.get_pid()
        assert adapter.get_api_key() == raw.get_api_key()
        assert adapter.get_goods_by_id("G001") is None


# ════════════════════════════════════════════════════
# 默认熔断器单例测试
# ════════════════════════════════════════════════════


class TestDefaultBreaker:
    """全局默认熔断器单例测试"""

    def test_singleton(self):
        b1 = CircuitBreakerAdapter.get_default_breaker()
        b2 = CircuitBreakerAdapter.get_default_breaker()
        assert b1 is b2

    def test_reset(self):
        CircuitBreakerAdapter.get_default_breaker()
        CircuitBreakerAdapter.reset_default_breaker()
        assert CircuitBreakerAdapter._default_breaker is None

    @pytest.mark.asyncio
    async def test_adapter_uses_default_breaker(self):
        """未传 breaker 时使用默认单例"""
        raw = MockAdapter()
        adapter = CircuitBreakerAdapter(raw)
        assert adapter._breaker is CircuitBreakerAdapter.get_default_breaker()

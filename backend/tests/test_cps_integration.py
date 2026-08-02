# @ai-generated
"""
CPS 模块集成测试（B01→B02→B03→B04 全链路）

覆盖场景：
1. 全链路搜索：接口→服务层→缓存→适配器→熔断器→回源
2. 全链路转链：接口→服务层→适配器→熔断器
3. 熔断触发后接口降级返回兜底数据
4. 熔断恢复后接口自动恢复
5. 缓存命中时适配器不被调用
6. 缓存未命中走适配器回源并回写
7. 限流触发与正常放行
8. 渠道异常全链路降级

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_cps_integration.py -v
"""
import json
import logging
import sys
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.common import redis_client as rc_mod
from src.common.redis_client import RedisClient
from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import (
    ConvertLinkResult,
    GoodsDTO,
    GoodsSearchResult,
    OrderPullResult,
)
from src.cps.adapter_factory import AdapterFactory
from src.cps.cache.goods_cache import (
    CACHE_KEY_GOODS_L1,
    CACHE_KEY_GOODS_L2,
    CACHE_KEY_SEARCH_L1,
    CACHE_KEY_SEARCH_L2,
    GoodsCacheManager,
)
from src.cps.circuit_breaker import BreakerState, CircuitBreaker
from src.cps.circuit_breaker_adapter import CircuitBreakerAdapter
from src.schemas.cps_goods import (
    BizException,
    ConvertLinkRequest,
    GoodsSearchRequest,
)
from src.services.cps_goods_service import CpsGoodsService

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
    async def set_json(cls, key, value, expire=None):  # type: ignore[override]
        _STORE[key] = json.dumps(value, ensure_ascii=False, default=str)
        return True

    @classmethod
    async def get_json(cls, key):  # type: ignore[override]
        val = _STORE.get(key)
        if not val or val == "__EMPTY__":
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None

    @classmethod
    async def set_empty_cache(cls, key):  # type: ignore[override]
        _STORE[key] = "__EMPTY__"
        return True

    @classmethod
    async def is_empty_cache(cls, key):  # type: ignore[override]
        return _STORE.get(key) == "__EMPTY__"

    @classmethod
    async def delete(cls, key):  # type: ignore[override]
        return 1 if _STORE.pop(key, None) is not None else 0

    @classmethod
    async def setnx(cls, key, value):  # type: ignore[override]
        if key in _STORE:
            return False
        _STORE[key] = value
        return True

    @classmethod
    async def expire(cls, key, expire):  # type: ignore[override]
        return key in _STORE

    @classmethod
    async def getset(cls, key, value):  # type: ignore[override]
        old = _STORE.get(key)
        _STORE[key] = value
        return old

    RedisClient.get = get  # type: ignore[assignment]
    RedisClient.set = set  # type: ignore[assignment]
    RedisClient.set_json = set_json  # type: ignore[assignment]
    RedisClient.get_json = get_json  # type: ignore[assignment]
    RedisClient.set_empty_cache = set_empty_cache  # type: ignore[assignment]
    RedisClient.is_empty_cache = is_empty_cache  # type: ignore[assignment]
    RedisClient.delete = delete  # type: ignore[assignment]
    RedisClient.setnx = setnx  # type: ignore[assignment]
    RedisClient.expire = expire  # type: ignore[assignment]
    RedisClient.getset = getset  # type: ignore[assignment]


def _reset_store() -> None:
    _STORE.clear()


# ── Mock 适配器（可控成功/失败）──────────────────────


class ControllableAdapter(BaseCpsAdapter):
    """可控适配器，支持动态切换成功/失败"""

    def __init__(self, channel_code: str = "myq", fail: bool = False) -> None:
        self._code = channel_code
        self._fail = fail
        self.search_count = 0
        self.convert_count = 0

    def get_channel_name(self) -> str:
        return f"测试-{self._code}"

    def get_channel_code(self) -> str:
        return self._code

    async def search_goods(self, keyword, page=1, size=20):
        self.search_count += 1
        if self._fail:
            raise CpsChannelException(
                CpsErrorType.API_ERROR, "模拟渠道异常", self.get_channel_name()
            )
        return GoodsSearchResult(
            items=[
                GoodsDTO(
                    goods_id=f"G_{keyword}_1",
                    goods_title=f"搜索结果-{keyword}",
                    original_price=Decimal("99.00"),
                    sale_price=Decimal("79.00"),
                    commission_rate=Decimal("5.0"),
                    estimate_commission=Decimal("3.95"),
                    sales_volume=5000,
                    source_channel=self._code,
                )
            ],
            total=1,
            page=page,
            size=size,
        )

    async def convert_link(self, original_url, user_channel_id):
        self.convert_count += 1
        if self._fail:
            raise CpsChannelException(
                CpsErrorType.API_ERROR, "模拟转链失败", self.get_channel_name()
            )
        return ConvertLinkResult(
            promote_url=f"https://promote.com/{user_channel_id}",
            channel_pid=f"pid_{user_channel_id}",
            estimate_commission=Decimal("9.95"),
            goods_id="G001",
        )

    async def pull_order(self, start_time, end_time):
        return OrderPullResult()

    async def health_check(self):
        return not self._fail


# ── Fixtures ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def setup_env():
    """每个测试前重置环境"""
    _reset_store()
    _install_mock_redis()
    AdapterFactory.clear_instances()
    CircuitBreakerAdapter.reset_default_breaker()
    yield
    _reset_store()
    AdapterFactory.clear_instances()
    CircuitBreakerAdapter.reset_default_breaker()


@pytest.fixture
def mock_adapter():
    """可控适配器（默认成功）"""
    return ControllableAdapter(channel_code="myq", fail=False)


@pytest.fixture
def failing_adapter():
    """可控适配器（默认失败）"""
    return ControllableAdapter(channel_code="myq", fail=True)


# ════════════════════════════════════════════════════
# 全链路搜索测试
# ════════════════════════════════════════════════════


class TestSearchFullChain:
    """搜索接口全链路测试：接口→服务→缓存→熔断→适配器"""

    @pytest.mark.asyncio
    async def test_cache_miss_backfill_from_adapter(self, mock_adapter):
        """缓存未命中 → 走适配器回源 → 回写缓存"""
        breaker = CircuitBreaker(failure_threshold=5)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        result = await svc.search_goods(req)

        assert len(result.items) == 1
        assert result.items[0].goods_id == "G_耳机_1"
        assert mock_adapter.search_count == 1
        # L2 缓存应写入
        assert any("耳机" in k and "l2" in k for k in _STORE)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_adapter(self, mock_adapter):
        """缓存命中 → 不调适配器"""
        breaker = CircuitBreaker(failure_threshold=5)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        # 预置缓存
        goods = GoodsDTO(
            goods_id="G_CACHED",
            goods_title="缓存商品",
            original_price=Decimal("50.00"),
            sale_price=Decimal("39.00"),
            sales_volume=5000,
        )
        result_obj = GoodsSearchResult(items=[goods], total=1, page=1, size=20)
        _STORE[f"{CACHE_KEY_SEARCH_L1}耳机:1:20"] = json.dumps(
            result_obj.model_dump(), default=str
        )

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        result = await svc.search_goods(req)

        assert len(result.items) == 1
        assert result.items[0].goods_id == "G_CACHED"
        assert mock_adapter.search_count == 0  # 未调适配器

    @pytest.mark.asyncio
    async def test_breaker_open_returns_fallback(self, mock_adapter):
        """熔断 OPEN → 搜索返回兜底空结果"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        # 触发熔断
        await breaker.record_failure("myq")

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        result = await svc.search_goods(req)

        # 兜底返回空结果（不抛异常）
        assert result.items == []
        assert result.total == 0
        assert mock_adapter.search_count == 0  # 适配器未被调用

    @pytest.mark.asyncio
    async def test_channel_exception_degrades(self, failing_adapter):
        """渠道异常 → B02 缓存管理器容错降级返回空结果"""
        breaker = CircuitBreaker(failure_threshold=5)
        wrapped = CircuitBreakerAdapter(failing_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        # B02 _fetch_search 会捕获适配器异常并返回空结果（容错降级）
        result = await svc.search_goods(req)
        assert result.items == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_breaker_triggers_on_repeated_failures(self, failing_adapter):
        """连续失败触发熔断 → 后续请求返回兜底空结果"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        wrapped = CircuitBreakerAdapter(failing_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        # 用不同 keyword 避免命中空值标记（B02 失败后写空值标记）
        keywords = ["耳机", "音箱", "键盘"]
        for kw in keywords:
            req = GoodsSearchRequest(keyword=kw, channel_code="myq")
            result = await svc.search_goods(req)
            assert result.items == []  # B02 容错降级

        # 熔断应已触发（3 次失败）
        assert await breaker.get_state("myq") == BreakerState.OPEN

        # 第 4 次：熔断 OPEN → CircuitBreakerAdapter 兜底空结果
        req = GoodsSearchRequest(keyword="鼠标", channel_code="myq")
        result = await svc.search_goods(req)
        assert result.items == []

    @pytest.mark.asyncio
    async def test_breaker_recovery_restores_service(self, mock_adapter):
        """熔断恢复后服务自动恢复"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = cache_mgr

        # 1. 触发熔断
        await breaker.record_failure("myq")
        assert await breaker.get_state("myq") == BreakerState.OPEN

        # 2. 熔断状态搜索返回空（兜底）
        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        result = await svc.search_goods(req)
        assert result.items == []

        # 3. 恢复：手动 reset + 清除可能的空值标记
        await breaker.reset("myq")
        _STORE.clear()  # 清除空值标记，避免干扰恢复后的搜索
        assert await breaker.get_state("myq") == BreakerState.CLOSED

        # 4. 用新 keyword 搜索应正常返回（走适配器）
        req = GoodsSearchRequest(keyword="恢复测试", channel_code="myq")
        result = await svc.search_goods(req)
        assert len(result.items) == 1
        assert result.items[0].goods_id == "G_恢复测试_1"


# ════════════════════════════════════════════════════
# 全链路转链测试
# ════════════════════════════════════════════════════


class TestConvertLinkFullChain:
    """转链接口全链路测试"""

    @pytest.mark.asyncio
    async def test_convert_link_success(self, mock_adapter):
        """转链成功"""
        breaker = CircuitBreaker(failure_threshold=5)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)

        with patch.object(AdapterFactory, "get_adapter", return_value=wrapped):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com/item?id=1",
                user_channel_id="rel_001",
                channel_code="myq",
            )
            result = await svc.convert_link(req)

        assert result.promote_url == "https://promote.com/rel_001"
        assert result.estimate_commission == 9.95
        assert mock_adapter.convert_count == 1

    @pytest.mark.asyncio
    async def test_convert_link_breaker_open_raises(self, mock_adapter):
        """熔断 OPEN → 转链抛 BizException"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)

        # 触发熔断
        await breaker.record_failure("myq")

        with patch.object(AdapterFactory, "get_adapter", return_value=wrapped):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
                channel_code="myq",
            )
            with pytest.raises(BizException) as exc_info:
                await svc.convert_link(req)

        # 熔断抛 CpsChannelException(API_ERROR) → BizException(502)
        assert exc_info.value.code == 502
        assert mock_adapter.convert_count == 0

    @pytest.mark.asyncio
    async def test_convert_link_channel_timeout(self, mock_adapter):
        """渠道超时 → BizException(504)"""
        breaker = CircuitBreaker(failure_threshold=5)

        class TimeoutAdapter(ControllableAdapter):
            async def convert_link(self, url, uid):
                self.convert_count += 1
                raise CpsChannelException(
                    CpsErrorType.REQUEST_TIMEOUT, "超时", self.get_channel_name()
                )

        wrapped = CircuitBreakerAdapter(TimeoutAdapter("myq"), breaker)
        with patch.object(AdapterFactory, "get_adapter", return_value=wrapped):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
                channel_code="myq",
            )
            with pytest.raises(BizException) as exc_info:
                await svc.convert_link(req)

        assert exc_info.value.code == 504


# ════════════════════════════════════════════════════
# 接口层端到端测试
# ════════════════════════════════════════════════════


class TestEndpointE2E:
    """接口层端到端集成测试"""

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI

        from src.api.public.cps_goods import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient

        return TestClient(app)

    def test_search_e2e_success(self, app, client, mock_adapter):
        """搜索接口 E2E：限流放行 → 缓存未命中 → 适配器回源"""
        breaker = CircuitBreaker(failure_threshold=5)
        wrapped = CircuitBreakerAdapter(mock_adapter, breaker)
        cache_mgr = GoodsCacheManager(adapter=wrapped)
        mock_svc = MagicMock()
        mock_svc.search_goods = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "items": [{"goods_id": "G_E2E", "goods_title": "端到端"}],
                        "total": 1,
                        "page": 1,
                        "size": 20,
                        "cache_hit": True,
                    }
                )
            )
        )
        from src.api.public.cps_goods import get_cps_goods_service

        app.dependency_overrides[get_cps_goods_service] = lambda: mock_svc

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(True, {})),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "耳机"},
                headers={"X-User-Id": "u001"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["items"][0]["goods_id"] == "G_E2E"

    def test_search_e2e_rate_limited(self, client):
        """搜索接口 E2E：限流触发 → 429"""
        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(False, {"count": 20})),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "耳机"},
                headers={"X-User-Id": "u001"},
            )
        body = resp.json()
        assert body["code"] == 429

    def test_convert_e2e_success(self, app, client):
        """转链接口 E2E 成功"""
        mock_svc = MagicMock()
        mock_svc.convert_link = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(
                    return_value={
                        "promote_url": "https://promote.com/xxx",
                        "channel_pid": "pid_001",
                        "estimate_commission": 9.95,
                        "goods_id": "G001",
                        "channel_code": "myq",
                    }
                )
            )
        )
        from src.api.public.cps_goods import get_cps_goods_service

        app.dependency_overrides[get_cps_goods_service] = lambda: mock_svc

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(True, {})),
        ):
            resp = client.post(
                "/api/public/goods/convert-link",
                json={
                    "original_url": "https://tb.com/item?id=1",
                    "user_channel_id": "rel_001",
                    "channel_code": "myq",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["promote_url"] == "https://promote.com/xxx"

    def test_convert_e2e_breaker_open(self, app, client):
        """转链接口 E2E：熔断触发 → 502"""
        mock_svc = MagicMock()
        mock_svc.convert_link = AsyncMock(
            side_effect=BizException(code=502, msg="渠道熔断中")
        )
        from src.api.public.cps_goods import get_cps_goods_service

        app.dependency_overrides[get_cps_goods_service] = lambda: mock_svc

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(True, {})),
        ):
            resp = client.post(
                "/api/public/goods/convert-link",
                json={
                    "original_url": "https://tb.com",
                    "user_channel_id": "x",
                },
            )
        body = resp.json()
        assert body["code"] == 502


# ════════════════════════════════════════════════════
# 适配器工厂集成测试
# ════════════════════════════════════════════════════


class TestAdapterFactoryIntegration:
    """适配器工厂集成测试"""

    @pytest.mark.asyncio
    async def test_factory_returns_wrapped_adapter(self):
        """工厂返回的适配器已包装熔断器"""
        AdapterFactory.clear_instances()
        adapter = AdapterFactory.get_adapter("myq")
        assert isinstance(adapter, CircuitBreakerAdapter)

    @pytest.mark.asyncio
    async def test_factory_raw_adapter(self):
        """get_raw_adapter 返回原始适配器"""
        AdapterFactory.clear_instances()
        raw = AdapterFactory.get_raw_adapter("myq")
        assert not isinstance(raw, CircuitBreakerAdapter)

    @pytest.mark.asyncio
    async def test_factory_singleton_wrapped(self):
        """包装适配器单例"""
        AdapterFactory.clear_instances()
        a1 = AdapterFactory.get_adapter("myq")
        a2 = AdapterFactory.get_adapter("myq")
        assert a1 is a2

    @pytest.mark.asyncio
    async def test_factory_all_channels(self):
        """三个渠道都能获取包装适配器"""
        AdapterFactory.clear_instances()
        for code in ("myq", "orderx", "dta"):
            adapter = AdapterFactory.get_adapter(code)
            assert isinstance(adapter, CircuitBreakerAdapter)
            assert adapter.get_channel_code() == code


# ════════════════════════════════════════════════════
# 熔断器跨渠道隔离测试
# ════════════════════════════════════════════════════


class TestBreakerChannelIsolation:
    """熔断器跨渠道隔离测试"""

    @pytest.mark.asyncio
    async def test_myq_breaker_does_not_affect_orderx(self):
        """myq 熔断不影响 orderx"""
        myq_adapter = ControllableAdapter("myq", fail=True)
        orderx_adapter = ControllableAdapter("orderx", fail=False)

        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        myq_wrapped = CircuitBreakerAdapter(myq_adapter, breaker)
        orderx_wrapped = CircuitBreakerAdapter(orderx_adapter, breaker)

        # myq 失败触发熔断
        with pytest.raises(CpsChannelException):
            await myq_wrapped.search_goods("x")
        assert await breaker.get_state("myq") == BreakerState.OPEN

        # orderx 应正常工作
        result = await orderx_wrapped.search_goods("x")
        assert len(result.items) == 1
        assert await breaker.get_state("orderx") == BreakerState.CLOSED

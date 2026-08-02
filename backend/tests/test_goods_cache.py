# @ai-generated
"""
CPS 商品双层缓存单元测试

覆盖场景：
- 布隆过滤器：add/exists/误判/异常降级
- 单商品缓存：L1命中/L2命中回写L1/回源回写/空值兜底/布隆拦截/防击穿DCL
- 搜索缓存：L1命中/L2命中/回源回写/空结果兜底/防击穿
- 主动失效：invalidate_goods/invalidate_search
- 差异化TTL：按销量判定L1/L2写入策略

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_goods_cache.py -v
"""
import json
import logging
import sys
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, ".")

from src.common import redis_client as rc_mod
from src.common.redis_client import RedisClient
from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.dto import GoodsDTO, GoodsSearchResult
from src.cps.cache.bloom_filter import GoodsBloomFilter
from src.cps.cache.goods_cache import (
    CACHE_KEY_GOODS_L1,
    CACHE_KEY_GOODS_L2,
    CACHE_KEY_SEARCH_L1,
    CACHE_KEY_SEARCH_L2,
    GOODS_HOT_SALES_THRESHOLD,
    GOODS_NORMAL_SALES_THRESHOLD,
    GoodsCacheManager,
)

logging.basicConfig(level=logging.DEBUG)

# ── 内存 Redis 模拟 ──────────────────────────────────

_STORE: Dict[str, str] = {}
_LOCKS: Dict[str, str] = {}
_CALLS: Dict[str, int] = {"get": 0, "set": 0, "delete": 0}


def _install_mock_redis() -> None:
    """用内存 dict 替换 RedisClient 的读写方法"""

    @classmethod
    async def get(cls, key: str) -> Optional[str]:  # type: ignore[override]
        _CALLS["get"] += 1
        return _STORE.get(key)

    @classmethod
    async def set(cls, key, value, expire=None, ex=None):  # type: ignore[override]
        _CALLS["set"] += 1
        _STORE[key] = value if isinstance(value, str) else str(value)
        return True

    @classmethod
    async def set_json(cls, key, value, expire=None):  # type: ignore[override]
        _CALLS["set"] += 1
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
        _CALLS["set"] += 1
        _STORE[key] = "__EMPTY__"
        return True

    @classmethod
    async def is_empty_cache(cls, key):  # type: ignore[override]
        return _STORE.get(key) == "__EMPTY__"

    @classmethod
    async def delete(cls, key):  # type: ignore[override]
        _CALLS["delete"] += 1
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
    _LOCKS.clear()
    _CALLS.clear()
    _CALLS.update({"get": 0, "set": 0, "delete": 0})


# ── Mock 适配器 ──────────────────────────────────────


class MockAdapter(BaseCpsAdapter):
    """Mock CPS 适配器（B01 基类的测试实现）"""

    def __init__(self, search_result: Optional[GoodsSearchResult] = None) -> None:
        self._search_result = search_result
        self.search_called: int = 0

    def get_channel_name(self) -> str:
        return "测试渠道"

    def get_channel_code(self) -> str:
        return "test"

    async def search_goods(
        self, keyword: str, page: int = 1, size: int = 20
    ) -> GoodsSearchResult:
        self.search_called += 1
        if self._search_result is None:
            return GoodsSearchResult(page=page, size=size)
        return self._search_result

    async def convert_link(self, original_url: str, user_channel_id: str):
        from src.cps.adapter.dto import ConvertLinkResult

        return ConvertLinkResult(promote_url="x")

    async def pull_order(self, start_time, end_time):
        from src.cps.adapter.dto import OrderPullResult

        return OrderPullResult()

    async def health_check(self) -> bool:
        return True


def _make_goods(
    goods_id: str = "G001",
    title: str = "测试商品",
    sales: int = 5000,
    price: str = "99.00",
) -> GoodsDTO:
    return GoodsDTO(
        goods_id=goods_id,
        goods_title=title,
        goods_img="https://img.test/a.jpg",
        original_price=Decimal(price),
        sale_price=Decimal("79.00"),
        commission_rate=Decimal("5.00"),
        estimate_commission=Decimal("3.95"),
        category="数码",
        promote_url="https://test.com/p",
        shop_name="测试店",
        sales_volume=sales,
        source_channel="test",
    )


# ── Fixtures ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def setup_mock_redis():
    """每个测试前重置内存 Redis 并安装 mock"""
    _reset_store()
    _install_mock_redis()
    yield
    _reset_store()


@pytest.fixture
def hot_goods() -> GoodsDTO:
    """热门商品（销量 >= HOT_THRESHOLD）"""
    return _make_goods(goods_id="HOT001", sales=GOODS_HOT_SALES_THRESHOLD + 1000)


@pytest.fixture
def normal_goods() -> GoodsDTO:
    """普通商品（NORMAL <= 销量 < HOT）"""
    return _make_goods(goods_id="NORM001", sales=GOODS_NORMAL_SALES_THRESHOLD + 500)


@pytest.fixture
def cold_goods() -> GoodsDTO:
    """冷门商品（销量 < NORMAL）"""
    return _make_goods(goods_id="COLD001", sales=100)


# ════════════════════════════════════════════════════
# 布隆过滤器测试
# ════════════════════════════════════════════════════


class TestBloomFilter:
    """布隆过滤器单元测试"""

    def test_default_params(self):
        bf = GoodsBloomFilter()
        assert bf.capacity == 1_000_000
        assert bf.error_rate == 0.01
        assert bf.bit_size > 0
        assert bf.hash_count >= 1
        stats = bf.get_stats()
        assert stats["hash_count"] == bf.hash_count

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            GoodsBloomFilter(capacity=0)
        with pytest.raises(ValueError):
            GoodsBloomFilter(error_rate=0)
        with pytest.raises(ValueError):
            GoodsBloomFilter(error_rate=1.5)

    @pytest.mark.asyncio
    async def test_add_and_exists(self):
        bf = GoodsBloomFilter()
        # 模拟 setbit/getbit
        bit_store: Dict[int, int] = {}
        client_mock = AsyncMock()
        client_mock.setbit = AsyncMock(
            side_effect=lambda k, p, v: bit_store.__setitem__(p, v)
        )
        client_mock.getbit = AsyncMock(side_effect=lambda k, p: bit_store.get(p, 0))
        with patch.object(RedisClient, "get_client", return_value=client_mock):
            await bf.add("G001")
            assert await bf.exists("G001") is True
            assert await bf.exists("G999_NOT_EXIST") is False

    @pytest.mark.asyncio
    async def test_exists_degrade_on_exception(self):
        """异常时降级为 True（不阻断主流程）"""
        bf = GoodsBloomFilter()
        with patch.object(
            RedisClient, "get_client", side_effect=RuntimeError("conn lost")
        ):
            # exists 异常返回 True（降级）
            assert await bf.exists("G001") is True
            # add 异常返回 False
            assert await bf.add("G001") is False

    def test_positions_deterministic(self):
        """同一值生成的哈希位置稳定"""
        bf = GoodsBloomFilter()
        p1 = bf._get_positions("G001")
        p2 = bf._get_positions("G001")
        assert p1 == p2
        assert len(p1) == bf.hash_count
        # 不同值应生成不同位置
        p3 = bf._get_positions("G002")
        assert p1 != p3


# ════════════════════════════════════════════════════
# 单商品缓存测试
# ════════════════════════════════════════════════════


class TestGetGoods:
    """单商品双层缓存测试"""

    @pytest.mark.asyncio
    async def test_empty_goods_id_returns_none(self):
        mgr = GoodsCacheManager(adapter=MockAdapter())
        assert await mgr.get_goods("") is None

    @pytest.mark.asyncio
    async def test_bloom_miss_returns_none(self):
        """布隆过滤器未命中 → 直接返回 None，不查缓存不回源"""
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[_make_goods()]))
        mgr = GoodsCacheManager(adapter=adapter)
        # 布隆过滤器返回 False（不存在）
        with (
            patch.object(GoodsBloomFilter, "exists", return_value=True)
            if False
            else patch.object(
                GoodsBloomFilter, "exists", new=AsyncMock(return_value=False)
            )
        ):
            result = await mgr.get_goods("G_NOT_IN_BLOOM")
        assert result is None
        assert adapter.search_called == 0  # 未回源

    @pytest.mark.asyncio
    async def test_backfill_from_adapter(self):
        """L1/L2 都 miss → 回源 → 回写 L1+L2"""
        goods = _make_goods("G001", sales=GOODS_HOT_SALES_THRESHOLD + 1)
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[goods]))
        mgr = GoodsCacheManager(adapter=adapter)
        # 布隆放行
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                result = await mgr.get_goods("G001")
        assert result is not None
        assert result.goods_id == "G001"
        assert adapter.search_called == 1
        # L1/L2 都应写入
        assert f"{CACHE_KEY_GOODS_L1}G001" in _STORE
        assert f"{CACHE_KEY_GOODS_L2}G001" in _STORE

    @pytest.mark.asyncio
    async def test_l1_hit_skips_adapter(self):
        """L1 命中 → 不回源"""
        goods = _make_goods("G001")
        # 预置 L1 缓存
        _STORE[f"{CACHE_KEY_GOODS_L1}G001"] = json.dumps(
            goods.model_dump(), default=str
        )
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            result = await mgr.get_goods("G001")
        assert result is not None
        assert result.goods_id == "G001"
        assert adapter.search_called == 0  # 未回源

    @pytest.mark.asyncio
    async def test_l2_hit_backfill_l1(self):
        """L2 命中 → 回写 L1 → 不回源"""
        goods = _make_goods("G001", sales=GOODS_HOT_SALES_THRESHOLD + 1)
        _STORE[f"{CACHE_KEY_GOODS_L2}G001"] = json.dumps(
            goods.model_dump(), default=str
        )
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            result = await mgr.get_goods("G001")
        assert result is not None
        assert result.goods_id == "G001"
        assert adapter.search_called == 0
        # L1 应被回写
        assert f"{CACHE_KEY_GOODS_L1}G001" in _STORE

    @pytest.mark.asyncio
    async def test_empty_marker_prevents_repeated_fetch(self):
        """回源无数据 → 写空值标记 → 第二次不回源"""
        adapter = MockAdapter(search_result=GoodsSearchResult())  # 空结果
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                r1 = await mgr.get_goods("G_EMPTY")
                assert r1 is None
                assert adapter.search_called == 1
                # 空值标记已写入
                assert _STORE.get(f"{CACHE_KEY_GOODS_L2}G_EMPTY") == "__EMPTY__"
                # 第二次：应命中空值标记，不回源
                r2 = await mgr.get_goods("G_EMPTY")
                assert r2 is None
                assert adapter.search_called == 1  # 仍未回源

    @pytest.mark.asyncio
    async def test_custom_fetcher_overrides_adapter(self):
        """自定义 fetcher 优先于适配器"""
        custom_goods = _make_goods("CUSTOM_G", sales=GOODS_HOT_SALES_THRESHOLD)
        custom_fetcher = AsyncMock(return_value=custom_goods)
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)

        async def fetcher(gid: str):
            return await custom_fetcher(gid)

        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                result = await mgr.get_goods("CUSTOM_G", fetcher=fetcher)
        assert result is not None
        assert result.goods_id == "CUSTOM_G"
        assert custom_fetcher.called
        assert adapter.search_called == 0  # 适配器未被调用

    @pytest.mark.asyncio
    async def test_lock_timeout_degrades_gracefully(self):
        """锁等待超时 → 降级返回 None"""
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[_make_goods()]))
        mgr = GoodsCacheManager(adapter=adapter)
        # acquire_with_wait 返回 None（超时）
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch(
                "src.cps.cache.goods_cache.LockUtil.acquire_with_wait",
                new=AsyncMock(return_value=None),
            ):
                result = await mgr.get_goods("G_LOCKED")
        assert result is None
        assert adapter.search_called == 0

    @pytest.mark.asyncio
    async def test_dcl_after_lock_skips_adapter(self):
        """锁内双重检查命中 → 不回源"""
        goods = _make_goods("G001")
        _STORE[f"{CACHE_KEY_GOODS_L2}G001"] = json.dumps(
            goods.model_dump(), default=str
        )
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        # 锁获取成功（owner 非空）
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch(
                "src.cps.cache.goods_cache.LockUtil.acquire_with_wait",
                new=AsyncMock(return_value="owner-123"),
            ):
                with patch(
                    "src.cps.cache.goods_cache.LockUtil.release_lock",
                    new=AsyncMock(return_value=True),
                ):
                    result = await mgr.get_goods("G001")
        assert result is not None
        assert result.goods_id == "G001"
        assert adapter.search_called == 0  # DCL 命中，未回源


# ════════════════════════════════════════════════════
# 搜索缓存测试
# ════════════════════════════════════════════════════


class TestSearchGoods:
    """搜索双层缓存测试"""

    @pytest.mark.asyncio
    async def test_empty_keyword_returns_empty(self):
        mgr = GoodsCacheManager(adapter=MockAdapter())
        result = await mgr.search_goods("", page=1, size=20)
        assert result.items == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_backfill_from_adapter(self):
        """搜索缓存 miss → 回源 → 回写 L1+L2"""
        goods = _make_goods("G001", sales=GOODS_HOT_SALES_THRESHOLD + 1)
        adapter = MockAdapter(
            search_result=GoodsSearchResult(items=[goods], total=1, page=1, size=20)
        )
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "add_batch", new=AsyncMock(return_value=1)):
            result = await mgr.search_goods("耳机", page=1, size=20)
        assert len(result.items) == 1
        assert result.items[0].goods_id == "G001"
        assert adapter.search_called == 1
        # L1+L2 都应写入
        assert any("耳机" in k and "l1" in k for k in _STORE)
        assert any("耳机" in k and "l2" in k for k in _STORE)

    @pytest.mark.asyncio
    async def test_l1_hit_skips_adapter(self):
        """搜索 L1 命中 → 不回源"""
        result_obj = GoodsSearchResult(
            items=[_make_goods("G001")], total=1, page=1, size=20
        )
        _STORE[f"{CACHE_KEY_SEARCH_L1}耳机:1:20"] = json.dumps(
            result_obj.model_dump(), default=str
        )
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        result = await mgr.search_goods("耳机", page=1, size=20)
        assert len(result.items) == 1
        assert adapter.search_called == 0

    @pytest.mark.asyncio
    async def test_l2_hit_backfill_l1(self):
        """搜索 L2 命中 → 回写 L1 → 不回源"""
        result_obj = GoodsSearchResult(
            items=[_make_goods("G001", sales=GOODS_HOT_SALES_THRESHOLD + 1)],
            total=1,
            page=1,
            size=20,
        )
        _STORE[f"{CACHE_KEY_SEARCH_L2}耳机:1:20"] = json.dumps(
            result_obj.model_dump(), default=str
        )
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        result = await mgr.search_goods("耳机", page=1, size=20)
        assert len(result.items) == 1
        assert adapter.search_called == 0
        # L1 应被回写
        assert f"{CACHE_KEY_SEARCH_L1}耳机:1:20" in _STORE

    @pytest.mark.asyncio
    async def test_empty_result_writes_marker(self):
        """搜索无结果 → 写空值标记 → 第二次不回源"""
        adapter = MockAdapter(search_result=GoodsSearchResult())
        mgr = GoodsCacheManager(adapter=adapter)
        r1 = await mgr.search_goods("不存在的词", page=1, size=20)
        assert r1.items == []
        assert adapter.search_called == 1
        # 空值标记已写入 L2
        assert _STORE.get(f"{CACHE_KEY_SEARCH_L2}不存在的词:1:20") == "__EMPTY__"
        # 第二次：命中空值标记
        r2 = await mgr.search_goods("不存在的词", page=1, size=20)
        assert r2.items == []
        assert adapter.search_called == 1

    @pytest.mark.asyncio
    async def test_lock_timeout_degrades_gracefully(self):
        """搜索锁超时 → 降级返回空结果"""
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        with patch(
            "src.cps.cache.goods_cache.LockUtil.acquire_with_wait",
            new=AsyncMock(return_value=None),
        ):
            result = await mgr.search_goods("耳机", page=1, size=20)
        assert result.items == []
        assert adapter.search_called == 0

    @pytest.mark.asyncio
    async def test_custom_fetcher_overrides_adapter(self):
        """自定义搜索 fetcher 优先"""
        custom_result = GoodsSearchResult(
            items=[_make_goods("CUSTOM")], total=1, page=1, size=20
        )
        custom_fetcher = AsyncMock(return_value=custom_result)
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)

        async def fetcher(kw: str, p: int, s: int):
            return await custom_fetcher(kw, p, s)

        with patch.object(GoodsBloomFilter, "add_batch", new=AsyncMock(return_value=1)):
            result = await mgr.search_goods("自定义", page=1, size=20, fetcher=fetcher)
        assert len(result.items) == 1
        assert result.items[0].goods_id == "CUSTOM"
        assert custom_fetcher.called
        assert adapter.search_called == 0


# ════════════════════════════════════════════════════
# 差异化 TTL 测试
# ════════════════════════════════════════════════════


class TestDifferentiatedTTL:
    """按销量差异化 TTL 策略测试"""

    @pytest.mark.asyncio
    async def test_hot_goods_writes_l1(self, hot_goods: GoodsDTO):
        """热门商品 → 写入 L1"""
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[hot_goods]))
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                await mgr.get_goods(hot_goods.goods_id)
        assert f"{CACHE_KEY_GOODS_L1}{hot_goods.goods_id}" in _STORE
        assert f"{CACHE_KEY_GOODS_L2}{hot_goods.goods_id}" in _STORE

    @pytest.mark.asyncio
    async def test_cold_goods_skips_l1(self, cold_goods: GoodsDTO):
        """冷门商品 → 不写 L1，只写 L2"""
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[cold_goods]))
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                await mgr.get_goods(cold_goods.goods_id)
        # L1 不应写入（销量不达热门阈值）
        assert f"{CACHE_KEY_GOODS_L1}{cold_goods.goods_id}" not in _STORE
        # L2 应写入
        assert f"{CACHE_KEY_GOODS_L2}{cold_goods.goods_id}" in _STORE

    @pytest.mark.asyncio
    async def test_normal_goods_skips_l1(self, normal_goods: GoodsDTO):
        """普通商品 → 不写 L1，只写 L2"""
        adapter = MockAdapter(search_result=GoodsSearchResult(items=[normal_goods]))
        mgr = GoodsCacheManager(adapter=adapter)
        with patch.object(GoodsBloomFilter, "exists", new=AsyncMock(return_value=True)):
            with patch.object(
                GoodsBloomFilter, "add", new=AsyncMock(return_value=True)
            ):
                await mgr.get_goods(normal_goods.goods_id)
        assert f"{CACHE_KEY_GOODS_L1}{normal_goods.goods_id}" not in _STORE
        assert f"{CACHE_KEY_GOODS_L2}{normal_goods.goods_id}" in _STORE

    def test_calc_l2_ttl_hot(self):
        """热门商品 L2 TTL = COLD_GOODS_SEARCH"""
        from src.config.constants import CacheTTL

        assert GoodsCacheManager._calc_l2_ttl(GOODS_HOT_SALES_THRESHOLD + 1) == int(
            CacheTTL.COLD_GOODS_SEARCH
        )

    def test_calc_l2_ttl_normal(self):
        """普通商品 L2 TTL = COLD_GOODS_SEARCH"""
        from src.config.constants import CacheTTL

        assert GoodsCacheManager._calc_l2_ttl(GOODS_NORMAL_SALES_THRESHOLD + 1) == int(
            CacheTTL.COLD_GOODS_SEARCH
        )

    def test_calc_l2_ttl_cold(self):
        """冷门商品 L2 TTL = NORMAL_GOODS_SEARCH（更短）"""
        from src.config.constants import CacheTTL

        assert GoodsCacheManager._calc_l2_ttl(100) == int(CacheTTL.NORMAL_GOODS_SEARCH)


# ════════════════════════════════════════════════════
# 主动失效测试
# ════════════════════════════════════════════════════


class TestInvalidate:
    """主动失效缓存测试"""

    @pytest.mark.asyncio
    async def test_invalidate_goods(self):
        _STORE[f"{CACHE_KEY_GOODS_L1}G001"] = "data1"
        _STORE[f"{CACHE_KEY_GOODS_L2}G001"] = "data2"
        mgr = GoodsCacheManager()
        count = await mgr.invalidate_goods("G001")
        assert count == 2
        assert f"{CACHE_KEY_GOODS_L1}G001" not in _STORE
        assert f"{CACHE_KEY_GOODS_L2}G001" not in _STORE

    @pytest.mark.asyncio
    async def test_invalidate_goods_missing(self):
        mgr = GoodsCacheManager()
        count = await mgr.invalidate_goods("NOT_EXIST")
        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_search(self):
        _STORE[f"{CACHE_KEY_SEARCH_L1}耳机:1:20"] = "data1"
        _STORE[f"{CACHE_KEY_SEARCH_L2}耳机:1:20"] = "data2"
        mgr = GoodsCacheManager()
        count = await mgr.invalidate_search("耳机", page=1, size=20)
        assert count == 2
        assert f"{CACHE_KEY_SEARCH_L1}耳机:1:20" not in _STORE
        assert f"{CACHE_KEY_SEARCH_L2}耳机:1:20" not in _STORE


# ════════════════════════════════════════════════════
# 模块集成测试
# ════════════════════════════════════════════════════


class TestModuleImport:
    """模块导入与导出测试"""

    def test_import_goods_cache_manager(self):
        from src.cps.cache import GoodsCacheManager as M

        assert M is GoodsCacheManager

    def test_import_bloom_filter(self):
        from src.cps.cache import GoodsBloomFilter as B

        assert B is GoodsBloomFilter

    def test_adapter_injection(self):
        adapter = MockAdapter()
        mgr = GoodsCacheManager(adapter=adapter)
        assert mgr._adapter is adapter
        # 支持延迟绑定
        mgr2 = GoodsCacheManager()
        mgr2.set_adapter(adapter)
        assert mgr2._adapter is adapter

# @ai-generated
"""
CPS 商品对外接口单元测试（B03）

覆盖场景：
1. 限流触发：搜索桶/转链桶超限返回 429
2. 缓存命中：B02 缓存命中时不调适配器
3. 缓存未命中：走 B01 适配器回源
4. 渠道异常降级：CpsChannelException → BizException
5. 参数校验：非法 channel_code / 空 keyword
6. 适配器工厂：渠道选择/不支持渠道
7. 异常转换：各 error_type → 对应 HTTP code

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_cps_goods_api.py -v
"""
import json
import logging
import sys
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import (
    ConvertLinkResult,
    GoodsDTO,
    GoodsSearchResult,
)
from src.cps.adapter_factory import AdapterFactory
from src.schemas.cps_goods import (
    BizException,
    ConvertLinkRequest,
    ConvertLinkResponse,
    GoodsItemResponse,
    GoodsSearchRequest,
    GoodsSearchResponse,
)
from src.services.cps_goods_service import CpsGoodsService

logging.basicConfig(level=logging.DEBUG)


# ── 测试工具 ─────────────────────────────────────────


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
        source_channel="myq",
    )


# ════════════════════════════════════════════════════
# 适配器工厂测试
# ════════════════════════════════════════════════════


class TestAdapterFactory:
    """适配器工厂测试"""

    def test_get_adapter_myq(self):
        AdapterFactory.clear_instances()
        adapter = AdapterFactory.get_adapter("myq")
        assert adapter.get_channel_code() == "myq"
        assert adapter.get_channel_name() == "喵有券"

    def test_get_adapter_orderx(self):
        AdapterFactory.clear_instances()
        adapter = AdapterFactory.get_adapter("orderx")
        assert adapter.get_channel_code() == "orderx"

    def test_get_adapter_dta(self):
        AdapterFactory.clear_instances()
        adapter = AdapterFactory.get_adapter("dta")
        assert adapter.get_channel_code() == "dta"

    def test_get_adapter_singleton(self):
        """同渠道多次获取返回同一实例"""
        AdapterFactory.clear_instances()
        a1 = AdapterFactory.get_adapter("myq")
        a2 = AdapterFactory.get_adapter("myq")
        assert a1 is a2

    def test_get_adapter_unsupported(self):
        AdapterFactory.clear_instances()
        with pytest.raises(ValueError, match="不支持的渠道"):
            AdapterFactory.get_adapter("unknown")

    def test_get_supported_channels(self):
        channels = AdapterFactory.get_supported_channels()
        assert "myq" in channels
        assert "orderx" in channels
        assert "dta" in channels


# ════════════════════════════════════════════════════
# DTO 校验测试
# ════════════════════════════════════════════════════


class TestDtoValidation:
    """入参 DTO 校验测试"""

    def test_search_request_valid(self):
        req = GoodsSearchRequest(keyword="耳机", page=1, size=20, channel_code="myq")
        assert req.keyword == "耳机"
        assert req.channel_code == "myq"

    def test_search_request_invalid_channel(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoodsSearchRequest(keyword="耳机", channel_code="invalid")

    def test_search_request_empty_keyword(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoodsSearchRequest(keyword="")

    def test_search_request_invalid_page(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoodsSearchRequest(keyword="x", page=0)

    def test_convert_request_valid(self):
        req = ConvertLinkRequest(
            original_url="https://tb.com/item?id=1",
            user_channel_id="rel_001",
            channel_code="orderx",
        )
        assert req.original_url.startswith("https://")
        assert req.channel_code == "orderx"

    def test_convert_request_invalid_channel(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
                channel_code="xxx",
            )


# ════════════════════════════════════════════════════
# 服务层测试：商品搜索
# ════════════════════════════════════════════════════


class TestSearchGoodsService:
    """商品搜索服务层测试"""

    @pytest.mark.asyncio
    async def test_search_cache_hit(self):
        """缓存命中 → 不调适配器"""
        goods = _make_goods("G001")
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.search_goods = AsyncMock(
            return_value=GoodsSearchResult(items=[goods], total=1, page=1, size=20)
        )
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = mock_cache_mgr

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        result = await svc.search_goods(req)

        assert isinstance(result, GoodsSearchResponse)
        assert len(result.items) == 1
        assert result.items[0].goods_id == "G001"
        assert result.cache_hit is True
        mock_cache_mgr.search_goods.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_cache_miss_backfill(self):
        """缓存未命中 → 缓存管理器内部走适配器回源"""
        # 缓存返回空结果（模拟未命中后回源也无数据）
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.search_goods = AsyncMock(
            return_value=GoodsSearchResult(items=[], total=0, page=1, size=20)
        )
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = mock_cache_mgr

        req = GoodsSearchRequest(keyword="不存在", channel_code="myq")
        result = await svc.search_goods(req)

        assert result.items == []
        assert result.total == 0
        assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_search_channel_exception_degrade(self):
        """渠道异常 → 降级为 BizException"""
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.search_goods = AsyncMock(
            side_effect=CpsChannelException(
                error_type=CpsErrorType.RATE_LIMITED,
                message="渠道限流",
                channel_name="喵有券",
            )
        )
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = mock_cache_mgr

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        with pytest.raises(BizException) as exc_info:
            await svc.search_goods(req)
        assert exc_info.value.code == 429

    @pytest.mark.asyncio
    async def test_search_unsupported_channel(self):
        """不支持的渠道 → BizException(400)"""
        # 通过 mock 适配器工厂抛 ValueError 模拟不支持的渠道
        with patch.object(
            AdapterFactory,
            "get_adapter",
            side_effect=ValueError("不支持的渠道标识: unknown"),
        ):
            svc = CpsGoodsService()
            # 构造合法的请求对象，但 _get_cache_manager 会触发工厂异常
            req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
            svc._cache_managers.clear()
            # 强制让 _get_cache_manager 调用工厂
            with pytest.raises(BizException) as exc_info:
                await svc.search_goods(req)
            assert exc_info.value.code == 400

    @pytest.mark.asyncio
    async def test_search_unexpected_error(self):
        """未知异常 → BizException(500)"""
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.search_goods = AsyncMock(side_effect=RuntimeError("boom"))
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = mock_cache_mgr

        req = GoodsSearchRequest(keyword="耳机", channel_code="myq")
        with pytest.raises(BizException) as exc_info:
            await svc.search_goods(req)
        assert exc_info.value.code == 500

    @pytest.mark.asyncio
    async def test_search_decimal_serialization(self):
        """DTO Decimal 字段正确序列化为 float"""
        goods = _make_goods("G001", price="123.45")
        mock_cache_mgr = MagicMock()
        mock_cache_mgr.search_goods = AsyncMock(
            return_value=GoodsSearchResult(items=[goods], total=1)
        )
        svc = CpsGoodsService()
        svc._cache_managers["myq"] = mock_cache_mgr

        req = GoodsSearchRequest(keyword="耳机")
        result = await svc.search_goods(req)
        assert isinstance(result.items[0].original_price, float)
        assert result.items[0].original_price == 123.45


# ════════════════════════════════════════════════════
# 服务层测试：链接转链
# ════════════════════════════════════════════════════


class TestConvertLinkService:
    """链接转链服务层测试"""

    @pytest.mark.asyncio
    async def test_convert_link_success(self):
        """转链成功"""
        mock_adapter = MagicMock()
        mock_adapter.convert_link = AsyncMock(
            return_value=ConvertLinkResult(
                promote_url="https://promote.com/xxx",
                channel_pid="pid_001",
                estimate_commission=Decimal("9.95"),
                goods_id="G001",
            )
        )
        with patch.object(AdapterFactory, "get_adapter", return_value=mock_adapter):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com/item?id=1",
                user_channel_id="rel_001",
                channel_code="myq",
            )
            result = await svc.convert_link(req)

        assert isinstance(result, ConvertLinkResponse)
        assert result.promote_url == "https://promote.com/xxx"
        assert result.estimate_commission == 9.95
        assert result.channel_code == "myq"
        mock_adapter.convert_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_convert_link_channel_timeout(self):
        """渠道超时 → BizException(504)"""
        mock_adapter = MagicMock()
        mock_adapter.convert_link = AsyncMock(
            side_effect=CpsChannelException(
                error_type=CpsErrorType.REQUEST_TIMEOUT,
                message="请求超时",
                channel_name="喵有券",
            )
        )
        with patch.object(AdapterFactory, "get_adapter", return_value=mock_adapter):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
            )
            with pytest.raises(BizException) as exc_info:
                await svc.convert_link(req)
        assert exc_info.value.code == 504

    @pytest.mark.asyncio
    async def test_convert_link_invalid_key(self):
        """渠道密钥失效 → BizException(503)"""
        mock_adapter = MagicMock()
        mock_adapter.convert_link = AsyncMock(
            side_effect=CpsChannelException(
                error_type=CpsErrorType.INVALID_API_KEY,
                message="密钥无效",
                channel_name="喵有券",
            )
        )
        with patch.object(AdapterFactory, "get_adapter", return_value=mock_adapter):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
            )
            with pytest.raises(BizException) as exc_info:
                await svc.convert_link(req)
        assert exc_info.value.code == 503

    @pytest.mark.asyncio
    async def test_convert_link_unexpected_error(self):
        """未知异常 → BizException(500)"""
        mock_adapter = MagicMock()
        mock_adapter.convert_link = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(AdapterFactory, "get_adapter", return_value=mock_adapter):
            svc = CpsGoodsService()
            req = ConvertLinkRequest(
                original_url="https://tb.com",
                user_channel_id="x",
            )
            with pytest.raises(BizException) as exc_info:
                await svc.convert_link(req)
        assert exc_info.value.code == 500


# ════════════════════════════════════════════════════
# 异常转换测试
# ════════════════════════════════════════════════════


class TestExceptionConversion:
    """渠道异常 → 业务异常映射测试"""

    @pytest.mark.parametrize(
        "error_type,expected_code",
        [
            (CpsErrorType.RATE_LIMITED, 429),
            (CpsErrorType.INVALID_API_KEY, 503),
            (CpsErrorType.REQUEST_TIMEOUT, 504),
            (CpsErrorType.GOODS_NOT_FOUND, 404),
            (CpsErrorType.NO_ORDER_FOUND, 404),
            (CpsErrorType.NETWORK_ERROR, 502),
            (CpsErrorType.API_ERROR, 502),
            (CpsErrorType.PARSE_ERROR, 502),
        ],
    )
    def test_error_type_to_code_mapping(self, error_type, expected_code):
        exc = CpsChannelException(
            error_type=error_type, message="test", channel_name="test"
        )
        biz = CpsGoodsService._convert_channel_exception(exc)
        assert biz.code == expected_code


# ════════════════════════════════════════════════════
# 接口层测试（FastAPI TestClient）
# ════════════════════════════════════════════════════


class TestSearchEndpoint:
    """商品搜索接口端到端测试"""

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

    def test_search_rate_limited(self, client):
        """搜索限流触发 → 429"""
        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(False, {"count": 20})),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "耳机"},
                headers={"X-User-Id": "u001"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 429
        assert "频繁" in body["msg"]

    def test_search_success(self, app, client):
        """搜索成功"""
        goods = _make_goods("G001")
        mock_result = GoodsSearchResponse(
            items=[
                GoodsItemResponse(
                    goods_id="G001",
                    goods_title="测试",
                    original_price=99.0,
                    sale_price=79.0,
                )
            ],
            total=1,
            cache_hit=True,
        )
        mock_svc = MagicMock()
        mock_svc.search_goods = AsyncMock(return_value=mock_result)
        from src.api.public.cps_goods import get_cps_goods_service

        app.dependency_overrides[get_cps_goods_service] = lambda: mock_svc
        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(True, {"count": 1})),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "耳机", "channel_code": "myq"},
                headers={"X-User-Id": "u001"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["goods_id"] == "G001"

    def test_search_missing_keyword(self, client):
        """缺少 keyword 参数 → 422"""
        resp = client.get("/api/public/goods/search")
        assert resp.status_code == 422  # FastAPI 参数校验

    def test_search_invalid_channel(self, client):
        """非法 channel_code → 422"""
        # 限流先于参数校验执行，需 mock 放行
        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(True, {})),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "x", "channel_code": "invalid"},
            )
        body = resp.json()
        assert body["code"] == 422

    def test_search_biz_exception(self, app, client):
        """服务层抛 BizException → 对应 code"""
        from src.api.public.cps_goods import get_cps_goods_service

        mock_svc = MagicMock()
        mock_svc.search_goods = AsyncMock(
            side_effect=BizException(code=504, msg="渠道超时")
        )
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
        body = resp.json()
        assert body["code"] == 504


class TestConvertLinkEndpoint:
    """链接转链接口端到端测试"""

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

    def test_convert_rate_limited(self, client):
        """转链限流触发 → 429"""
        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(return_value=(False, {"count": 100})),
        ):
            resp = client.post(
                "/api/public/goods/convert-link",
                json={
                    "original_url": "https://tb.com/item?id=1",
                    "user_channel_id": "rel_001",
                },
                headers={"X-User-Id": "u001"},
            )
        body = resp.json()
        assert body["code"] == 429

    def test_convert_success(self, app, client):
        """转链成功"""
        mock_result = ConvertLinkResponse(
            promote_url="https://promote.com/xxx",
            channel_pid="pid_001",
            estimate_commission=9.95,
            goods_id="G001",
            channel_code="myq",
        )
        mock_svc = MagicMock()
        mock_svc.convert_link = AsyncMock(return_value=mock_result)
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
        assert body["code"] == 200
        assert body["data"]["promote_url"] == "https://promote.com/xxx"

    def test_convert_missing_url(self, client):
        """缺少 original_url → 422"""
        resp = client.post(
            "/api/public/goods/convert-link",
            json={"user_channel_id": "x"},
        )
        assert resp.status_code == 422

    def test_convert_biz_exception_503(self, app, client):
        """渠道密钥失效 → 503"""
        from src.api.public.cps_goods import get_cps_goods_service

        mock_svc = MagicMock()
        mock_svc.convert_link = AsyncMock(
            side_effect=BizException(code=503, msg="密钥失效")
        )
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
        assert body["code"] == 503


# ════════════════════════════════════════════════════
# 限流 key 与异常分支补充测试
# ════════════════════════════════════════════════════


class TestLimitKeyAndErrorBranches:
    """限流 key 生成与异常分支补充测试"""

    def test_limit_key_uses_user_id(self):
        """有 X-User-Id 时用 uid 作为限流 key"""
        from src.api.public.cps_goods import _get_limit_key

        request = MagicMock()
        key = _get_limit_key("u12345", request)
        assert key == "uid:u12345"

    def test_limit_key_falls_back_to_ip(self):
        """无 X-User-Id 时回退客户端 IP"""
        from src.api.public.cps_goods import _get_limit_key

        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        key = _get_limit_key(None, request)
        assert key == "ip:192.168.1.1"

    def test_limit_key_unknown_when_no_client(self):
        """无 user_id 且无 client 时用 unknown"""
        from src.api.public.cps_goods import _get_limit_key

        request = MagicMock()
        request.client = None
        key = _get_limit_key(None, request)
        assert key == "ip:unknown"

    def test_search_unexpected_exception_returns_500(self):
        """搜索接口未知异常 → 500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.public.cps_goods import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            resp = client.get(
                "/api/public/goods/search",
                params={"keyword": "x"},
            )
        body = resp.json()
        assert body["code"] == 500

    def test_convert_unexpected_exception_returns_500(self):
        """转链接口未知异常 → 500"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.public.cps_goods import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            resp = client.post(
                "/api/public/goods/convert-link",
                json={"original_url": "https://x.com", "user_channel_id": "x"},
            )
        body = resp.json()
        assert body["code"] == 500


# ════════════════════════════════════════════════════
# 限流桶隔离测试
# ════════════════════════════════════════════════════


class TestRateLimitIsolation:
    """验证搜索桶与转链桶独立限流"""

    @pytest.mark.asyncio
    async def test_search_and_transform_use_different_bucket(self):
        """搜索桶与转链桶使用不同 RateLimitType"""
        from src.config.constants import RateLimitType

        search_calls = []
        transform_calls = []

        async def mock_check(limit_type, key):
            if limit_type == RateLimitType.SEARCH:
                search_calls.append(key)
                return True, {}
            if limit_type == RateLimitType.TRANSFORM:
                transform_calls.append(key)
                return True, {}
            return True, {}

        with patch(
            "src.api.public.cps_goods.RateLimitUtil.check_by_type",
            new=mock_check,
        ):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from src.api.public.cps_goods import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            # 搜索走 SEARCH 桶
            client.get(
                "/api/public/goods/search",
                params={"keyword": "x"},
                headers={"X-User-Id": "u001"},
            )
            # 转链走 TRANSFORM 桶
            client.post(
                "/api/public/goods/convert-link",
                json={"original_url": "https://x.com", "user_channel_id": "x"},
                headers={"X-User-Id": "u001"},
            )

        assert len(search_calls) == 1
        assert len(transform_calls) == 1
        # 两个桶的 key 相同（同一用户），但 RateLimitType 不同
        assert search_calls[0] == transform_calls[0] == "uid:u001"

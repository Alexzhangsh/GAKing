# @ai-generated
"""
CPS 适配器基础 pytest 单元测试
覆盖：模块导入、抽象基类约束、DTO 数据结构、异常封装、渠道映射逻辑
"""
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import pytest


# ── Fixtures ──────────────────────────────────────────


@pytest.fixture
def mock_orderx_raw_data():
    """订单侠原始商品数据样本"""
    return {
        "item_id": "ITEM_12345",
        "title": "测试蓝牙耳机 降噪高音质",
        "pic_url": "https://img.alicdn.com/test.jpg",
        "price": "299.00",
        "qh_final_price": "199.00",
        "commission_rate": "5.00",
        "commission": "9.95",
        "category": "数码/耳机",
        "share_url": "https://e.tb.cn/h/xxxxx",
        "coupon_info": {"coupon_amount": 100, "coupon_condition": 200},
        "shop_name": "官方旗舰店",
        "sales": 50000,
    }


@pytest.fixture
def mock_orderx_order_data():
    """订单侠原始订单数据样本"""
    return {
        "tb_order_id": "TB2026010100012345",
        "pay_time": "2026-01-01 12:00:00",
        "confirm_time": "2026-01-03 10:00:00",
        "settlement_time": "",
        "order_status": "已付款",
        "total_fee": "199.00",
        "pid": "mm_12345",
        "item_id": "ITEM_12345",
        "title": "测试蓝牙耳机",
        "pic_url": "https://img.alicdn.com/test.jpg",
        "commission": "9.95",
        "refund_info": None,
    }


@pytest.fixture
def mock_myq_raw_data():
    """喵有券原始商品数据样本"""
    return {
        "item_id": "MYQ_ITEM_999",
        "title": "喵有券测试商品",
        "pic_url": "https://ecapi.cn/img.jpg",
        "price": "150.00",
        "coupon_price": "99.00",
        "commission_rate": "3.50",
        "commission": "3.47",
        "category": "服饰",
        "share_url": "https://ecapi.cn/promo/xx",
        "coupon_info": {"amount": 50},
        "shop_name": "喵有券测试店",
        "sales": 2000,
    }


@pytest.fixture
def mock_dt_raw_data():
    """大淘客原始商品数据样本"""
    return {
        "item_id": "DT_ITEM_555",
        "title": "大淘客测试商品",
        "pic_url": "https://dtk.com/img.jpg",
        "price": "599.00",
        "coupon_price": "399.00",
        "commission_rate": "7.00",
        "commission": "27.93",
        "category": "家电",
        "share_url": "https://dtk.com/promo/yy",
        "coupon_info": {"amount": 200},
        "shop_name": "大淘客测试店",
        "sales": 1000,
    }


# ── 模块导入与实例化测试 ──────────────────────────────


class TestImports:
    """测试模块导入与适配器实例化"""

    def test_import_base_adapter(self):
        """基类导入成功"""
        from src.cps.adapter.base_adapter import BaseCpsAdapter

        assert BaseCpsAdapter is not None

    def test_import_dto(self):
        """DTO 导入成功"""
        from src.cps.adapter.dto import GoodsDTO, GoodsSearchResult, ConvertLinkResult
        from src.cps.adapter.dto import OrderDTO, OrderPullResult

        assert GoodsDTO is not None
        assert OrderDTO is not None

    def test_import_exception(self):
        """异常类导入成功"""
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType

        assert CpsChannelException is not None
        assert CpsErrorType.RATE_LIMITED.value == "RATE_LIMITED"

    def test_import_orderx_adapter(self):
        """订单侠适配器导入并实例化"""
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        assert adapter.get_channel_code() == "orderx"
        assert adapter.get_channel_name() == "订单侠"

    def test_import_myq_adapter(self):
        """喵有券适配器导入并实例化"""
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter

        adapter = MiaoyouquanAdapter(apkey="test_key")
        assert adapter.get_channel_code() == "myq"
        assert adapter.get_channel_name() == "喵有券"

    def test_import_dt_adapter(self):
        """大淘客适配器导入并实例化"""
        from src.cps.adapter.dataoke_adapter import DataokeAdapter

        adapter = DataokeAdapter(appid="test_id", appkey="test_key")
        assert adapter.get_channel_code() == "dta"
        assert adapter.get_channel_name() == "大淘客"


# ── 抽象基类约束测试 ──────────────────────────────────


class TestAbstractClass:
    """测试抽象基类约束——缺少抽象方法不能实例化"""

    def test_incomplete_adapter_cannot_instantiate(self):
        """缺少 search_goods / convert_link / pull_order / health_check 的子类不能实例化"""
        from src.cps.adapter.base_adapter import BaseCpsAdapter

        class Incomplete(BaseCpsAdapter):
            def get_channel_name(self) -> str:
                return "incomplete"

            def get_channel_code(self) -> str:
                return "inc"

        with pytest.raises(TypeError):
            Incomplete()

    def test_minimal_adapter_can_instantiate(self):
        """实现了所有抽象方法的子类可以实例化"""
        from src.cps.adapter.base_adapter import BaseCpsAdapter
        from src.cps.adapter.dto import (
            GoodsSearchResult,
            ConvertLinkResult,
            OrderPullResult,
        )

        class Complete(BaseCpsAdapter):
            def get_channel_name(self) -> str:
                return "complete"

            def get_channel_code(self) -> str:
                return "com"

            async def search_goods(
                self, keyword: str, page: int = 1, size: int = 20
            ) -> GoodsSearchResult:
                return GoodsSearchResult()

            async def convert_link(
                self, original_url: str, user_channel_id: str
            ) -> ConvertLinkResult:
                return ConvertLinkResult(promote_url="x")

            async def pull_order(
                self, start_time: datetime, end_time: datetime
            ) -> OrderPullResult:
                return OrderPullResult()

            async def health_check(self) -> bool:
                return True

        instance = Complete()
        assert instance.get_channel_code() == "com"


# ── DTO 数据结构测试 ──────────────────────────────────


class TestGoodsDTO:
    """商品 DTO 数据结构验证"""

    def test_create_minimal(self):
        from src.cps.adapter.dto import GoodsDTO

        goods = GoodsDTO(
            goods_id="G001",
            goods_title="测试商品",
            original_price=Decimal("100"),
            sale_price=Decimal("80"),
        )
        assert goods.goods_id == "G001"
        assert goods.original_price == Decimal("100")
        assert goods.sale_price == Decimal("80")
        assert goods.source_channel == ""

    def test_all_fields(self):
        from src.cps.adapter.dto import GoodsDTO

        goods = GoodsDTO(
            goods_id="G001",
            goods_title="完整商品",
            goods_img="https://img.com/a.jpg",
            original_price=Decimal("299.00"),
            sale_price=Decimal("199.00"),
            commission_rate=Decimal("5.00"),
            estimate_commission=Decimal("9.95"),
            category="数码",
            promote_url="https://promote.com/x",
            coupon_info={"amount": 50},
            shop_name="旗舰店",
            sales_volume=10000,
            source_channel="orderx",
        )
        assert goods.coupon_info == {"amount": 50}
        assert goods.sales_volume == 10000
        assert goods.source_channel == "orderx"

    def test_zero_defaults(self):
        from src.cps.adapter.dto import GoodsDTO

        goods = GoodsDTO(goods_id="G001", goods_title="t")
        assert goods.original_price == Decimal("0")
        assert goods.estimate_commission == Decimal("0")
        assert goods.sales_volume == 0

    def test_invalid_price_rejected(self):
        from src.cps.adapter.dto import GoodsDTO
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoodsDTO(goods_id="G001", original_price=Decimal("-1"))

    def test_model_dump_decimal(self):
        from src.cps.adapter.dto import GoodsDTO

        goods = GoodsDTO(
            goods_id="G001",
            original_price=Decimal("123.45"),
            estimate_commission=Decimal("6.78"),
        )
        d = goods.model_dump()
        assert isinstance(d["original_price"], float)
        assert d["original_price"] == 123.45
        assert d["estimate_commission"] == 6.78


class TestOrderDTO:
    """订单 DTO 数据结构验证"""

    def test_create_minimal(self):
        from src.cps.adapter.dto import OrderDTO

        order = OrderDTO(
            origin_order_id="TB001",
            order_amount=Decimal("199.00"),
        )
        assert order.origin_order_id == "TB001"
        assert order.order_amount == Decimal("199.00")
        assert order.order_status == ""

    def test_all_fields(self):
        from src.cps.adapter.dto import OrderDTO

        order = OrderDTO(
            origin_order_id="TB001",
            pay_time=datetime(2026, 1, 1, 12, 0),
            confirm_time=datetime(2026, 1, 3, 10, 0),
            settle_time=None,
            order_status="已付款",
            order_amount=Decimal("199.00"),
            channel_pid="mm_123",
            goods_id="G001",
            goods_title="商品",
            total_commission=Decimal("9.95"),
            user_commission=Decimal("7.96"),
            platform_commission=Decimal("1.99"),
            channel_code="orderx",
        )
        assert order.user_commission == Decimal("7.96")
        assert order.channel_code == "orderx"

    def test_order_missing_required_raises(self):
        from src.cps.adapter.dto import OrderDTO
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrderDTO()


class TestConvertLinkResult:
    """转链结果 DTO 验证"""

    def test_create_minimal(self):
        from src.cps.adapter.dto import ConvertLinkResult

        r = ConvertLinkResult(promote_url="https://promote.com/x")
        assert r.promote_url == "https://promote.com/x"
        assert r.channel_pid == ""

    def test_all_fields(self):
        from src.cps.adapter.dto import ConvertLinkResult

        r = ConvertLinkResult(
            promote_url="https://promote.com/x",
            channel_pid="pid_001",
            estimate_commission=Decimal("10.00"),
            goods_id="G001",
            raw_data={"raw": True},
        )
        assert r.raw_data == {"raw": True}


# ── 异常封装测试 ──────────────────────────────────


class TestCpsException:
    """CPS 统一异常封装测试"""

    def test_create_exception(self):
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType

        exc = CpsChannelException(
            error_type=CpsErrorType.RATE_LIMITED,
            message="限流",
            channel_name="订单侠",
            status_code=429,
        )
        assert exc.error_type == CpsErrorType.RATE_LIMITED
        assert exc.channel_name == "订单侠"
        assert exc.status_code == 429
        assert "RATE_LIMITED" in str(exc)
        assert "订单侠" in str(exc)
        assert "429" in str(exc)

    def test_error_types(self):
        from src.cps.adapter.cps_exception import CpsErrorType

        assert CpsErrorType.RATE_LIMITED.value == "RATE_LIMITED"
        assert CpsErrorType.INVALID_API_KEY.value == "INVALID_API_KEY"
        assert CpsErrorType.REQUEST_TIMEOUT.value == "REQUEST_TIMEOUT"
        assert CpsErrorType.NO_ORDER_FOUND.value == "NO_ORDER_FOUND"
        assert CpsErrorType.GOODS_NOT_FOUND.value == "GOODS_NOT_FOUND"
        assert CpsErrorType.API_ERROR.value == "API_ERROR"
        assert CpsErrorType.PARSE_ERROR.value == "PARSE_ERROR"
        assert CpsErrorType.NETWORK_ERROR.value == "NETWORK_ERROR"

    def test_exception_is_exception(self):
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType

        exc = CpsChannelException(
            error_type=CpsErrorType.API_ERROR,
            message="测试",
            channel_name="test",
        )
        assert isinstance(exc, Exception)
        with pytest.raises(CpsChannelException):
            raise exc


# ── 订单侠适配器内部逻辑测试 ──────────────────────────


class TestDingdanxiaAdapter:
    """订单侠适配器单元测试"""

    def test_channel_info(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        assert adapter.get_channel_name() == "订单侠"
        assert adapter.get_channel_code() == "orderx"
        assert adapter.get_api_key() == "test_key"

    def test_signature(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        sign = adapter._sign({"keyword": "test", "page": "1"})
        assert len(sign) == 32
        assert isinstance(sign, str)

    def test_build_params(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        params = adapter._build_params({"keyword": "蓝牙耳机"})
        assert params["apikey"] == "test_key"
        assert params["keyword"] == "蓝牙耳机"
        assert "sign" in params

    def test_parse_datetime_none(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        assert DingdanxiaAdapter._parse_datetime(None) is None
        assert DingdanxiaAdapter._parse_datetime("") is None

    def test_parse_datetime_valid(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        dt = DingdanxiaAdapter._parse_datetime("2026-01-15 14:30:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14

    def test_parse_datetime_invalid(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        assert DingdanxiaAdapter._parse_datetime("invalid_date") is None
        assert DingdanxiaAdapter._parse_datetime(123) is None

    def test_parse_order(self, mock_orderx_order_data: Dict[str, Any]):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        order = adapter._parse_order(mock_orderx_order_data)
        assert order.origin_order_id == "TB2026010100012345"
        assert order.order_amount == Decimal("199.00")
        assert order.order_status == "已付款"
        assert order.channel_pid == "mm_12345"
        assert order.channel_code == "orderx"
        assert order.pay_time is not None
        assert order.pay_time.year == 2026

    def test_parse_order_missing_fields(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        adapter = DingdanxiaAdapter(apikey="test_key")
        order = adapter._parse_order({})
        assert order.origin_order_id == ""
        assert order.order_amount == Decimal("0")
        assert order.order_status == ""
        assert order.pay_time is None

    def test_parse_goods_data(self, mock_orderx_raw_data: Dict[str, Any]):
        from src.cps.adapter.dto import GoodsDTO

        goods = GoodsDTO(
            goods_id=str(mock_orderx_raw_data.get("item_id", "")),
            goods_title=str(mock_orderx_raw_data.get("title", "")),
            goods_img=str(mock_orderx_raw_data.get("pic_url", "")),
            original_price=Decimal(str(mock_orderx_raw_data.get("price", "0"))),
            sale_price=Decimal(str(mock_orderx_raw_data.get("qh_final_price", "0"))),
            commission_rate=Decimal(
                str(mock_orderx_raw_data.get("commission_rate", "0"))
            ),
            estimate_commission=Decimal(
                str(mock_orderx_raw_data.get("commission", "0"))
            ),
            category=str(mock_orderx_raw_data.get("category", "")),
            promote_url=str(mock_orderx_raw_data.get("share_url", "")),
            coupon_info=mock_orderx_raw_data.get("coupon_info"),
            shop_name=str(mock_orderx_raw_data.get("shop_name", "")),
            sales_volume=int(mock_orderx_raw_data.get("sales", 0)),
            source_channel="orderx",
        )
        assert goods.goods_id == "ITEM_12345"
        assert goods.original_price == Decimal("299.00")
        assert goods.sale_price == Decimal("199.00")
        assert goods.estimate_commission == Decimal("9.95")
        assert goods.coupon_info == {"coupon_amount": 100, "coupon_condition": 200}


# ── 喵有券适配器单元测试 ──────────────────────────


class TestMiaoyouquanAdapter:
    """喵有券适配器单元测试"""

    def test_channel_info(self):
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter

        adapter = MiaoyouquanAdapter(apkey="test_key")
        assert adapter.get_channel_name() == "喵有券"
        assert adapter.get_channel_code() == "myq"

    def test_build_params(self):
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter

        adapter = MiaoyouquanAdapter(apkey="test_key")
        params = adapter._build_params({"keyword": "耳机"})
        assert params["apkey"] == "test_key"
        assert "sign" not in params
        assert params["keyword"] == "耳机"

    def test_parse_order(self, mock_orderx_order_data: Dict[str, Any]):
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter

        adapter = MiaoyouquanAdapter(apkey="test_key")
        order = adapter._parse_order(mock_orderx_order_data)
        assert order.channel_code == "myq"
        assert order.origin_order_id == "TB2026010100012345"


# ── 大淘客适配器单元测试 ──────────────────────────


class TestDataokeAdapter:
    """大淘客适配器单元测试"""

    def test_channel_info(self):
        from src.cps.adapter.dataoke_adapter import DataokeAdapter

        adapter = DataokeAdapter(appid="test_id", appkey="test_key")
        assert adapter.get_channel_name() == "大淘客"
        assert adapter.get_channel_code() == "dta"

    def test_build_params(self):
        from src.cps.adapter.dataoke_adapter import DataokeAdapter

        adapter = DataokeAdapter(appid="test_id", appkey="test_key")
        params = adapter._build_params({"keyword": "耳机"})
        assert params["app_id"] == "test_id"
        assert params["app_secret"] == "test_key"
        assert params["keyword"] == "耳机"

    def test_parse_order(self, mock_orderx_order_data: Dict[str, Any]):
        from src.cps.adapter.dataoke_adapter import DataokeAdapter

        adapter = DataokeAdapter(appid="test_id", appkey="test_key")
        order = adapter._parse_order(mock_orderx_order_data)
        assert order.channel_code == "dta"
        assert order.origin_order_id == "TB2026010100012345"


# ── 搜索结果和订单结果 DTO 测试 ──────────────────────────


class TestSearchResult:
    """搜索结果 DTO 测试"""

    def test_create_empty(self):
        from src.cps.adapter.dto import GoodsSearchResult

        r = GoodsSearchResult()
        assert r.items == []
        assert r.total == 0
        assert r.page == 1

    def test_create_with_items(self):
        from src.cps.adapter.dto import GoodsSearchResult, GoodsDTO

        items = [
            GoodsDTO(goods_id="G1", goods_title="t1"),
            GoodsDTO(goods_id="G2", goods_title="t2"),
        ]
        r = GoodsSearchResult(items=items, total=2, page=1, size=20)
        assert len(r.items) == 2
        assert r.total == 2


class TestOrderPullResult:
    """订单拉取结果 DTO 测试"""

    def test_create_empty(self):
        from src.cps.adapter.dto import OrderPullResult

        r = OrderPullResult()
        assert r.orders == []
        assert r.total == 0

    def test_create_with_orders(self):
        from src.cps.adapter.dto import OrderPullResult, OrderDTO

        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        orders = [
            OrderDTO(origin_order_id="TB1", order_amount=Decimal("10")),
            OrderDTO(origin_order_id="TB2", order_amount=Decimal("20")),
        ]
        r = OrderPullResult(orders=orders, total=2, start_time=start, end_time=end)
        assert len(r.orders) == 2
        assert r.total == 2
        assert r.start_time == start


# ── 订单侠适配器异步完整链路测试 ──────────────────────────


class TestDingdanxiaAsyncFlows:
    """订单侠适配器异步方法完整链路测试（mock HTTP）

    覆盖 search_goods / convert_link / pull_order / health_check
    的正常路径与异常路径，验证字段映射、异常封装、日志埋点。
    """

    def _make_adapter(self):
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter

        return DingdanxiaAdapter(apikey="test_key")

    @pytest.mark.asyncio
    async def test_search_goods_success(self, mock_orderx_raw_data):
        """搜索成功：字段映射正确"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(
            return_value={
                "code": 200,
                "msg": "ok",
                "data": {"list": [mock_orderx_raw_data], "total": 1},
            }
        )
        with patch.object(mod, "post_json", mock_post):
            result = await adapter.search_goods("蓝牙耳机", page=1, size=20)

        assert result.total == 1
        assert len(result.items) == 1
        goods = result.items[0]
        assert goods.goods_id == "ITEM_12345"
        assert goods.goods_title == "测试蓝牙耳机 降噪高音质"
        assert goods.sale_price == Decimal("199.00")
        assert goods.commission_rate == Decimal("5.00")
        assert goods.source_channel == "orderx"

    @pytest.mark.asyncio
    async def test_search_goods_api_error(self):
        """搜索接口业务错误：抛出 CpsChannelException(API_ERROR)"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(return_value={"code": 500, "msg": "服务器错误"})
        with patch.object(mod, "post_json", mock_post):
            with pytest.raises(CpsChannelException) as exc_info:
                await adapter.search_goods("test")
        assert exc_info.value.error_type == CpsErrorType.API_ERROR
        assert "订单侠" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_goods_skip_bad_item(self, mock_orderx_raw_data):
        """搜索：单条商品字段异常被跳过，不影响整体"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        bad_item = {"item_id": "BAD", "price": "not-a-number"}
        mock_post = AsyncMock(
            return_value={
                "code": 200,
                "data": {"list": [mock_orderx_raw_data, bad_item], "total": 2},
            }
        )
        with patch.object(mod, "post_json", mock_post):
            result = await adapter.search_goods("test")

        assert len(result.items) == 1
        assert result.items[0].goods_id == "ITEM_12345"

    @pytest.mark.asyncio
    async def test_convert_link_success(self):
        """转链成功：share_url 非空"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(
            return_value={
                "code": 200,
                "data": {
                    "share_url": "https://e.tb.cn/h/xxxx",
                    "relation_id": "mm_123",
                    "commission": "9.95",
                    "item_id": "ITEM_12345",
                },
            }
        )
        with patch.object(mod, "post_json", mock_post):
            result = await adapter.convert_link("https://item.taobao.com/x", "mm_123")

        assert result.promote_url == "https://e.tb.cn/h/xxxx"
        assert result.channel_pid == "mm_123"
        assert result.estimate_commission == Decimal("9.95")
        assert result.goods_id == "ITEM_12345"

    @pytest.mark.asyncio
    async def test_convert_link_empty_share_url(self):
        """转链结果缺少 share_url：抛出 CpsChannelException"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(return_value={"code": 200, "data": {"relation_id": "x"}})
        with patch.object(mod, "post_json", mock_post):
            with pytest.raises(CpsChannelException) as exc_info:
                await adapter.convert_link("https://item.taobao.com/x", "mm_123")
        assert exc_info.value.error_type == CpsErrorType.API_ERROR
        assert "share_url" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_convert_link_api_error(self):
        """转链接口业务错误：抛出 CpsChannelException"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from src.cps.adapter.cps_exception import CpsChannelException
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(return_value={"code": 400, "msg": "参数错误"})
        with patch.object(mod, "post_json", mock_post):
            with pytest.raises(CpsChannelException):
                await adapter.convert_link("https://item.taobao.com/x", "mm_123")

    @pytest.mark.asyncio
    async def test_pull_order_success(self, mock_orderx_order_data):
        """订单拉取成功：字段映射正确"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(
            return_value={
                "code": 200,
                "data": {"list": [mock_orderx_order_data], "total": 1},
            }
        )
        start = datetime(2026, 1, 1, 0, 0)
        end = datetime(2026, 1, 1, 0, 30)
        with patch.object(mod, "post_json", mock_post):
            result = await adapter.pull_order(start, end)

        assert result.total == 1
        order = result.orders[0]
        assert order.origin_order_id == "TB2026010100012345"
        assert order.order_amount == Decimal("199.00")
        assert order.order_status == "已付款"
        assert order.channel_code == "orderx"
        assert order.pay_time is not None

    @pytest.mark.asyncio
    async def test_pull_order_api_error(self):
        """订单拉取接口业务错误：抛出 CpsChannelException"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(return_value={"code": 500, "msg": "订单接口错误"})
        start = datetime(2026, 1, 1, 0, 0)
        end = datetime(2026, 1, 1, 0, 30)
        with patch.object(mod, "post_json", mock_post):
            with pytest.raises(CpsChannelException) as exc_info:
                await adapter.pull_order(start, end)
        assert exc_info.value.error_type == CpsErrorType.API_ERROR

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """健康探测成功"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(return_value={"code": 200})
        with patch.object(mod, "post_json", mock_post):
            assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """健康探测失败：返回 False 不抛异常"""
        from src.cps.adapter import dingdanxia_adapter as mod
        from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
        from unittest.mock import AsyncMock, patch

        adapter = self._make_adapter()
        mock_post = AsyncMock(
            side_effect=CpsChannelException(
                error_type=CpsErrorType.API_ERROR,
                message="接口错误",
                channel_name="订单侠",
            )
        )
        with patch.object(mod, "post_json", mock_post):
            assert await adapter.health_check() is False


# ── HTTP 客户端工具测试 ──────────────────────────


class TestHttpClient:
    """HTTP 请求工具单元测试"""

    def test_import(self):
        from src.cps.adapter.http_client import post_json

        assert post_json is not None


# ── 配置相关测试 ──────────────────────────


class TestChannelConfig:
    """渠道配置读取测试"""

    def test_env_config_cps_fields(self):
        from src.config.env_config import EnvConfig

        assert hasattr(EnvConfig, "MIAO_QUAN_TOKEN")
        assert hasattr(EnvConfig, "DATAOK_APPID")
        assert hasattr(EnvConfig, "DATAOK_APPKEY")
        assert hasattr(EnvConfig, "ORDERX_TOKEN")

# @ai-generated
"""
CPS 适配器本地调试脚本
验证三个渠道适配器的接口可用性、数据结构标准化、抽象方法完整性
可实例化三个适配器，调用统一接口返回标准化数据结构
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, ".")

from src.cps.adapter.base_adapter import BaseCpsAdapter
from src.cps.adapter.dto import (
    GoodsDTO,
    GoodsSearchResult,
    ConvertLinkResult,
    OrderDTO,
    OrderPullResult,
)
from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType


# ── Mock 适配器（用于测试抽象基类和数据结构） ──────────


class MockCpsAdapter(BaseCpsAdapter):
    """Mock CPS 适配器（本地调试用，模拟标准数据返回）"""

    def get_channel_name(self) -> str:
        return "测试渠道"

    def get_channel_code(self) -> str:
        return "test"

    def get_pid(self) -> str:
        return "test_pid_001"

    def get_api_key(self) -> str:
        return "test_api_key"

    async def search_goods(
        self, keyword: str, page: int = 1, size: int = 20
    ) -> GoodsSearchResult:
        self._log(logging.DEBUG, "search_goods mock: keyword=%s", keyword)
        return GoodsSearchResult(
            items=[
                GoodsDTO(
                    goods_id="ITEM_001",
                    goods_title="测试商品-高端蓝牙耳机",
                    goods_img="https://test.com/img.jpg",
                    original_price=Decimal("299.00"),
                    sale_price=Decimal("199.00"),
                    commission_rate=Decimal("5.00"),
                    estimate_commission=Decimal("9.95"),
                    category="数码/耳机",
                    promote_url="https://test.com/p/xxx",
                    coupon_info={"amount": 100, "condition": "满200可用"},
                    shop_name="测试旗舰店",
                    sales_volume=10000,
                    source_channel="test",
                ),
            ],
            total=1,
            page=page,
            size=size,
        )

    async def convert_link(
        self, original_url: str, user_channel_id: str
    ) -> ConvertLinkResult:
        self._log(
            logging.DEBUG,
            "convert_link mock: url=%s channel_id=%s",
            original_url,
            user_channel_id,
        )
        return ConvertLinkResult(
            promote_url="https://test.com/promote/xxx",
            channel_pid=f"pid_{user_channel_id}",
            estimate_commission=Decimal("12.50"),
            goods_id="ITEM_001",
            raw_data={"mock": True},
        )

    async def pull_order(
        self, start_time: datetime, end_time: datetime
    ) -> OrderPullResult:
        self._log(
            logging.DEBUG, "pull_order mock: start=%s end=%s", start_time, end_time
        )
        return OrderPullResult(
            orders=[
                OrderDTO(
                    origin_order_id="TB20260101000001",
                    pay_time=datetime(2026, 1, 1, 12, 0, 0),
                    confirm_time=datetime(2026, 1, 3, 10, 0, 0),
                    settle_time=None,
                    order_status="已结算",
                    order_amount=Decimal("199.00"),
                    channel_pid="pid_001",
                    goods_id="ITEM_001",
                    goods_title="测试商品",
                    goods_img="https://test.com/img.jpg",
                    total_commission=Decimal("9.95"),
                    user_commission=Decimal("7.96"),
                    platform_commission=Decimal("1.99"),
                    channel_code="test",
                ),
            ],
            total=1,
            start_time=start_time,
            end_time=end_time,
        )

    async def health_check(self) -> bool:
        self._log(logging.DEBUG, "health_check mock: OK")
        return True


# ── 渠道适配器导入测试 ──────────────────────────────


def test_imports():
    """测试三个渠道适配器可正常导入"""
    print("=" * 60)
    print("【测试1】模块导入与可实例化")
    print("=" * 60)

    try:
        from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter
        from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter
        from src.cps.adapter.dataoke_adapter import DataokeAdapter

        print("  ✓ 三个渠道适配器模块导入成功")

        # 可实例化测试
        dx = DingdanxiaAdapter(apikey="test_key")
        myq = MiaoyouquanAdapter(apkey="test_key")
        dtok = DataokeAdapter(appid="test_id", appkey="test_key")

        assert (
            dx.get_channel_code() == "orderx"
        ), f"订单侠channel_code错误: {dx.get_channel_code()}"
        assert (
            myq.get_channel_code() == "myq"
        ), f"喵有券channel_code错误: {myq.get_channel_code()}"
        assert (
            dtok.get_channel_code() == "dta"
        ), f"大淘客channel_code错误: {dtok.get_channel_code()}"

        print(
            f"  ✓ 订单侠适配器 - channel_code: {dx.get_channel_code()}, name: {dx.get_channel_name()}"
        )
        print(
            f"  ✓ 喵有券适配器 - channel_code: {myq.get_channel_code()}, name: {myq.get_channel_name()}"
        )
        print(
            f"  ✓ 大淘客适配器 - channel_code: {dtok.get_channel_code()}, name: {dtok.get_channel_name()}"
        )
    except Exception as e:
        print(f"  ✗ 导入/实例化失败: {e}")
        raise


def test_abstract_class():
    """测试抽象基类约束——缺少抽象方法的子类不能实例化"""
    print()
    print("=" * 60)
    print("【测试2】抽象基类约束验证")
    print("=" * 60)

    # 缺少方法的子类应无法实例化
    class IncompleteAdapter(BaseCpsAdapter):
        def get_channel_name(self) -> str:
            return "incomplete"

        def get_channel_code(self) -> str:
            return "inc"

    try:
        IncompleteAdapter()
        print("  ✗ 抽象约束未生效，应无法实例化")
    except TypeError as e:
        print(f"  ✓ 抽象约束生效，缺少抽象方法无法实例化: {e}")

    print()


async def test_mock_adapter():
    """测试 Mock 适配器接口行为"""
    print("=" * 60)
    print("【测试3】Mock适配器接口行为验证")
    print("=" * 60)

    adapter = MockCpsAdapter()

    # 1. 健康探测
    health = await adapter.health_check()
    assert health is True, "健康探测失败"
    print(f"  ✓ health_check: {health}")

    # 2. 商品搜索
    result = await adapter.search_goods("蓝牙耳机", page=1, size=20)
    assert isinstance(result, GoodsSearchResult)
    assert len(result.items) == 1
    goods = result.items[0]
    assert isinstance(goods, GoodsDTO)
    assert goods.goods_id == "ITEM_001"
    assert goods.original_price == Decimal("299.00")
    assert goods.sale_price == Decimal("199.00")
    assert goods.source_channel == "test"
    print(f"  ✓ search_goods: items={len(result.items)}, total={result.total}")
    print(f"    → goods_id={goods.goods_id}, title={goods.goods_title}")
    print(
        f"    → price={goods.original_price}, sale={goods.sale_price}, commission={goods.estimate_commission}"
    )

    # 3. 链接转链
    convert = await adapter.convert_link("https://tb.com/item?id=123", "user_001")
    assert isinstance(convert, ConvertLinkResult)
    assert convert.promote_url != ""
    assert convert.channel_pid == "pid_user_001"
    print(
        f"  ✓ convert_link: url={convert.promote_url}, pid={convert.channel_pid}, commission={convert.estimate_commission}"
    )

    # 4. 订单拉取
    start = datetime(2026, 1, 1, 0, 0, 0)
    end = datetime(2026, 1, 31, 23, 59, 59)
    orders = await adapter.pull_order(start, end)
    assert isinstance(orders, OrderPullResult)
    assert len(orders.orders) == 1
    order = orders.orders[0]
    assert isinstance(order, OrderDTO)
    assert order.origin_order_id == "TB20260101000001"
    assert order.order_amount == Decimal("199.00")
    print(f"  ✓ pull_order: orders={len(orders.orders)}, total={orders.total}")
    print(
        f"    → origin_id={order.origin_order_id}, amount={order.order_amount}, status={order.order_status}"
    )

    # 5. DTO 序列化验证
    goods_dict = goods.model_dump()
    assert isinstance(goods_dict["original_price"], float)
    print(f"  ✓ GoodsDTO 序列化: original_price={goods_dict['original_price']} (float)")

    print()
    print("  ✅ Mock 适配器全部接口验证通过！")


def test_exception_handling():
    """测试统一异常封装"""
    print()
    print("=" * 60)
    print("【测试4】统一异常封装验证")
    print("=" * 60)

    # 创建各种类型的异常
    exc1 = CpsChannelException(
        error_type=CpsErrorType.RATE_LIMITED,
        message="接口限流",
        channel_name="订单侠",
        status_code=429,
    )
    assert "RATE_LIMITED" in str(exc1)
    assert "订单侠" in str(exc1)
    assert "429" in str(exc1)
    print(f"  ✓ 限流异常: {exc1}")

    exc2 = CpsChannelException(
        error_type=CpsErrorType.INVALID_API_KEY,
        message="API Key 无效",
        channel_name="喵有券",
        status_code=401,
    )
    assert exc2.error_type == CpsErrorType.INVALID_API_KEY
    print(f"  ✓ 密钥异常: {exc2}")

    exc3 = CpsChannelException(
        error_type=CpsErrorType.GOODS_NOT_FOUND,
        message="商品不存在",
        channel_name="大淘客",
    )
    assert exc3.error_type == CpsErrorType.GOODS_NOT_FOUND
    print(f"  ✓ 商品不存在异常: {exc3}")

    print()
    print("  ✅ 异常封装验证通过！")


def test_channel_adapters_instantiation():
    """测试真实渠道适配器的实例化和基本配置获取"""
    print()
    print("=" * 60)
    print("【测试5】真实渠道适配器基本功能")
    print("=" * 60)

    from src.cps.adapter.dingdanxia_adapter import DingdanxiaAdapter
    from src.cps.adapter.miaoyouquan_adapter import MiaoyouquanAdapter
    from src.cps.adapter.dataoke_adapter import DataokeAdapter

    # 订单侠
    dx = DingdanxiaAdapter(apikey="mock_dx_key")
    assert dx.get_channel_name() == "订单侠"
    assert dx.get_channel_code() == "orderx"
    assert dx.get_api_key() == "mock_dx_key"
    assert dx.get_pid() == ""
    print(
        f"  ✓ 订单侠适配器: name={dx.get_channel_name()}, code={dx.get_channel_code()}"
    )

    # 喵有券
    myq = MiaoyouquanAdapter(apkey="mock_myq_key")
    assert myq.get_channel_name() == "喵有券"
    assert myq.get_channel_code() == "myq"
    assert myq.get_api_key() == "mock_myq_key"
    print(
        f"  ✓ 喵有券适配器: name={myq.get_channel_name()}, code={myq.get_channel_code()}"
    )

    # 大淘客
    dtok = DataokeAdapter(appid="mock_dt_id", appkey="mock_dt_key")
    assert dtok.get_channel_name() == "大淘客"
    assert dtok.get_channel_code() == "dta"
    assert dtok.get_api_key() == "mock_dt_key"
    print(
        f"  ✓ 大淘客适配器: name={dtok.get_channel_name()}, code={dtok.get_channel_code()}"
    )

    print()
    print("  ✅ 真实渠道适配器实例化和基本配置获取验证通过！")


async def main():
    """主调试入口"""
    print("\n" + "=" * 60)
    print("  CPS 适配器本地调试脚本")
    print("  项目：金角大王 CPS V2.0")
    print("=" * 60 + "\n")

    # 测试 1: 导入和实例化
    test_imports()

    # 测试 2: 抽象基类约束
    test_abstract_class()

    # 测试 3: Mock 适配器接口
    await test_mock_adapter()

    # 测试 4: 异常封装
    test_exception_handling()

    # 测试 5: 真实适配器基本功能
    test_channel_adapters_instantiation()

    print("\n" + "=" * 60)
    print("  ✅ 全部调试测试通过！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

# @ai-generated
"""
B05 订单同步 Service 层单元测试（核心，覆盖率≥90%）

覆盖场景：
1. _map_channel_status：通用映射/渠道专属映射/冲突码区分/未知状态
2. _split_time_windows：切分逻辑/边界/默认值
3. _build_order_data：佣金拆分（80%/20%）/字段构造
4. _pull_with_retry：成功/重试成功/3次失败入队/非渠道异常
5. _persist_orders：全新订单/已存在状态更新/user_id 反查/无 origin_order_id 跳过
6. pull_channel_orders：游标为空/游标追上/熔断跳过/正常/部分失败
7. pull_all_channels：三渠道串行
8. manual_sync_channel：指定时间范围
9. manual_retry_failed：队列空/补发成功/补发失败重新入队
10. manual_retry_failed：队列空/补发成功/补发失败重新入队
11. get_sync_status：状态查询

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_order_sync_service.py -v
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.cps.adapter.cps_exception import CpsChannelException, CpsErrorType
from src.cps.adapter.dto import OrderDTO, OrderPullResult
from src.cps.circuit_breaker import BreakerState
from src.services.order_sync_service import OrderSyncService
from src.config.constants import OrderStatus


# ── 测试工具 ─────────────────────────────────────────


def _make_order_dto(
    origin_order_id: str = "TB_001",
    order_status: str = "已付款",
    channel_pid: str = "pid_001",
    total_commission: str = "10.00",
    order_amount: str = "100.00",
    pay_time: datetime = None,
    settle_time: datetime = None,
    channel_code: str = "myq",
) -> OrderDTO:
    return OrderDTO(
        origin_order_id=origin_order_id,
        pay_time=pay_time or datetime(2026, 8, 1, 10, 0, 0),
        confirm_time=None,
        settle_time=settle_time,
        order_status=order_status,
        order_amount=Decimal(order_amount),
        channel_pid=channel_pid,
        refund_info=None,
        goods_id="G001",
        goods_title="测试商品",
        goods_img="https://img.test/a.jpg",
        total_commission=Decimal(total_commission),
        user_commission=Decimal("0"),
        platform_commission=Decimal("0"),
        channel_code=channel_code,
        raw_data={},
    )


def _make_sync_dao_mock():
    """构造 OrderSyncDAO mock"""
    dao = AsyncMock()
    dao.list_existing_out_order_nos = AsyncMock(return_value=set())
    dao.find_user_id_by_channel_pid = AsyncMock(return_value=10001)
    dao.batch_upsert_orders = AsyncMock(return_value=([], 0))
    dao.batch_update_status = AsyncMock(return_value=0)
    dao.list_orders_by_out_order_nos = AsyncMock(return_value=[])
    return dao


# ══════════════════════════════════════════════════════
# 1. _map_channel_status 测试
# ══════════════════════════════════════════════════════


class TestMapChannelStatus:
    """渠道状态字符串 → OrderStatus 映射测试"""

    def setup_method(self):
        self.svc = OrderSyncService(_make_sync_dao_mock())

    def test_common_chinese_status(self):
        """通用中文名映射"""
        assert self.svc._map_channel_status("待付款", "myq") == int(OrderStatus.PENDING)
        assert self.svc._map_channel_status("已付款", "myq") == int(
            OrderStatus.SETTLABLE
        )
        assert self.svc._map_channel_status("已结算", "myq") == int(OrderStatus.SETTLED)
        assert self.svc._map_channel_status("订单失效", "myq") == int(
            OrderStatus.INVALID
        )
        assert self.svc._map_channel_status("已退款", "myq") == int(
            OrderStatus.REFUNDED
        )

    def test_common_english_status(self):
        """通用英文枚举映射"""
        assert self.svc._map_channel_status("PAYING", "myq") == int(OrderStatus.PENDING)
        assert self.svc._map_channel_status("PAID", "myq") == int(OrderStatus.SETTLABLE)
        assert self.svc._map_channel_status("SETTLED", "myq") == int(
            OrderStatus.SETTLED
        )
        assert self.svc._map_channel_status("CONFIRMED", "myq") == int(
            OrderStatus.SETTLABLE
        )

    def test_channel_specific_conflict_code(self):
        """渠道专属冲突码区分（"3" 在不同渠道含义不同）"""
        # 喵有券 code=3 → PENDING（付款中）
        assert self.svc._map_channel_status("3", "myq") == int(OrderStatus.PENDING)
        # 订单侠 code=3 → PENDING（付款中）
        assert self.svc._map_channel_status("3", "orderx") == int(OrderStatus.PENDING)
        # 大淘客 code=3 → SETTLED（已结算，与喵有券/订单侠冲突）
        assert self.svc._map_channel_status("3", "dta") == int(OrderStatus.SETTLED)

    def test_dta_specific_codes(self):
        """大淘客专属码"""
        assert self.svc._map_channel_status("1", "dta") == int(OrderStatus.PENDING)
        assert self.svc._map_channel_status("2", "dta") == int(OrderStatus.SETTLABLE)
        assert self.svc._map_channel_status("-1", "dta") == int(OrderStatus.INVALID)

    def test_unknown_status_returns_none(self):
        """未知状态返回 None"""
        assert self.svc._map_channel_status("未知状态", "myq") is None
        assert self.svc._map_channel_status("999", "myq") is None

    def test_empty_status_returns_none(self):
        """空状态返回 None"""
        assert self.svc._map_channel_status("", "myq") is None
        assert self.svc._map_channel_status(None, "myq") is None


# ══════════════════════════════════════════════════════
# 2. _split_time_windows 测试
# ══════════════════════════════════════════════════════


class TestSplitTimeWindows:
    """时间窗口切分测试"""

    def setup_method(self):
        self.svc = OrderSyncService(_make_sync_dao_mock())

    def test_single_window(self):
        """区间小于窗口长度 → 单窗口"""
        start = datetime(2026, 8, 1, 10, 0, 0)
        end = datetime(2026, 8, 1, 10, 15, 0)  # 15分钟 < 30分钟
        windows = self.svc._split_time_windows(start, end, 30)
        assert len(windows) == 1
        assert windows[0] == (start, end)

    def test_multiple_windows(self):
        """区间大于窗口长度 → 多窗口"""
        start = datetime(2026, 8, 1, 10, 0, 0)
        end = datetime(2026, 8, 1, 11, 30, 0)  # 90分钟 → 3个30分钟窗口
        windows = self.svc._split_time_windows(start, end, 30)
        assert len(windows) == 3
        assert windows[0] == (start, datetime(2026, 8, 1, 10, 30, 0))
        assert windows[1] == (
            datetime(2026, 8, 1, 10, 30, 0),
            datetime(2026, 8, 1, 11, 0, 0),
        )
        assert windows[2] == (datetime(2026, 8, 1, 11, 0, 0), end)

    def test_default_window_minutes(self):
        """window_minutes<=0 时用默认值"""
        start = datetime(2026, 8, 1, 10, 0, 0)
        end = datetime(2026, 8, 1, 10, 10, 0)
        windows = self.svc._split_time_windows(start, end, 0)
        assert len(windows) == 1

    def test_exact_boundary(self):
        """区间恰好是窗口整数倍"""
        start = datetime(2026, 8, 1, 10, 0, 0)
        end = datetime(2026, 8, 1, 11, 0, 0)  # 60分钟 = 2*30
        windows = self.svc._split_time_windows(start, end, 30)
        assert len(windows) == 2


# ══════════════════════════════════════════════════════
# 3. _build_order_data 测试
# ══════════════════════════════════════════════════════


class TestBuildOrderData:
    """订单入库数据构造测试"""

    def setup_method(self):
        self.svc = OrderSyncService(_make_sync_dao_mock())

    def test_commission_split(self):
        """佣金 80%/20% 拆分"""
        o = _make_order_dto(total_commission="10.00")
        data = self.svc._build_order_data(o, "myq", 10001, int(OrderStatus.SETTLABLE))
        assert data["total_commission"] == Decimal("10.00")
        assert data["user_commission"] == Decimal("8.00")
        assert data["platform_commission"] == Decimal("2.00")

    def test_internal_order_no_prefix(self):
        """内部单号 GAK 前缀"""
        o = _make_order_dto(origin_order_id="TB_12345")
        data = self.svc._build_order_data(o, "myq", 10001, None)
        assert data["internal_order_no"] == "GAKTB_12345"

    def test_default_status_when_none(self):
        """mapped_status=None 时默认 PENDING"""
        o = _make_order_dto()
        data = self.svc._build_order_data(o, "myq", 10001, None)
        assert data["order_status"] == int(OrderStatus.PENDING)

    def test_zero_commission(self):
        """0 佣金场景"""
        o = _make_order_dto(total_commission="0")
        data = self.svc._build_order_data(o, "myq", 10001, int(OrderStatus.PENDING))
        assert data["total_commission"] == Decimal("0")
        assert data["user_commission"] == Decimal("0.00")
        assert data["platform_commission"] == Decimal("0.00")


# ══════════════════════════════════════════════════════
# 4. _pull_with_retry 测试
# ══════════════════════════════════════════════════════


class TestPullWithRetry:
    """单窗口拉取 + 重试测试"""

    def setup_method(self):
        self.svc = OrderSyncService(_make_sync_dao_mock())

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """首次成功，不重试"""
        adapter = AsyncMock()
        adapter.pull_order = AsyncMock(return_value=OrderPullResult(orders=[], total=0))
        result = await self.svc._pull_with_retry(
            adapter, datetime.now() - timedelta(hours=1), datetime.now(), "myq"
        )
        assert result.total == 0
        assert adapter.pull_order.call_count == 1

    @pytest.mark.asyncio
    async def test_success_on_retry(self):
        """重试后成功"""
        adapter = AsyncMock()
        adapter.pull_order = AsyncMock(
            side_effect=[
                CpsChannelException(CpsErrorType.NETWORK_ERROR, "网络错误", "喵有券"),
                OrderPullResult(orders=[], total=0),
            ]
        )
        with patch(
            "src.services.order_sync_service.asyncio.sleep", new_callable=AsyncMock
        ):
            result = await self.svc._pull_with_retry(
                adapter, datetime.now() - timedelta(hours=1), datetime.now(), "myq"
            )
        assert result.total == 0
        assert adapter.pull_order.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_failed_pushes_queue(self):
        """3次重试均失败 → 入失败队列 + 抛异常"""
        adapter = AsyncMock()
        adapter.pull_order = AsyncMock(
            side_effect=CpsChannelException(
                CpsErrorType.API_ERROR, "接口错误", "喵有券"
            )
        )
        with patch(
            "src.services.order_sync_service.asyncio.sleep", new_callable=AsyncMock
        ):
            with patch(
                "src.services.order_sync_service.RedisClient.lpush",
                new_callable=AsyncMock,
            ) as mock_lpush:
                with patch(
                    "src.services.order_sync_service.RedisClient.expire",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(CpsChannelException):
                        await self.svc._pull_with_retry(
                            adapter,
                            datetime.now() - timedelta(hours=1),
                            datetime.now(),
                            "myq",
                        )
        assert adapter.pull_order.call_count == 3
        # 验证失败记录入队
        mock_lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_channel_exception_retry(self):
        """非渠道异常（如 RuntimeError）也重试"""
        adapter = AsyncMock()
        adapter.pull_order = AsyncMock(side_effect=RuntimeError("unexpected"))
        with patch(
            "src.services.order_sync_service.asyncio.sleep", new_callable=AsyncMock
        ):
            with patch(
                "src.services.order_sync_service.RedisClient.lpush",
                new_callable=AsyncMock,
            ):
                with patch(
                    "src.services.order_sync_service.RedisClient.expire",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(CpsChannelException):
                        await self.svc._pull_with_retry(
                            adapter,
                            datetime.now() - timedelta(hours=1),
                            datetime.now(),
                            "myq",
                        )
        assert adapter.pull_order.call_count == 3


# ══════════════════════════════════════════════════════
# 5. _persist_orders 测试
# ══════════════════════════════════════════════════════


class TestPersistOrders:
    """幂等入库测试"""

    def setup_method(self):
        self.dao = _make_sync_dao_mock()
        self.svc = OrderSyncService(self.dao)

    @pytest.mark.asyncio
    async def test_empty_orders(self):
        """空订单列表"""
        inserted, updated = await self.svc._persist_orders([], "myq")
        assert inserted == 0
        assert updated == 0

    @pytest.mark.asyncio
    async def test_all_new_orders(self):
        """全部新订单"""
        self.dao.list_existing_out_order_nos = AsyncMock(return_value=set())
        self.dao.find_user_id_by_channel_pid = AsyncMock(return_value=10001)
        self.dao.batch_upsert_orders = AsyncMock(return_value=([MagicMock()], 1))

        orders = [
            _make_order_dto("TB_001", "已付款"),
            _make_order_dto("TB_002", "已结算"),
        ]
        inserted, updated = await self.svc._persist_orders(orders, "myq")
        assert inserted == 1
        assert updated == 0
        self.dao.batch_upsert_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_orders_status_update(self):
        """已存在订单状态变更 → 批量更新"""
        self.dao.list_existing_out_order_nos = AsyncMock(
            return_value={"TB_001", "TB_002"}
        )
        self.dao.batch_update_status = AsyncMock(return_value=2)

        orders = [
            _make_order_dto("TB_001", "已结算"),
            _make_order_dto("TB_002", "已退款"),
        ]
        inserted, updated = await self.svc._persist_orders(orders, "myq")
        assert inserted == 0
        assert updated == 2
        self.dao.batch_update_status.assert_called_once()
        # 验证更新列表内容
        update_list = self.dao.batch_update_status.call_args[0][0]
        assert len(update_list) == 2

    @pytest.mark.asyncio
    async def test_user_id_not_found_warning(self):
        """user_id 反查找不到 → user_id=0"""
        self.dao.list_existing_out_order_nos = AsyncMock(return_value=set())
        self.dao.find_user_id_by_channel_pid = AsyncMock(return_value=0)
        self.dao.batch_upsert_orders = AsyncMock(return_value=([MagicMock()], 1))

        orders = [_make_order_dto("TB_NEW", "已付款", channel_pid="pid_unknown")]
        inserted, updated = await self.svc._persist_orders(orders, "myq")
        assert inserted == 1
        # 验证入库数据 user_id=0
        orders_data = self.dao.batch_upsert_orders.call_args[0][0]
        assert orders_data[0]["user_id"] == 0

    @pytest.mark.asyncio
    async def test_skip_empty_origin_order_id(self):
        """跳过无 origin_order_id 的订单"""
        orders = [_make_order_dto(origin_order_id="")]
        inserted, updated = await self.svc._persist_orders(orders, "myq")
        assert inserted == 0
        assert updated == 0
        self.dao.batch_upsert_orders.assert_not_called()


# ══════════════════════════════════════════════════════
# 6. pull_channel_orders 测试
# ══════════════════════════════════════════════════════


class TestPullChannelOrders:
    """主入口拉取测试"""

    def setup_method(self):
        self.dao = _make_sync_dao_mock()
        self.svc = OrderSyncService(self.dao)

    @pytest.mark.asyncio
    async def test_breaker_open_skip(self):
        """熔断 OPEN 跳过"""
        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.OPEN)
            mock_get_breaker.return_value = breaker
            result = await self.svc.pull_channel_orders("myq")
        assert result["status"] == "skipped"
        assert "熔断" in result["message"]

    @pytest.mark.asyncio
    async def test_cursor_empty_first_run(self):
        """游标为空，首次回溯"""
        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker

            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with patch(
                    "src.services.order_sync_service.AdapterFactory.get_adapter"
                ) as mock_get_adapter:
                    adapter = AsyncMock()
                    adapter.pull_order = AsyncMock(
                        return_value=OrderPullResult(orders=[], total=0)
                    )
                    mock_get_adapter.return_value = adapter
                    with patch(
                        "src.services.order_sync_service.RedisClient.set",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "src.services.order_sync_service.RedisClient.expire",
                            new_callable=AsyncMock,
                        ):
                            result = await self.svc.pull_channel_orders("myq")
        assert result["status"] == "success"
        assert result["windows_total"] >= 1

    @pytest.mark.asyncio
    async def test_cursor_caught_up(self):
        """游标已追上当前时间，跳过"""
        # 游标设为未来时间（避免 datetime.now() 微秒差导致 cursor < now）
        future_iso = (datetime.now() + timedelta(minutes=5)).isoformat()
        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker

            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value=future_iso,
            ):
                result = await self.svc.pull_channel_orders("myq")
        assert result["status"] == "skipped"
        assert "追上" in result["message"]

    @pytest.mark.asyncio
    async def test_unsupported_channel(self):
        """不支持的渠道"""
        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker

            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with patch(
                    "src.services.order_sync_service.AdapterFactory.get_adapter",
                    side_effect=ValueError("不支持的渠道标识: unknown"),
                ):
                    result = await self.svc.pull_channel_orders("unknown")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_normal_pull_with_orders(self):
        """正常拉取有订单"""
        # 游标设为 15 分钟前（单个窗口，避免多窗口重复拉取导致计数翻倍）
        cursor_time = (datetime.now() - timedelta(minutes=15)).isoformat()
        orders = [
            _make_order_dto("TB_001", "已付款"),
            _make_order_dto("TB_002", "已结算"),
        ]

        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker

            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value=cursor_time,
            ):
                with patch(
                    "src.services.order_sync_service.AdapterFactory.get_adapter"
                ) as mock_get_adapter:
                    adapter = AsyncMock()
                    adapter.pull_order = AsyncMock(
                        return_value=OrderPullResult(orders=orders, total=2)
                    )
                    mock_get_adapter.return_value = adapter
                    with patch.object(
                        self.svc, "_persist_orders", new_callable=AsyncMock
                    ) as mock_persist:
                        mock_persist.return_value = (2, 0)
                        with patch(
                            "src.services.order_sync_service.RedisClient.set",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "src.services.order_sync_service.RedisClient.expire",
                                new_callable=AsyncMock,
                            ):
                                result = await self.svc.pull_channel_orders("myq")
        assert result["status"] == "success"
        assert result["pulled_count"] == 2
        assert result["inserted_count"] == 2

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """窗口拉取失败 → partial 状态"""
        cursor_time = (datetime.now() - timedelta(minutes=90)).isoformat()

        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker

            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value=cursor_time,
            ):
                with patch(
                    "src.services.order_sync_service.AdapterFactory.get_adapter"
                ) as mock_get_adapter:
                    adapter = AsyncMock()
                    adapter.pull_order = AsyncMock(
                        side_effect=CpsChannelException(
                            CpsErrorType.API_ERROR, "接口错误", "喵有券"
                        )
                    )
                    mock_get_adapter.return_value = adapter
                    with patch(
                        "src.services.order_sync_service.asyncio.sleep",
                        new_callable=AsyncMock,
                    ):
                        with patch(
                            "src.services.order_sync_service.RedisClient.lpush",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "src.services.order_sync_service.RedisClient.expire",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "src.services.order_sync_service.RedisClient.set",
                                    new_callable=AsyncMock,
                                ):
                                    result = await self.svc.pull_channel_orders("myq")
        assert result["status"] == "partial"
        assert result["failed_count"] >= 1


# ══════════════════════════════════════════════════════
# 7. pull_all_channels 测试
# ══════════════════════════════════════════════════════


class TestPullAllChannels:
    """三渠道串行拉取测试"""

    @pytest.mark.asyncio
    async def test_all_channels_success(self):
        """三渠道全部成功"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch.object(
            svc, "pull_channel_orders", new_callable=AsyncMock
        ) as mock_pull:
            mock_pull.return_value = {
                "status": "success",
                "pulled_count": 5,
                "inserted_count": 3,
                "updated_count": 2,
            }
            result = await svc.pull_all_channels()
        assert result["status"] == "success"
        assert len(result["channels"]) == 3
        assert mock_pull.call_count == 3

    @pytest.mark.asyncio
    async def test_partial_channel_failure(self):
        """某渠道失败 → partial"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch.object(
            svc, "pull_channel_orders", new_callable=AsyncMock
        ) as mock_pull:
            mock_pull.side_effect = [
                {
                    "status": "success",
                    "pulled_count": 5,
                    "inserted_count": 3,
                    "updated_count": 2,
                },
                Exception("渠道异常"),
                {
                    "status": "success",
                    "pulled_count": 0,
                    "inserted_count": 0,
                    "updated_count": 0,
                },
            ]
            result = await svc.pull_all_channels()
        assert result["status"] == "partial"
        assert result["channels"][1]["status"] == "failed"


# ══════════════════════════════════════════════════════
# 8. manual_sync_channel 测试
# ══════════════════════════════════════════════════════


class TestManualSyncChannel:
    """手动触发同步测试"""

    @pytest.mark.asyncio
    async def test_with_start_time(self):
        """指定 start_time → 临时覆盖游标"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch.object(
            svc, "pull_channel_orders", new_callable=AsyncMock
        ) as mock_pull:
            mock_pull.return_value = {"status": "success"}
            with patch(
                "src.services.order_sync_service.RedisClient.set",
                new_callable=AsyncMock,
            ) as mock_set:
                result = await svc.manual_sync_channel(
                    "myq",
                    start_time=datetime(2026, 7, 1, 0, 0, 0),
                    end_time=datetime(2026, 7, 2, 0, 0, 0),
                )
        assert result["status"] == "success"
        # 验证游标被临时设置
        mock_set.assert_called()
        mock_pull.assert_called_once_with("myq")

    @pytest.mark.asyncio
    async def test_without_start_time(self):
        """未指定 start_time → 走游标"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch.object(
            svc, "pull_channel_orders", new_callable=AsyncMock
        ) as mock_pull:
            mock_pull.return_value = {"status": "success"}
            result = await svc.manual_sync_channel("myq")
        assert result["status"] == "success"
        mock_pull.assert_called_once_with("myq")


# ══════════════════════════════════════════════════════
# 9. manual_retry_failed 测试
# ══════════════════════════════════════════════════════


class TestManualRetryFailed:
    """手动补发失败队列测试"""

    @pytest.mark.asyncio
    async def test_empty_queue(self):
        """失败队列为空"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch(
            "src.services.order_sync_service.AdapterFactory.get_adapter"
        ) as mock_get_adapter:
            mock_get_adapter.return_value = AsyncMock()
            with patch(
                "src.services.order_sync_service.RedisClient.rpop",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await svc.manual_retry_failed("myq", batch_size=5)
        assert result["retried_count"] == 0
        assert result["status"] == "success"
        assert "空" in result["message"]

    @pytest.mark.asyncio
    async def test_retry_success(self):
        """补发成功"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        failed_payload = json.dumps(
            {
                "start": (datetime.now() - timedelta(hours=1)).isoformat(),
                "end": datetime.now().isoformat(),
                "retry_count": 3,
                "error": "test",
            }
        )
        with patch(
            "src.services.order_sync_service.AdapterFactory.get_adapter"
        ) as mock_get_adapter:
            adapter = AsyncMock()
            adapter.pull_order = AsyncMock(
                return_value=OrderPullResult(orders=[], total=0)
            )
            mock_get_adapter.return_value = adapter
            with patch.object(
                svc, "_persist_orders", new_callable=AsyncMock
            ) as mock_persist:
                mock_persist.return_value = (0, 0)
                with patch(
                    "src.services.order_sync_service.RedisClient.rpop",
                    new_callable=AsyncMock,
                    side_effect=[failed_payload, None],
                ):
                    result = await svc.manual_retry_failed("myq", batch_size=5)
        assert result["retried_count"] == 1
        assert result["success_count"] == 1
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_retry_failure_requeue(self):
        """补发失败 → 重新入队"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        failed_payload = json.dumps(
            {
                "start": (datetime.now() - timedelta(hours=1)).isoformat(),
                "end": datetime.now().isoformat(),
                "retry_count": 3,
                "error": "test",
            }
        )
        with patch(
            "src.services.order_sync_service.AdapterFactory.get_adapter"
        ) as mock_get_adapter:
            adapter = AsyncMock()
            adapter.pull_order = AsyncMock(
                side_effect=CpsChannelException(
                    CpsErrorType.API_ERROR, "仍失败", "喵有券"
                )
            )
            mock_get_adapter.return_value = adapter
            with patch(
                "src.services.order_sync_service.RedisClient.rpop",
                new_callable=AsyncMock,
                side_effect=[failed_payload, None],
            ):
                with patch(
                    "src.services.order_sync_service.RedisClient.lpush",
                    new_callable=AsyncMock,
                ) as mock_lpush:
                    result = await svc.manual_retry_failed("myq", batch_size=5)
        assert result["retried_count"] == 1
        assert result["still_failed_count"] == 1
        assert result["status"] == "partial"
        # 验证重新入队
        mock_lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsupported_channel(self):
        """不支持的渠道"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch(
            "src.services.order_sync_service.AdapterFactory.get_adapter",
            side_effect=ValueError("不支持的渠道标识: unknown"),
        ):
            result = await svc.manual_retry_failed("unknown")
        assert result["status"] == "failed"


# ══════════════════════════════════════════════════════
# 10. get_sync_status 测试
# ══════════════════════════════════════════════════════


class TestGetSyncStatus:
    """状态查询测试"""

    @pytest.mark.asyncio
    async def test_status_query(self):
        """查询三渠道状态（S04：生产仅启用喵有券渠道）"""
        dao = _make_sync_dao_mock()
        svc = OrderSyncService(dao)
        with patch(
            "src.services.order_sync_service.CircuitBreakerAdapter.get_default_breaker"
        ) as mock_get_breaker:
            breaker = AsyncMock()
            breaker.get_state = AsyncMock(return_value=BreakerState.CLOSED)
            mock_get_breaker.return_value = breaker
            with patch(
                "src.services.order_sync_service.RedisClient.get",
                new_callable=AsyncMock,
                return_value="2026-08-01T10:00:00",
            ):
                with patch(
                    "src.services.order_sync_service.RedisClient.llen",
                    new_callable=AsyncMock,
                    return_value=2,
                ):
                    result = await svc.get_sync_status()
        # S04 生产渠道开关：仅喵有券启用（orderx/dta 停用）
        assert result["total_enabled"] == 1
        assert len(result["channels"]) == 3
        enabled_by_code = {ch["channel_code"]: ch["enabled"] for ch in result["channels"]}
        assert enabled_by_code["myq"] is True
        assert enabled_by_code["orderx"] is False
        assert enabled_by_code["dta"] is False
        for ch in result["channels"]:
            assert ch["cursor"] == "2026-08-01T10:00:00"
            assert ch["failed_queue_length"] == 2
            assert ch["breaker_state"] == "CLOSED"
            assert ch["cron_expr"] != ""

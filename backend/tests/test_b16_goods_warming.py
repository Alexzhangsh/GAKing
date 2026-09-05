# @ai-generated
"""
B16 商品预热定时任务单元测试

覆盖场景：
1. DAO 层：list_hot_products / list_normal_products / list_expired_products /
           list_soft_delete_candidates / batch_update_sync_status / batch_soft_delete
2. 预热筛选函数：_myq_extra_filter / _orderx_extra_filter
3. 数据构建函数：_get_dynamic_upsert_data / _get_create_data
4. 预热任务函数（mock 适配器 + mock DAO）：warming_myq / warming_orderx
5. 刷新任务函数（mock DAO）：refresh_hot / refresh_normal
6. 冷品清理任务函数：cleanup_expired_goods

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_b16_goods_warming.py -v
"""
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.cps.adapter.dto import GoodsDTO, GoodsSearchResult
from src.dao.goods_management_dao import GoodsManagementDAO
from src.models.business.goods_management_model import GoodsManagement
from src.scheduler.goods_warming_jobs import (
    _get_create_data,
    _get_dynamic_upsert_data,
    _myq_extra_filter,
    _orderx_extra_filter,
    cleanup_expired_goods,
    refresh_hot_myq,
    refresh_hot_orderx,
    refresh_normal_myq,
    refresh_normal_orderx,
    warming_myq,
    warming_orderx,
)


# ════════════════════════════════════════════════════
# Mock 工具
# ════════════════════════════════════════════════════


def _make_goods_dto(
    goods_id: str = "G001",
    title: str = "测试商品",
    price: Decimal = Decimal("49.90"),
    commission_rate: Decimal = Decimal("20.00"),
    sales: int = 500,
    category: str = "数码",
    shop_name: str = "测试店铺",
) -> GoodsDTO:
    return GoodsDTO(
        goods_id=goods_id,
        goods_title=title,
        goods_img="https://img.test/a.jpg",
        original_price=Decimal("99.00"),
        sale_price=price,
        commission_rate=commission_rate,
        estimate_commission=price * commission_rate / Decimal("100"),
        category=category,
        promote_url="https://test.com/p/123",
        shop_name=shop_name,
        sales_volume=sales,
        source_channel="myq",
    )


def _make_goods_model(
    goods_id: str = "G001",
    source_channel: str = "myq",
    popularity: int = 0,
    sync_status: str = "normal",
    last_visit_time: Optional[datetime] = None,
    category: str = "数码",
    sale_price: Decimal = Decimal("49.90"),
    commission_rate: Decimal = Decimal("20.00"),
) -> MagicMock:
    """构建 GoodsManagement 模型 mock 实例"""
    obj = MagicMock(spec=GoodsManagement)
    obj.id = abs(hash(goods_id + source_channel)) % 1000000
    obj.goods_id = goods_id
    obj.goods_title = "测试商品"
    obj.source_channel = source_channel
    obj.sale_price = sale_price
    obj.commission_rate = commission_rate
    obj.category = category
    obj.popularity = popularity
    obj.sync_status = sync_status
    obj.last_visit_time = last_visit_time or datetime.now()
    obj.last_sync_time = datetime.now()
    obj.shop_name = "测试店铺"
    obj.shelf_status = "on_shelf"
    obj.is_delete = False
    obj.create_time = datetime.now()
    obj.update_time = datetime.now()
    return obj


def _make_mock_dao(
    hot_products=None,
    normal_products=None,
    expired_products=None,
    soft_delete_candidates=None,
    get_by_goods_id=None,
) -> AsyncMock:
    """构建 mock GoodsManagementDAO"""
    dao = AsyncMock(spec=GoodsManagementDAO)
    dao.list_hot_products = AsyncMock(return_value=hot_products or [])
    dao.list_normal_products = AsyncMock(return_value=normal_products or [])
    dao.list_expired_products = AsyncMock(return_value=expired_products or [])
    dao.list_soft_delete_candidates = AsyncMock(return_value=soft_delete_candidates or [])
    dao.get_by_goods_id_channel = AsyncMock(return_value=get_by_goods_id)
    dao.update_by_id = AsyncMock(return_value=True)
    dao.create = AsyncMock(return_value=_make_goods_model())
    dao.batch_update_sync_status = AsyncMock(return_value=0)
    dao.batch_soft_delete = AsyncMock(return_value=0)
    return dao


def _make_mock_async_context_manager(dao):
    """构建 mock async context manager，模拟 DatabaseManager.get_session()"""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=dao)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ════════════════════════════════════════════════════
# 筛选函数测试
# ════════════════════════════════════════════════════


class TestFilterFunctions:
    """预热筛选函数测试"""

    def test_myq_extra_filter_accept(self):
        goods = _make_goods_dto(price=Decimal("49.90"))
        assert _myq_extra_filter(goods) is True

    def test_myq_extra_filter_too_low(self):
        goods = _make_goods_dto(price=Decimal("5.00"))
        assert _myq_extra_filter(goods) is False

    def test_myq_extra_filter_too_high(self):
        goods = _make_goods_dto(price=Decimal("199.00"))
        assert _myq_extra_filter(goods) is False

    def test_myq_extra_filter_boundary_low(self):
        goods = _make_goods_dto(price=Decimal("9.90"))
        assert _myq_extra_filter(goods) is True

    def test_myq_extra_filter_boundary_high(self):
        goods = _make_goods_dto(price=Decimal("99.00"))
        assert _myq_extra_filter(goods) is True

    def test_orderx_extra_filter_accept(self):
        goods = _make_goods_dto(sales=200)
        assert _orderx_extra_filter(goods) is True

    def test_orderx_extra_filter_reject(self):
        goods = _make_goods_dto(sales=50)
        assert _orderx_extra_filter(goods) is False

    def test_orderx_extra_filter_boundary(self):
        goods = _make_goods_dto(sales=100)
        assert _orderx_extra_filter(goods) is True


# ════════════════════════════════════════════════════
# 数据构建函数测试
# ════════════════════════════════════════════════════


class TestDataBuilders:
    """upsert/新建数据构建函数测试"""

    def test_get_dynamic_upsert_data(self):
        goods = _make_goods_dto(price=Decimal("59.90"), commission_rate=Decimal("18.00"))
        data = _get_dynamic_upsert_data(goods)

        assert data["sale_price"] == Decimal("59.90")
        assert data["commission_rate"] == Decimal("18.00")
        assert data["shelf_status"] == "on_shelf"
        assert data["sync_status"] == "normal"
        assert "last_sync_time" in data
        assert "goods_title" not in data
        assert "goods_img" not in data
        assert "shop_name" not in data
        assert "category" not in data
        assert "popularity" not in data

    def test_get_create_data(self):
        goods = _make_goods_dto(
            goods_id="G002",
            title="新品测试",
            price=Decimal("39.90"),
            commission_rate=Decimal("25.00"),
            category="美食",
            shop_name="美食店",
        )
        data = _get_create_data(goods)

        assert data["goods_title"] == "新品测试"
        assert data["sale_price"] == Decimal("39.90")
        assert data["commission_rate"] == Decimal("25.00")
        assert data["category"] == "美食"
        assert data["shop_name"] == "美食店"
        assert data["shelf_status"] == "on_shelf"
        assert data["sync_status"] == "normal"
        assert data["popularity"] == 0
        assert "goods_img" in data
        assert "last_sync_time" in data


# ════════════════════════════════════════════════════
# DAO 方法测试（mock session.execute 返回链）
# ════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="function")
class TestGoodsManagementDAOB16:
    """B16 DAO 扩展方法测试"""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def dao(self, mock_session):
        return GoodsManagementDAO(mock_session)

    def _setup_scalars(self, mock_session, items):
        """设置 execute 返回的 scalars().all() 链"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_session.execute.return_value = mock_result

    async def test_list_hot_products(self, dao, mock_session):
        items = [_make_goods_model(popularity=5)]
        self._setup_scalars(mock_session, items)

        result = await dao.list_hot_products()
        assert len(result) == 1
        assert result[0].popularity == 5

    async def test_list_hot_products_with_channel(self, dao, mock_session):
        items = [_make_goods_model(popularity=3, source_channel="myq")]
        self._setup_scalars(mock_session, items)

        result = await dao.list_hot_products(source_channel="myq")
        assert len(result) == 1

    async def test_list_hot_products_empty(self, dao, mock_session):
        self._setup_scalars(mock_session, [])
        result = await dao.list_hot_products()
        assert result == []

    async def test_list_normal_products(self, dao, mock_session):
        items = [_make_goods_model(popularity=0)]
        self._setup_scalars(mock_session, items)

        result = await dao.list_normal_products()
        assert len(result) == 1
        assert result[0].popularity == 0

    async def test_list_expired_products(self, dao, mock_session):
        old_time = datetime.now() - timedelta(days=31)
        items = [_make_goods_model(last_visit_time=old_time)]
        self._setup_scalars(mock_session, items)

        result = await dao.list_expired_products(expiry_days=30)
        assert len(result) == 1

    async def test_list_expired_products_none(self, dao, mock_session):
        self._setup_scalars(mock_session, [])
        result = await dao.list_expired_products(expiry_days=30)
        assert len(result) == 0

    async def test_list_soft_delete_candidates(self, dao, mock_session):
        old_time = datetime.now() - timedelta(days=8)
        items = [_make_goods_model(sync_status="expired", last_visit_time=old_time)]
        self._setup_scalars(mock_session, items)

        result = await dao.list_soft_delete_candidates(grace_days=7)
        assert len(result) == 1

    async def test_batch_update_sync_status(self, dao, mock_session):
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        result = await dao.batch_update_sync_status([1, 2, 3, 4, 5], "expired")
        assert result == 5

    async def test_batch_update_sync_status_empty(self, dao):
        result = await dao.batch_update_sync_status([], "expired")
        assert result == 0

    async def test_batch_soft_delete(self, dao, mock_session):
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        result = await dao.batch_soft_delete([1, 2, 3])
        assert result == 3

    async def test_batch_soft_delete_empty(self, dao):
        result = await dao.batch_soft_delete([])
        assert result == 0


# ════════════════════════════════════════════════════
# 预热任务测试（mock 适配器 + mock DAO）
# ════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="function")
class TestWarmingJobs:
    """预热任务函数测试"""

    @pytest.fixture(autouse=True)
    def _patch_common(self):
        """mock Redis 和开关"""
        patchers = [
            patch("src.scheduler.goods_warming_jobs.RedisClient.get", new_callable=AsyncMock, return_value=None),
            patch("src.scheduler.goods_warming_jobs.RedisClient.setex", new_callable=AsyncMock),
            patch("src.scheduler.goods_warming_jobs.TASK_GOODS_WARMING_ENABLE", True),
            patch("src.scheduler.goods_warming_jobs.TASK_WARMING_MYQ_ENABLE", True),
            patch("src.scheduler.goods_warming_jobs.TASK_WARMING_ORDERX_ENABLE", True),
            patch("src.scheduler.goods_warming_jobs.TASK_WARMING_MAX_PAGES", 1),
            patch("src.scheduler.goods_warming_jobs.TASK_WARMING_PAGE_SIZE", 10),
        ]
        for p in patchers:
            p.start()
        yield
        patch.stopall()

    def _make_mock_adapter(self, goods_list: List[GoodsDTO]) -> AsyncMock:
        adapter = AsyncMock()
        adapter.search_goods = AsyncMock(
            return_value=GoodsSearchResult(
                items=goods_list, total=len(goods_list), page=1, size=10
            )
        )
        return adapter

    async def test_warming_myq_success(self):
        """喵有券预热成功"""
        goods = _make_goods_dto(
            goods_id="M001",
            commission_rate=Decimal("20.00"),
            price=Decimal("49.90"),
        )
        adapter = self._make_mock_adapter([goods])
        mock_dao = _make_mock_dao(get_by_goods_id=None)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.MiaoyouquanAdapter", return_value=adapter), \
             patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await warming_myq()

        assert result["status"] in ("success", "partial")
        assert result["pulled_count"] >= 1
        assert result["upserted_count"] >= 1

    async def test_warming_myq_commission_filter(self):
        """喵有券预热：佣金不达标被过滤"""
        goods = _make_goods_dto(
            goods_id="M002", commission_rate=Decimal("10.00"), price=Decimal("49.90")
        )
        adapter = self._make_mock_adapter([goods])
        mock_dao = _make_mock_dao(get_by_goods_id=None)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.MiaoyouquanAdapter", return_value=adapter), \
             patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await warming_myq()

        assert result["upserted_count"] == 0
        assert result["skipped_count"] >= 1

    async def test_warming_orderx_success(self):
        """订单侠预热成功"""
        goods = _make_goods_dto(
            goods_id="O001", commission_rate=Decimal("15.00"), sales=200, category="食品"
        )
        adapter = self._make_mock_adapter([goods])
        mock_dao = _make_mock_dao(get_by_goods_id=None)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DingdanxiaAdapter", return_value=adapter), \
             patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await warming_orderx()

        assert result["status"] in ("success", "partial")
        assert result["upserted_count"] >= 1

    async def test_warming_orderx_sales_filter(self):
        """订单侠预热：月销量不达标被过滤"""
        goods = _make_goods_dto(
            goods_id="O002", commission_rate=Decimal("15.00"), sales=50, category="食品"
        )
        adapter = self._make_mock_adapter([goods])
        mock_dao = _make_mock_dao(get_by_goods_id=None)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DingdanxiaAdapter", return_value=adapter), \
             patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await warming_orderx()

        assert result["upserted_count"] == 0
        assert result["skipped_count"] >= 1

    async def test_warming_switch_off(self):
        """预热总开关关闭时跳过"""
        with patch("src.scheduler.goods_warming_jobs.TASK_GOODS_WARMING_ENABLE", False):
            result = await warming_myq()
        assert result["status"] == "skipped"


# ════════════════════════════════════════════════════
# 刷新任务测试
# ════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="function")
class TestRefreshJobs:
    """商品刷新任务测试"""

    @pytest.fixture(autouse=True)
    def _patch_common(self):
        patchers = [
            patch("src.scheduler.goods_warming_jobs.TASK_GOODS_REFRESH_ENABLE", True),
        ]
        for p in patchers:
            p.start()
        yield
        patch.stopall()

    async def test_refresh_hot_myq_no_products(self):
        """热门商品刷新：无待刷新商品"""
        mock_dao = _make_mock_dao(hot_products=[])
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await refresh_hot_myq()
        assert result["status"] == "success"
        assert result["total"] == 0

    async def test_refresh_hot_orderx_no_products(self):
        """订单侠热门商品刷新：无待刷新商品"""
        mock_dao = _make_mock_dao(hot_products=[])
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await refresh_hot_orderx()
        assert result["status"] == "success"
        assert result["total"] == 0

    async def test_refresh_normal_myq_no_products(self):
        """普通商品刷新：无待刷新商品"""
        mock_dao = _make_mock_dao(normal_products=[])
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await refresh_normal_myq()
        assert result["status"] == "success"
        assert result["total"] == 0

    async def test_refresh_normal_orderx_no_products(self):
        """订单侠普通商品刷新：无待刷新商品"""
        mock_dao = _make_mock_dao(normal_products=[])
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await refresh_normal_orderx()
        assert result["status"] == "success"
        assert result["total"] == 0

    async def test_refresh_switch_off(self):
        """刷新开关关闭时跳过"""
        with patch("src.scheduler.goods_warming_jobs.TASK_GOODS_REFRESH_ENABLE", False):
            result = await refresh_hot_myq()
        assert result["status"] == "skipped"


# ════════════════════════════════════════════════════
# 冷品清理任务测试
# ════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="function")
class TestCleanupJob:
    """冷品清理任务测试"""

    @pytest.fixture(autouse=True)
    def _patch_common(self):
        patchers = [
            patch("src.scheduler.goods_warming_jobs.TASK_GOODS_CLEANUP_ENABLE", True),
            patch("src.scheduler.goods_warming_jobs.TASK_CLEANUP_BATCH_SIZE", 500),
        ]
        for p in patchers:
            p.start()
        yield
        patch.stopall()

    async def test_cleanup_no_products(self):
        """清理任务：无过期商品"""
        mock_dao = _make_mock_dao()
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await cleanup_expired_goods()
        assert result["status"] == "success"
        assert result["marked_expired"] == 0
        assert result["soft_deleted"] == 0

    async def test_cleanup_with_expired(self):
        """清理任务：有商品需标记过期"""
        old_time = datetime.now() - timedelta(days=31)
        expired = [_make_goods_model(last_visit_time=old_time, popularity=0)]
        mock_dao = _make_mock_dao(expired_products=expired)
        mock_dao.batch_update_sync_status = AsyncMock(return_value=1)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await cleanup_expired_goods()
        assert result["status"] == "success"
        assert result["marked_expired"] >= 1

    async def test_cleanup_with_soft_delete(self):
        """清理任务：有商品需软删除"""
        old_time = datetime.now() - timedelta(days=8)
        candidates = [_make_goods_model(sync_status="expired", last_visit_time=old_time)]
        mock_dao = _make_mock_dao(soft_delete_candidates=candidates)
        mock_dao.batch_soft_delete = AsyncMock(return_value=1)
        mock_cm = _make_mock_async_context_manager(mock_dao)

        with patch("src.scheduler.goods_warming_jobs.DatabaseManager.get_session", return_value=mock_cm), \
             patch("src.scheduler.goods_warming_jobs.GoodsManagementDAO", return_value=mock_dao):
            result = await cleanup_expired_goods()
        assert result["status"] == "success"
        assert result["soft_deleted"] >= 1

    async def test_cleanup_switch_off(self):
        """清理开关关闭时跳过"""
        with patch("src.scheduler.goods_warming_jobs.TASK_GOODS_CLEANUP_ENABLE", False):
            result = await cleanup_expired_goods()
        assert result["status"] == "skipped"

# @ai-generated
"""
B05 订单同步 DAO 单元测试

覆盖场景：
1. list_existing_out_order_nos：空列表/有结果/无结果
2. find_user_id_by_channel_pid：空 pid/找到/找不到
3. batch_upsert_orders：全新/部分已存在/全已存在/IntegrityError 回退
4. batch_update_status：正常/空列表/单条失败
5. list_orders_by_out_order_nos：空列表/有结果

运行：PYTHONPATH=. .venv/bin/python -m pytest tests/test_order_sync_dao.py -v
"""
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, ".")

from src.dao.order_sync_dao import OrderSyncDAO
from src.models.business.order_model import Order


# ── 测试工具 ─────────────────────────────────────────


def _make_session_mock():
    """构造 AsyncSession mock"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


def _make_result_mock(rows):
    """构造 execute 返回的 result mock，rows 是 [(col1,), ...] 或 [obj, ...]"""
    result = MagicMock()
    # .all() 返回行列表
    result.all = MagicMock(return_value=rows)
    # .first() 返回首行或 None
    result.first = MagicMock(return_value=rows[0] if rows else None)
    # .scalar_one_or_none() / .scalars().all()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(
        return_value=[r[0] if isinstance(r, tuple) else r for r in rows]
    )
    result.scalars = MagicMock(return_value=scalars_mock)
    return result


# ══════════════════════════════════════════════════════
# 1. list_existing_out_order_nos 测试
# ══════════════════════════════════════════════════════


class TestListExistingOutOrderNos:
    """批量查重测试"""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """空列表直接返回空集合"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        result = await dao.list_existing_out_order_nos([])
        assert result == set()
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_has_existing(self):
        """部分订单已存在"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock(
            [("ORDER_001",), ("ORDER_002",)]
        )
        dao = OrderSyncDAO(session)
        result = await dao.list_existing_out_order_nos(
            ["ORDER_001", "ORDER_002", "ORDER_003"]
        )
        assert result == {"ORDER_001", "ORDER_002"}

    @pytest.mark.asyncio
    async def test_none_existing(self):
        """无已存在订单"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock([])
        dao = OrderSyncDAO(session)
        result = await dao.list_existing_out_order_nos(["ORDER_NEW"])
        assert result == set()


# ══════════════════════════════════════════════════════
# 2. find_user_id_by_channel_pid 测试
# ══════════════════════════════════════════════════════


class TestFindUserIdByChannelPid:
    """user_id 反查测试"""

    @pytest.mark.asyncio
    async def test_empty_pid(self):
        """空 pid 返回 0"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        assert await dao.find_user_id_by_channel_pid("", "myq") == 0
        assert await dao.find_user_id_by_channel_pid("pid_001", "") == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_found_user_id(self):
        """找到历史订单 user_id"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock([(10001,)])
        dao = OrderSyncDAO(session)
        result = await dao.find_user_id_by_channel_pid("pid_001", "myq")
        assert result == 10001

    @pytest.mark.asyncio
    async def test_not_found(self):
        """无历史订单返回 0"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock([])
        dao = OrderSyncDAO(session)
        result = await dao.find_user_id_by_channel_pid("pid_unknown", "myq")
        assert result == 0


# ══════════════════════════════════════════════════════
# 3. batch_upsert_orders 测试
# ══════════════════════════════════════════════════════


class TestBatchUpsertOrders:
    """批量幂等插入测试"""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """空列表返回 ([], 0)"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        result = await dao.batch_upsert_orders([])
        assert result == ([], 0)

    @pytest.mark.asyncio
    async def test_all_new_orders(self):
        """全部新订单：查重无已存在，批量插入成功"""
        session = _make_session_mock()
        # 第一次 execute：查重返回空
        session.execute.return_value = _make_result_mock([])
        dao = OrderSyncDAO(session)

        orders_data = [
            {
                "out_order_no": "ORDER_001",
                "user_id": 10001,
                "internal_order_no": "GAK_ORDER_001",
            },
            {
                "out_order_no": "ORDER_002",
                "user_id": 10002,
                "internal_order_no": "GAK_ORDER_002",
            },
        ]
        with patch.object(
            OrderSyncDAO, "batch_create", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = [MagicMock(id=1), MagicMock(id=2)]
            inserted, count = await dao.batch_upsert_orders(orders_data)
        assert count == 2
        assert len(inserted) == 2
        mock_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_existing_orders(self):
        """全部已存在：查重全部命中，不插入"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock(
            [("ORDER_001",), ("ORDER_002",)]
        )
        dao = OrderSyncDAO(session)

        orders_data = [
            {"out_order_no": "ORDER_001", "user_id": 10001},
            {"out_order_no": "ORDER_002", "user_id": 10002},
        ]
        with patch.object(
            OrderSyncDAO, "batch_create", new_callable=AsyncMock
        ) as mock_batch:
            inserted, count = await dao.batch_upsert_orders(orders_data)
        assert count == 0
        assert inserted == []
        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_existing(self):
        """部分已存在：过滤后只插入新订单"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock([("ORDER_001",)])
        dao = OrderSyncDAO(session)

        orders_data = [
            {"out_order_no": "ORDER_001", "user_id": 10001},  # 已存在
            {"out_order_no": "ORDER_002", "user_id": 10002},  # 新订单
        ]
        with patch.object(
            OrderSyncDAO, "batch_create", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = [MagicMock(id=2)]
            inserted, count = await dao.batch_upsert_orders(orders_data)
        assert count == 1
        # 验证 batch_create 收到的是过滤后的新订单
        called_data = mock_batch.call_args[0][0]
        assert len(called_data) == 1
        assert called_data[0]["out_order_no"] == "ORDER_002"

    @pytest.mark.asyncio
    async def test_integrity_error_fallback(self):
        """批量插入 IntegrityError → 回退逐条插入"""
        session = _make_session_mock()
        session.execute.return_value = _make_result_mock([])  # 查重无已存在
        dao = OrderSyncDAO(session)

        orders_data = [
            {"out_order_no": "ORDER_001", "user_id": 10001},
            {"out_order_no": "ORDER_002", "user_id": 10002},
        ]
        with patch.object(
            OrderSyncDAO, "batch_create", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.side_effect = IntegrityError(
                "INSERT", params={}, orig=Exception("Duplicate entry")
            )
            # 逐条插入：第一条成功，第二条也成功
            inserted, count = await dao.batch_upsert_orders(orders_data)
        assert count == 2
        assert len(inserted) == 2
        # 验证回滚被调用
        assert session.rollback.call_count >= 1


# ══════════════════════════════════════════════════════
# 4. batch_update_status 测试
# ══════════════════════════════════════════════════════


class TestBatchUpdateStatus:
    """批量状态更新测试"""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """空列表返回 0"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        assert await dao.batch_update_status([]) == 0

    @pytest.mark.asyncio
    async def test_update_success(self):
        """正常更新"""
        session = _make_session_mock()
        # execute 调用：第一次 update，然后查 id（_invalidate_cache_by_out_order_no）
        update_result = MagicMock()
        update_result.rowcount = 1
        id_result = _make_result_mock([(101,)])
        session.execute.side_effect = [update_result, id_result]
        dao = OrderSyncDAO(session)

        with patch("src.dao.order_sync_dao.RedisClient.delete", new_callable=AsyncMock):
            updates = [
                {
                    "out_order_no": "ORDER_001",
                    "order_status": 30,
                    "pay_time": datetime.now(),
                    "settle_time": None,
                }
            ]
            count = await dao.batch_update_status(updates)
        assert count == 1

    @pytest.mark.asyncio
    async def test_skip_empty_out_order_no(self):
        """out_order_no 为空跳过"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        updates = [{"out_order_no": "", "order_status": 30}]
        count = await dao.batch_update_status(updates)
        assert count == 0
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_failure_not_block(self):
        """单条失败不阻断其他订单"""
        session = _make_session_mock()
        update_result = MagicMock()
        update_result.rowcount = 1
        id_result = _make_result_mock([(101,)])
        # 第一条 update 成功，第二条 flush 抛异常
        session.execute.side_effect = [update_result, id_result, Exception("db error")]
        session.flush = AsyncMock(side_effect=[None, Exception("flush error")])
        dao = OrderSyncDAO(session)

        with patch("src.dao.order_sync_dao.RedisClient.delete", new_callable=AsyncMock):
            updates = [
                {"out_order_no": "ORDER_001", "order_status": 30},
                {"out_order_no": "ORDER_002", "order_status": 40},
            ]
            count = await dao.batch_update_status(updates)
        # 第一条成功，第二条失败，count=1
        assert count == 1


# ══════════════════════════════════════════════════════
# 5. list_orders_by_out_order_nos 测试
# ══════════════════════════════════════════════════════


class TestListOrdersByOutOrderNos:
    """按 out_order_no 列表查询测试"""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """空列表返回 []"""
        session = _make_session_mock()
        dao = OrderSyncDAO(session)
        result = await dao.list_orders_by_out_order_nos([])
        assert result == []
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_has_orders(self):
        """有结果"""
        session = _make_session_mock()
        mock_order = MagicMock(spec=Order)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [mock_order]
        session.execute.return_value = result_mock
        dao = OrderSyncDAO(session)
        result = await dao.list_orders_by_out_order_nos(["ORDER_001"])
        assert len(result) == 1

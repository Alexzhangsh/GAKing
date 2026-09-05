# @ai-generated
"""
X02-1 用户会员记录 DAO 单元测试
覆盖：get_active_record / paginate_records / mark_expired_before / list_for_export
使用 AsyncMock 模拟 session，不依赖真实 DB/Redis
"""
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, ".")

from src.dao.user_member_record_dao import UserMemberRecordDAO
from src.models.business.user_member_record_model import UserMemberRecord


def _make_record(
    record_id: int = 1,
    user_id: int = 100,
    status: str = "active",
    expire_at: datetime = None,
) -> UserMemberRecord:
    record = MagicMock(spec=UserMemberRecord)
    record.id = record_id
    record.user_id = user_id
    record.status = status
    record.expire_at = expire_at or (datetime.now() + timedelta(days=30))
    record.package_id = 1
    record.package_name = "月度会员"
    record.update_time = datetime.now()
    return record


def _make_dao(session=None):
    session = session or AsyncMock()
    return UserMemberRecordDAO(session)


class TestGetActiveRecord:
    """有效会员查询测试"""

    @pytest.mark.asyncio
    async def test_found_active(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.execute.return_value.scalar_one_or_none = MagicMock(
            return_value=_make_record(user_id=100, status="active")
        )
        dao = _make_dao(session)

        record = await dao.get_active_record(100)
        assert record is not None
        assert record.status == "active"

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        dao = _make_dao(session)

        record = await dao.get_active_record(999)
        assert record is None


class TestPaginateRecords:
    """分页查询测试"""

    @pytest.mark.asyncio
    async def test_paginate_default(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=3)
        list_result = MagicMock()
        list_result.scalars.return_value.all = MagicMock(
            return_value=[_make_record(1), _make_record(2), _make_record(3)]
        )
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        dao = _make_dao(session)

        items, total = await dao.paginate_records(page=1, page_size=20)
        assert total == 3
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_paginate_with_filters(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=1)
        list_result = MagicMock()
        list_result.scalars.return_value.all = MagicMock(
            return_value=[_make_record(1, user_id=100, status="active")]
        )
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        dao = _make_dao(session)

        items, total = await dao.paginate_records(
            page=1, page_size=20, user_id=100, status="active"
        )
        assert total == 1
        assert items[0].user_id == 100
        assert items[0].status == "active"


class TestMarkExpiredBefore:
    """到期批量标记测试"""

    @pytest.mark.asyncio
    async def test_mark_expired(self):
        now = datetime.now()
        expired_record = _make_record(record_id=1, status="active",
                                       expire_at=now - timedelta(hours=1))
        result = MagicMock()
        result.scalars.return_value.all.return_value = [expired_record]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        dao = _make_dao(session)

        count = await dao.mark_expired_before(now)
        assert count == 1
        assert expired_record.status == "expired"

    @pytest.mark.asyncio
    async def test_no_expired(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        dao = _make_dao(session)

        count = await dao.mark_expired_before(datetime.now())
        assert count == 0


class TestListForExport:
    """导出全量查询测试"""

    @pytest.mark.asyncio
    async def test_export_with_keyword(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _make_record(1),
            _make_record(2),
        ]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        dao = _make_dao(session)

        items = await dao.list_for_export(keyword="会员", limit=1000, offset=0)
        assert len(items) == 2
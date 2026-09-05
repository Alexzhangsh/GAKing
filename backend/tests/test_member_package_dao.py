# @ai-generated
"""
X02-1 会员套餐 DAO 单元测试
覆盖：get_by_code / paginate_packages / list_on_shelf
使用 AsyncMock 模拟 session，不依赖真实 DB/Redis
"""
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, ".")

from src.dao.member_package_dao import MemberPackageDAO
from src.models.business.member_package_model import MemberPackage


def _make_package(
    package_id: int = 1,
    package_code: str = "VIP_MONTH",
    package_name: str = "月度会员",
    status: int = 1,
    sort_order: int = 0,
) -> MemberPackage:
    pkg = MagicMock(spec=MemberPackage)
    pkg.id = package_id
    pkg.package_code = package_code
    pkg.package_name = package_name
    pkg.status = status
    pkg.sort_order = sort_order
    return pkg


def _make_dao(session=None):
    session = session or AsyncMock()
    return MemberPackageDAO(session)


class TestGetByCode:
    """按编码查询测试"""

    @pytest.mark.asyncio
    async def test_found(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.execute.return_value.scalar_one_or_none = MagicMock(
            return_value=_make_package(package_code="VIP_MONTH")
        )
        dao = _make_dao(session)

        pkg = await dao.get_by_code("VIP_MONTH")
        assert pkg is not None
        assert pkg.package_code == "VIP_MONTH"

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        dao = _make_dao(session)

        pkg = await dao.get_by_code("NOT_EXIST")
        assert pkg is None


class TestPaginatePackages:
    """分页查询测试"""

    @pytest.mark.asyncio
    async def test_paginate_default(self):
        session = AsyncMock()
        # 第一次 execute → 总数，第二次 execute → 列表
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=2)
        list_result = MagicMock()
        list_result.scalars.return_value.all = MagicMock(
            return_value=[_make_package(1), _make_package(2)]
        )
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        dao = _make_dao(session)

        items, total = await dao.paginate_packages(page=1, page_size=20)
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_paginate_with_filters(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=1)
        list_result = MagicMock()
        list_result.scalars.return_value.all = MagicMock(
            return_value=[_make_package(1, status=1)]
        )
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        dao = _make_dao(session)

        items, total = await dao.paginate_packages(
            page=1, page_size=20, status=1, keyword="会员"
        )
        assert total == 1
        assert items[0].status == 1

    @pytest.mark.asyncio
    async def test_paginate_invalid_page(self):
        """非法页码自动修正"""
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=0)
        list_result = MagicMock()
        list_result.scalars.return_value.all = MagicMock(return_value=[])
        session.execute = AsyncMock(side_effect=[count_result, list_result])
        dao = _make_dao(session)

        items, total = await dao.paginate_packages(page=0, page_size=0)
        assert total == 0
        assert items == []


class TestListOnShelf:
    """上架套餐列表测试"""

    @pytest.mark.asyncio
    async def test_list_on_shelf(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _make_package(1, status=1),
            _make_package(2, status=1),
        ]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        dao = _make_dao(session)

        items = await dao.list_on_shelf()
        assert len(items) == 2
        assert all(i.status == 1 for i in items)

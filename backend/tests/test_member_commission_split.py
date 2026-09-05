# @ai-generated
"""
X02-1 结算服务会员分佣集成测试
覆盖：_resolve_split 方法（会员档位分佣优先，否则按渠道配置）
使用 AsyncMock 模拟依赖，不依赖真实 DB/Redis
"""
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")

from src.services.commission_rule_engine import CommissionSplit
from src.services.commission_settlement_service import CommissionSettlementService


def _make_order(
    order_id: int = 1,
    user_id: int = 100,
    channel_code: str = "myq",
):
    order = MagicMock()
    order.id = order_id
    order.user_id = user_id
    order.channel_code = channel_code
    return order


def _make_service(
    order_dao=None,
    flow_dao=None,
    settlement_dao=None,
    rule_engine=None,
):
    order_dao = order_dao or MagicMock()
    flow_dao = flow_dao or MagicMock()
    settlement_dao = settlement_dao or MagicMock()
    rule_engine = rule_engine or MagicMock()
    return CommissionSettlementService(
        order_dao, flow_dao, settlement_dao, rule_engine
    )


class TestResolveSplit:
    """_resolve_split 会员分佣比例解析测试"""

    @pytest.mark.asyncio
    async def test_member_rate_priority(self):
        """会员存在档位分佣比例时，直接使用档位比例"""
        order = _make_order(user_id=100)
        svc = _make_service()

        with patch(
            "src.services.commission_settlement_service.get_member_commission_rate",
            AsyncMock(return_value=Decimal("0.85")),
        ) as mock_rate:
            split = await svc._resolve_split(order)

        assert split.user_rate == Decimal("0.85")
        assert split.platform_rate == Decimal("0.15")

    @pytest.mark.asyncio
    async def test_no_member_fallback_to_channel(self):
        """无会员身份时，回退到渠道配置"""
        order = _make_order(user_id=100, channel_code="myq")
        rule_engine = MagicMock()
        rule_engine.get_rates = AsyncMock(
            return_value=CommissionSplit(
                user_rate=Decimal("0.80"),
                platform_rate=Decimal("0.20"),
            )
        )
        svc = _make_service(rule_engine=rule_engine)

        with patch(
            "src.services.commission_settlement_service.get_member_commission_rate",
            AsyncMock(return_value=None),
        ):
            with patch(
                "src.services.commission_settlement_service.resolve_user_type_async",
                AsyncMock(return_value="NORMAL"),
            ):
                split = await svc._resolve_split(order)

        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")

    @pytest.mark.asyncio
    async def test_member_rate_none_fallback_vip(self):
        """会员身份但无档位比例时，按 VIP 渠道配置"""
        order = _make_order(user_id=100, channel_code="orderx")
        rule_engine = MagicMock()
        rule_engine.get_rates = AsyncMock(
            return_value=CommissionSplit(
                user_rate=Decimal("0.70"),
                platform_rate=Decimal("0.30"),
            ),
        )
        svc = _make_service(rule_engine=rule_engine)

        with patch(
            "src.services.commission_settlement_service.get_member_commission_rate",
            AsyncMock(return_value=None),
        ):
            with patch(
                "src.services.commission_settlement_service.resolve_user_type_async",
                AsyncMock(return_value="VIP"),
            ):
                split = await svc._resolve_split(order)

        assert split.user_rate == Decimal("0.70")
        assert split.platform_rate == Decimal("0.30")
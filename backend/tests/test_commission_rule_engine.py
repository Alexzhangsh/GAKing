# @ai-generated
"""
B07 佣金比例规则引擎单元测试
覆盖：默认兜底 / 渠道配置覆盖 / 默认配置 / 配置异常回退 / 总和校验 / 计算精度 / VIP预留
"""
import json
import sys
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, ".")

from src.config.b07_constants import UserType
from src.services.commission_rule_engine import (
    CommissionRuleEngine,
    CommissionSplit,
    resolve_user_type,
)


# ══════════════════════════════════════════════════════
# get_rates 测试
# ══════════════════════════════════════════════════════


class TestGetRates:
    """get_rates 方法测试"""

    @pytest.mark.asyncio
    async def test_no_config_loader_uses_defaults(self):
        """无配置加载器 → 使用兜底常量 80%/20%"""
        engine = CommissionRuleEngine(config_loader=None)
        split = await engine.get_rates("myq", UserType.NORMAL)
        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")

    @pytest.mark.asyncio
    async def test_channel_config_overrides_default(self):
        """渠道专属配置优先于默认配置"""
        channel_config = json.dumps(
            {"NORMAL": {"user_rate": "0.85", "platform_rate": "0.15"}}
        )
        default_config = json.dumps(
            {"NORMAL": {"user_rate": "0.80", "platform_rate": "0.20"}}
        )

        async def loader(key: str):
            if key.startswith("commission_rule:channel:"):
                return channel_config
            elif key == "commission_rule:default":
                return default_config
            return None

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("myq", UserType.NORMAL)
        assert split.user_rate == Decimal("0.85")
        assert split.platform_rate == Decimal("0.15")

    @pytest.mark.asyncio
    async def test_default_config_used_when_no_channel(self):
        """无渠道配置时使用默认配置"""
        default_config = json.dumps(
            {"NORMAL": {"user_rate": "0.90", "platform_rate": "0.10"}}
        )

        async def loader(key: str):
            if key == "commission_rule:default":
                return default_config
            return None

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("orderx", UserType.NORMAL)
        assert split.user_rate == Decimal("0.90")
        assert split.platform_rate == Decimal("0.10")

    @pytest.mark.asyncio
    async def test_config_loader_returns_none_falls_back(self):
        """配置加载器返回 None → 兜底常量"""

        async def loader(key: str):
            return None

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("dta", UserType.NORMAL)
        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back(self):
        """配置 JSON 格式错误 → 兜底常量"""

        async def loader(key: str):
            return "{invalid json"

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("myq", UserType.NORMAL)
        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")

    @pytest.mark.asyncio
    async def test_missing_user_type_falls_back(self):
        """配置中缺少当前用户类型 → 兜底"""
        config = json.dumps({"VIP": {"user_rate": "0.90", "platform_rate": "0.10"}})

        async def loader(key: str):
            return config

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("myq", UserType.NORMAL)
        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")

    @pytest.mark.asyncio
    async def test_vip_type_with_config(self):
        """VIP 用户类型配置"""
        config = json.dumps(
            {
                "NORMAL": {"user_rate": "0.80", "platform_rate": "0.20"},
                "VIP": {"user_rate": "0.90", "platform_rate": "0.10"},
            }
        )

        async def loader(key: str):
            return config

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("myq", UserType.VIP)
        assert split.user_rate == Decimal("0.90")
        assert split.platform_rate == Decimal("0.10")

    @pytest.mark.asyncio
    async def test_rate_sum_validation_fails(self):
        """比例总和不等于 1.0 → 抛 ValueError"""
        config = json.dumps({"NORMAL": {"user_rate": "0.80", "platform_rate": "0.30"}})

        async def loader(key: str):
            return config

        engine = CommissionRuleEngine(config_loader=loader)
        with pytest.raises(ValueError, match="总和不等于 1.0"):
            await engine.get_rates("myq", UserType.NORMAL)

    @pytest.mark.asyncio
    async def test_loader_exception_falls_back(self):
        """配置加载器抛异常 → 兜底常量"""

        async def loader(key: str):
            raise RuntimeError("DB 连接失败")

        engine = CommissionRuleEngine(config_loader=loader)
        split = await engine.get_rates("myq", UserType.NORMAL)
        assert split.user_rate == Decimal("0.80")
        assert split.platform_rate == Decimal("0.20")


# ══════════════════════════════════════════════════════
# calculate 测试
# ══════════════════════════════════════════════════════


class TestCalculate:
    """calculate 方法测试"""

    def test_normal_calculation(self):
        """常规金额计算"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        result = CommissionRuleEngine.calculate(Decimal("100.00"), split)
        assert result.user_commission == Decimal("80.00")
        assert result.platform_commission == Decimal("20.00")
        assert result.total_commission == Decimal("100.00")

    def test_zero_commission(self):
        """零佣金"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        result = CommissionRuleEngine.calculate(Decimal("0.00"), split)
        assert result.user_commission == Decimal("0.00")
        assert result.platform_commission == Decimal("0.00")

    def test_precision_rounding(self):
        """精度舍入测试（ROUND_HALF_UP）"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        # 33.33 * 0.80 = 26.664 → 26.66
        result = CommissionRuleEngine.calculate(Decimal("33.33"), split)
        assert result.user_commission == Decimal("26.66")
        # 33.33 - 26.66 = 6.67
        assert result.platform_commission == Decimal("6.67")

    def test_subtraction_guarantees_sum(self):
        """减法保证总和精确"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        result = CommissionRuleEngine.calculate(Decimal("99.99"), split)
        # 99.99 * 0.80 = 79.992 → 79.99
        assert result.user_commission == Decimal("79.99")
        # 99.99 - 79.99 = 20.00
        assert result.platform_commission == Decimal("20.00")
        # 总和 == 原始金额
        assert result.user_commission + result.platform_commission == Decimal("99.99")

    def test_large_amount(self):
        """大金额"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        result = CommissionRuleEngine.calculate(Decimal("99999.99"), split)
        assert result.user_commission == Decimal("79999.99")
        assert result.platform_commission == Decimal("20000.00")

    def test_custom_rates(self):
        """自定义比例"""
        split = CommissionSplit(Decimal("0.85"), Decimal("0.15"))
        result = CommissionRuleEngine.calculate(Decimal("1000.00"), split)
        assert result.user_commission == Decimal("850.00")
        assert result.platform_commission == Decimal("150.00")

    def test_string_input(self):
        """字符串输入自动转 Decimal"""
        split = CommissionSplit(Decimal("0.80"), Decimal("0.20"))
        result = CommissionRuleEngine.calculate("100.00", split)
        assert result.user_commission == Decimal("80.00")

    def test_rates_preserved_in_result(self):
        """结果中保留比例信息"""
        split = CommissionSplit(Decimal("0.75"), Decimal("0.25"))
        result = CommissionRuleEngine.calculate(Decimal("100.00"), split)
        assert result.user_rate == Decimal("0.75")
        assert result.platform_rate == Decimal("0.25")


# ══════════════════════════════════════════════════════
# resolve_user_type 测试
# ══════════════════════════════════════════════════════


class TestResolveUserType:
    """resolve_user_type 函数测试"""

    def test_returns_normal(self):
        """当前固定返回 NORMAL"""
        assert resolve_user_type(1) == UserType.NORMAL
        assert resolve_user_type(999) == UserType.NORMAL
        assert resolve_user_type(0) == UserType.NORMAL

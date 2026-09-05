# @ai-generated
"""
B09 提现规则校验 + 手续费计算 单元测试（AsyncMock 模拟，不依赖真实 DB/Redis）

覆盖范围（目标覆盖率 ≥90%）：
 1. WithdrawFeeCalculator
    - calculate 单一费率兜底（无阶梯配置 → PayConfigUtil 单一费率）
    - calculate 阶梯命中（3 档区间匹配，含 max_amount=None 无上限档）
    - _calc_single（max(amount×rate, min_fee) 公式）
    - _calc_by_tiers（区间匹配 / 未命中返回 None）
    - _load_tiers（Redis 命中 / 空标记 / 解析失败 / Redis 异常降级）
    - _parse_tiers（正常解析 / 单档异常跳过 / 空列表）
    - set_tiers_config（写入前校验 + 失效旧缓存）
    - invalidate_tiers_cache
 2. WithdrawRuleValidator
    - validate_all 全通过（最低金额+单日限额+冻结足额+手续费计算）
    - _check_min_amount（低于 10 元拒绝）
    - _check_daily_limit（Redis 命中 / DAO 回源 / 超限拒绝 / 异常降级跳过）
    - _check_sufficient_balance（余额足额 / 余额不足 / 账户不存在 / 异常降级）
    - _get_daily_used（缓存命中数值 / 空标记 / 缓存损坏回源 / 回写缓存）
    - invalidate_daily_used_cache
 3. UserWithdrawApplyDAO.sum_apply_amount_by_user_and_date
    - 正常查询返回累计金额
    - 无记录返回 Decimal("0")
 4. WithdrawService.apply_withdraw（B09 增强后）
    - 规则校验通过 → 正常发起提现
    - 最低金额不足 → ValueError
    - 单日限额超限 → ValueError
    - 余额不足 → ValueError
    - 阶梯手续费正确计算
    - 提现成功后失效单日累计缓存
"""
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, ".")

from src.common.withdraw_fee_calculator import (
    FeeResult,
    FeeTier,
    WithdrawFeeCalculator,
)
from src.common.withdraw_rule_validator import WithdrawRuleValidator
from src.common.pay_config_util import PayConfigUtil, WithdrawFeeConfig
from src.config.constants import (
    WITHDRAW_DAILY_LIMIT,
    WITHDRAW_FEE_MIN,
    WITHDRAW_FEE_QUANTIZE,
    WITHDRAW_FEE_RATE,
    WITHDRAW_MIN_AMOUNT,
)
from src.services.withdraw_service import WithdrawService


# ════════════════════════════════════════════════════════════════════
# WithdrawFeeCalculator 测试
# ════════════════════════════════════════════════════════════════════


class TestWithdrawFeeCalculator:
    """手续费计算器单元测试"""

    @pytest.mark.asyncio
    async def test_calculate_single_fallback_no_tiers(self):
        """无阶梯配置 → 回退单一费率"""
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=[])
        ):
            with patch.object(
                PayConfigUtil,
                "get_withdraw_config",
                new=AsyncMock(
                    return_value=WithdrawFeeConfig(
                        rate=WITHDRAW_FEE_RATE, min_fee=WITHDRAW_FEE_MIN
                    )
                ),
            ):
                result = await WithdrawFeeCalculator.calculate(Decimal("1000"))
        assert result.calc_mode == "single"
        assert result.tier_label == "single"
        # 1000 × 0.001 = 1.0, max(1.0, 1.0) = 1.00
        assert result.fee == Decimal("1.00")

    @pytest.mark.asyncio
    async def test_calculate_single_fallback_min_fee_applies(self):
        """小金额触发最低手续费兜底"""
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=[])
        ):
            with patch.object(
                PayConfigUtil,
                "get_withdraw_config",
                new=AsyncMock(
                    return_value=WithdrawFeeConfig(
                        rate=Decimal("0.001"), min_fee=Decimal("1.00")
                    )
                ),
            ):
                # 100 × 0.001 = 0.1 < 1.0 → 取最低 1.00
                result = await WithdrawFeeCalculator.calculate(Decimal("100"))
        assert result.fee == Decimal("1.00")
        assert result.calc_mode == "single"

    @pytest.mark.asyncio
    async def test_calculate_tier_hit_first_bracket(self):
        """阶梯命中第一档（0-1000）"""
        tiers = [
            FeeTier(
                min_amount=Decimal("0"),
                max_amount=Decimal("1000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            ),
            FeeTier(
                min_amount=Decimal("1000"),
                max_amount=Decimal("10000"),
                rate=Decimal("0.0008"),
                min_fee=Decimal("1.00"),
            ),
            FeeTier(
                min_amount=Decimal("10000"),
                max_amount=None,
                rate=Decimal("0.0005"),
                min_fee=Decimal("2.00"),
            ),
        ]
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=tiers)
        ):
            # 500 在 0-1000 区间
            result = await WithdrawFeeCalculator.calculate(Decimal("500"))
        assert result.calc_mode == "tier"
        assert result.tier_label == "0-1000"
        # 500 × 0.001 = 0.5 < 1.0 → 取最低 1.00
        assert result.fee == Decimal("1.00")

    @pytest.mark.asyncio
    async def test_calculate_tier_hit_second_bracket(self):
        """阶梯命中第二档（1000-10000）"""
        tiers = [
            FeeTier(
                min_amount=Decimal("0"),
                max_amount=Decimal("1000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            ),
            FeeTier(
                min_amount=Decimal("1000"),
                max_amount=Decimal("10000"),
                rate=Decimal("0.0008"),
                min_fee=Decimal("1.00"),
            ),
            FeeTier(
                min_amount=Decimal("10000"),
                max_amount=None,
                rate=Decimal("0.0005"),
                min_fee=Decimal("2.00"),
            ),
        ]
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=tiers)
        ):
            # 5000 在 1000-10000 区间
            result = await WithdrawFeeCalculator.calculate(Decimal("5000"))
        assert result.calc_mode == "tier"
        assert result.tier_label == "1000-10000"
        # 5000 × 0.0008 = 4.0 > 1.0 → 取 4.00
        assert result.fee == Decimal("4.00")

    @pytest.mark.asyncio
    async def test_calculate_tier_hit_unbounded_bracket(self):
        """阶梯命中无上限档（10000+）"""
        tiers = [
            FeeTier(
                min_amount=Decimal("0"),
                max_amount=Decimal("1000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            ),
            FeeTier(
                min_amount=Decimal("10000"),
                max_amount=None,
                rate=Decimal("0.0005"),
                min_fee=Decimal("2.00"),
            ),
        ]
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=tiers)
        ):
            # 20000 在 10000+ 区间
            result = await WithdrawFeeCalculator.calculate(Decimal("20000"))
        assert result.calc_mode == "tier"
        assert result.tier_label == "10000+"
        # 20000 × 0.0005 = 10.0 > 2.0 → 取 10.00
        assert result.fee == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_calculate_tier_not_hit_fallback_single(self):
        """阶梯存在但金额未命中任何区间 → 回退单一费率"""
        tiers = [
            FeeTier(
                min_amount=Decimal("1000"),
                max_amount=Decimal("5000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            ),
        ]
        with patch.object(
            WithdrawFeeCalculator, "_load_tiers", new=AsyncMock(return_value=tiers)
        ):
            with patch.object(
                PayConfigUtil,
                "get_withdraw_config",
                new=AsyncMock(
                    return_value=WithdrawFeeConfig(
                        rate=Decimal("0.001"), min_fee=Decimal("1.00")
                    )
                ),
            ):
                # 100 不在 1000-5000 区间 → 回退
                result = await WithdrawFeeCalculator.calculate(Decimal("100"))
        assert result.calc_mode == "single"
        assert result.fee == Decimal("1.00")

    def test_calc_single_normal(self):
        """单一费率正常计算：amount × rate"""
        cfg = WithdrawFeeConfig(rate=Decimal("0.001"), min_fee=Decimal("1.00"))
        fee = WithdrawFeeCalculator._calc_single(Decimal("5000"), cfg)
        # 5000 × 0.001 = 5.0 > 1.0
        assert fee == Decimal("5.00")

    def test_calc_single_min_fee_applies(self):
        """单一费率触发最低手续费"""
        cfg = WithdrawFeeConfig(rate=Decimal("0.001"), min_fee=Decimal("1.00"))
        fee = WithdrawFeeCalculator._calc_single(Decimal("100"), cfg)
        # 100 × 0.001 = 0.1 < 1.0
        assert fee == Decimal("1.00")

    def test_calc_by_tiers_hit(self):
        """阶梯匹配命中"""
        tiers = [
            FeeTier(
                min_amount=Decimal("0"),
                max_amount=Decimal("1000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            )
        ]
        result = WithdrawFeeCalculator._calc_by_tiers(Decimal("500"), tiers)
        assert result is not None
        assert result.calc_mode == "tier"
        assert result.fee == Decimal("1.00")  # max(0.5, 1.0)

    def test_calc_by_tiers_not_hit(self):
        """阶梯未命中返回 None"""
        tiers = [
            FeeTier(
                min_amount=Decimal("1000"),
                max_amount=Decimal("5000"),
                rate=Decimal("0.001"),
                min_fee=Decimal("1.00"),
            )
        ]
        result = WithdrawFeeCalculator._calc_by_tiers(Decimal("100"), tiers)
        assert result is None

    @pytest.mark.asyncio
    async def test_load_tiers_cache_hit(self):
        """Redis 缓存命中阶梯配置"""
        cached_json = json.dumps(
            [
                {
                    "min_amount": "0",
                    "max_amount": "1000",
                    "rate": "0.001",
                    "min_fee": "1.00",
                }
            ]
        )
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.get",
            new=AsyncMock(return_value=cached_json),
        ):
            tiers = await WithdrawFeeCalculator._load_tiers()
        assert len(tiers) == 1
        assert tiers[0].min_amount == Decimal("0")
        assert tiers[0].rate == Decimal("0.001")

    @pytest.mark.asyncio
    async def test_load_tiers_empty_marker(self):
        """Redis 空标记 → 返回空列表"""
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.get",
            new=AsyncMock(return_value="__EMPTY__"),
        ):
            tiers = await WithdrawFeeCalculator._load_tiers()
        assert tiers == []

    @pytest.mark.asyncio
    async def test_load_tiers_cache_miss_returns_empty(self):
        """Redis 未命中 → 返回空列表（触发单一兜底）"""
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.get",
            new=AsyncMock(return_value=None),
        ):
            tiers = await WithdrawFeeCalculator._load_tiers()
        assert tiers == []

    @pytest.mark.asyncio
    async def test_load_tiers_json_decode_error(self):
        """JSON 解析失败 → 降级返回空列表"""
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.get",
            new=AsyncMock(return_value="{invalid json"),
        ):
            tiers = await WithdrawFeeCalculator._load_tiers()
        assert tiers == []

    @pytest.mark.asyncio
    async def test_load_tiers_redis_exception(self):
        """Redis 异常 → 降级返回空列表"""
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.get",
            new=AsyncMock(side_effect=Exception("redis down")),
        ):
            tiers = await WithdrawFeeCalculator._load_tiers()
        assert tiers == []

    def test_parse_tiers_normal(self):
        """正常解析多档阶梯配置"""
        data = [
            {
                "min_amount": "0",
                "max_amount": "1000",
                "rate": "0.001",
                "min_fee": "1.00",
            },
            {
                "min_amount": "1000",
                "max_amount": None,
                "rate": "0.0005",
                "min_fee": "2.00",
            },
        ]
        tiers = WithdrawFeeCalculator._parse_tiers(data)
        assert len(tiers) == 2
        # 按min_amount升序
        assert tiers[0].min_amount == Decimal("0")
        assert tiers[1].min_amount == Decimal("1000")
        assert tiers[1].max_amount is None

    def test_parse_tiers_skip_bad_entry(self):
        """单档解析失败跳过，不阻断整体"""
        data = [
            {"min_amount": "0", "rate": "0.001"},  # 缺 max_amount 但有 min_fee 默认0
            {"rate": "0.001"},  # 缺 min_amount → KeyError 跳过
            {
                "min_amount": "1000",
                "max_amount": None,
                "rate": "0.0005",
                "min_fee": "2.00",
            },
        ]
        tiers = WithdrawFeeCalculator._parse_tiers(data)
        assert len(tiers) == 2  # 跳过第2条

    def test_parse_tiers_empty_list(self):
        """空列表返回空"""
        tiers = WithdrawFeeCalculator._parse_tiers([])
        assert tiers == []

    def test_parse_tiers_default_min_fee(self):
        """min_fee 缺失默认 0"""
        data = [{"min_amount": "0", "max_amount": "1000", "rate": "0.001"}]
        tiers = WithdrawFeeCalculator._parse_tiers(data)
        assert tiers[0].min_fee == Decimal("0")

    @pytest.mark.asyncio
    async def test_invalidate_tiers_cache(self):
        """失效阶梯缓存"""
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.delete",
            new=AsyncMock(return_value=1),
        ) as mock_del:
            await WithdrawFeeCalculator.invalidate_tiers_cache()
        mock_del.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_tiers_config_success(self):
        """写入阶梯配置成功"""
        data = [
            {
                "min_amount": "0",
                "max_amount": "1000",
                "rate": "0.001",
                "min_fee": "1.00",
            }
        ]
        with patch(
            "src.common.withdraw_fee_calculator.RedisClient.set_json",
            new=AsyncMock(return_value=True),
        ) as mock_set:
            await WithdrawFeeCalculator.set_tiers_config(data)
        mock_set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_tiers_config_invalid_raises(self):
        """写入无效阶梯配置抛 ValueError"""
        bad_data = [{"rate": "0.001"}]  # 缺 min_amount，解析后为空
        with pytest.raises(ValueError, match="解析失败或为空"):
            await WithdrawFeeCalculator.set_tiers_config(bad_data)


# ════════════════════════════════════════════════════════════════════
# WithdrawRuleValidator 测试
# ════════════════════════════════════════════════════════════════════


class TestWithdrawRuleValidator:
    """提现规则校验器单元测试"""

    def _make_validator(
        self,
        account_dao: Optional[MagicMock] = None,
        apply_dao: Optional[MagicMock] = None,
    ) -> WithdrawRuleValidator:
        if account_dao is None:
            account_dao = MagicMock()
        if apply_dao is None:
            apply_dao = MagicMock()
        return WithdrawRuleValidator(account_dao, apply_dao)

    @pytest.mark.asyncio
    async def test_validate_all_pass(self):
        """全部校验通过"""
        validator = self._make_validator()
        # mock 余额充足
        validator.account_dao.get_account_cached = AsyncMock(
            return_value={"available_balance": Decimal("1000")}
        )
        # mock 单日累计 0
        validator.apply_dao.sum_apply_amount_by_user_and_date = AsyncMock(
            return_value=Decimal("0")
        )
        # mock Redis 未命中 → 查 DAO
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "src.common.withdraw_rule_validator.RedisClient.set",
                new=AsyncMock(return_value=True),
            ):
                with patch.object(
                    WithdrawFeeCalculator,
                    "calculate",
                    new=AsyncMock(
                        return_value=FeeResult(
                            fee=Decimal("1.00"),
                            tier_label="single",
                            calc_mode="single",
                        )
                    ),
                ):
                    fee, tier_label = await validator.validate_all(1, Decimal("100"))
        assert fee == Decimal("1.00")
        assert tier_label == "single"

    @pytest.mark.asyncio
    async def test_validate_all_min_amount_rejected(self):
        """低于最低提现金额被拒"""
        validator = self._make_validator()
        with pytest.raises(ValueError, match="最低提现金额"):
            await validator.validate_all(1, Decimal("5"))  # 5 < 10

    @pytest.mark.asyncio
    async def test_validate_all_daily_limit_exceeded(self):
        """单日限额超限被拒"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(
            return_value={"available_balance": Decimal("100000")}
        )
        # mock Redis 命中已用 49999
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="49999.00"),
        ):
            with pytest.raises(ValueError, match="超出单日提现限额"):
                # 49999 + 100 = 50099 > 50000
                await validator.validate_all(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_validate_all_insufficient_balance(self):
        """余额不足被拒"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(
            return_value={"available_balance": Decimal("50")}
        )
        # mock 单日累计 0（Redis 命中空标记）
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="__EMPTY__"),
        ):
            with pytest.raises(ValueError, match="可用余额不足"):
                # 余额 50 < 提现 100
                await validator.validate_all(1, Decimal("100"))

    def test_check_min_amount_pass(self):
        """最低金额校验通过"""
        WithdrawRuleValidator._check_min_amount(Decimal("10"))
        WithdrawRuleValidator._check_min_amount(Decimal("100"))

    def test_check_min_amount_rejected(self):
        """最低金额校验拒绝"""
        with pytest.raises(ValueError, match="最低提现金额"):
            WithdrawRuleValidator._check_min_amount(Decimal("9.99"))
        with pytest.raises(ValueError, match="最低提现金额"):
            WithdrawRuleValidator._check_min_amount(Decimal("0"))

    @pytest.mark.asyncio
    async def test_check_daily_limit_cache_hit(self):
        """单日限额：Redis 缓存命中"""
        validator = self._make_validator()
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="1000.00"),
        ):
            # 已用 1000 + 本次 100 = 1100 < 50000
            await validator._check_daily_limit(1, Decimal("100"), WITHDRAW_DAILY_LIMIT)
        # DAO 不应被调用
        validator.apply_dao.sum_apply_amount_by_user_and_date.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_daily_limit_cache_miss_query_dao(self):
        """单日限额：缓存未命中查 DAO 并回写"""
        validator = self._make_validator()
        validator.apply_dao.sum_apply_amount_by_user_and_date = AsyncMock(
            return_value=Decimal("2000")
        )
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "src.common.withdraw_rule_validator.RedisClient.set",
                new=AsyncMock(return_value=True),
            ) as mock_set:
                await validator._check_daily_limit(
                    1, Decimal("100"), WITHDRAW_DAILY_LIMIT
                )
        validator.apply_dao.sum_apply_amount_by_user_and_date.assert_awaited_once()
        mock_set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_daily_limit_zero_used_set_empty(self):
        """单日限额：累计为 0 写空标记"""
        validator = self._make_validator()
        validator.apply_dao.sum_apply_amount_by_user_and_date = AsyncMock(
            return_value=Decimal("0")
        )
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "src.common.withdraw_rule_validator.RedisClient.set_empty_cache",
                new=AsyncMock(return_value=True),
            ) as mock_empty:
                with patch(
                    "src.common.withdraw_rule_validator.RedisClient.expire",
                    new=AsyncMock(return_value=True),
                ):
                    await validator._check_daily_limit(
                        1, Decimal("100"), WITHDRAW_DAILY_LIMIT
                    )
        mock_empty.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_daily_limit_exceeded_raises(self):
        """单日限额超限抛 ValueError"""
        validator = self._make_validator()
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="49999.00"),
        ):
            with pytest.raises(ValueError, match="超出单日提现限额"):
                await validator._check_daily_limit(
                    1, Decimal("100"), WITHDRAW_DAILY_LIMIT
                )

    @pytest.mark.asyncio
    async def test_check_daily_limit_exception_degraded(self):
        """单日限额校验异常降级跳过（不阻断提现）"""
        validator = self._make_validator()
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(side_effect=Exception("redis down")),
        ):
            # 异常不抛出，静默降级
            await validator._check_daily_limit(1, Decimal("100"), WITHDRAW_DAILY_LIMIT)

    @pytest.mark.asyncio
    async def test_get_daily_used_cache_corrupt_fallback_dao(self):
        """缓存损坏回源 DAO"""
        validator = self._make_validator()
        validator.apply_dao.sum_apply_amount_by_user_and_date = AsyncMock(
            return_value=Decimal("500")
        )
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="not_a_number"),
        ):
            with patch(
                "src.common.withdraw_rule_validator.RedisClient.set",
                new=AsyncMock(return_value=True),
            ):
                used = await validator._get_daily_used(1, date.today())
        assert used == Decimal("500")
        validator.apply_dao.sum_apply_amount_by_user_and_date.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_daily_used_empty_marker(self):
        """空标记返回 0"""
        validator = self._make_validator()
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="__EMPTY__"),
        ):
            used = await validator._get_daily_used(1, date.today())
        assert used == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_get_daily_used_cache_hit_value(self):
        """缓存命中数值"""
        validator = self._make_validator()
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.get",
            new=AsyncMock(return_value="1500.50"),
        ):
            used = await validator._get_daily_used(1, date.today())
        assert used == Decimal("1500.50")

    @pytest.mark.asyncio
    async def test_check_sufficient_balance_pass(self):
        """余额充足校验通过"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(
            return_value={"available_balance": Decimal("500")}
        )
        await validator._check_sufficient_balance(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_check_sufficient_balance_insufficient(self):
        """余额不足被拒"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(
            return_value={"available_balance": Decimal("50")}
        )
        with pytest.raises(ValueError, match="可用余额不足"):
            await validator._check_sufficient_balance(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_check_sufficient_balance_account_none(self):
        """账户不存在 → 降级让 DAO 兜底"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(return_value=None)
        # 不抛异常，静默通过
        await validator._check_sufficient_balance(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_check_sufficient_balance_exception_degraded(self):
        """余额查询异常降级跳过"""
        validator = self._make_validator()
        validator.account_dao.get_account_cached = AsyncMock(
            side_effect=Exception("redis down")
        )
        # 异常不阻断
        await validator._check_sufficient_balance(1, Decimal("100"))

    def test_daily_used_key_format(self):
        """缓存 key 格式正确"""
        key = WithdrawRuleValidator._daily_used_key(123, date(2026, 8, 2))
        assert "123" in key
        assert "20260802" in key

    def test_seconds_until_end_of_day(self):
        """TTL 计算合理（60 ~ 86400）"""
        ttl = WithdrawRuleValidator._seconds_until_end_of_day()
        assert 60 <= ttl <= 86400

    @pytest.mark.asyncio
    async def test_invalidate_daily_used_cache(self):
        """失效单日累计缓存"""
        with patch(
            "src.common.withdraw_rule_validator.RedisClient.delete",
            new=AsyncMock(return_value=1),
        ) as mock_del:
            await WithdrawRuleValidator.invalidate_daily_used_cache(123)
        mock_del.assert_awaited_once()


# ════════════════════════════════════════════════════════════════════
# UserWithdrawApplyDAO.sum_apply_amount_by_user_and_date 测试
# ════════════════════════════════════════════════════════════════════


class TestUserWithdrawApplyDAODailySum:
    """DAO 单日累计查询测试"""

    @pytest.mark.asyncio
    async def test_sum_returns_value(self):
        """查询返回累计金额"""
        from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("1500.00")
        mock_session.execute = AsyncMock(return_value=mock_result)

        dao = UserWithdrawApplyDAO(mock_session)
        total = await dao.sum_apply_amount_by_user_and_date(1, date(2026, 8, 2))
        assert total == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_sum_returns_zero_when_none(self):
        """无记录返回 0"""
        from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        dao = UserWithdrawApplyDAO(mock_session)
        total = await dao.sum_apply_amount_by_user_and_date(1, date(2026, 8, 2))
        assert total == Decimal("0")

    @pytest.mark.asyncio
    async def test_sum_returns_zero_on_parse_error(self):
        """解析异常返回 0"""
        from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = "invalid_decimal"
        mock_session.execute = AsyncMock(return_value=mock_result)

        dao = UserWithdrawApplyDAO(mock_session)
        total = await dao.sum_apply_amount_by_user_and_date(1, date(2026, 8, 2))
        assert total == Decimal("0")


# ════════════════════════════════════════════════════════════════════
# WithdrawService.apply_withdraw（B09 增强后）测试
# ════════════════════════════════════════════════════════════════════


class TestWithdrawServiceB09:
    """WithdrawService B09 增强后的 apply_withdraw 测试"""

    def _make_service(
        self,
        account_dao: Optional[MagicMock] = None,
        apply_dao: Optional[MagicMock] = None,
    ) -> WithdrawService:
        if account_dao is None:
            account_dao = MagicMock()
        if apply_dao is None:
            apply_dao = MagicMock()
        return WithdrawService(account_dao, apply_dao)

    @pytest.mark.asyncio
    async def test_apply_withdraw_success_with_tier_fee(self):
        """B09 增强：阶梯手续费正确计算"""
        svc = self._make_service()
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        mock_record = MagicMock()
        mock_record.to_dict.return_value = {"apply_no": "GAKW001", "fee": "4.00"}
        svc.apply_dao.create = AsyncMock(return_value=mock_record)

        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value="owner_123"),
                ):
                    with patch(
                        "src.services.withdraw_service.LockUtil.release_lock",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "src.services.withdraw_service.WithdrawRuleValidator"
                        ) as MockValidator:
                            mock_validator_inst = MagicMock()
                            mock_validator_inst.validate_all = AsyncMock(
                                return_value=(Decimal("4.00"), "1000-10000")
                            )
                            mock_validator_inst.invalidate_daily_used_cache = AsyncMock(
                                return_value=None
                            )
                            MockValidator.return_value = mock_validator_inst
                            MockValidator.invalidate_daily_used_cache = AsyncMock(
                                return_value=None
                            )

                            result = await svc.apply_withdraw(1, Decimal("5000"))

        assert result["fee"] == "4.00"
        # 验证余额扣减调用
        svc.account_dao.adjust_balance.assert_awaited_once()
        # 验证申请创建调用
        svc.apply_dao.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_withdraw_min_amount_rejected(self):
        """低于最低提现金额被拒"""
        svc = self._make_service()
        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with pytest.raises(ValueError, match="最低提现金额"):
                    await svc.apply_withdraw(1, Decimal("5"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_idempotent_blocked(self):
        """幂等防重复提交拦截"""
        svc = self._make_service()
        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(ValueError, match="操作过于频繁"):
                await svc.apply_withdraw(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_lock_failed(self):
        """用户级分布式锁获取失败"""
        svc = self._make_service()
        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value=None),
                ):
                    with pytest.raises(ValueError, match="正在处理"):
                        await svc.apply_withdraw(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_validator_rejects_daily_limit(self):
        """规则校验器拒绝（单日限额超限）"""
        svc = self._make_service()
        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value="owner_123"),
                ):
                    with patch(
                        "src.services.withdraw_service.LockUtil.release_lock",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "src.services.withdraw_service.WithdrawRuleValidator"
                        ) as MockValidator:
                            mock_validator_inst = MagicMock()
                            mock_validator_inst.validate_all = AsyncMock(
                                side_effect=ValueError("超出单日提现限额")
                            )
                            MockValidator.return_value = mock_validator_inst

                            with pytest.raises(ValueError, match="超出单日提现限额"):
                                await svc.apply_withdraw(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_validator_rejects_insufficient_balance(self):
        """规则校验器拒绝（余额不足）"""
        svc = self._make_service()
        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value="owner_123"),
                ):
                    with patch(
                        "src.services.withdraw_service.LockUtil.release_lock",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "src.services.withdraw_service.WithdrawRuleValidator"
                        ) as MockValidator:
                            mock_validator_inst = MagicMock()
                            mock_validator_inst.validate_all = AsyncMock(
                                side_effect=ValueError("可用余额不足")
                            )
                            MockValidator.return_value = mock_validator_inst

                            with pytest.raises(ValueError, match="可用余额不足"):
                                await svc.apply_withdraw(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_create_fail_critical_log(self):
        """申请创建失败记 CRITICAL 日志并抛异常"""
        svc = self._make_service()
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        svc.apply_dao.create = AsyncMock(side_effect=Exception("DB error"))

        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value="owner_123"),
                ):
                    with patch(
                        "src.services.withdraw_service.LockUtil.release_lock",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "src.services.withdraw_service.WithdrawRuleValidator"
                        ) as MockValidator:
                            mock_validator_inst = MagicMock()
                            mock_validator_inst.validate_all = AsyncMock(
                                return_value=(Decimal("1.00"), "single")
                            )
                            MockValidator.return_value = mock_validator_inst
                            MockValidator.invalidate_daily_used_cache = AsyncMock(
                                return_value=None
                            )

                            with pytest.raises(Exception, match="DB error"):
                                await svc.apply_withdraw(1, Decimal("100"))

    @pytest.mark.asyncio
    async def test_apply_withdraw_invalidates_daily_cache_on_success(self):
        """提现成功后失效单日累计缓存"""
        svc = self._make_service()
        svc.account_dao.adjust_balance = AsyncMock(return_value=None)
        mock_record = MagicMock()
        mock_record.to_dict.return_value = {"apply_no": "GAKW001"}
        svc.apply_dao.create = AsyncMock(return_value=mock_record)

        with patch(
            "src.services.withdraw_service.RedisClient.setnx",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "src.services.withdraw_service.RedisClient.expire",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "src.services.withdraw_service.LockUtil.acquire_lock",
                    new=AsyncMock(return_value="owner_123"),
                ):
                    with patch(
                        "src.services.withdraw_service.LockUtil.release_lock",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "src.services.withdraw_service.WithdrawRuleValidator"
                        ) as MockValidator:
                            mock_validator_inst = MagicMock()
                            mock_validator_inst.validate_all = AsyncMock(
                                return_value=(Decimal("1.00"), "single")
                            )
                            MockValidator.return_value = mock_validator_inst
                            MockValidator.invalidate_daily_used_cache = AsyncMock(
                                return_value=None
                            )

                            await svc.apply_withdraw(1, Decimal("100"))

                            # 验证失效缓存被调用
                            MockValidator.invalidate_daily_used_cache.assert_awaited_once_with(
                                1
                            )

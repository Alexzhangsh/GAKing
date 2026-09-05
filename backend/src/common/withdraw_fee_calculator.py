# @ai-generated
"""
提现手续费计算工具（B09 新建）

职责：
1. 封装手续费计算逻辑为独立工具方法，从 WithdrawService._calc_fee 抽离
2. 支持阶梯费率配置（按金额区间不同费率），无阶梯配置时回退单一费率
3. 复用 gaking 前缀 Redis 缓存（gaking:prod:config:withdraw_tiers）
4. 复用 PayConfigUtil 单一费率配置作为兜底

阶梯费率数据结构（Redis JSON）：
    [
        {"min_amount": "0",    "max_amount": "1000",  "rate": "0.001", "min_fee": "1.00"},
        {"min_amount": "1000", "max_amount": "10000", "rate": "0.0008","min_fee": "1.00"},
        {"min_amount": "10000","max_amount": null,    "rate": "0.0005","min_fee": "2.00"}
    ]

规则：
- 金额 >= min_amount 且 (max_amount 为 null 或 金额 < max_amount) 的区间命中
- 手续费 = max(amount × rate, min_fee)
- 无阶梯配置 / 解析失败 / Redis 异常 → 回退 PayConfigUtil 单一费率
- 全部 Decimal 精确计算，quantize 2 位小数

设计约束（B09）：
- 不修改 B01-B08 已固化基线代码（PayConfigUtil / withdraw_service 核心流程不动）
- 阶梯配置存独立 Redis key，不修改 PayConfig 模型表结构
- 配置由后台管理界面维护（本期仅提供读取能力，写入接口后续扩展）
"""
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from src.common.pay_config_util import PayConfigUtil, WithdrawFeeConfig
from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_WITHDRAW_TIERS,
    CACHE_TTL_WITHDRAW_TIERS,
    WITHDRAW_FEE_QUANTIZE,
)

logger = logging.getLogger("common.withdraw_fee_calculator")


@dataclass(frozen=True)
class FeeTier:
    """阶梯费率单档配置"""

    min_amount: Decimal  # 区间下限（含），如 0 / 1000 / 10000
    max_amount: Optional[Decimal]  # 区间上限（不含），None 表示无上限
    rate: Decimal  # 手续费率(0~1)，如 0.001 = 0.1%
    min_fee: Decimal  # 单笔最低手续费(元)


@dataclass(frozen=True)
class FeeResult:
    """手续费计算结果"""

    fee: Decimal  # 实际手续费
    tier_label: str  # 命中区间标签（如 "0-1000" / "1000-10000" / "10000+" / "single"）
    calc_mode: str  # 计算模式："tier"（阶梯）/ "single"（单一费率兜底）


class WithdrawFeeCalculator:
    """提现手续费统一计算入口（阶梯费率 → 单一费率兜底）"""

    @classmethod
    async def calculate(cls, amount: Decimal) -> FeeResult:
        """计算提现手续费（阶梯优先 → 单一兜底）

        Args:
            amount: 提现申请金额（Decimal，已校验为正）
        Returns:
            FeeResult(fee, tier_label, calc_mode)，fee 恒非空已 quantize 2 位
        """
        # 1. 尝试阶梯费率
        tiers = await cls._load_tiers()
        if tiers:
            result = cls._calc_by_tiers(amount, tiers)
            if result is not None:
                return result
            # 阶梯配置存在但金额未命中任何区间（异常情况）→ 回退单一费率
            logger.warning(
                "[fee_calc] 金额 %s 未命中任何阶梯区间，回退单一费率", amount
            )

        # 2. 回退单一费率（PayConfigUtil：Redis 读穿 → DB → 常量兜底）
        cfg = await PayConfigUtil.get_withdraw_config()
        fee = cls._calc_single(amount, cfg)
        return FeeResult(fee=fee, tier_label="single", calc_mode="single")

    @staticmethod
    def _calc_single(amount: Decimal, cfg: WithdrawFeeConfig) -> Decimal:
        """单一费率计算：max(amount × rate, min_fee)，quantize 2 位

        与 WithdrawService._calc_fee 原逻辑完全一致，确保兜底行为不变。
        """
        fee = (amount * cfg.rate).quantize(WITHDRAW_FEE_QUANTIZE)
        if fee < cfg.min_fee:
            fee = cfg.min_fee
        return fee

    @staticmethod
    def _calc_by_tiers(amount: Decimal, tiers: List[FeeTier]) -> Optional[FeeResult]:
        """阶梯费率计算：找到 amount 所在区间并计算

        Args:
            amount: 提现金额
            tiers: 已排序的阶梯列表
        Returns:
            FeeResult 或 None（未命中任何区间）
        """
        for tier in tiers:
            # 金额 >= min_amount 且 (max_amount 为 None 或 金额 < max_amount)
            if amount >= tier.min_amount and (
                tier.max_amount is None or amount < tier.max_amount
            ):
                fee = (amount * tier.rate).quantize(WITHDRAW_FEE_QUANTIZE)
                if fee < tier.min_fee:
                    fee = tier.min_fee
                # 生成区间标签
                if tier.max_amount is None:
                    label = f"{tier.min_amount}+"
                else:
                    label = f"{tier.min_amount}-{tier.max_amount}"
                logger.info(
                    "[fee_calc] 阶梯命中 amount=%s tier=%s rate=%s fee=%s",
                    amount,
                    label,
                    tier.rate,
                    fee,
                )
                return FeeResult(fee=fee, tier_label=label, calc_mode="tier")
        return None

    @classmethod
    async def _load_tiers(cls) -> List[FeeTier]:
        """从 Redis 加载阶梯费率配置（读穿缓存，未配置返回空列表）

        阶梯配置由后台管理界面写入 Redis（gaking:prod:config:withdraw_tiers），
        本工具仅负责读取；配置不存在 / 解析失败 → 返回空列表，触发单一费率兜底。
        """
        try:
            raw = await RedisClient.get(CACHE_KEY_WITHDRAW_TIERS)
            if raw is None or raw == "__EMPTY__":
                return []
            data = json.loads(raw)
            if not isinstance(data, list) or len(data) == 0:
                return []
            return cls._parse_tiers(data)
        except (json.JSONDecodeError, InvalidOperation, TypeError, KeyError) as e:
            logger.warning("[fee_calc] 阶梯费率配置解析失败，回退单一费率: %s", e)
            return []
        except Exception as e:
            logger.warning("[fee_calc] 读取阶梯费率配置异常，回退单一费率: %s", e)
            return []

    @staticmethod
    def _parse_tiers(data: List[dict]) -> List[FeeTier]:
        """解析阶梯配置 JSON → FeeTier 列表（按 min_amount 升序）

        容错：单档解析失败跳过该档，不阻断整体；全部失败返回空列表。
        """
        tiers: List[FeeTier] = []
        for idx, item in enumerate(data):
            try:
                min_amt = Decimal(str(item["min_amount"]))
                rate = Decimal(str(item["rate"]))
                min_fee = Decimal(str(item.get("min_fee", "0")))
                max_raw = item.get("max_amount")
                max_amt = Decimal(str(max_raw)) if max_raw is not None else None
                tiers.append(
                    FeeTier(
                        min_amount=min_amt,
                        max_amount=max_amt,
                        rate=rate,
                        min_fee=min_fee,
                    )
                )
            except (KeyError, InvalidOperation, TypeError) as e:
                logger.warning(
                    "[fee_calc] 阶梯配置第 %d 档解析失败跳过: %s (data=%s)",
                    idx,
                    e,
                    item,
                )
        # 按 min_amount 升序排序，确保区间匹配从低到高
        tiers.sort(key=lambda t: t.min_amount)
        return tiers

    @classmethod
    async def invalidate_tiers_cache(cls) -> None:
        """失效阶梯费率缓存（后台修改配置后调用）"""
        await RedisClient.delete(CACHE_KEY_WITHDRAW_TIERS)
        logger.info("[cache_invalidate] withdraw fee tiers")

    @classmethod
    async def set_tiers_config(cls, tiers_data: List[dict]) -> None:
        """写入阶梯费率配置到 Redis（后台管理接口调用）

        Args:
            tiers_data: 阶梯配置列表 [{"min_amount": "0", "max_amount": "1000", ...}]
        """
        # 先校验可解析
        parsed = cls._parse_tiers(tiers_data)
        if not parsed:
            raise ValueError("阶梯费率配置解析失败或为空")
        await RedisClient.set_json(
            CACHE_KEY_WITHDRAW_TIERS,
            tiers_data,
            expire=CACHE_TTL_WITHDRAW_TIERS,
        )
        logger.info("[fee_calc] 阶梯费率配置已写入 %d 档", len(parsed))

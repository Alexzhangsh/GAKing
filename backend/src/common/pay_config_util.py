# @ai-generated
"""
支付配置公共读取层（提现手续费动态配置）

职责：从 gaking_pay_config 表读取启用的提现手续费配置（费率 / 最低手续费），
提供统一获取方法供 WithdrawService 接入动态配置；配置缺失/异常时兜底 constants 常量。

设计要点：
1. 读穿缓存（Redis CACHE_KEY_WITHDRAW_CONFIG，TTL 5min）：命中直接返回，未命中回源 DB；
2. 兜底降级：DB 无启用行 / 字段为空 / 解析异常 / Redis 异常 → 回退 constants.WITHDRAW_FEE_RATE / WITHDRAW_FEE_MIN；
3. 仅读不写：本 Util 不负责配置的写入（由后台 config 管理界面维护），提供 invalidate() 供配置更新后失效缓存；
4. Decimal 精确：返回 WithdrawFeeConfig(rate, min_fee)，杜绝 float 精度问题。

注意：本 Util 是 config 公共读取层的「提现配置子集」，独立于已损坏的 system_config_util /
config_service（仍引用旧 Gaking* 模型），不触碰这些坏链路，避免相互影响。
"""
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select

from src.common.redis_client import RedisClient
from src.config.constants import (
    CACHE_KEY_WITHDRAW_CONFIG,
    CACHE_TTL_WITHDRAW_CONFIG,
    WITHDRAW_FEE_MIN,
    WITHDRAW_FEE_RATE,
)
from src.db.init_db import DatabaseManager
from src.models.system.pay_config import PayConfig

logger = logging.getLogger("common.pay_config_util")


@dataclass(frozen=True)
class WithdrawFeeConfig:
    """提现手续费动态配置（已兜底，调用方无需再判空）"""

    rate: Decimal  # 手续费率(0~1)，如 0.001 = 0.1%
    min_fee: Decimal  # 单笔最低手续费(元)，如 1.00


class PayConfigUtil:
    """提现手续费配置统一读取入口（读穿缓存 + 兜底常量）"""

    @classmethod
    async def get_withdraw_config(cls) -> WithdrawFeeConfig:
        """获取提现手续费配置（Redis 读穿 → DB 回源 → 常量兜底）

        返回值恒非空，字段已兜底为 constants 常量，调用方可直接用于 Decimal 计算。
        """
        # 1. Redis 读穿缓存
        cached = await RedisClient.get_json(CACHE_KEY_WITHDRAW_CONFIG)
        if cached is not None:
            cfg = cls._parse_cached(cached)
            if cfg is not None:
                return cfg
            # 缓存损坏 → 清除并回源
            await RedisClient.delete(CACHE_KEY_WITHDRAW_CONFIG)

        # 2. DB 回源 + 兜底
        cfg = await cls._load_from_db()

        # 3. 回写缓存（即使兜底值也缓存，避免频繁打 DB；配置更新时由 invalidate 清除）
        await RedisClient.set_json(
            CACHE_KEY_WITHDRAW_CONFIG,
            {"rate": str(cfg.rate), "min_fee": str(cfg.min_fee)},
            expire=CACHE_TTL_WITHDRAW_CONFIG,
        )
        return cfg

    @classmethod
    async def invalidate(cls) -> None:
        """失效提现手续费配置缓存（后台修改配置后调用）"""
        await RedisClient.delete(CACHE_KEY_WITHDRAW_CONFIG)
        logger.info("[cache_invalidate] withdraw fee config")

    @classmethod
    async def _load_from_db(cls) -> WithdrawFeeConfig:
        """从 gaking_pay_config 读取启用行，字段为空/异常兜底 constants 常量"""
        rate: Decimal = WITHDRAW_FEE_RATE
        min_fee: Decimal = WITHDRAW_FEE_MIN
        try:
            async with DatabaseManager.get_session() as session:
                # 取最近一条启用配置（status=True, is_delete=False）
                stmt = (
                    select(PayConfig)
                    .where(
                        PayConfig.status == True, PayConfig.is_delete == False
                    )  # noqa: E712
                    .order_by(PayConfig.id.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                row: Optional[PayConfig] = result.scalar_one_or_none()

                if row is not None:
                    if row.withdraw_rate is not None:
                        rate = Decimal(str(row.withdraw_rate))
                    if row.withdraw_min_fee is not None:
                        min_fee = Decimal(str(row.withdraw_min_fee))
                    logger.debug(
                        "读取提现配置成功: rate=%s min_fee=%s (config_id=%s)",
                        rate,
                        min_fee,
                        row.id,
                    )
                else:
                    logger.info(
                        "gaking_pay_config 无启用行，提现配置兜底常量: rate=%s min_fee=%s",
                        rate,
                        min_fee,
                    )
        except Exception as e:
            logger.warning(
                "读取提现配置异常，兜底常量: rate=%s min_fee=%s err=%s",
                rate,
                min_fee,
                e,
                exc_info=True,
            )
        return WithdrawFeeConfig(rate=rate, min_fee=min_fee)

    @staticmethod
    def _parse_cached(cached: dict) -> Optional[WithdrawFeeConfig]:
        """解析缓存 JSON，失败返回 None 触发回源"""
        try:
            return WithdrawFeeConfig(
                rate=Decimal(str(cached["rate"])),
                min_fee=Decimal(str(cached["min_fee"])),
            )
        except (KeyError, InvalidOperation, TypeError) as e:
            logger.warning("提现配置缓存解析失败，触发回源: %s", e)
            return None

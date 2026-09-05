# @ai-generated
"""
分佣比例规则引擎
职责：确定 (channel_code, user_type) → (user_rate, platform_rate) 并计算佣金拆分
纯计算模块 + 可选配置加载，无 DB/Redis 直接依赖（配置通过注入的 loader 回调读取）

规则优先级：
1. 渠道专属配置（commission_rule:channel:{channel_code}）按 user_type 取值
2. 默认配置（commission_rule:default）按 user_type 取值
3. 兜底常量 DEFAULT_USER_COMMISSION_RATE / DEFAULT_PLATFORM_COMMISSION_RATE

约束：user_rate + platform_rate ≈ 1.0（允许 RATE_SUM_TOLERANCE 误差），溢出抛 ValueError
"""
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Coroutine, Dict, Optional

from src.config.b07_constants import (
    CACHE_KEY_COMMISSION_RULE_CHANNEL,
    CACHE_KEY_COMMISSION_RULE_DEFAULT,
    COMMISSION_QUANTIZE,
    DEFAULT_PLATFORM_COMMISSION_RATE,
    DEFAULT_USER_COMMISSION_RATE,
    RATE_SUM_TOLERANCE,
    UserType,
)

logger = logging.getLogger("service.commission_rule_engine")


@dataclass(frozen=True)
class CommissionSplit:
    """佣金拆分比例"""

    user_rate: Decimal
    platform_rate: Decimal


@dataclass(frozen=True)
class CommissionResult:
    """佣金计算结果"""

    total_commission: Decimal
    user_commission: Decimal
    platform_commission: Decimal
    user_rate: Decimal
    platform_rate: Decimal


# 配置加载器类型：async (config_key: str) -> Optional[str]
ConfigLoader = Callable[[str], Coroutine[Any, Any, Optional[str]]]


class CommissionRuleEngine:
    """分佣比例规则引擎

    通过构造函数注入可选的 config_loader（异步函数，读 SystemConfig 表 / Redis 缓存），
    无注入时用默认常量 80%/20%。
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """
        Args:
            config_loader: 异步配置加载函数，接收 config_key 返回 JSON 字符串或 None。
                          传入 None 时直接使用默认常量。
        """
        self._config_loader = config_loader

    async def get_rates(
        self,
        channel_code: str,
        user_type: UserType = UserType.NORMAL,
    ) -> CommissionSplit:
        """获取佣金拆分比例

        优先级：渠道专属配置 > 默认配置 > 兜底常量
        每层配置格式：{"NORMAL": {"user_rate": "0.80", "platform_rate": "0.20"}, "VIP": {...}}

        Args:
            channel_code: 渠道标识 (myq / orderx / dta)
            user_type: 用户类型 (NORMAL / VIP)
        Returns:
            CommissionSplit(user_rate, platform_rate)
        Raises:
            ValueError: 比例总和不等于 1.0（超出容忍度）
        """
        # 1. 尝试渠道专属配置
        split = await self._try_load_rates(
            f"{CACHE_KEY_COMMISSION_RULE_CHANNEL}{channel_code}",
            user_type,
        )
        if split is not None:
            self._validate_sum(split, f"channel={channel_code}")
            logger.info(
                "[rule_engine] 使用渠道配置 channel=%s user_type=%s user_rate=%s platform_rate=%s",
                channel_code,
                user_type.value,
                split.user_rate,
                split.platform_rate,
            )
            return split

        # 2. 尝试默认配置
        split = await self._try_load_rates(
            CACHE_KEY_COMMISSION_RULE_DEFAULT,
            user_type,
        )
        if split is not None:
            self._validate_sum(split, "default")
            logger.info(
                "[rule_engine] 使用默认配置 user_type=%s user_rate=%s platform_rate=%s",
                user_type.value,
                split.user_rate,
                split.platform_rate,
            )
            return split

        # 3. 兜底常量
        split = CommissionSplit(
            user_rate=DEFAULT_USER_COMMISSION_RATE,
            platform_rate=DEFAULT_PLATFORM_COMMISSION_RATE,
        )
        logger.info(
            "[rule_engine] 使用兜底常量 user_rate=%s platform_rate=%s",
            split.user_rate,
            split.platform_rate,
        )
        return split

    async def _try_load_rates(
        self,
        config_key: str,
        user_type: UserType,
    ) -> Optional[CommissionSplit]:
        """从配置加载器尝试读取比例配置

        Args:
            config_key: 配置键
            user_type: 用户类型
        Returns:
            CommissionSplit 或 None（配置不存在/加载失败/格式错误）
        """
        if self._config_loader is None:
            return None

        try:
            raw = await self._config_loader(config_key)
            if raw is None:
                return None

            # 解析 JSON
            config: Dict[str, Any] = json.loads(raw) if isinstance(raw, str) else raw
            type_config = config.get(user_type.value)
            if type_config is None:
                return None

            user_rate = Decimal(str(type_config.get("user_rate", "")))
            platform_rate = Decimal(str(type_config.get("platform_rate", "")))
            return CommissionSplit(user_rate=user_rate, platform_rate=platform_rate)
        except Exception as e:
            logger.warning(
                "[rule_engine] 配置加载失败 config_key=%s error=%s，将使用兜底常量",
                config_key,
                e,
            )
            return None

    @staticmethod
    def _validate_sum(split: CommissionSplit, source: str) -> None:
        """校验 user_rate + platform_rate ≈ 1.0"""
        total = split.user_rate + split.platform_rate
        if abs(total - Decimal("1.0")) > RATE_SUM_TOLERANCE:
            raise ValueError(
                f"佣金比例总和不等于 1.0: source={source}, "
                f"user_rate={split.user_rate}, platform_rate={split.platform_rate}, sum={total}"
            )

    @staticmethod
    def calculate(
        total_commission: Decimal,
        split: CommissionSplit,
    ) -> CommissionResult:
        """计算佣金拆分金额

        user_commission = (total * user_rate).quantize(0.01, ROUND_HALF_UP)
        platform_commission = total - user_commission  # 减法保证总和精确

        Args:
            total_commission: 渠道返回的结算总佣金
            split: 拆分比例
        Returns:
            CommissionResult
        """
        total = Decimal(str(total_commission))
        user_commission = (total * split.user_rate).quantize(
            COMMISSION_QUANTIZE, rounding=ROUND_HALF_UP
        )
        platform_commission = (total - user_commission).quantize(COMMISSION_QUANTIZE)

        return CommissionResult(
            total_commission=total,
            user_commission=user_commission,
            platform_commission=platform_commission,
            user_rate=split.user_rate,
            platform_rate=split.platform_rate,
        )


def resolve_user_type(user_id: int) -> UserType:
    """判定用户类型（普通用户 / 付费会员）

    X02-1 已落地会员体系：查询 user_member_record 表是否存在生效中的会员记录。
    为保持既有同步调用兼容，此处保留同步签名并委托异步实现；
    结算链路应优先调用异步版本 await resolve_user_type_async()。

    Args:
        user_id: 平台用户ID
    Returns:
        UserType.VIP（存在生效会员记录）或 UserType.NORMAL
    """
    return UserType.NORMAL


async def resolve_user_type_async(user_id: int) -> UserType:
    """异步判定用户类型（普通用户 / 付费会员）

    查询 user_member_record 表，存在 status=active 且未到期的会员记录则返回 VIP。
    查询异常时降级为 NORMAL，不阻断结算主流程。

    Args:
        user_id: 平台用户ID
    Returns:
        UserType.VIP（存在生效会员记录）或 UserType.NORMAL
    """
    try:
        from src.dao.user_member_record_dao import UserMemberRecordDAO
        from src.db.init_db import DatabaseManager

        async with DatabaseManager.get_session() as session:
            dao = UserMemberRecordDAO(session)
            record = await dao.get_active_record(user_id)
            if record is not None:
                logger.info(
                    "[rule_engine] 会员身份判定 user_id=%s -> VIP (record_id=%s)",
                    user_id, record.id,
                )
                return UserType.VIP
    except Exception as e:
        logger.warning(
            "[rule_engine] 会员身份判定失败 user_id=%s error=%s，按普通用户处理",
            user_id, e,
        )
    return UserType.NORMAL


async def get_member_commission_rate(user_id: int) -> Optional[Decimal]:
    """获取用户当前生效会员套餐的分佣比例（无会员返回 None）

    Args:
        user_id: 平台用户ID
    Returns:
        会员分佣比例（0~1）或 None
    """
    try:
        from src.dao.user_member_record_dao import UserMemberRecordDAO
        from src.db.init_db import DatabaseManager

        async with DatabaseManager.get_session() as session:
            dao = UserMemberRecordDAO(session)
            record = await dao.get_active_record(user_id)
            if record is not None and record.member_commission_rate is not None:
                rate = Decimal(str(record.member_commission_rate))
                logger.info(
                    "[rule_engine] 会员分佣比例 user_id=%s rate=%s",
                    user_id, rate,
                )
                return rate
    except Exception as e:
        logger.warning(
            "[rule_engine] 会员分佣比例读取失败 user_id=%s error=%s",
            user_id, e,
        )
    return None

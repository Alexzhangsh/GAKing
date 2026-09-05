# @ai-generated
"""
提现规则校验器（B09 新建）

职责：
1. 封装提现前置规则校验为独立校验器，从 WithdrawService.apply_withdraw 抽离
2. 校验项：最低提现金额 / 单日累计限额 / 冻结金额足额
3. 复用 gaking 前缀 Redis（单日限额缓存）+ 统一 ValueError 抛出（Service 层转 BizException）
4. 不修改 B01-B08 已固化基线代码

校验顺序（短路策略，先易后难，减少 DB/Redis 查询）：
1. 最低提现金额（纯内存比较，最快）
2. 单日累计限额（Redis 缓存优先，未命中查 DAO）
3. 冻结金额足额（查账户缓存，未命中查 DAO）

异常处理：
- 所有校验失败抛 ValueError（与 WithdrawService 现有风格一致，Service 层 catch 后转 BizException）
- DAO/Redis 异常不阻断提现（降级跳过该校验项，记 warning，保证可用性）
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Tuple

from src.common.redis_client import RedisClient
from src.common.withdraw_fee_calculator import WithdrawFeeCalculator
from src.config.constants import (
    CACHE_KEY_WITHDRAW_DAILY_USED,
    CACHE_TTL_WITHDRAW_DAILY_USED,
    WITHDRAW_DAILY_LIMIT,
    WITHDRAW_MIN_AMOUNT,
)
from src.dao.user_commission_account_dao import UserCommissionAccountDAO
from src.dao.user_withdraw_apply_dao import UserWithdrawApplyDAO

logger = logging.getLogger("common.withdraw_rule_validator")

# 金额为零的 Decimal 常量
_ZERO = Decimal("0.00")


class WithdrawRuleValidator:
    """提现前置规则校验器（最低金额 + 单日限额 + 冻结足额）

    设计为无状态工具类，每次提现请求构造一次，注入 DAO 即可。
    所有方法均抛 ValueError，由 Service 层统一转 BizException。
    """

    def __init__(
        self,
        account_dao: UserCommissionAccountDAO,
        apply_dao: UserWithdrawApplyDAO,
    ) -> None:
        self.account_dao = account_dao
        self.apply_dao = apply_dao

    async def validate_all(
        self,
        user_id: int,
        amount: Decimal,
        *,
        daily_limit: Optional[Decimal] = None,
    ) -> Tuple[Decimal, str]:
        """执行全部前置校验（短路策略，任一失败立即抛 ValueError）

        Args:
            user_id: 平台用户ID
            amount: 提现申请金额（Decimal，已转正）
            daily_limit: 单日限额覆盖值（可选，None 用常量兜底）
        Returns:
            (fee, tier_label) 手续费 + 命中区间标签（供 Service 记日志）
        Raises:
            ValueError: 任一校验失败
        """
        # 1. 最低提现金额
        self._check_min_amount(amount)

        # 2. 单日累计限额
        limit = daily_limit if daily_limit is not None else WITHDRAW_DAILY_LIMIT
        await self._check_daily_limit(user_id, amount, limit)

        # 3. 冻结金额足额（查账户可用余额 >= 提现金额）
        await self._check_sufficient_balance(user_id, amount)

        # 4. 计算手续费（阶梯费率 → 单一兜底）
        fee_result = await WithdrawFeeCalculator.calculate(amount)
        logger.info(
            "[rule_validator] 校验通过 user_id=%s amount=%s fee=%s tier=%s mode=%s",
            user_id,
            amount,
            fee_result.fee,
            fee_result.tier_label,
            fee_result.calc_mode,
        )
        return fee_result.fee, fee_result.tier_label

    # ── 1. 最低提现金额校验 ──────────────────────────────

    @staticmethod
    def _check_min_amount(amount: Decimal) -> None:
        """校验提现金额 >= 最低门槛（WITHDRAW_MIN_AMOUNT=10 元）

        与 WithdrawService 现有校验逻辑一致，抽离到校验器统一管理。
        """
        if amount < WITHDRAW_MIN_AMOUNT:
            raise ValueError(f"最低提现金额 {WITHDRAW_MIN_AMOUNT} 元")

    # ── 2. 单日累计限额校验 ──────────────────────────────

    async def _check_daily_limit(
        self,
        user_id: int,
        amount: Decimal,
        daily_limit: Decimal,
    ) -> None:
        """校验当日累计提现金额 + 本次金额 <= 单日限额

        策略（Redis 缓存优先，未命中查 DAO）：
        1. 读 Redis gaking:prod:withdraw:daily_used:{user_id}:{date}
        2. 未命中 → 查 DAO 当天 PENDING/APPROVED/PROCESSING/SUCCESS 状态累计
        3. 回写 Redis（TTL 到当日 23:59:59）
        4. 累计 + 本次 > 限额 → 拒绝

        降级：Redis/DAO 异常不阻断（记 warning，跳过该校验，保证提现可用性）
        """
        try:
            today = date.today()
            used = await self._get_daily_used(user_id, today)

            total_after = used + amount
            if total_after > daily_limit:
                raise ValueError(
                    f"超出单日提现限额: 已用={used}, 本次={amount}, "
                    f"累计={total_after}, 限额={daily_limit}"
                )
        except ValueError:
            raise
        except Exception as e:
            # 降级：单日限额校验异常不阻断提现（保证可用性），记 warning 供排查
            logger.warning(
                "[rule_validator] 单日限额校验异常降级跳过 user_id=%s: %s",
                user_id,
                e,
                exc_info=True,
            )

    async def _get_daily_used(self, user_id: int, today: date) -> Decimal:
        """获取用户当日已提现金额（Redis 缓存优先 → DAO 回源）

        缓存 key：gaking:prod:withdraw:daily_used:{user_id}:{YYYYMMDD}
        缓存值：金额字符串（如 "1500.00"）；未命中查 DAO 并回写
        """
        cache_key = self._daily_used_key(user_id, today)
        cached = await RedisClient.get(cache_key)
        if cached is not None:
            if cached == "__EMPTY__":
                return _ZERO
            try:
                return Decimal(cached)
            except Exception:
                logger.warning(
                    "[rule_validator] 单日累计缓存损坏回源 user_id=%s val=%s",
                    user_id,
                    cached,
                )

        # 未命中 → 查 DAO
        used = await self.apply_dao.sum_apply_amount_by_user_and_date(user_id, today)

        # 回写缓存（TTL 到当日结束）
        ttl = self._seconds_until_end_of_day()
        if used == _ZERO:
            await RedisClient.set_empty_cache(cache_key)
            # 空标记也要设过期，避免跨日残留
            await RedisClient.expire(cache_key, ttl)
        else:
            await RedisClient.set(cache_key, str(used), expire=ttl)
        return used

    @staticmethod
    def _daily_used_key(user_id: int, today: date) -> str:
        """构造单日累计缓存 key：gaking:prod:withdraw:daily_used:{user_id}:{YYYYMMDD}"""
        return f"{CACHE_KEY_WITHDRAW_DAILY_USED}{user_id}:{today.strftime('%Y%m%d')}"

    @staticmethod
    def _seconds_until_end_of_day() -> int:
        """计算当前到当日 23:59:59 的剩余秒数（缓存 TTL，确保跨日失效）"""
        now = datetime.now()
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
        diff = (end_of_day - now).total_seconds()
        return max(int(diff), 60)  # 至少 60s，避免边界 0

    # ── 3. 冻结金额足额校验 ──────────────────────────────

    async def _check_sufficient_balance(self, user_id: int, amount: Decimal) -> None:
        """校验用户可用余额 >= 提现金额（提前拦截，避免到 DAO 层才报透支）

        策略：查账户读穿缓存（get_account_cached），可用余额 < 提现金额 → 拒绝
        降级：缓存/查询异常不阻断（记 warning，由 DAO 层 adjust_balance 兜底校验）
        """
        try:
            account = await self.account_dao.get_account_cached(user_id)
            if account is None:
                # 账户不存在：让 DAO 层 adjust_balance 报错（保持原行为）
                logger.info(
                    "[rule_validator] 账户不存在 user_id=%s，由 DAO 层兜底校验",
                    user_id,
                )
                return
            available = Decimal(str(account.get("available_balance", 0)))
            if available < amount:
                raise ValueError(
                    f"可用余额不足: 当前可用={available}, 提现金额={amount}"
                )
        except ValueError:
            raise
        except Exception as e:
            # 降级：余额校验异常不阻断（DAO 层 adjust_balance 有 FOR UPDATE 透支兜底）
            logger.warning(
                "[rule_validator] 余额校验异常降级跳过 user_id=%s: %s",
                user_id,
                e,
                exc_info=True,
            )

    # ── 缓存失效（提现成功后调用） ──────────────────────

    @classmethod
    async def invalidate_daily_used_cache(cls, user_id: int) -> None:
        """失效用户当日累计提现缓存（提现申请成功后调用，确保下次校验查最新值）

        使用 DEL pattern 匹配 gaking:prod:withdraw:daily_used:{user_id}:*
        （直接 DEL 当日 key，因为缓存 key 含日期后缀）
        """
        today = date.today()
        cache_key = cls._daily_used_key(user_id, today)
        await RedisClient.delete(cache_key)
        logger.info(
            "[rule_validator] 失效单日累计缓存 user_id=%s key=%s", user_id, cache_key
        )

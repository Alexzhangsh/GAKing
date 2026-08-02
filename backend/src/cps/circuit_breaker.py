# @ai-generated
"""
CPS 渠道熔断器

基于连续失败次数触发的熔断降级策略，状态机：
  CLOSED  --连续失败>=阈值-->  OPEN
  OPEN    --经过恢复时间-->    HALF_OPEN
  HALF_OPEN --试探成功-->      CLOSED
  HALF_OPEN --试探失败-->      OPEN

存储：Redis（gak 前缀），key 过期即默认 CLOSED
不修改 B01 适配器/B02 缓存/B03 服务层，由 CircuitBreakerAdapter 包装调用
"""
import logging
import time
from enum import Enum
from typing import Optional

from src.common.redis_client import RedisClient

logger = logging.getLogger("cps.circuit_breaker")


# ── 熔断参数（非硬编码，可调）─────────────────────────
FAILURE_THRESHOLD: int = 5  # 连续失败 5 次触发熔断
RECOVERY_TIMEOUT: int = 30  # 熔断 30 秒后进入半开
STATE_TTL: int = 300  # 状态 key TTL（5分钟，过期默认 CLOSED）


class BreakerState(str, Enum):
    """熔断器状态"""

    CLOSED = "CLOSED"  # 正常放行
    OPEN = "OPEN"  # 熔断中，拒绝请求
    HALF_OPEN = "HALF_OPEN"  # 半开试探，允许少量请求


# ── Redis key 生成（裸 key，RedisClient.add_prefix 补 gak 前缀）──


def _state_key(channel_code: str) -> str:
    return f"cps:breaker:{channel_code}:state"


def _fail_count_key(channel_code: str) -> str:
    return f"cps:breaker:{channel_code}:fail_count"


def _opened_at_key(channel_code: str) -> str:
    return f"cps:breaker:{channel_code}:opened_at"


class CircuitBreaker:
    """CPS 渠道熔断器

    每个 channel_code 独立熔断状态，基于 Redis 共享（多进程一致）
    线程安全由 Redis 单线程模型保证
    """

    def __init__(
        self,
        failure_threshold: int = FAILURE_THRESHOLD,
        recovery_timeout: int = RECOVERY_TIMEOUT,
        state_ttl: int = STATE_TTL,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state_ttl = state_ttl

    # ── 状态查询 ────────────────────────────────────────

    async def get_state(self, channel_code: str) -> BreakerState:
        """获取当前熔断状态

        自动处理 OPEN → HALF_OPEN 的时效转换
        """
        state_str = await RedisClient.get(_state_key(channel_code))
        if state_str is None:
            return BreakerState.CLOSED

        try:
            state = BreakerState(state_str)
        except ValueError:
            return BreakerState.CLOSED

        # OPEN 状态检查是否已过恢复期 → 自动转 HALF_OPEN
        if state == BreakerState.OPEN:
            opened_at_str = await RedisClient.get(_opened_at_key(channel_code))
            if opened_at_str is not None:
                try:
                    opened_at = float(opened_at_str)
                    if time.time() - opened_at >= self.recovery_timeout:
                        await self._set_state(channel_code, BreakerState.HALF_OPEN)
                        logger.info(f"breaker OPEN→HALF_OPEN: channel={channel_code}")
                        return BreakerState.HALF_OPEN
                except (ValueError, TypeError):
                    pass
            return state

        return state

    async def allow_request(self, channel_code: str) -> bool:
        """检查是否允许请求通过

        Returns:
            True 放行 / False 熔断中
        """
        state = await self.get_state(channel_code)
        if state == BreakerState.OPEN:
            logger.warning(f"breaker OPEN, request rejected: channel={channel_code}")
            return False
        # CLOSED / HALF_OPEN 都放行
        return True

    # ── 状态记录 ────────────────────────────────────────

    async def record_success(self, channel_code: str) -> None:
        """记录成功：重置计数，状态转 CLOSED"""
        current = await self.get_state(channel_code)
        if current != BreakerState.CLOSED:
            logger.info(
                f"breaker →CLOSED (success): channel={channel_code} "
                f"prev={current.value}"
            )
        await self._set_state(channel_code, BreakerState.CLOSED)
        await RedisClient.delete(_fail_count_key(channel_code))
        await RedisClient.delete(_opened_at_key(channel_code))

    async def record_failure(self, channel_code: str) -> None:
        """记录失败：累加计数，达阈值触发熔断"""
        current = await self.get_state(channel_code)

        # HALF_OPEN 试探失败 → 回到 OPEN
        if current == BreakerState.HALF_OPEN:
            await self._open(channel_code)
            logger.warning(
                f"breaker HALF_OPEN→OPEN (probe failed): " f"channel={channel_code}"
            )
            return

        # CLOSED 累加失败计数
        count = await self._incr_fail_count(channel_code)
        if count >= self.failure_threshold:
            await self._open(channel_code)
            logger.warning(
                f"breaker CLOSED→OPEN (failures={count}): " f"channel={channel_code}"
            )

    # ── 状态变更（内部）────────────────────────────────

    async def _set_state(self, channel_code: str, state: BreakerState) -> None:
        await RedisClient.set(
            _state_key(channel_code), state.value, expire=self.state_ttl
        )

    async def _open(self, channel_code: str) -> None:
        """触发熔断"""
        await self._set_state(channel_code, BreakerState.OPEN)
        await RedisClient.set(
            _opened_at_key(channel_code),
            str(time.time()),
            expire=self.state_ttl,
        )

    async def _incr_fail_count(self, channel_code: str) -> int:
        """累加失败计数，返回当前值"""
        key = _fail_count_key(channel_code)
        current_str = await RedisClient.get(key)
        current = int(current_str) if current_str else 0
        current += 1
        await RedisClient.set(key, str(current), expire=self.state_ttl)
        return current

    # ── 管理接口 ────────────────────────────────────────

    async def reset(self, channel_code: str) -> None:
        """重置熔断器（手动恢复/测试用）"""
        await RedisClient.delete(_state_key(channel_code))
        await RedisClient.delete(_fail_count_key(channel_code))
        await RedisClient.delete(_opened_at_key(channel_code))
        logger.info(f"breaker reset: channel={channel_code}")

    async def get_stats(self, channel_code: str) -> dict:
        """获取熔断器状态（监控/调试用）"""
        state = await self.get_state(channel_code)
        fail_count_str = await RedisClient.get(_fail_count_key(channel_code))
        opened_at_str = await RedisClient.get(_opened_at_key(channel_code))
        return {
            "channel_code": channel_code,
            "state": state.value,
            "fail_count": int(fail_count_str) if fail_count_str else 0,
            "opened_at": float(opened_at_str) if opened_at_str else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

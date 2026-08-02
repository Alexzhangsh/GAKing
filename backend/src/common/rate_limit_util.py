# @ai-generated
import time
from typing import Tuple
from datetime import datetime

from src.common.redis_client import RedisClient
from src.config.constants import RATE_LIMIT_PREFIX, RateLimitType
from src.config.env_config import EnvConfig


class RateLimitUtil:
    def __init__(self, key: str, limit: int = None, window: int = None):
        self.key = key
        self.limit = limit
        self.window = window

    async def allow(self) -> bool:
        if self.limit and self.window:
            allowed, _ = await self.check_sliding_window(self.key, self.limit, self.window)
            return allowed
        return True
    @classmethod
    async def check_sliding_window(cls, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        rate_key = f"{RATE_LIMIT_PREFIX}{key}"
        current_time = int(time.time())
        window_start = current_time - window_seconds
        request_id = f"{current_time}:{id(cls)}.{hash(str(time.time()))}"
        
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.zremrangebyscore(rate_key, 0, window_start)
            pipe.zcard(rate_key)
            results = await pipe.execute()
        
        count = results[1]
        if count >= limit:
            return False, count
        
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.zadd(rate_key, {request_id: current_time})
            pipe.expire(rate_key, window_seconds)
            await pipe.execute()
        
        return True, count + 1

    @classmethod
    async def check_fixed_window(cls, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        rate_key = f"{RATE_LIMIT_PREFIX}{key}"
        current_time = int(time.time())
        window_key = f"{rate_key}:{current_time // window_seconds}"
        
        count = await RedisClient.incr(window_key)
        if count == 1:
            await RedisClient.expire(window_key, window_seconds)
        
        if count > limit:
            return False, count
        return True, count

    @classmethod
    async def check_bucket(cls, key: str, capacity: int, rate: float) -> Tuple[bool, float]:
        rate_key = f"{RATE_LIMIT_PREFIX}bucket:{key}"
        current_time = time.time()
        
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.hget(rate_key, "tokens")
            pipe.hget(rate_key, "last_time")
            results = await pipe.execute()
        
        tokens = float(results[0]) if results[0] else capacity
        last_time = float(results[1]) if results[1] else current_time
        
        elapsed = current_time - last_time
        tokens = min(capacity, tokens + elapsed * rate)
        
        if tokens >= 1:
            tokens -= 1
            async with RedisClient.get_client().pipeline() as pipe:
                pipe.hset(rate_key, "tokens", tokens)
                pipe.hset(rate_key, "last_time", current_time)
                pipe.expire(rate_key, int(capacity / rate) + 1)
                await pipe.execute()
            return True, tokens
        
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.hset(rate_key, "tokens", tokens)
            pipe.hset(rate_key, "last_time", current_time)
            pipe.expire(rate_key, int(capacity / rate) + 1)
            await pipe.execute()
        return False, tokens

    @classmethod
    async def check_double_bucket(cls, key: str, burst_capacity: int, burst_rate: float, 
                                  steady_capacity: int, steady_rate: float) -> Tuple[bool, dict]:
        burst_key = f"{RATE_LIMIT_PREFIX}bucket:burst:{key}"
        steady_key = f"{RATE_LIMIT_PREFIX}bucket:steady:{key}"
        current_time = time.time()
        
        burst_ok, burst_tokens = await cls._check_single_bucket(burst_key, burst_capacity, burst_rate, current_time)
        steady_ok, steady_tokens = await cls._check_single_bucket(steady_key, steady_capacity, steady_rate, current_time)
        
        return burst_ok and steady_ok, {
            "burst_tokens": burst_tokens,
            "steady_tokens": steady_tokens,
            "burst_ok": burst_ok,
            "steady_ok": steady_ok
        }

    @classmethod
    async def _check_single_bucket(cls, key: str, capacity: int, rate: float, current_time: float) -> Tuple[bool, float]:
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.hget(key, "tokens")
            pipe.hget(key, "last_time")
            results = await pipe.execute()
        
        tokens = float(results[0]) if results[0] else capacity
        last_time = float(results[1]) if results[1] else current_time
        
        elapsed = current_time - last_time
        tokens = min(capacity, tokens + elapsed * rate)
        
        if tokens >= 1:
            tokens -= 1
            async with RedisClient.get_client().pipeline() as pipe:
                pipe.hset(key, "tokens", tokens)
                pipe.hset(key, "last_time", current_time)
                pipe.expire(key, int(capacity / rate) + 1)
                await pipe.execute()
            return True, tokens
        
        async with RedisClient.get_client().pipeline() as pipe:
            pipe.hset(key, "tokens", tokens)
            pipe.hset(key, "last_time", current_time)
            pipe.expire(key, int(capacity / rate) + 1)
            await pipe.execute()
        return False, tokens

    @classmethod
    async def check_by_type(cls, limit_type: RateLimitType, key: str) -> Tuple[bool, dict]:
        if limit_type == RateLimitType.NORMAL:
            return await cls.check_sliding_window(f"{limit_type.value}:{key}", EnvConfig.RATE_LIMIT_NORMAL, 60)
        elif limit_type == RateLimitType.SEARCH:
            return await cls.check_sliding_window(f"{limit_type.value}:{key}", EnvConfig.RATE_LIMIT_SEARCH, 60)
        elif limit_type == RateLimitType.TRANSFORM:
            return await cls.check_sliding_window(f"{limit_type.value}:{key}", EnvConfig.RATE_LIMIT_TRANSFORM, 60)
        elif limit_type == RateLimitType.PAY:
            return await cls.check_sliding_window(f"{limit_type.value}:{key}", EnvConfig.RATE_LIMIT_PAY, 60)
        elif limit_type == RateLimitType.DATAOK_SEARCH:
            return await cls.check_double_bucket(
                f"{limit_type.value}:{key}",
                burst_capacity=EnvConfig.DATAOK_SEARCH_LIMIT,
                burst_rate=EnvConfig.DATAOK_SEARCH_LIMIT / 60,
                steady_capacity=EnvConfig.DATAOK_SEARCH_LIMIT * 2,
                steady_rate=EnvConfig.DATAOK_SEARCH_LIMIT / 60
            )
        elif limit_type == RateLimitType.DATAOK_TRANSFORM:
            return await cls.check_double_bucket(
                f"{limit_type.value}:{key}",
                burst_capacity=EnvConfig.DATAOK_TRANSFORM_LIMIT,
                burst_rate=EnvConfig.DATAOK_TRANSFORM_LIMIT / 60,
                steady_capacity=EnvConfig.DATAOK_TRANSFORM_LIMIT * 2,
                steady_rate=EnvConfig.DATAOK_TRANSFORM_LIMIT / 60
            )
        return True, {}

    @classmethod
    async def get_remaining(cls, key: str, limit: int, window_seconds: int) -> int:
        rate_key = f"{RATE_LIMIT_PREFIX}{key}"
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        await RedisClient.get_client().zremrangebyscore(rate_key, 0, window_start)
        count = await RedisClient.get_client().zcard(rate_key)
        
        return max(0, limit - count)

    @classmethod
    async def reset_limit(cls, key: str) -> bool:
        rate_key = f"{RATE_LIMIT_PREFIX}{key}"
        keys = []
        async for k in RedisClient.get_client().scan_iter(f"{rate_key}*"):
            keys.append(k)
        
        if keys:
            await RedisClient.get_client().delete(*keys)
            return True
        return False


class DoubleBucketRateLimit:
    def __init__(self, key: str, max_tokens: int, refill_rate: float):
        self.key = key
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate

    async def allow(self) -> bool:
        allowed, _ = await RateLimitUtil.check_bucket(self.key, self.max_tokens, self.refill_rate)
        return allowed
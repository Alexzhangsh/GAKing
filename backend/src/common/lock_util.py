# @ai-generated
import uuid
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from src.common.redis_client import RedisClient
from src.config.constants import LOCK_PREFIX, LockTimeout


# S04 P2-1 优化：原子锁脚本（修复 setnx+expire 非原子导致锁残留问题）
# KEYS[1]=锁key  ARGV[1]=owner  ARGV[2]=过期时间戳  ARGV[3]=TTL秒  ARGV[4]=当前时间戳
_LOCK_ACQUIRE_LUA = """
local val = redis.call('get', KEYS[1])
local now = tonumber(ARGV[4])
if not val then
    redis.call('set', KEYS[1], ARGV[1] .. ':' .. ARGV[2])
    redis.call('expire', KEYS[1], ARGV[3])
    return 1
end
local sep = string.find(val, ':', 1, true)
if sep then
    local expire_ts = tonumber(string.sub(val, sep + 1))
    if expire_ts and expire_ts < now then
        redis.call('set', KEYS[1], ARGV[1] .. ':' .. ARGV[2])
        redis.call('expire', KEYS[1], ARGV[3])
        return 1
    end
end
return 0
"""

# 原子释放锁脚本：仅当 value 前缀为 owner: 时才删除（防误删他人锁）
_LOCK_RELEASE_LUA = """
local val = redis.call('get', KEYS[1])
if val then
    local owner = ARGV[1]
    if string.sub(val, 1, #owner) == owner then
        local c = string.sub(val, #owner + 1, #owner + 1)
        if c == ':' then
            return redis.call('del', KEYS[1])
        end
    end
end
return 0
"""

# 锁冲突统计键（用于运维观测任务跳过情况）
LOCK_CONFLICT_COUNTER_PREFIX = "scheduler:lock_conflict:"


class LockUtil:
    @classmethod
    async def acquire_lock(cls, key: str, timeout: int = LockTimeout.NORMAL, lock_owner: Optional[str] = None) -> Optional[str]:
        lock_key = f"{LOCK_PREFIX}{key}"
        owner = lock_owner or str(uuid.uuid4())
        now = datetime.now().timestamp()
        # S06 P2-1 修复：timeout 为 IntEnum，Python3.10 下 str() 得 "LockTimeout.NORMAL"
        # 而非 "10"，导致 Lua 收到非法 TTL、锁永久残留。统一先 int() 再转字符串。
        timeout_sec = int(timeout)
        lock_expire = now + timeout_sec + 1

        # S04 P2-1：改用 Lua 原子脚本（SET NX EX + 过期锁接管），
        # 修复原 setnx+expire 两步非原子、进程崩溃导致锁永久残留的问题
        result = await RedisClient.eval_script(
            _LOCK_ACQUIRE_LUA,
            1,
            lock_key,
            owner,
            str(lock_expire),
            str(timeout_sec),
            str(now),
        )
        if result == 1:
            return owner
        return None

    @classmethod
    def acquire(cls, key: str, timeout: int = LockTimeout.NORMAL):
        return _LockContextManager(key, timeout)

    @classmethod
    async def release_lock(cls, key: str, lock_owner: str) -> bool:
        lock_key = f"{LOCK_PREFIX}{key}"
        # S04 P2-1：改用 Lua 原子释放（仅当锁属于当前 owner 才删除）
        result = await RedisClient.eval_script(
            _LOCK_RELEASE_LUA,
            1,
            lock_key,
            lock_owner,
        )
        # 0=未修改（锁不存在或不属于当前owner），>0=成功删除
        return result is not None and result > 0

    @classmethod
    async def is_locked(cls, key: str) -> bool:
        lock_key = f"{LOCK_PREFIX}{key}"
        existing_value = await RedisClient.get(lock_key)
        
        if existing_value:
            try:
                _, existing_expire = existing_value.split(":")
                existing_expire = float(existing_expire)
                if datetime.now().timestamp() < existing_expire:
                    return True
            except (ValueError, IndexError):
                pass
        
        return False

    @classmethod
    async def renew_lock(cls, key: str, lock_owner: str, timeout: int = LockTimeout.NORMAL) -> bool:
        lock_key = f"{LOCK_PREFIX}{key}"
        existing_value = await RedisClient.get(lock_key)
        
        if existing_value:
            try:
                existing_owner, _ = existing_value.split(":")
                if existing_owner == lock_owner:
                    timeout_sec = int(timeout)
                    new_expire = datetime.now().timestamp() + timeout_sec + 1
                    await RedisClient.set(lock_key, f"{lock_owner}:{new_expire}")
                    await RedisClient.expire(lock_key, timeout_sec)
                    return True
            except (ValueError, IndexError):
                pass
        
        return False

    @classmethod
    async def acquire_with_wait(cls, key: str, timeout: int = LockTimeout.NORMAL, 
                                wait_timeout: int = 30, poll_interval: float = 0.1) -> Optional[str]:
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < wait_timeout:
            owner = await cls.acquire_lock(key, timeout)
            if owner:
                return owner
            await asyncio.sleep(poll_interval)
        
        return None

    @classmethod
    async def record_lock_conflict(cls, task_name: str) -> None:
        """记录锁冲突（任务因锁被占用而跳过），用于运维观测跳过概率

        Redis key: gaking:prod:scheduler:lock_conflict:{YYYYMMDD}:{task_name}
        TTL: 7 天，超期自动清理
        """
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{LOCK_CONFLICT_COUNTER_PREFIX}{day}:{task_name}"
        await RedisClient.incr(counter_key)
        await RedisClient.expire(counter_key, 7 * 24 * 3600)

    @classmethod
    async def force_release(cls, key: str) -> bool:
        lock_key = f"{LOCK_PREFIX}{key}"
        result = await RedisClient.delete(lock_key)
        return result > 0

    @classmethod
    async def get_lock_owner(cls, key: str) -> Optional[str]:
        lock_key = f"{LOCK_PREFIX}{key}"
        existing_value = await RedisClient.get(lock_key)
        
        if existing_value:
            try:
                existing_owner, _ = existing_value.split(":")
                return existing_owner
            except (ValueError, IndexError):
                pass
        
        return None

    @classmethod
    async def get_remaining_time(cls, key: str) -> int:
        lock_key = f"{LOCK_PREFIX}{key}"
        existing_value = await RedisClient.get(lock_key)
        
        if existing_value:
            try:
                _, existing_expire = existing_value.split(":")
                remaining = int(float(existing_expire) - datetime.now().timestamp())
                return max(0, remaining)
            except (ValueError, IndexError):
                pass
        
        return 0


class _LockContextManager:
    def __init__(self, key: str, timeout: int):
        self.key = key
        self.timeout = timeout
        self.lock_owner = None
        self._renew_task = None

    async def __aenter__(self):
        # S06 P2-1 增强：使用 acquire_with_wait 短等待再获取锁（默认 30s），
        # 避免定时任务调度间隔短于锁 TTL 时立即失败
        self.lock_owner = await LockUtil.acquire_with_wait(
            self.key, self.timeout, wait_timeout=30, poll_interval=0.5
        )
        if self.lock_owner is None:
            raise RuntimeError(f"Failed to acquire lock for {self.key}")
        
        async def renew_loop():
            while True:
                await asyncio.sleep(self.timeout / 2)
                await LockUtil.renew_lock(self.key, self.lock_owner, self.timeout)
        
        self._renew_task = asyncio.create_task(renew_loop())
        return self.lock_owner

    async def __aexit__(self, exc_type, exc, tb):
        if self._renew_task:
            self._renew_task.cancel()
            try:
                await self._renew_task
            except asyncio.CancelledError:
                pass
        if self.lock_owner:
            await LockUtil.release_lock(self.key, self.lock_owner)
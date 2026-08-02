# @ai-generated
import uuid
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from src.common.redis_client import RedisClient
from src.config.constants import LOCK_PREFIX, LockTimeout


class LockUtil:
    @classmethod
    async def acquire_lock(cls, key: str, timeout: int = LockTimeout.NORMAL, lock_owner: Optional[str] = None) -> Optional[str]:
        lock_key = f"{LOCK_PREFIX}{key}"
        owner = lock_owner or str(uuid.uuid4())
        now = datetime.now().timestamp()
        lock_expire = now + timeout + 1

        acquired = await RedisClient.setnx(lock_key, f"{owner}:{lock_expire}")
        
        if acquired:
            await RedisClient.expire(lock_key, timeout)
            return owner
        
        existing_value = await RedisClient.get(lock_key)
        if existing_value:
            try:
                existing_owner, existing_expire = existing_value.split(":")
                existing_expire = float(existing_expire)
                
                if now > existing_expire:
                    old_value = await RedisClient.getset(lock_key, f"{owner}:{lock_expire}")
                    if old_value == existing_value:
                        await RedisClient.expire(lock_key, timeout)
                        return owner
            except (ValueError, IndexError):
                pass
        
        return None

    @classmethod
    def acquire(cls, key: str, timeout: int = LockTimeout.NORMAL):
        return _LockContextManager(key, timeout)

    @classmethod
    async def release_lock(cls, key: str, lock_owner: str) -> bool:
        lock_key = f"{LOCK_PREFIX}{key}"
        existing_value = await RedisClient.get(lock_key)
        
        if existing_value:
            try:
                existing_owner, _ = existing_value.split(":")
                if existing_owner == lock_owner:
                    await RedisClient.delete(lock_key)
                    return True
            except (ValueError, IndexError):
                pass
        
        return False

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
                    new_expire = datetime.now().timestamp() + timeout + 1
                    await RedisClient.set(lock_key, f"{lock_owner}:{new_expire}")
                    await RedisClient.expire(lock_key, timeout)
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
        self.lock_owner = await LockUtil.acquire_lock(self.key, self.timeout)
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
# @ai-generated
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Tuple
from fastapi import HTTPException

from src.common.redis_client import RedisClient
from src.common.lock_util import LockUtil
from src.config.constants import IDEMPOTENT_PREFIX
from src.config.env_config import EnvConfig


class WebhookUtil:
    _timestamp_threshold = 300
    _idempotent_expire = 600

    @classmethod
    async def validate_timestamp(cls, timestamp: int) -> Tuple[bool, str]:
        current_time = int(datetime.now().timestamp())
        diff = abs(current_time - timestamp)
        
        if diff > cls._timestamp_threshold:
            return False, f"Timestamp expired, diff={diff}s"
        
        return True, ""

    @classmethod
    def validate_signature(cls, body: bytes, signature: str, secret: str) -> Tuple[bool, str]:
        if not secret:
            return False, "Webhook secret not configured"
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            return False, "Signature validation failed"
        
        return True, ""

    @classmethod
    async def verify_signature(cls, timestamp: int, signature: str, data: str, secret: str) -> bool:
        valid, _ = await cls.validate_timestamp(timestamp)
        if not valid:
            return False
        
        body = f"{timestamp}.{data}".encode('utf-8')
        valid, _ = cls.validate_signature(body, signature, secret)
        return valid

    @classmethod
    async def check_idempotency(cls, idempotency_key: str) -> bool:
        valid, _ = await cls.validate_idempotency(idempotency_key)
        return valid

    @classmethod
    async def validate_idempotency(cls, idempotency_key: str) -> Tuple[bool, str]:
        if not idempotency_key:
            return False, "Idempotency key is required"
        
        key = f"{IDEMPOTENT_PREFIX}{idempotency_key}"
        
        exists = await RedisClient.exists(key)
        if exists:
            return False, "Duplicate request detected"
        
        await RedisClient.set(key, "1", expire=cls._idempotent_expire)
        return True, ""

    @classmethod
    async def validate_webhook(cls, timestamp: int, signature: str, body: bytes, 
                               secret: str, idempotency_key: str = None) -> Tuple[bool, str]:
        valid, msg = await cls.validate_timestamp(timestamp)
        if not valid:
            return False, f"Timestamp validation failed: {msg}"
        
        valid, msg = cls.validate_signature(body, signature, secret)
        if not valid:
            return False, f"Signature validation failed: {msg}"
        
        if idempotency_key:
            valid, msg = await cls.validate_idempotency(idempotency_key)
            if not valid:
                return False, f"Idempotency validation failed: {msg}"
        
        return True, ""

    @classmethod
    async def validate_webhook_with_lock(cls, timestamp: int, signature: str, body: bytes, 
                                         secret: str, idempotency_key: str = None,
                                         lock_key: str = None) -> Tuple[bool, str]:
        if lock_key:
            owner = await LockUtil.acquire_lock(lock_key)
            if not owner:
                return False, "Concurrent request detected"
            
            try:
                return await cls.validate_webhook(timestamp, signature, body, secret, idempotency_key)
            finally:
                await LockUtil.release_lock(lock_key, owner)
        
        return await cls.validate_webhook(timestamp, signature, body, secret, idempotency_key)

    @classmethod
    def build_signature(cls, body: bytes, secret: str) -> str:
        return hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

    @classmethod
    async def mark_processed(cls, idempotency_key: str, result: dict = None) -> bool:
        if not idempotency_key:
            return False
        
        key = f"{IDEMPOTENT_PREFIX}{idempotency_key}"
        value = result if result else {"processed": True}
        await RedisClient.set_json(key, value, expire=cls._idempotent_expire)
        return True

    @classmethod
    async def get_processed_result(cls, idempotency_key: str) -> Optional[dict]:
        if not idempotency_key:
            return None
        
        key = f"{IDEMPOTENT_PREFIX}{idempotency_key}"
        return await RedisClient.get_json(key)
# @ai-generated
import json
import logging
import random
from typing import Any, Optional, Dict, List, Union

from redis.asyncio import Redis, ConnectionPool

from src.config.env_config import EnvConfig
from src.config.constants import REDIS_PREFIX

logger = logging.getLogger("redis_client")

_EMPTY_CACHE_TTL_SECONDS = 60
_TTL_JITTER_RATIO = 0.2

class RedisClient:
    _pool: ConnectionPool = None
    _client: Redis = None

    @classmethod
    def initialize(cls) -> None:
        if cls._pool is not None:
            return

        cls._pool = ConnectionPool(
            host=EnvConfig.REDIS_HOST,
            port=EnvConfig.REDIS_PORT,
            db=EnvConfig.REDIS_DB,
            password=EnvConfig.REDIS_PASSWORD,
            decode_responses=True,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=3,
            retry_on_timeout=True,
        )
        cls._client = Redis(connection_pool=cls._pool)
        logger.info(
            f"Redis pool initialized: host={EnvConfig.REDIS_HOST}:{EnvConfig.REDIS_PORT}, "
            f"max_connections=20"
        )

    @classmethod
    def get_client(cls) -> Redis:
        if cls._client is None:
            raise RuntimeError("Redis client not initialized")
        return cls._client

    @classmethod
    async def get_instance(cls):
        if cls._client is None:
            cls.initialize()
        return cls

    @classmethod
    def add_prefix(cls, key: str) -> str:
        if key.startswith(REDIS_PREFIX):
            return key
        return f"{REDIS_PREFIX}{key}"

    @classmethod
    def _jitter_ttl(cls, base_ttl: int) -> int:
        if base_ttl <= 0:
            return base_ttl
        jitter = int(base_ttl * _TTL_JITTER_RATIO)
        return base_ttl + random.randint(-jitter, jitter)

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        try:
            return await cls.get_client().get(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis GET failed for key '{key}': {e}")
            return None

    @classmethod
    async def set(
        cls,
        key: str,
        value: Union[str, bytes, int, float],
        expire: Optional[int] = None,
        ex: Optional[int] = None,
    ) -> bool:
        actual_expire = ex if ex is not None else expire
        try:
            result = await cls.get_client().set(cls.add_prefix(key), value)
            if actual_expire:
                jittered = cls._jitter_ttl(actual_expire)
                await cls.get_client().expire(cls.add_prefix(key), jittered)
            return result
        except Exception as e:
            logger.warning(f"Redis SET failed for key '{key}': {e}")
            return False

    @classmethod
    async def set_empty_cache(cls, key: str) -> bool:
        try:
            return await cls.set(key, "__EMPTY__", expire=_EMPTY_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Redis set_empty_cache failed for key '{key}': {e}")
            return False

    @classmethod
    async def is_empty_cache(cls, key: str) -> bool:
        try:
            val = await cls.get(key)
            return val == "__EMPTY__"
        except Exception:
            return False

    @classmethod
    async def keys(cls, pattern: str = "*") -> list:
        try:
            return await cls.get_client().keys(f"{REDIS_PREFIX}{pattern}")
        except Exception as e:
            logger.warning(f"Redis KEYS failed for pattern '{pattern}': {e}")
            return []

    @classmethod
    async def delete(cls, key: str) -> int:
        try:
            return await cls.get_client().delete(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis DELETE failed for key '{key}': {e}")
            return 0

    @classmethod
    async def exists(cls, key: str) -> int:
        try:
            return await cls.get_client().exists(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis EXISTS failed for key '{key}': {e}")
            return 0

    @classmethod
    async def expire(cls, key: str, expire: int) -> bool:
        try:
            jittered = cls._jitter_ttl(expire)
            return await cls.get_client().expire(cls.add_prefix(key), jittered)
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed for key '{key}': {e}")
            return False

    @classmethod
    async def ttl(cls, key: str) -> int:
        try:
            return await cls.get_client().ttl(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis TTL failed for key '{key}': {e}")
            return -2

    @classmethod
    async def get_json(cls, key: str) -> Optional[Dict[str, Any]]:
        try:
            value = await cls.get(key)
            if value and value != "__EMPTY__":
                return json.loads(value)
            return None
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.warning(f"Redis get_json failed for key '{key}': {e}")
            return None

    @classmethod
    async def set_json(
        cls, key: str, value: Dict[str, Any], expire: Optional[int] = None
    ) -> bool:
        json_str = json.dumps(value, ensure_ascii=False)
        return await cls.set(key, json_str, expire)

    @classmethod
    async def hget(cls, key: str, field: str) -> Optional[str]:
        try:
            return await cls.get_client().hget(cls.add_prefix(key), field)
        except Exception as e:
            logger.warning(f"Redis HGET failed for key '{key}' field '{field}': {e}")
            return None

    @classmethod
    async def hset(cls, key: str, field: str, value: str) -> int:
        try:
            return await cls.get_client().hset(cls.add_prefix(key), field, value)
        except Exception as e:
            logger.warning(f"Redis HSET failed for key '{key}': {e}")
            return 0

    @classmethod
    async def hgetall(cls, key: str) -> Dict[str, str]:
        try:
            return await cls.get_client().hgetall(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis HGETALL failed for key '{key}': {e}")
            return {}

    @classmethod
    async def hdel(cls, key: str, field: str) -> int:
        try:
            return await cls.get_client().hdel(cls.add_prefix(key), field)
        except Exception as e:
            logger.warning(f"Redis HDEL failed for key '{key}': {e}")
            return 0

    @classmethod
    async def llen(cls, key: str) -> int:
        try:
            return await cls.get_client().llen(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis LLEN failed for key '{key}': {e}")
            return 0

    @classmethod
    async def lpush(cls, key: str, *values: str) -> int:
        try:
            return await cls.get_client().lpush(cls.add_prefix(key), *values)
        except Exception as e:
            logger.warning(f"Redis LPUSH failed for key '{key}': {e}")
            return 0

    @classmethod
    async def rpush(cls, key: str, *values: str) -> int:
        try:
            return await cls.get_client().rpush(cls.add_prefix(key), *values)
        except Exception as e:
            logger.warning(f"Redis RPUSH failed for key '{key}': {e}")
            return 0

    @classmethod
    async def lpop(cls, key: str) -> Optional[str]:
        try:
            return await cls.get_client().lpop(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis LPOP failed for key '{key}': {e}")
            return None

    @classmethod
    async def rpop(cls, key: str) -> Optional[str]:
        try:
            return await cls.get_client().rpop(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis RPOP failed for key '{key}': {e}")
            return None

    @classmethod
    async def lrange(cls, key: str, start: int = 0, end: int = -1) -> List[str]:
        try:
            return await cls.get_client().lrange(cls.add_prefix(key), start, end)
        except Exception as e:
            logger.warning(f"Redis LRANGE failed for key '{key}': {e}")
            return []

    @classmethod
    async def incr(cls, key: str, amount: int = 1) -> int:
        try:
            return await cls.get_client().incr(cls.add_prefix(key), amount)
        except Exception as e:
            logger.warning(f"Redis INCR failed for key '{key}': {e}")
            return 0

    @classmethod
    async def decr(cls, key: str, amount: int = 1) -> int:
        try:
            return await cls.get_client().decr(cls.add_prefix(key), amount)
        except Exception as e:
            logger.warning(f"Redis DECR failed for key '{key}': {e}")
            return 0

    @classmethod
    async def getset(cls, key: str, value: str) -> Optional[str]:
        try:
            return await cls.get_client().getset(cls.add_prefix(key), value)
        except Exception as e:
            logger.warning(f"Redis GETSET failed for key '{key}': {e}")
            return None

    @classmethod
    async def setnx(cls, key: str, value: str) -> bool:
        try:
            return await cls.get_client().setnx(cls.add_prefix(key), value)
        except Exception as e:
            logger.warning(f"Redis SETNX failed for key '{key}': {e}")
            return False

    @classmethod
    async def setex(cls, key: str, time: int, value: str) -> bool:
        try:
            jittered = cls._jitter_ttl(time)
            return await cls.get_client().setex(cls.add_prefix(key), jittered, value)
        except Exception as e:
            logger.warning(f"Redis SETEX failed for key '{key}': {e}")
            return False

    @classmethod
    async def zadd(
        cls, key: str, mapping: Dict[str, float], nx: bool = False, xx: bool = False
    ) -> int:
        try:
            return await cls.get_client().zadd(
                cls.add_prefix(key), mapping, nx=nx, xx=xx
            )
        except Exception as e:
            logger.warning(f"Redis ZADD failed for key '{key}': {e}")
            return 0

    @classmethod
    async def zrange(
        cls, key: str, start: int = 0, end: int = -1, withscores: bool = False
    ) -> List[Any]:
        try:
            return await cls.get_client().zrange(
                cls.add_prefix(key), start, end, withscores=withscores
            )
        except Exception as e:
            logger.warning(f"Redis ZRANGE failed for key '{key}': {e}")
            return []

    @classmethod
    async def zrem(cls, key: str, *members: str) -> int:
        try:
            return await cls.get_client().zrem(cls.add_prefix(key), *members)
        except Exception as e:
            logger.warning(f"Redis ZREM failed for key '{key}': {e}")
            return 0

    @classmethod
    async def zcard(cls, key: str) -> int:
        try:
            return await cls.get_client().zcard(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis ZCARD failed for key '{key}': {e}")
            return 0

    @classmethod
    async def smembers(cls, key: str) -> set:
        try:
            return await cls.get_client().smembers(cls.add_prefix(key))
        except Exception as e:
            logger.warning(f"Redis SMEMBERS failed for key '{key}': {e}")
            return set()

    @classmethod
    async def sadd(cls, key: str, *members: str) -> int:
        try:
            return await cls.get_client().sadd(cls.add_prefix(key), *members)
        except Exception as e:
            logger.warning(f"Redis SADD failed for key '{key}': {e}")
            return 0

    @classmethod
    async def srem(cls, key: str, *members: str) -> int:
        try:
            return await cls.get_client().srem(cls.add_prefix(key), *members)
        except Exception as e:
            logger.warning(f"Redis SREM failed for key '{key}': {e}")
            return 0

    @classmethod
    async def scan_iter(cls, match: str = None, count: int = 1000) -> Any:
        prefix = REDIS_PREFIX if match and not match.startswith(REDIS_PREFIX) else ""
        pattern = f"{prefix}{match}" if match else None
        return cls.get_client().scan_iter(match=pattern, count=count)

    @classmethod
    async def flushdb(cls) -> bool:
        try:
            return await cls.get_client().flushdb()
        except Exception as e:
            logger.warning(f"Redis FLUSHDB failed: {e}")
            return False

    @classmethod
    async def eval_script(
        cls, script: str, numkeys: int, *args: str
    ) -> Any:
        try:
            return await cls.get_client().eval(script, numkeys, *args)
        except Exception as e:
            logger.warning(f"Redis EVAL failed: {e}")
            return None

    @classmethod
    async def health_check(cls) -> bool:
        try:
            await cls.get_client().ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.close()
            cls._client = None
            cls._pool = None
            logger.info("Redis client and pool closed")

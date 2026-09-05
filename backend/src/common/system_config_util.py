# @ai-generated
import json
from typing import Any, Optional, Dict
from sqlalchemy import select

from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig as GakingSystemConfig
from src.common.redis_client import RedisClient
from src.config.constants import CACHE_KEY_SYSTEM_CONFIG


class SystemConfigUtil:
    _config_cache: Dict[str, str] = {}
    _cache_loaded: bool = False

    @classmethod
    async def load_config(cls) -> None:
        async with DatabaseManager.get_session() as session:
            result = await session.execute(
                select(GakingSystemConfig).where(GakingSystemConfig.is_delete == False)
            )
            configs = result.scalars().all()
            cls._config_cache = {config.config_key: config.config_value for config in configs}
            cls._cache_loaded = True
            await RedisClient.set_json(CACHE_KEY_SYSTEM_CONFIG, cls._config_cache)

    @classmethod
    async def get(cls, key: str, default: Any = None) -> Any:
        if not cls._cache_loaded:
            await cls.load_config()

        value = cls._config_cache.get(key)
        if value is None:
            return default

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    @classmethod
    async def get_str(cls, key: str, default: str = "") -> str:
        value = await cls.get(key, default)
        return str(value) if value is not None else default

    @classmethod
    async def get_int(cls, key: str, default: int = 0) -> int:
        value = await cls.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    async def get_float(cls, key: str, default: float = 0.0) -> float:
        value = await cls.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    async def get_bool(cls, key: str, default: bool = False) -> bool:
        value = await cls.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    @classmethod
    async def get_json(cls, key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        value = await cls.get(key, default)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default or {}
        return default or {}

    @classmethod
    async def refresh(cls) -> None:
        await cls.load_config()

    @classmethod
    async def set(cls, key: str, value: Any) -> None:
        async with DatabaseManager.get_session() as session:
            result = await session.execute(
                select(GakingSystemConfig).where(GakingSystemConfig.config_key == key)
            )
            config = result.scalar_one_or_none()

            if config:
                config.config_value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            else:
                config = GakingSystemConfig(
                    config_key=key,
                    config_value=json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value),
                    config_name=key,
                )
                session.add(config)

            await session.commit()

        cls._config_cache[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        await RedisClient.set_json(CACHE_KEY_SYSTEM_CONFIG, cls._config_cache)

    @classmethod
    async def delete(cls, key: str) -> None:
        async with DatabaseManager.get_session() as session:
            result = await session.execute(
                select(GakingSystemConfig).where(GakingSystemConfig.config_key == key)
            )
            config = result.scalar_one_or_none()

            if config:
                config.is_delete = True
                await session.commit()

        if key in cls._config_cache:
            del cls._config_cache[key]
            await RedisClient.set_json(CACHE_KEY_SYSTEM_CONFIG, cls._config_cache)

    @classmethod
    def get_all(cls) -> Dict[str, str]:
        return cls._config_cache.copy()
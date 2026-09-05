# @ai-generated
"""
系统配置统一读写工具（B14 新建，不复用已损坏的 system_config_util.py）
双层缓存：内存 Dict + Redis（gaking:prod:config:system 永久有效）
写后失效：DB 写入 → 更新内存 → 全量刷新 Redis
异常降级：DB/Redis 异常时降级到常量默认值，记 warn 不抛（不阻塞业务）

B14 自身消费方（限流中间件等）动态读取此工具，实现配置热生效
B12/B13 模块保持常量兜底，后续采纳 B14ConfigUtil.get_xxx(key, fallback=常量) 即可热生效
"""
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from sqlalchemy import select

from src.common.redis_client import RedisClient
from src.config.b14_constants import B14_CONFIG_REGISTRY, CACHE_KEY_B14_CONFIG
from src.db.init_db import DatabaseManager
from src.models.system.system_config import SystemConfig

logger = logging.getLogger("common.b14_config_util")


class B14ConfigUtil:
    """系统配置统一读写工具（双层缓存 + 热生效）"""

    # 内存缓存：key → value(字符串)
    _memory_cache: Dict[str, str] = {}
    _cache_loaded: bool = False

    # ════════════════════════════════════════════════════
    # 加载与刷新
    # ════════════════════════════════════════════════════

    @classmethod
    async def load_all(cls) -> None:
        """全量加载配置：DB → 内存 → Redis

        启动时调用一次；DB 异常时降级到 Redis，Redis 异常时降级到内存空
        """
        try:
            async with DatabaseManager.get_session() as session:
                result = await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.is_delete == False  # noqa: E712
                    )
                )
                configs = result.scalars().all()
                cls._memory_cache = {
                    c.config_key: c.config_value for c in configs
                }
                cls._cache_loaded = True
        except Exception as e:
            logger.warning("[b14_config] DB 加载配置失败，尝试 Redis: %s", e)
            # 降级：尝试从 Redis 加载
            await cls._load_from_redis()

        # 写入 Redis 缓存
        try:
            await RedisClient.set_json(
                CACHE_KEY_B14_CONFIG, cls._memory_cache
            )
        except Exception as e:
            logger.warning("[b14_config] Redis 写入缓存失败: %s", e)

    @classmethod
    async def _load_from_redis(cls) -> None:
        """从 Redis 加载配置（DB 不可用时的降级路径）"""
        try:
            data = await RedisClient.get_json(CACHE_KEY_B14_CONFIG)
            if data and isinstance(data, dict):
                cls._memory_cache = {k: str(v) for k, v in data.items()}
                cls._cache_loaded = True
        except Exception as e:
            logger.warning("[b14_config] Redis 加载配置失败: %s", e)

    @classmethod
    async def refresh(cls) -> None:
        """刷新缓存：清空内存 + Redis，重新全量加载"""
        cls._memory_cache = {}
        cls._cache_loaded = False
        try:
            await RedisClient.delete(CACHE_KEY_B14_CONFIG)
        except Exception as e:
            logger.warning("[b14_config] Redis 删除缓存失败: %s", e)
        await cls.load_all()

    @classmethod
    async def invalidate(cls, key: Optional[str] = None) -> None:
        """失效缓存（单 key 或全量）

        Args:
            key: 指定 key 失效；None 表示全量刷新
        """
        if key is None:
            await cls.refresh()
            return
        # 单 key 失效：从内存移除 + 全量刷 Redis（保证一致性）
        cls._memory_cache.pop(key, None)
        try:
            await RedisClient.set_json(
                CACHE_KEY_B14_CONFIG, cls._memory_cache
            )
        except Exception as e:
            logger.warning("[b14_config] invalidate Redis 刷新失败: %s", e)

    # ════════════════════════════════════════════════════
    # 读取（带降级）
    # ════════════════════════════════════════════════════

    @classmethod
    async def get(cls, key: str, default: Any = None) -> Any:
        """获取配置值（字符串）

        读取顺序：内存 → Redis → DB → 注册表默认值 → default 参数
        """
        if not cls._cache_loaded:
            await cls.load_all()

        # 内存命中
        value = cls._memory_cache.get(key)
        if value is not None:
            return value

        # 内存未命中，降级到注册表默认值
        registry = B14_CONFIG_REGISTRY.get(key)
        if registry is not None:
            return registry["default"]
        return default

    @classmethod
    async def get_str(cls, key: str, default: str = "") -> str:
        """获取字符串配置"""
        value = await cls.get(key, default)
        return str(value) if value is not None else default

    @classmethod
    async def get_int(cls, key: str, default: Optional[int] = None) -> int:
        """获取整数配置

        default 为 None 时自动从注册表取默认值
        """
        if default is None:
            registry = B14_CONFIG_REGISTRY.get(key)
            default = int(registry["default"]) if registry else 0
        value = await cls.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    async def get_bool(cls, key: str, default: Optional[bool] = None) -> bool:
        """获取布尔配置"""
        if default is None:
            registry = B14_CONFIG_REGISTRY.get(key)
            default = bool(registry["default"]) if registry else False
        value = await cls.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    @classmethod
    async def get_decimal(
        cls, key: str, default: Optional[Decimal] = None
    ) -> Decimal:
        """获取金额配置（Decimal）"""
        if default is None:
            registry = B14_CONFIG_REGISTRY.get(key)
            default = Decimal(str(registry["default"])) if registry else Decimal("0")
        value = await cls.get(key, str(default))
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default

    @classmethod
    async def get_json(
        cls, key: str, default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """获取 JSON 配置"""
        value = await cls.get(key, None)
        if value is None:
            return default or {}
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default or {}

    # ════════════════════════════════════════════════════
    # 写入
    # ════════════════════════════════════════════════════

    @classmethod
    async def set(cls, key: str, value: Any) -> None:
        """写入配置（DB upsert + 内存更新 + Redis 刷新）

        Args:
            key: 配置键
            value: 配置值（dict/list 自动 JSON 序列化）
        """
        str_value = (
            json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else str(value)
        )

        # 写 DB（upsert）
        try:
            async with DatabaseManager.get_session() as session:
                result = await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.config_key == key
                    )
                )
                config = result.scalar_one_or_none()
                if config is not None:
                    config.config_value = str_value
                else:
                    config = SystemConfig(
                        config_key=key,
                        config_value=str_value,
                        config_name=key,
                        remark="",
                    )
                    session.add(config)
                await session.flush()
                await session.commit()
        except Exception as e:
            logger.error("[b14_config] DB 写入失败 key=%s: %s", key, e)
            raise

        # 更新内存 + Redis
        cls._memory_cache[key] = str_value
        try:
            await RedisClient.set_json(CACHE_KEY_B14_CONFIG, cls._memory_cache)
        except Exception as e:
            logger.warning("[b14_config] Redis 刷新失败: %s", e)

    @classmethod
    def get_all_memory(cls) -> Dict[str, str]:
        """获取内存缓存全量副本（调试/监控用）"""
        return cls._memory_cache.copy()

# @ai-generated
from typing import Dict, List, Optional
from sqlalchemy import select

from src.db.init_db import DatabaseManager
from src.db.models import GakingChannelMapping
from src.common.redis_client import RedisClient
from src.config.constants import CACHE_KEY_CHANNEL_MAPPING, ChannelCode


class ChannelMappingUtil:
    _mapping_cache: Dict[str, List[dict]] = {}
    _cache_loaded: bool = False

    @classmethod
    async def load_mapping(cls) -> None:
        async with DatabaseManager.get_session() as session:
            result = await session.execute(
                select(GakingChannelMapping).where(GakingChannelMapping.is_delete == False, GakingChannelMapping.status == True)
            )
            mappings = result.scalars().all()
            
            cls._mapping_cache = {}
            for mapping in mappings:
                channel_code = mapping.channel_code
                if channel_code not in cls._mapping_cache:
                    cls._mapping_cache[channel_code] = []
                cls._mapping_cache[channel_code].append({
                    "third_field": mapping.third_field,
                    "system_field": mapping.system_field,
                    "field_desc": mapping.field_desc,
                })
            
            cls._cache_loaded = True
            await RedisClient.set_json(CACHE_KEY_CHANNEL_MAPPING, cls._mapping_cache)

    @classmethod
    async def get_mapping(cls, channel_code: str) -> List[dict]:
        if not cls._cache_loaded:
            await cls.load_mapping()
        return cls._mapping_cache.get(channel_code, [])

    @classmethod
    async def convert(cls, channel_code: str, third_party_data: Dict[str, any]) -> Dict[str, any]:
        mappings = await cls.get_mapping(channel_code)
        if not mappings:
            return third_party_data
        
        result = {}
        for mapping in mappings:
            third_field = mapping["third_field"]
            system_field = mapping["system_field"]
            if third_field in third_party_data:
                result[system_field] = third_party_data[third_field]
        
        for key, value in third_party_data.items():
            if key not in [m["third_field"] for m in mappings]:
                result[key] = value
        
        return result

    @classmethod
    async def reverse_convert(cls, channel_code: str, system_data: Dict[str, any]) -> Dict[str, any]:
        mappings = await cls.get_mapping(channel_code)
        if not mappings:
            return system_data
        
        result = {}
        for mapping in mappings:
            third_field = mapping["third_field"]
            system_field = mapping["system_field"]
            if system_field in system_data:
                result[third_field] = system_data[system_field]
        
        for key, value in system_data.items():
            if key not in [m["system_field"] for m in mappings]:
                result[key] = value
        
        return result

    @classmethod
    async def get_system_field(cls, channel_code: str, third_field: str) -> Optional[str]:
        mappings = await cls.get_mapping(channel_code)
        for mapping in mappings:
            if mapping["third_field"] == third_field:
                return mapping["system_field"]
        return None

    @classmethod
    async def get_third_field(cls, channel_code: str, system_field: str) -> Optional[str]:
        mappings = await cls.get_mapping(channel_code)
        for mapping in mappings:
            if mapping["system_field"] == system_field:
                return mapping["third_field"]
        return None

    @classmethod
    async def refresh(cls) -> None:
        await cls.load_mapping()

    @classmethod
    def get_all(cls) -> Dict[str, List[dict]]:
        return cls._mapping_cache.copy()

    @classmethod
    async def get_channel_list(cls) -> List[str]:
        if not cls._cache_loaded:
            await cls.load_mapping()
        return list(cls._mapping_cache.keys())
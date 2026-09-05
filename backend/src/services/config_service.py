# @ai-generated
from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.models.system.system_config import SystemConfig as GakingSystemConfig
from src.models.system.pay_config import PayConfig as GakingPayConfig
from src.models.system.cloud_config import CloudConfig as GakingCloudConfig
from src.models.system.channel_config import ChannelMapping as GakingChannelMapping
from src.schemas.config import (
    SystemConfigCreate,
    SystemConfigUpdate,
    PayConfigCreate,
    PayConfigUpdate,
    CloudConfigCreate,
    CloudConfigUpdate,
    ChannelMappingCreate,
    ChannelMappingUpdate,
)
from src.common.system_config_util import SystemConfigUtil
from src.common.channel_mapping_util import ChannelMappingUtil


class ConfigService:
    @classmethod
    async def create_system_config(cls, db: AsyncSession, data: SystemConfigCreate):
        existing = await cls.get_system_config_by_key(db, data.config_key, include_deleted=True)
        if existing:
            raise HTTPException(status_code=400, detail="配置键名已存在")
        
        config = GakingSystemConfig(
            config_key=data.config_key,
            config_value=data.config_value,
            config_name=data.config_name,
            config_desc=data.config_desc,
            sort_num=data.sort_num,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        await SystemConfigUtil.refresh()
        return config

    @classmethod
    async def get_system_config_by_id(cls, db: AsyncSession, config_id: int):
        result = await db.execute(
            select(GakingSystemConfig).where(GakingSystemConfig.id == config_id, GakingSystemConfig.is_delete == False)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_system_config_by_key(cls, db: AsyncSession, config_key: str, include_deleted: bool = False):
        if include_deleted:
            result = await db.execute(
                select(GakingSystemConfig).where(GakingSystemConfig.config_key == config_key)
            )
        else:
            result = await db.execute(
                select(GakingSystemConfig).where(GakingSystemConfig.config_key == config_key, GakingSystemConfig.is_delete == False)
            )
        return result.scalar_one_or_none()

    @classmethod
    async def list_system_config(cls, db: AsyncSession, page: int = 1, page_size: int = 10):
        offset = (page - 1) * page_size
        result = await db.execute(
            select(GakingSystemConfig)
            .where(GakingSystemConfig.is_delete == False)
            .order_by(GakingSystemConfig.sort_num.asc(), GakingSystemConfig.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = result.scalars().all()
        
        count_result = await db.execute(
            select(GakingSystemConfig).where(GakingSystemConfig.is_delete == False)
        )
        total = len(count_result.scalars().all())
        
        return total, items

    @classmethod
    async def update_system_config(cls, db: AsyncSession, config_id: int, data: SystemConfigUpdate):
        config = await cls.get_system_config_by_id(db, config_id)
        if not config:
            return None
        
        if data.config_value is not None:
            config.config_value = data.config_value
        if data.config_name is not None:
            config.config_name = data.config_name
        if data.config_desc is not None:
            config.config_desc = data.config_desc
        if data.sort_num is not None:
            config.sort_num = data.sort_num
        
        await db.commit()
        await db.refresh(config)
        await SystemConfigUtil.refresh()
        return config

    @classmethod
    async def delete_system_config(cls, db: AsyncSession, config_id: int):
        config = await cls.get_system_config_by_id(db, config_id)
        if not config:
            return False
        
        config.is_delete = True
        await db.commit()
        await SystemConfigUtil.refresh()
        return True

    @classmethod
    async def create_pay_config(cls, db: AsyncSession, data: PayConfigCreate):
        config = GakingPayConfig(
            pay_type=data.pay_type,
            mch_id=data.mch_id,
            api_key=data.api_key,
            cert_path=data.cert_path,
            notify_url=data.notify_url,
            withdraw_rate=data.withdraw_rate,
            withdraw_min=data.withdraw_min,
            withdraw_fixed_fee=data.withdraw_fixed_fee,
            status=data.status,
            remark=data.remark,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def get_pay_config_by_id(cls, db: AsyncSession, config_id: int):
        result = await db.execute(
            select(GakingPayConfig).where(GakingPayConfig.id == config_id, GakingPayConfig.is_delete == False)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def list_pay_config(cls, db: AsyncSession, page: int = 1, page_size: int = 10, pay_type: Optional[int] = None):
        offset = (page - 1) * page_size
        query = select(GakingPayConfig).where(GakingPayConfig.is_delete == False)
        
        if pay_type is not None:
            query = query.where(GakingPayConfig.pay_type == pay_type)
        
        result = await db.execute(
            query.order_by(GakingPayConfig.create_time.desc()).offset(offset).limit(page_size)
        )
        items = result.scalars().all()
        
        count_result = await db.execute(query)
        total = len(count_result.scalars().all())
        
        return total, items

    @classmethod
    async def update_pay_config(cls, db: AsyncSession, config_id: int, data: PayConfigUpdate):
        config = await cls.get_pay_config_by_id(db, config_id)
        if not config:
            return None
        
        if data.pay_type is not None:
            config.pay_type = data.pay_type
        if data.mch_id is not None:
            config.mch_id = data.mch_id
        if data.api_key is not None:
            config.api_key = data.api_key
        if data.cert_path is not None:
            config.cert_path = data.cert_path
        if data.notify_url is not None:
            config.notify_url = data.notify_url
        if data.withdraw_rate is not None:
            config.withdraw_rate = data.withdraw_rate
        if data.withdraw_min is not None:
            config.withdraw_min = data.withdraw_min
        if data.withdraw_fixed_fee is not None:
            config.withdraw_fixed_fee = data.withdraw_fixed_fee
        if data.status is not None:
            config.status = data.status
        if data.remark is not None:
            config.remark = data.remark
        
        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def delete_pay_config(cls, db: AsyncSession, config_id: int):
        config = await cls.get_pay_config_by_id(db, config_id)
        if not config:
            return False
        
        config.is_delete = True
        await db.commit()
        return True

    @classmethod
    async def create_cloud_config(cls, db: AsyncSession, data: CloudConfigCreate):
        config = GakingCloudConfig(
            config_name=data.config_name,
            cdn_domain=data.cdn_domain,
            obs_bucket=data.obs_bucket,
            obs_endpoint=data.obs_endpoint,
            access_key=data.access_key,
            secret_key=data.secret_key,
            status=data.status,
            remark=data.remark,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def get_cloud_config_by_id(cls, db: AsyncSession, config_id: int):
        result = await db.execute(
            select(GakingCloudConfig).where(GakingCloudConfig.id == config_id, GakingCloudConfig.is_delete == False)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def list_cloud_config(cls, db: AsyncSession, page: int = 1, page_size: int = 10, status: Optional[bool] = None):
        offset = (page - 1) * page_size
        query = select(GakingCloudConfig).where(GakingCloudConfig.is_delete == False)
        
        if status is not None:
            query = query.where(GakingCloudConfig.status == status)
        
        result = await db.execute(
            query.order_by(GakingCloudConfig.create_time.desc()).offset(offset).limit(page_size)
        )
        items = result.scalars().all()
        
        count_result = await db.execute(query)
        total = len(count_result.scalars().all())
        
        return total, items

    @classmethod
    async def update_cloud_config(cls, db: AsyncSession, config_id: int, data: CloudConfigUpdate):
        config = await cls.get_cloud_config_by_id(db, config_id)
        if not config:
            return None
        
        if data.config_name is not None:
            config.config_name = data.config_name
        if data.cdn_domain is not None:
            config.cdn_domain = data.cdn_domain
        if data.obs_bucket is not None:
            config.obs_bucket = data.obs_bucket
        if data.obs_endpoint is not None:
            config.obs_endpoint = data.obs_endpoint
        if data.access_key is not None:
            config.access_key = data.access_key
        if data.secret_key is not None:
            config.secret_key = data.secret_key
        if data.status is not None:
            config.status = data.status
        if data.remark is not None:
            config.remark = data.remark
        
        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def delete_cloud_config(cls, db: AsyncSession, config_id: int):
        config = await cls.get_cloud_config_by_id(db, config_id)
        if not config:
            return False
        
        config.is_delete = True
        await db.commit()
        return True

    @classmethod
    async def create_channel_mapping(cls, db: AsyncSession, data: ChannelMappingCreate):
        mapping = GakingChannelMapping(
            channel_code=data.channel_code,
            third_field=data.third_field,
            system_field=data.system_field,
            field_desc=data.field_desc,
            status=data.status,
            sort_num=data.sort_num,
            remark=data.remark,
        )
        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)
        await ChannelMappingUtil.refresh()
        return mapping

    @classmethod
    async def get_channel_mapping_by_id(cls, db: AsyncSession, mapping_id: int):
        result = await db.execute(
            select(GakingChannelMapping).where(GakingChannelMapping.id == mapping_id, GakingChannelMapping.is_delete == False)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def list_channel_mapping(cls, db: AsyncSession, page: int = 1, page_size: int = 10, channel_code: Optional[str] = None):
        offset = (page - 1) * page_size
        query = select(GakingChannelMapping).where(GakingChannelMapping.is_delete == False)
        
        if channel_code is not None:
            query = query.where(GakingChannelMapping.channel_code == channel_code)
        
        result = await db.execute(
            query.order_by(GakingChannelMapping.sort_num.asc(), GakingChannelMapping.create_time.desc()).offset(offset).limit(page_size)
        )
        items = result.scalars().all()
        
        count_result = await db.execute(query)
        total = len(count_result.scalars().all())
        
        return total, items

    @classmethod
    async def update_channel_mapping(cls, db: AsyncSession, mapping_id: int, data: ChannelMappingUpdate):
        mapping = await cls.get_channel_mapping_by_id(db, mapping_id)
        if not mapping:
            return None
        
        if data.third_field is not None:
            mapping.third_field = data.third_field
        if data.system_field is not None:
            mapping.system_field = data.system_field
        if data.field_desc is not None:
            mapping.field_desc = data.field_desc
        if data.status is not None:
            mapping.status = data.status
        if data.sort_num is not None:
            mapping.sort_num = data.sort_num
        if data.remark is not None:
            mapping.remark = data.remark
        
        await db.commit()
        await db.refresh(mapping)
        await ChannelMappingUtil.refresh()
        return mapping

    @classmethod
    async def delete_channel_mapping(cls, db: AsyncSession, mapping_id: int):
        mapping = await cls.get_channel_mapping_by_id(db, mapping_id)
        if not mapping:
            return False
        
        mapping.is_delete = True
        await db.commit()
        await ChannelMappingUtil.refresh()
        return True
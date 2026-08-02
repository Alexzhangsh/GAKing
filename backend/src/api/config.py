# @ai-generated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.init_db import DatabaseManager
from src.services.config_service import ConfigService
from src.schemas.config import (
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigResponse,
    PayConfigCreate,
    PayConfigUpdate,
    PayConfigResponse,
    CloudConfigCreate,
    CloudConfigUpdate,
    CloudConfigResponse,
    ChannelMappingCreate,
    ChannelMappingUpdate,
    ChannelMappingResponse,
)

router = APIRouter(prefix="/api/admin", tags=["config"])


async def get_db():
    async with DatabaseManager.get_session() as session:
        yield session


@router.post("/system-config", response_model=SystemConfigResponse)
async def create_system_config(data: SystemConfigCreate, db: AsyncSession = Depends(get_db)):
    existing = await ConfigService.get_system_config_by_key(db, data.config_key)
    if existing:
        raise HTTPException(status_code=400, detail="配置键名已存在")
    
    config = await ConfigService.create_system_config(db, data)
    return config


@router.get("/system-config/{config_id}", response_model=SystemConfigResponse)
async def get_system_config(config_id: int, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.get_system_config_by_id(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.get("/system-config")
async def list_system_config(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    total, items = await ConfigService.list_system_config(db, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [SystemConfigResponse.from_orm(item) for item in items]
    }


@router.put("/system-config/{config_id}", response_model=SystemConfigResponse)
async def update_system_config(config_id: int, data: SystemConfigUpdate, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.update_system_config(db, config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return config


@router.delete("/system-config/{config_id}")
async def delete_system_config(config_id: int, db: AsyncSession = Depends(get_db)):
    success = await ConfigService.delete_system_config(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"message": "删除成功"}


@router.post("/pay-config", response_model=PayConfigResponse)
async def create_pay_config(data: PayConfigCreate, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.create_pay_config(db, data)
    return config


@router.get("/pay-config/{config_id}", response_model=PayConfigResponse)
async def get_pay_config(config_id: int, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.get_pay_config_by_id(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="支付配置不存在")
    return config


@router.get("/pay-config")
async def list_pay_config(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    pay_type: int = Query(None),
    db: AsyncSession = Depends(get_db)
):
    total, items = await ConfigService.list_pay_config(db, page, page_size, pay_type)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [PayConfigResponse.from_orm(item) for item in items]
    }


@router.put("/pay-config/{config_id}", response_model=PayConfigResponse)
async def update_pay_config(config_id: int, data: PayConfigUpdate, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.update_pay_config(db, config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="支付配置不存在")
    return config


@router.delete("/pay-config/{config_id}")
async def delete_pay_config(config_id: int, db: AsyncSession = Depends(get_db)):
    success = await ConfigService.delete_pay_config(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="支付配置不存在")
    return {"message": "删除成功"}


@router.post("/cloud-config", response_model=CloudConfigResponse)
async def create_cloud_config(data: CloudConfigCreate, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.create_cloud_config(db, data)
    return config


@router.get("/cloud-config/{config_id}", response_model=CloudConfigResponse)
async def get_cloud_config(config_id: int, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.get_cloud_config_by_id(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="云配置不存在")
    return config


@router.get("/cloud-config")
async def list_cloud_config(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: bool = Query(None),
    db: AsyncSession = Depends(get_db)
):
    total, items = await ConfigService.list_cloud_config(db, page, page_size, status)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [CloudConfigResponse.from_orm(item) for item in items]
    }


@router.put("/cloud-config/{config_id}", response_model=CloudConfigResponse)
async def update_cloud_config(config_id: int, data: CloudConfigUpdate, db: AsyncSession = Depends(get_db)):
    config = await ConfigService.update_cloud_config(db, config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="云配置不存在")
    return config


@router.delete("/cloud-config/{config_id}")
async def delete_cloud_config(config_id: int, db: AsyncSession = Depends(get_db)):
    success = await ConfigService.delete_cloud_config(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="云配置不存在")
    return {"message": "删除成功"}


@router.post("/channel-mapping", response_model=ChannelMappingResponse)
async def create_channel_mapping(data: ChannelMappingCreate, db: AsyncSession = Depends(get_db)):
    mapping = await ConfigService.create_channel_mapping(db, data)
    return mapping


@router.get("/channel-mapping/{mapping_id}", response_model=ChannelMappingResponse)
async def get_channel_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    mapping = await ConfigService.get_channel_mapping_by_id(db, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="渠道映射不存在")
    return mapping


@router.get("/channel-mapping")
async def list_channel_mapping(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    channel_code: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    total, items = await ConfigService.list_channel_mapping(db, page, page_size, channel_code)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [ChannelMappingResponse.from_orm(item) for item in items]
    }


@router.put("/channel-mapping/{mapping_id}", response_model=ChannelMappingResponse)
async def update_channel_mapping(mapping_id: int, data: ChannelMappingUpdate, db: AsyncSession = Depends(get_db)):
    mapping = await ConfigService.update_channel_mapping(db, mapping_id, data)
    if not mapping:
        raise HTTPException(status_code=404, detail="渠道映射不存在")
    return mapping


@router.delete("/channel-mapping/{mapping_id}")
async def delete_channel_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    success = await ConfigService.delete_channel_mapping(db, mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="渠道映射不存在")
    return {"message": "删除成功"}
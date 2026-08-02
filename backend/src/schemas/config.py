# @ai-generated
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional


class SystemConfigCreate(BaseModel):
    config_key: str = Field(..., max_length=64)
    config_value: str = Field(default="", max_length=2000)
    config_name: str = Field(..., max_length=128)
    config_desc: str = Field(default="", max_length=512)
    sort_num: int = Field(default=0)


class SystemConfigUpdate(BaseModel):
    config_value: Optional[str] = Field(None, max_length=2000)
    config_name: Optional[str] = Field(None, max_length=128)
    config_desc: Optional[str] = Field(None, max_length=512)
    sort_num: Optional[int] = None


class SystemConfigResponse(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_name: str
    config_desc: str
    sort_num: int
    create_time: str
    update_time: str

    class Config:
        from_attributes = True


class PayConfigCreate(BaseModel):
    pay_type: int = Field(default=1)
    mch_id: str = Field(default="", max_length=64)
    api_key: str = Field(default="", max_length=128)
    cert_path: str = Field(default="", max_length=256)
    notify_url: str = Field(default="", max_length=256)
    withdraw_rate: Decimal = Field(default=0.00)
    withdraw_min: Decimal = Field(default=0.00)
    withdraw_fixed_fee: Decimal = Field(default=0.00)
    status: bool = Field(default=True)
    remark: str = Field(default="", max_length=512)


class PayConfigUpdate(BaseModel):
    pay_type: Optional[int] = None
    mch_id: Optional[str] = Field(None, max_length=64)
    api_key: Optional[str] = Field(None, max_length=128)
    cert_path: Optional[str] = Field(None, max_length=256)
    notify_url: Optional[str] = Field(None, max_length=256)
    withdraw_rate: Optional[Decimal] = None
    withdraw_min: Optional[Decimal] = None
    withdraw_fixed_fee: Optional[Decimal] = None
    status: Optional[bool] = None
    remark: Optional[str] = Field(None, max_length=512)


class PayConfigResponse(BaseModel):
    id: int
    pay_type: int
    mch_id: str
    api_key: str
    cert_path: str
    notify_url: str
    withdraw_rate: Decimal
    withdraw_min: Decimal
    withdraw_fixed_fee: Decimal
    status: bool
    remark: str
    create_time: str
    update_time: str

    class Config:
        from_attributes = True


class CloudConfigCreate(BaseModel):
    config_name: str = Field(..., max_length=128)
    cdn_domain: str = Field(default="", max_length=256)
    obs_bucket: str = Field(default="", max_length=128)
    obs_endpoint: str = Field(default="", max_length=256)
    access_key: str = Field(default="", max_length=256)
    secret_key: str = Field(default="", max_length=256)
    status: bool = Field(default=True)
    remark: str = Field(default="", max_length=512)


class CloudConfigUpdate(BaseModel):
    config_name: Optional[str] = Field(None, max_length=128)
    cdn_domain: Optional[str] = Field(None, max_length=256)
    obs_bucket: Optional[str] = Field(None, max_length=128)
    obs_endpoint: Optional[str] = Field(None, max_length=256)
    access_key: Optional[str] = Field(None, max_length=256)
    secret_key: Optional[str] = Field(None, max_length=256)
    status: Optional[bool] = None
    remark: Optional[str] = Field(None, max_length=512)


class CloudConfigResponse(BaseModel):
    id: int
    config_name: str
    cdn_domain: str
    obs_bucket: str
    obs_endpoint: str
    access_key: str
    secret_key: str
    status: bool
    remark: str
    create_time: str
    update_time: str

    class Config:
        from_attributes = True


class ChannelMappingCreate(BaseModel):
    channel_code: str = Field(..., max_length=32)
    third_field: str = Field(..., max_length=64)
    system_field: str = Field(..., max_length=64)
    field_desc: str = Field(default="", max_length=128)
    status: bool = Field(default=True)
    sort_num: int = Field(default=0)
    remark: str = Field(default="", max_length=512)


class ChannelMappingUpdate(BaseModel):
    third_field: Optional[str] = Field(None, max_length=64)
    system_field: Optional[str] = Field(None, max_length=64)
    field_desc: Optional[str] = Field(None, max_length=128)
    status: Optional[bool] = None
    sort_num: Optional[int] = None
    remark: Optional[str] = Field(None, max_length=512)


class ChannelMappingResponse(BaseModel):
    id: int
    channel_code: str
    third_field: str
    system_field: str
    field_desc: str
    status: bool
    sort_num: int
    remark: str
    create_time: str
    update_time: str

    class Config:
        from_attributes = True


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class PageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list
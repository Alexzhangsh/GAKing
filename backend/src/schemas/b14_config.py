# @ai-generated
"""
B14 系统配置管理 Schema（动态配置热生效模块）
新建独立文件，不修改 B01-B13 任何基线 schema

字段说明：
- config_key 必须在 B14_CONFIG_REGISTRY 注册表内才能创建/更新（白名单约束）
- config_value 统一字符串存储，读取时由 B14ConfigUtil.get_int/get_bool/get_decimal 按类型转换
- 批量更新仅允许 task_*_enable 类开关配置（BATCH_UPDATE_KEY_PREFIX）
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class SystemConfigCreateRequest(BaseModel):
    """系统配置新增请求体（仅 B14_CONFIG_REGISTRY 内的 key 允许创建）"""

    config_key: str = Field(..., min_length=1, max_length=64, description="配置唯一键名")
    config_value: str = Field(..., min_length=1, max_length=2000, description="配置值")
    config_name: str = Field(default="", max_length=128, description="配置中文名称")
    remark: str = Field(default="", max_length=512, description="配置说明备注")


class SystemConfigUpdateRequest(BaseModel):
    """系统配置更新请求体（仅允许更新 value/name/remark，不允许改 key）"""

    config_value: str = Field(..., min_length=1, max_length=2000, description="配置值")
    config_name: Optional[str] = Field(default=None, max_length=128, description="配置中文名称")
    remark: Optional[str] = Field(default=None, max_length=512, description="配置说明备注")


class SystemConfigBatchUpdateItem(BaseModel):
    """批量更新单项"""

    config_key: str = Field(..., min_length=1, max_length=64, description="配置键")
    config_value: str = Field(..., min_length=1, max_length=2000, description="配置值")


class SystemConfigBatchUpdateRequest(BaseModel):
    """系统配置批量更新请求体（仅允许 task_*_enable 类开关）"""

    items: List[SystemConfigBatchUpdateItem] = Field(
        ..., min_length=1, max_length=20, description="批量更新项列表"
    )


class SystemConfigResponse(BaseModel):
    """系统配置响应体（DB 视角）"""

    id: int = Field(..., description="主键ID")
    config_key: str = Field(..., description="配置唯一键名")
    config_value: str = Field(..., description="配置值")
    config_name: str = Field(..., description="配置中文名称")
    remark: str = Field(..., description="配置说明备注")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")

    class Config:
        from_attributes = True


class SystemConfigRegistryItem(BaseModel):
    """配置注册表项（含元信息 + 当前值）"""

    config_key: str = Field(..., description="配置键")
    config_type: str = Field(..., description="配置类型：int/bool/str/decimal/json")
    default_value: Any = Field(..., description="注册表默认值")
    current_value: Any = Field(..., description="当前生效值（DB 或默认）")
    min_value: Optional[Any] = Field(default=None, description="最小值（int/decimal 类型）")
    max_value: Optional[Any] = Field(default=None, description="最大值（int/decimal 类型）")
    desc: str = Field(default="", description="配置说明")
    config_name: str = Field(default="", description="配置中文名称（DB 存在时）")


class SystemConfigListResponse(BaseModel):
    """系统配置分页列表响应体"""

    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: List[SystemConfigResponse] = Field(default_factory=list, description="配置列表")


class SystemConfigBatchUpdateResponse(BaseModel):
    """批量更新响应体"""

    updated: List[str] = Field(default_factory=list, description="成功更新的 key 列表")
    skipped: List[str] = Field(default_factory=list, description="跳过的 key 列表（不在白名单）")
    failed: List[str] = Field(default_factory=list, description="失败的 key 列表")


class ConfigCacheRefreshResponse(BaseModel):
    """配置缓存刷新响应体"""

    success: bool = Field(..., description="是否刷新成功")
    loaded_count: int = Field(..., description="加载的配置项数量")
    message: str = Field(default="", description="附加消息")


class ConfigValidateRequest(BaseModel):
    """配置值校验请求体（更新前预校验）"""

    config_key: str = Field(..., min_length=1, max_length=64, description="配置键")
    config_value: str = Field(..., min_length=1, max_length=2000, description="待校验配置值")


class ConfigValidateResponse(BaseModel):
    """配置值校验响应体"""

    valid: bool = Field(..., description="是否合法")
    parsed_value: Optional[Any] = Field(default=None, description="解析后的值")
    error_message: Optional[str] = Field(default=None, description="校验失败原因")

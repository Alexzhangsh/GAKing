# @ai-generated
"""
OBS/CDN 云资源配置表 ORM 模型
表名：gaking_cloud_config
业务说明：存储华为云 OBS 桶、CDN 域名、AK/SK 等云资源配置
"""
from sqlalchemy import Column, String, Boolean, UniqueConstraint

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class CloudConfig(Base, SerializableMixin, SoftDeleteMixin):
    """OBS/CDN 云资源配置表"""

    __tablename__ = "gaking_cloud_config"
    __table_args__ = (
        # config_name 唯一索引 —— 配置名称不重复
        UniqueConstraint("config_name", name="uk_config_name"),
        {"comment": "云资源CDN配置表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 配置名称，如 "prod-obs" / "dev-cdn"
    config_name = Column(String(128), nullable=False, comment="配置名称")
    # 华为云 OBS 桶名
    obs_bucket = Column(String(128), default="", comment="华为OBS桶名")
    # OBS 终端地址
    obs_endpoint = Column(String(256), default="", comment="OBS终端地址")
    # 云存储 AK 密钥
    access_key = Column(String(256), default="", comment="云存储AK密钥")
    # 云存储 SK 密钥
    secret_key = Column(String(256), default="", comment="云存储SK密钥")
    # CDN 根域名
    cdn_domain = Column(String(256), default="", comment="CDN根域名")
    # 状态：True-启用 False-禁用
    status = Column(Boolean, default=True, nullable=False, comment="状态：0-禁用 1-启用")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")

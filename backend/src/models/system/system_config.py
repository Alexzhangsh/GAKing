# @ai-generated
"""
全局系统配置表 ORM 模型
表名：gaking_system_config
业务说明：存储全局开关、系统参数（分润比例、过期天数、限流阈值等）
"""
from sqlalchemy import Column, String, Text, UniqueConstraint

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class SystemConfig(Base, SerializableMixin, SoftDeleteMixin):
    """全局系统配置表"""

    __tablename__ = "gaking_system_config"
    __table_args__ = (
        # config_key 唯一索引 —— 保证配置键不重复
        UniqueConstraint("config_key", name="uk_config_key"),
        {"comment": "系统全局配置表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 配置唯一键名，如 risk_hold_ratio / settle_cool_day / rate_limit_search
    config_key = Column(String(64), nullable=False, comment="配置唯一键名")
    # 配置值，支持文本、数字、JSON 格式
    config_value = Column(Text, nullable=False, comment="配置值，支持文本、数字、JSON")
    # 配置中文名称，用于后台展示
    config_name = Column(String(128), nullable=False, default="", comment="配置中文名称")
    # 配置说明备注
    remark = Column(String(512), default="", comment="配置说明备注")

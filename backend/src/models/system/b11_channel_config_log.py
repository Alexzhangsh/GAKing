# @ai-generated
"""
B11-1 渠道配置变更日志 ORM 模型
表名：gaking_channel_config_log
业务说明：记录渠道佣金比例、黑名单等配置的变更历史，用于审计追溯
"""
from sqlalchemy import Column, String, BigInteger, SmallInteger, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelConfigLog(Base, SerializableMixin, SoftDeleteMixin):
    """渠道配置变更日志表"""

    __tablename__ = "gaking_channel_config_log"
    __table_args__ = (
        Index("idx_ccl_channel_code", "channel_code"),
        Index("idx_ccl_operation_type", "operation_type"),
        Index("idx_ccl_operator", "operator_id"),
        Index("idx_ccl_create_time", "create_time"),
        Index("idx_ccl_channel_op", "channel_code", "operation_type"),
        {"comment": "渠道配置变更日志表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道标识
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq/orderx")
    # 配置键名
    config_key = Column(String(64), nullable=False, default="", comment="配置键名")
    # 变更前值
    old_value = Column(String(512), default="", comment="变更前值")
    # 变更前值中文描述
    old_value_label = Column(String(256), default="", comment="变更前值中文描述")
    # 变更后值
    new_value = Column(String(512), default="", comment="变更后值")
    # 变更后值中文描述
    new_value_label = Column(String(256), default="", comment="变更后值中文描述")
    # 操作人ID
    operator_id = Column(BigInteger, default=0, comment="操作人ID")
    # 操作人名称
    operator_name = Column(String(64), default="", comment="操作人名称")
    # 操作类型：blacklist_add/blacklist_remove/commission_config 等
    operation_type = Column(String(32), nullable=False, default="", comment="操作类型")
    # 备注
    remark = Column(Text, default="", comment="备注")
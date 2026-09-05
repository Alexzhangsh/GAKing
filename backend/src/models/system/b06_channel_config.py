# @ai-generated
"""
B06 渠道佣金比例配置表 ORM 模型
表名：gaking_channel_commission_config
业务说明：存储各渠道下不同用户类型（普通用户/付费会员）的佣金分润比例，
用户返利比例 + 平台留存比例 = 100%，后台配置做总和校验
"""
from sqlalchemy import Column, Integer, String, Numeric, UniqueConstraint, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelCommissionConfig(Base, SerializableMixin, SoftDeleteMixin):
    """渠道佣金比例配置表"""

    __tablename__ = "gaking_channel_commission_config"
    __table_args__ = (
        UniqueConstraint("channel_code", "user_type", name="uk_channel_user_type"),
        Index("idx_channel_code", "channel_code"),
        {"comment": "渠道佣金比例配置表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道标识：myq-喵有券 / orderx-订单侠
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠")
    # 用户类型：1-普通用户 2-付费会员
    user_type = Column(Integer, nullable=False, comment="用户类型：1-普通用户 2-付费会员")
    # 用户返利比例（0~1），如 0.50 表示用户获得 50%
    user_commission_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="用户返利比例(0~1)")
    # 平台留存比例（0~1），如 0.50 表示平台留存 50%
    platform_retention_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="平台留存比例(0~1)")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")
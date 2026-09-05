# @ai-generated
"""
B11-1 渠道黑名单 ORM 模型
表名：gaking_channel_blacklist
业务说明：渠道黑名单管理，支持按用户/IP/订单维度进行黑名单控制
"""
from sqlalchemy import Column, Integer, String, BigInteger, SmallInteger, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelBlacklist(Base, SerializableMixin, SoftDeleteMixin):
    """渠道黑名单表"""

    __tablename__ = "gaking_channel_blacklist"
    __table_args__ = (
        Index("idx_cb_channel_code", "channel_code"),
        Index("idx_cb_blacklist_type", "blacklist_type"),
        Index("idx_cb_blacklist_value", "blacklist_value"),
        Index("idx_cb_channel_type", "channel_code", "blacklist_type"),
        Index("idx_cb_status", "status"),
        {"comment": "渠道黑名单表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道标识：myq-喵有券 / orderx-订单侠
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq/orderx")
    # 黑名单类型：user-用户黑名单 ip-IP黑名单 order-订单黑名单
    blacklist_type = Column(String(32), nullable=False, comment="黑名单类型：user/ip/order")
    # 黑名单值（用户ID/IP地址/订单号）
    blacklist_value = Column(String(128), nullable=False, comment="黑名单值（用户ID/IP地址/订单号）")
    # 拉黑原因
    reason = Column(String(512), default="", comment="拉黑原因")
    # 状态：0-禁用 1-启用
    status = Column(SmallInteger, nullable=False, default=1, comment="状态：0-禁用 1-启用")
    # 操作人ID
    operator_id = Column(BigInteger, default=0, comment="操作人ID")
    # 操作人名称
    operator_name = Column(String(64), default="", comment="操作人名称")
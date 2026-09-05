# @ai-generated
"""
点击行为日志表 ORM 模型
表名：click_log
业务说明：用户访问短链落地时持久化的点击行为日志
用于 CPS 跟单：订单匹配时回查 72h 窗口内的点击记录
"""
from datetime import datetime

from sqlalchemy import (
    Column, String, BigInteger, DateTime, Index
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ClickLog(Base, SerializableMixin, SoftDeleteMixin):
    """点击行为日志表"""

    __tablename__ = "click_log"
    __table_args__ = (
        Index("idx_short_key", "short_key"),
        Index("idx_user_id", "user_id"),
        Index("idx_goods_id", "goods_id"),
        Index("idx_access_time", "access_time"),
        Index("idx_goods_access", "goods_id", "access_time"),
        {"comment": "点击行为日志表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 关联短链 key
    short_key = Column(String(32), nullable=False, comment="关联短链key")
    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 商品ID
    goods_id = Column(String(128), nullable=False, comment="商品ID")
    # 商品标题
    goods_title = Column(String(256), default="", comment="商品标题")
    # 来源渠道
    source_channel = Column(String(32), default="", comment="来源渠道")
    # User-Agent
    user_agent = Column(String(512), default="", comment="User-Agent")
    # IP 地址
    ip_address = Column(String(64), default="", comment="IP地址")
    # 来源 URL
    referer_url = Column(String(1024), default="", comment="来源URL")
    # 访问时间
    access_time = Column(DateTime, nullable=False, comment="访问时间")
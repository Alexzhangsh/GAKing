# @ai-generated
"""
短链映射表 ORM 模型
表名：short_link
业务说明：平台中转短链，短链 key 映射内部 user_id、goods_id、创建时间
用于 CPS 跟单：用户点击短链→记录行为→订单匹配时回查归属
"""
from datetime import datetime

from sqlalchemy import (
    Column, String, BigInteger, Integer, DateTime, Text, Index
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ShortLink(Base, SerializableMixin, SoftDeleteMixin):
    """短链映射表"""

    __tablename__ = "short_link"
    __table_args__ = (
        Index("idx_short_key", "short_key", unique=True),
        Index("idx_user_id", "user_id"),
        Index("idx_goods_id", "goods_id"),
        Index("idx_expire_at", "expire_at"),
        {"comment": "短链映射表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 短链唯一标识（base62 编码）
    short_key = Column(String(32), nullable=False, unique=True, comment="短链唯一标识")
    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 商品ID
    goods_id = Column(String(128), nullable=False, comment="商品ID")
    # 商品标题
    goods_title = Column(String(256), default="", comment="商品标题")
    # 渠道标识：myq/orderx/dta
    channel_code = Column(String(32), default="", comment="渠道标识")
    # 原始 CPS 推广链接
    source_url = Column(Text, default="", comment="原始CPS推广链接")
    # 过期时间（生成时间 + 72h）
    expire_at = Column(DateTime, nullable=False, comment="过期时间")
    # 累计点击次数
    click_count = Column(Integer, default=0, comment="累计点击次数")
    # 最后点击时间
    last_click_at = Column(DateTime, nullable=True, comment="最后点击时间")
# @ai-generated
"""
CPS 渠道配置表 ORM 模型
表名：gaking_channel_mapping
业务说明：存储喵有券(myq)/订单侠(orderx)两大 CPS 渠道的 API Token、
密钥、推广位PID、结算比例等配置
"""
from sqlalchemy import Column, String, Boolean, Numeric, UniqueConstraint

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelMapping(Base, SerializableMixin, SoftDeleteMixin):
    """CPS 渠道配置表"""

    __tablename__ = "gaking_channel_mapping"
    __table_args__ = (
        # channel_code 唯一索引 —— 渠道标识不重复
        UniqueConstraint("channel_code", name="uk_channel_code"),
        {"comment": "CPS渠道配置表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道标识：myq-喵有券 / orderx-订单侠
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠")
    # 渠道中文名称
    channel_name = Column(String(64), default="", comment="渠道中文名称")
    # 渠道 API Token
    api_token = Column(String(256), default="", comment="渠道API Token")
    # 渠道 API 密钥（用于签名校验）
    api_secret = Column(String(256), default="", comment="渠道API密钥，用于签名校验")
    # 渠道推广位 PID
    pid = Column(String(64), default="", comment="渠道推广位PID")
    # 结算比例（0~1），如 0.80 表示渠道结算 80%
    settle_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="结算比例(0~1)，如0.80")
    # 状态：True-启用 False-禁用
    status = Column(Boolean, default=True, nullable=False, comment="状态：0-禁用 1-启用")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")

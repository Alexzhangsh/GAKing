# @ai-generated
"""
B11-1 渠道每日统计 ORM 模型
表名：gaking_channel_daily_stat
业务说明：按渠道+日期维度聚合的订单统计数据，每日定时任务生成
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, UniqueConstraint, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelDailyStat(Base, SerializableMixin, SoftDeleteMixin):
    """渠道每日统计表"""

    __tablename__ = "gaking_channel_daily_stat"
    __table_args__ = (
        UniqueConstraint("stat_date", "channel_code", name="uk_stat_date_channel"),
        Index("idx_cds_channel_code", "channel_code"),
        Index("idx_cds_stat_date", "stat_date"),
        Index("idx_cds_channel_date", "channel_code", "stat_date"),
        {"comment": "渠道每日统计表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 统计日期
    stat_date = Column(Date, nullable=False, comment="统计日期")
    # 渠道标识
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq/orderx")
    # 订单总数
    order_count = Column(Integer, default=0, nullable=False, comment="订单总数")
    # 支付总金额（元）
    total_pay_amount = Column(Numeric(14, 2), default=0.00, nullable=False, comment="支付总金额(元)")
    # 总佣金（元）
    total_commission = Column(Numeric(14, 2), default=0.00, nullable=False, comment="总佣金(元)")
    # 用户佣金（元）
    user_commission = Column(Numeric(14, 2), default=0.00, nullable=False, comment="用户佣金(元)")
    # 平台佣金（元）
    platform_commission = Column(Numeric(14, 2), default=0.00, nullable=False, comment="平台佣金(元)")
    # 已结算订单数
    settled_count = Column(Integer, default=0, nullable=False, comment="已结算订单数")
    # 退款订单数
    refund_count = Column(Integer, default=0, nullable=False, comment="退款订单数")
    # 退款金额（元）
    refund_amount = Column(Numeric(14, 2), default=0.00, nullable=False, comment="退款金额(元)")
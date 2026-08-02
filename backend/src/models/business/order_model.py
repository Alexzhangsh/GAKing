# @ai-generated
"""
导购订单主表 ORM 模型
表名：orders
业务说明：CPS 导购订单核心主表，记录用户下单、佣金拆分、转账状态全链路数据
订单状态机：待付款(10) → 已付款(30) → 已结算(40) → 失效(50)
"""
from datetime import datetime

from sqlalchemy import Column, String, BigInteger, Integer, Numeric, DateTime, Index
from sqlalchemy.orm import relationship

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class Order(Base, SerializableMixin, SoftDeleteMixin):
    """导购订单主表"""

    __tablename__ = "orders"
    __table_args__ = (
        # user_id 单值索引 —— 高频按用户查询订单
        Index("idx_user_id", "user_id"),
        # out_order_no 唯一索引 —— 渠道订单号防重
        Index("idx_out_order_no", "out_order_no", unique=True),
        # internal_order_no 唯一索引 —— 平台单号防重
        Index("idx_internal_order_no", "internal_order_no", unique=True),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_create_time", "create_time"),
        # order_status 单值索引 —— 按状态批量查询
        Index("idx_order_status", "order_status"),
        # 联合索引 —— 用户+状态高频联查
        Index("idx_user_status", "user_id", "order_status"),
        {"comment": "导购订单主表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 渠道订单号（CPS渠道返回的订单号）
    out_order_no = Column(String(64), nullable=False, comment="渠道订单号")
    # 平台内部订单号（GAK前缀）
    internal_order_no = Column(String(64), nullable=False, comment="平台内部订单号")
    # 商品标题
    goods_title = Column(String(256), default="", comment="商品标题")
    # 商品主图URL
    goods_img = Column(String(512), default="", comment="商品主图URL")
    # 支付金额（元）
    pay_amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="支付金额(元)")
    # 总佣金（渠道返回的结算佣金）
    total_commission = Column(Numeric(10, 2), default=0.00, nullable=False, comment="总佣金(元)")
    # 用户佣金（80%分成）
    user_commission = Column(Numeric(10, 2), default=0.00, nullable=False, comment="用户佣金(元)")
    # 平台佣金（20%抽成）
    platform_commission = Column(Numeric(10, 2), default=0.00, nullable=False, comment="平台佣金(元)")
    # 渠道标识：myq-喵有券 / orderx-订单侠
    channel_code = Column(String(32), default="", comment="渠道标识：myq/orderx")
    # 订单状态：10-待付款 30-已付款 40-已结算 50-失效
    order_status = Column(Integer, default=10, nullable=False, comment="订单状态：10-待付款 30-已付款 40-已结算 50-失效")
    # 支付时间
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    # 结算时间
    settle_time = Column(DateTime, nullable=True, comment="结算时间")
    # 微信转账批次ID
    wx_batch_id = Column(String(64), default="", comment="微信转账批次ID")
    # 转账状态：PENDING/PROCESSING/SUCCESS/FAILED
    transfer_status = Column(String(32), default="PENDING", nullable=False, comment="转账状态：PENDING/PROCESSING/SUCCESS/FAILED")

    # 一对多关系：订单 → 佣金流水
    commission_flows = relationship("CommissionFlow", back_populates="order", lazy="select")

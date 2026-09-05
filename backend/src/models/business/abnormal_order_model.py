# @ai-generated
"""
异常订单表 ORM 模型
表名：abnormal_order
业务说明：CPS 跟单无法归属用户的异常订单，供运营人工复核
异常原因：72h 窗口内无匹配点击记录 / 多用户冲突待确认 等
"""
from datetime import datetime

from sqlalchemy import (
    Column, String, BigInteger, Integer, Numeric, DateTime, Text, Index
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class AbnormalOrder(Base, SerializableMixin, SoftDeleteMixin):
    """异常订单表"""

    __tablename__ = "abnormal_order"
    __table_args__ = (
        Index("idx_out_order_no", "out_order_no", unique=True),
        Index("idx_review_status", "review_status"),
        Index("idx_channel_code", "channel_code"),
        Index("idx_create_time", "create_time"),
        Index("idx_goods_id", "goods_id"),
        {"comment": "异常订单表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道订单号（唯一）
    out_order_no = Column(String(64), nullable=False, unique=True, comment="渠道订单号")
    # 渠道标识：myq/orderx/dta
    channel_code = Column(String(32), default="", comment="渠道标识")
    # 原始订单数据（完整 JSON）
    order_data = Column(Text, default="", comment="原始订单数据JSON")
    # 商品ID
    goods_id = Column(String(128), default="", comment="商品ID")
    # 商品标题
    goods_title = Column(String(256), default="", comment="商品标题")
    # 支付金额（元）
    pay_amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="支付金额(元)")
    # 总佣金（元）
    total_commission = Column(Numeric(10, 2), default=0.00, nullable=False, comment="总佣金(元)")
    # 渠道原始状态
    order_status = Column(String(32), default="", comment="渠道原始状态")
    # 支付时间
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    # 异常原因
    abnormal_reason = Column(String(512), default="", comment="异常原因")
    # 最近匹配的短链key（匹配失败时记录）
    matched_click_key = Column(String(32), default="", comment="最近匹配短链key")
    # 可能存在但无法确认的用户ID
    matched_user_id = Column(BigInteger, default=0, comment="可能匹配的用户ID")
    # 复核指定归属用户ID（>0 表示人工指定了归属）
    assigned_user_id = Column(BigInteger, default=0, comment="复核指定归属用户ID")
    # 复核状态：PENDING-待审核 / REVIEWED-已复核 / IGNORED-已忽略
    review_status = Column(String(32), default="PENDING", nullable=False, comment="复核状态")
    # 复核备注
    review_remark = Column(String(512), default="", comment="复核备注")
    # 复核人管理员ID
    reviewed_by = Column(BigInteger, default=0, comment="复核人管理员ID")
    # 复核时间
    reviewed_at = Column(DateTime, nullable=True, comment="复核时间")
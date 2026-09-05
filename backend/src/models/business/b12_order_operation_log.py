# @ai-generated
"""
B12-1 订单操作日志 ORM 模型
表名：gaking_order_operation_log
业务说明：记录订单状态变更全生命周期，包含状态流转前后值、操作人、操作类型、操作原因
"""
from sqlalchemy import Column, String, BigInteger, SmallInteger, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class OrderOperationLog(Base, SerializableMixin, SoftDeleteMixin):
    """订单操作日志表"""

    __tablename__ = "gaking_order_operation_log"
    __table_args__ = (
        Index("idx_ool_order_id", "order_id"),
        Index("idx_ool_order_status", "order_status_from", "order_status_to"),
        Index("idx_ool_operation_type", "operation_type"),
        Index("idx_ool_operator", "operator_id"),
        Index("idx_ool_create_time", "create_time"),
        Index("idx_ool_order_time", "order_id", "create_time"),
        {"comment": "订单操作日志表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 订单ID
    order_id = Column(BigInteger, nullable=False, comment="订单ID")
    # 渠道订单号（冗余，方便快速定位）
    out_order_no = Column(String(64), default="", comment="渠道订单号")
    # 平台内部订单号（冗余）
    internal_order_no = Column(String(64), default="", comment="平台内部订单号")
    # 操作前状态
    order_status_from = Column(SmallInteger, default=0, comment="操作前状态")
    # 操作后状态
    order_status_to = Column(SmallInteger, default=0, comment="操作后状态")
    # 操作前状态中文描述
    status_from_label = Column(String(32), default="", comment="操作前状态中文描述")
    # 操作后状态中文描述
    status_to_label = Column(String(32), default="", comment="操作后状态中文描述")
    # 操作类型：status_transition/manual_override/sync_update/anomaly_mark 等
    operation_type = Column(String(32), nullable=False, default="", comment="操作类型")
    # 操作人ID（0=系统自动）
    operator_id = Column(BigInteger, default=0, comment="操作人ID（0=系统自动）")
    # 操作人名称
    operator_name = Column(String(64), default="", comment="操作人名称")
    # 操作原因/备注
    remark = Column(Text, default="", comment="操作原因/备注")
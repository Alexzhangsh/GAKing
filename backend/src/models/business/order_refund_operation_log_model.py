# @ai-generated
"""
退款操作日志 ORM 模型（B05-6 新建）
表名：order_refund_operation_log
业务说明：记录退款订单逆向冲减佣金的每次操作流水，包括操作人、变更前后余额、状态等
"""
from sqlalchemy import Column, String, BigInteger, Numeric, Integer, Text, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class OrderRefundOperationLog(Base, SerializableMixin, SoftDeleteMixin):
    """退款操作日志表"""

    __tablename__ = "order_refund_operation_log"
    __table_args__ = (
        # order_id 单值索引 —— 按订单查询退款操作历史
        Index("idx_rol_order_id", "order_id"),
        # operator_id 单值索引 —— 按操作人筛选
        Index("idx_rol_operator_id", "operator_id"),
        # operation_type 单值索引 —— 按操作类型筛选
        Index("idx_rol_operation_type", "operation_type"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_rol_create_time", "create_time"),
        {
            "comment": "退款操作日志表（B05-6）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联订单ID
    order_id = Column(BigInteger, nullable=False, comment="关联订单ID")
    # 操作人管理员ID
    operator_id = Column(BigInteger, nullable=False, comment="操作人管理员ID")
    # 操作类型：DEDUCT-退款冲减
    operation_type = Column(String(32), nullable=False, comment="操作类型：DEDUCT-退款冲减")
    # 变更前订单状态
    order_status_before = Column(Integer, nullable=False, comment="变更前订单状态")
    # 变更后订单状态
    order_status_after = Column(Integer, nullable=False, comment="变更后订单状态")
    # 扣减金额（元）
    deduct_amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="扣减金额(元)")
    # 原始流水类型：ORDER/SUPPLEMENT
    flow_type = Column(String(32), default="", nullable=False, comment="原始流水类型：ORDER/SUPPLEMENT")
    # 原始流水转账状态：PENDING/SUCCESS
    flow_transfer_status = Column(String(32), default="", nullable=False, comment="原始流水转账状态：PENDING/SUCCESS")
    # 变更前可用余额（元）
    old_available_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更前可用余额(元)")
    # 变更后可用余额（元）
    new_available_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更后可用余额(元)")
    # 变更前累计佣金（元）
    old_total_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更前累计佣金(元)")
    # 变更后累计佣金（元）
    new_total_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更后累计佣金(元)")
    # 关联扣减流水ID（commission_flow.id）
    deduct_flow_id = Column(BigInteger, nullable=True, comment="关联扣减流水ID(commission_flow.id)")
    # 备注说明
    remark = Column(Text, default="", comment="备注说明")
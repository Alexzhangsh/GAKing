# @ai-generated
"""
佣金发放流水明细表 ORM 模型
表名：commission_flow
业务说明：记录每笔佣金的发放流水，与 orders 表一对多关联
流水类型：订单佣金/补发/扣减
外键约束：order_id ON DELETE SET NULL（订单删除时流水保留，order_id 置空）
"""
from sqlalchemy import Column, String, BigInteger, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class CommissionFlow(Base, SerializableMixin, SoftDeleteMixin):
    """佣金发放流水明细表"""

    __tablename__ = "commission_flow"
    __table_args__ = (
        # order_id 单值索引 —— 按订单查询流水
        Index("idx_order_id", "order_id"),
        # user_id 单值索引 —— 按用户查询流水
        Index("idx_user_id", "user_id"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_create_time", "create_time"),
        # 联合索引 —— 用户+流水类型高频联查
        Index("idx_user_flow_type", "user_id", "flow_type"),
        {"comment": "佣金发放流水明细表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 关联订单ID，外键指向 orders.id，ON DELETE SET NULL
    order_id = Column(
        BigInteger,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联订单ID",
    )
    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 流水类型：ORDER-订单佣金 / SUPPLEMENT-补发 / DEDUCT-扣减
    flow_type = Column(String(32), nullable=False, comment="流水类型：ORDER-订单佣金/SUPPLEMENT-补发/DEDUCT-扣减")
    # 流水金额（元）
    amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="流水金额(元)")
    # 变更前余额（元）
    before_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更前余额(元)")
    # 变更后余额（元）
    after_balance = Column(Numeric(10, 2), default=0.00, nullable=False, comment="变更后余额(元)")
    # 微信转账批次ID
    transfer_batch_id = Column(String(64), default="", comment="微信转账批次ID")
    # 转账状态：PENDING/PROCESSING/SUCCESS/FAILED
    transfer_status = Column(String(32), default="PENDING", nullable=False, comment="转账状态：PENDING/PROCESSING/SUCCESS/FAILED")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")

    # 一对多关系：佣金流水 → 订单
    order = relationship("Order", back_populates="commission_flows", lazy="select")

# @ai-generated
"""
佣金结算操作日志 ORM 模型（B12 新建）
表名：settlement_operation_log
业务说明：记录结算单每次状态变更的操作流水，供后台审计追溯
"""
from sqlalchemy import Column, String, BigInteger, Numeric, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class SettlementOperationLog(Base, SerializableMixin, SoftDeleteMixin):
    """佣金结算操作日志表"""

    __tablename__ = "settlement_operation_log"
    __table_args__ = (
        # settlement_id 单值索引 —— 按结算单查询操作历史
        Index("idx_sol_settlement_id", "settlement_id"),
        # order_id 单值索引 —— 按订单查询操作历史
        Index("idx_sol_order_id", "order_id"),
        # action 单值索引 —— 按操作类型筛选
        Index("idx_sol_action", "action"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_sol_create_time", "create_time"),
        {
            "comment": "佣金结算操作日志表（B12）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联结算单ID（逻辑关联 settlement_record.id）
    settlement_id = Column(BigInteger, nullable=False, comment="关联结算单ID")
    # 关联订单ID（冗余，便于按订单查询）
    order_id = Column(BigInteger, nullable=False, comment="关联订单ID")
    # 变更前状态
    from_status = Column(String(32), nullable=False, comment="变更前状态")
    # 变更后状态
    to_status = Column(String(32), nullable=False, comment="变更后状态")
    # 操作类型：CREATE_SETTLEMENT/FREEZE/UNFREEZE/MARK_PAID
    action = Column(String(32), nullable=False, comment="操作类型")
    # 操作人ID（后台管理员；定时任务触发时为空）
    operator_id = Column(BigInteger, nullable=True, comment="操作人ID")
    # 涉及金额（冻结/解冻的金额）
    amount = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="涉及金额(元)"
    )
    # 关联佣金流水ID（操作产生的 commission_flow.id）
    flow_id = Column(BigInteger, nullable=True, comment="关联佣金流水ID")
    # 操作备注
    remark = Column(Text, default="", comment="操作备注")

# @ai-generated
"""
B08-1 资金流水记录表 ORM 模型
表名：gaking_fund_flow
业务说明：记录用户佣金账户每笔余额变动的详细流水（入账/扣款/冻结/解冻/提现/退款冲减等）
每笔流水记录变动前后的可用余额与冻结余额快照，支持全链路资金追溯。
"""
from sqlalchemy import Column, String, BigInteger, Integer, Numeric, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class FundFlow(Base, SerializableMixin, SoftDeleteMixin):
    """资金流水记录表"""

    __tablename__ = "gaking_fund_flow"
    __table_args__ = (
        # user_id 单值索引 —— 按用户查询资金流水
        Index("idx_user_id", "user_id"),
        # flow_type 单值索引 —— 按类型统计
        Index("idx_flow_type", "flow_type"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_create_time", "create_time"),
        # biz_id 唯一索引 —— 按业务流水号查询（幂等防重复）
        Index("idx_biz_id", "biz_id", unique=True),
        # 联合索引 —— 用户+类型+时间高频查询
        Index("idx_user_type_time", "user_id", "flow_type", "create_time"),
        {"comment": "资金流水记录表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 流水类型：DEPOSIT/DEDUCT/FREEZE/UNFREEZE/WITHDRAW_APPLY/WITHDRAW_REJECT/WITHDRAW_SUCCESS/REFUND_DEDUCT/MANUAL_ADJUST/SETTLEMENT
    flow_type = Column(String(32), nullable=False, comment="流水类型")
    # 变动金额（元，正数为增加，负数为减少）
    amount = Column(Numeric(10, 2), nullable=False, default=0.00, comment="变动金额(元)")
    # 变动前可用余额（元）
    before_balance = Column(Numeric(10, 2), nullable=False, default=0.00, comment="变动前可用余额(元)")
    # 变动后可用余额（元）
    after_balance = Column(Numeric(10, 2), nullable=False, default=0.00, comment="变动后可用余额(元)")
    # 变动前冻结余额（元）
    before_frozen = Column(Numeric(10, 2), nullable=False, default=0.00, comment="变动前冻结余额(元)")
    # 变动后冻结余额（元）
    after_frozen = Column(Numeric(10, 2), nullable=False, default=0.00, comment="变动后冻结余额(元)")
    # 关联订单ID（可选）
    order_id = Column(BigInteger, nullable=True, default=None, comment="关联订单ID")
    # 关联提现申请ID（可选）
    withdraw_apply_id = Column(BigInteger, nullable=True, default=None, comment="关联提现申请ID")
    # 业务流水号（唯一，用于幂等防重复入账）
    biz_id = Column(String(64), nullable=False, comment="业务流水号")
    # 备注
    remark = Column(String(512), default="", comment="备注")
    # 操作人ID
    operator_id = Column(BigInteger, nullable=False, default=0, comment="操作人ID")
    # 操作人姓名
    operator_name = Column(String(64), default="", comment="操作人姓名")
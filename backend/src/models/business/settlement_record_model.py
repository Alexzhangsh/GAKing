# @ai-generated
"""
佣金结算单 ORM 模型（B12 新建）
表名：settlement_record
业务说明：记录每笔订单的佣金结算全链路状态流转
状态机：ORDERED → SETTLABLE → SETTLED → PAID（严格不可回退）

业务语义（用户确认）：
- ORDERED：订单已下单，待确认收货
- SETTLABLE：已确认收货，渠道返佣未到账，平台已记冻结佣金（frozen += amount）
- SETTLED：渠道返利到账，冻结解冻转可用（frozen → available）
- PAID：用户提现成功（关联 WithdrawStatus.SUCCESS）
"""
from sqlalchemy import Column, String, BigInteger, Integer, Numeric, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class SettlementRecord(Base, SerializableMixin, SoftDeleteMixin):
    """佣金结算单表"""

    __tablename__ = "settlement_record"
    __table_args__ = (
        # settlement_no 唯一索引 —— 结算单号防重
        Index("idx_settlement_no", "settlement_no", unique=True),
        # order_id 单值索引 —— 按订单查询结算单
        Index("idx_sr_order_id", "order_id"),
        # user_id 单值索引 —— 按用户查询结算单
        Index("idx_sr_user_id", "user_id"),
        # settlement_status 单值索引 —— 按状态批量查询
        Index("idx_sr_status", "settlement_status"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_sr_create_time", "create_time"),
        {
            "comment": "佣金结算单表（B12）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 平台结算单号（GAKS 前缀 + 时间戳 + order_id）
    settlement_no = Column(String(64), nullable=False, comment="平台结算单号")
    # 关联订单ID（逻辑关联，非外键约束，避免跨模块强耦合）
    order_id = Column(BigInteger, nullable=False, comment="关联订单ID")
    # 用户ID
    user_id = Column(BigInteger, nullable=False, comment="用户ID")
    # 渠道标识：myq / orderx
    channel_code = Column(String(32), default="", nullable=False, comment="渠道标识")
    # 总佣金（渠道返回的结算佣金）
    total_commission = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="总佣金(元)"
    )
    # 用户佣金（80% 分成）
    user_commission = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="用户佣金(元)"
    )
    # 平台佣金（20% 抽成）
    platform_commission = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="平台佣金(元)"
    )
    # 结算单状态：ORDERED/SETTLABLE/SETTLED/PAID
    settlement_status = Column(
        String(32),
        default="ORDERED",
        nullable=False,
        comment="结算单状态：ORDERED/SETTLABLE/SETTLED/PAID",
    )
    # 关联佣金流水ID（commission_flow.id，冻结入账时写入）
    flow_id = Column(BigInteger, nullable=True, comment="关联佣金流水ID")
    # 确认收货时间（订单进入 SETTLABLE 的时间）
    confirm_time = Column(DateTime, nullable=True, comment="确认收货时间")
    # 渠道结算到账时间（订单进入 SETTLED 的时间）
    settle_time = Column(DateTime, nullable=True, comment="渠道结算到账时间")
    # 提现打款时间（结算单进入 PAID 的时间）
    paid_time = Column(DateTime, nullable=True, comment="提现打款时间")
    # 延迟天数配置快照（创建结算单时从配置读取）
    delay_days = Column(Integer, default=30, nullable=False, comment="延迟结算天数快照")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")

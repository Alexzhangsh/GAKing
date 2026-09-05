# @ai-generated
"""
全链路对账差异明细 ORM 模型（B13 新建）
表名：reconciliation_diff
业务说明：记录对账过程中发现的具体差异明细，支持人工复核调平
差异类型：订单↔结算/结算↔账户/账户↔提现/提现↔打款/单边账
"""
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Numeric,
    DateTime,
    Index,
    Text,
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ReconciliationDiff(Base, SerializableMixin, SoftDeleteMixin):
    """全链路对账差异明细表"""

    __tablename__ = "reconciliation_diff"
    __table_args__ = (
        # reconciliation_id 单值索引 —— 按对账批次查询差异
        Index("idx_rd_reconciliation_id", "reconciliation_id"),
        # order_id 单值索引 —— 按订单查询差异
        Index("idx_rd_order_id", "order_id"),
        # user_id 单值索引 —— 按用户查询差异
        Index("idx_rd_user_id", "user_id"),
        # diff_type 单值索引 —— 按差异类型筛选
        Index("idx_rd_diff_type", "diff_type"),
        # status 单值索引 —— 按复核状态筛选
        Index("idx_rd_status", "status"),
        # alert_level 单值索引 —— 按告警级别筛选
        Index("idx_rd_alert_level", "alert_level"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_rd_create_time", "create_time"),
        {
            "comment": "全链路对账差异明细表（B13）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联对账批次ID
    reconciliation_id = Column(BigInteger, nullable=False, comment="关联对账批次ID")
    # 渠道标识（B17 渠道对账差异）：myq/orderx，用户维度差异为空
    channel_code = Column(String(32), nullable=True, comment="渠道标识：myq/orderx")
    # 关联订单ID（单边账-提现时可为空）
    order_id = Column(BigInteger, nullable=True, comment="关联订单ID")
    # 关联用户ID
    user_id = Column(BigInteger, nullable=False, comment="关联用户ID")
    # 关联结算单ID
    settlement_id = Column(BigInteger, nullable=True, comment="关联结算单ID")
    # 关联提现申请ID
    withdraw_id = Column(BigInteger, nullable=True, comment="关联提现申请ID")
    # 差异类型：ORDER_SETTLEMENT_MISMATCH/SETTLEMENT_ACCOUNT_MISMATCH/
    #          ACCOUNT_WITHDRAW_MISMATCH/WITHDRAW_TRANSFER_MISMATCH/
    #          SINGLE_SIDE_ORDER/SINGLE_SIDE_SETTLEMENT/SINGLE_SIDE_WITHDRAW
    diff_type = Column(String(64), nullable=False, comment="差异类型")
    # 源端类型：ORDER/SETTLEMENT/ACCOUNT/WITHDRAW
    source_type = Column(String(32), nullable=False, comment="源端类型")
    # 目标端类型：ORDER/SETTLEMENT/ACCOUNT/WITHDRAW
    target_type = Column(String(32), nullable=False, comment="目标端类型")
    # 源端金额（元）
    source_amount = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="源端金额(元)"
    )
    # 目标端金额（元）
    target_amount = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="目标端金额(元)"
    )
    # 差异金额（元）= |source_amount - target_amount|
    diff_amount = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="差异金额(元)"
    )
    # 告警级别：INFO/WARNING/CRITICAL
    alert_level = Column(
        String(32),
        default="WARNING",
        nullable=False,
        comment="告警级别：INFO/WARNING/CRITICAL",
    )
    # 是否已推送告警
    alert_sent = Column(
        String(8), default="N", nullable=False, comment="是否已推送告警：Y/N"
    )
    # 复核状态：PENDING/REVIEWING/RESOLVED/IGNORED
    status = Column(
        String(32),
        default="PENDING",
        nullable=False,
        comment="复核状态：PENDING/REVIEWING/RESOLVED/IGNORED",
    )
    # 复核人ID
    review_user_id = Column(BigInteger, nullable=True, comment="复核人ID")
    # 复核备注（调平说明）
    review_remark = Column(String(512), default="", comment="复核备注（调平说明）")
    # 复核时间
    reviewed_at = Column(DateTime, nullable=True, comment="复核时间")
    # 差异详情描述
    remark = Column(Text, nullable=True, comment="差异详情描述")

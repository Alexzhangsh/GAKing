# @ai-generated
"""
全链路对账批次 ORM 模型（B13 新建）
表名：reconciliation_record
业务说明：记录每次对账批次的执行状态、四方汇总金额、差异数量
四方核对：订单原始佣金 ↔ B12结算入账 ↔ B08资产账户余额 ↔ B10微信打款流水
"""
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Integer,
    Numeric,
    DateTime,
    Date,
    Index,
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ReconciliationRecord(Base, SerializableMixin, SoftDeleteMixin):
    """全链路对账批次表"""

    __tablename__ = "reconciliation_record"
    __table_args__ = (
        # reconciliation_no 唯一索引 —— 对账批次号防重
        Index("idx_reconciliation_no", "reconciliation_no", unique=True),
        # reconcile_date 单值索引 —— 按对账日期查询
        Index("idx_rr_date", "reconcile_date"),
        # status 单值索引 —— 按状态筛选
        Index("idx_rr_status", "status"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_rr_create_time", "create_time"),
        {
            "comment": "全链路对账批次表（B13）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 对账批次号（GAKR 前缀 + 时间戳）
    reconciliation_no = Column(String(64), nullable=False, comment="对账批次号")
    # 对账日期（对账数据所属的自然日）
    reconcile_date = Column(Date, nullable=False, comment="对账日期")
    # 对账类型：DAILY-每日自动 / MANUAL-手动触发
    reconcile_type = Column(
        String(32), default="DAILY", nullable=False, comment="对账类型：DAILY/MANUAL"
    )
    # 对账状态：PENDING/RUNNING/SUCCESS/PARTIAL/FAILED
    status = Column(
        String(32),
        default="PENDING",
        nullable=False,
        comment="对账状态：PENDING/RUNNING/SUCCESS/PARTIAL/FAILED",
    )
    # 对账用户数（参与四方核对的用户总数）
    user_count = Column(Integer, default=0, nullable=False, comment="对账用户数")
    # 对账订单数（参与核对的订单总数）
    order_count = Column(Integer, default=0, nullable=False, comment="对账订单数")
    # 平账数（四方一致的记录数）
    matched_count = Column(Integer, default=0, nullable=False, comment="平账数")
    # 差异数（发现不一致的记录数）
    diff_count = Column(Integer, default=0, nullable=False, comment="差异数")
    # 订单佣金总额（订单 user_commission 汇总）
    total_order_commission = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="订单佣金总额(元)"
    )
    # 结算入账总额（结算单 user_commission 汇总）
    total_settlement_commission = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="结算入账总额(元)"
    )
    # 账户余额总额（账户 total_balance 汇总）
    total_account_balance = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="账户余额总额(元)"
    )
    # 累计提现总额（提现 SUCCESS actual_amount 汇总）
    total_withdrawn = Column(
        Numeric(10, 2), default=0.00, nullable=False, comment="累计提现总额(元)"
    )
    # 对账开始时间
    started_at = Column(DateTime, nullable=True, comment="对账开始时间")
    # 对账完成时间
    completed_at = Column(DateTime, nullable=True, comment="对账完成时间")
    # 操作人ID（手动触发时为管理员ID，自动对账为空）
    operator_id = Column(BigInteger, nullable=True, comment="操作人ID")
    # 失败原因（FAILED 状态时记录异常信息）
    error_message = Column(String(1024), default="", comment="失败原因")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")

# @ai-generated
"""
提现审批状态流转日志表 ORM 模型（B11 新建）
表名：withdraw_review_log
业务说明：记录提现申请每次状态变更的操作流水，供后台审计追溯
"""
from sqlalchemy import Column, String, BigInteger, Text, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class WithdrawReviewLog(Base, SerializableMixin, SoftDeleteMixin):
    """提现审批状态流转日志表"""

    __tablename__ = "withdraw_review_log"
    __table_args__ = (
        # apply_id 单值索引 —— 按申请查询操作历史
        Index("idx_wrl_apply_id", "apply_id"),
        # action 单值索引 —— 按操作类型筛选
        Index("idx_wrl_action", "action"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_wrl_create_time", "create_time"),
        {
            "comment": "提现审批状态流转日志表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 关联提现申请ID（非外键约束，仅逻辑关联，避免跨模块强耦合）
    apply_id = Column(BigInteger, nullable=False, comment="提现申请ID")
    # 变更前状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED
    from_status = Column(String(32), nullable=False, comment="变更前状态")
    # 变更后状态
    to_status = Column(
        String(32, collation="utf8mb4_unicode_ci"), nullable=False, comment="变更后状态"
    )
    # 操作类型：APPROVE/REJECT/TRANSFER/TRANSFER_SUCCESS/TRANSFER_FAIL
    action = Column(String(32), nullable=False, comment="操作类型")
    # 操作人ID（后台管理员）
    operator_id = Column(BigInteger, nullable=True, comment="操作人ID（后台管理员）")
    # 操作备注（审核备注/驳回原因/打款批次号等）
    remark = Column(Text, default="", comment="操作备注")
    # 微信转账批次ID（仅 TRANSFER/TRANSFER_SUCCESS/TRANSFER_FAIL 操作有值）
    transfer_batch_id = Column(String(64), default="", comment="微信转账批次ID")

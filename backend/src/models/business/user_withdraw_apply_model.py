# @ai-generated
"""
用户提现申请表 ORM 模型
表名：user_withdraw_apply
业务说明：平台用户提现申请全生命周期记录，5 态状态机
状态机：PENDING(待审核) → APPROVED(审核通过) → PROCESSING(转账处理中) → SUCCESS(打款完成)
       任一审核中/通过状态可 → REJECTED(驳回/打款失败，退回余额)
id / is_delete / create_time / update_time 由 Base 基类统一提供。
"""
from sqlalchemy import Column, String, BigInteger, Numeric, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class UserWithdrawApply(Base, SerializableMixin, SoftDeleteMixin):
    """用户提现申请表"""

    __tablename__ = "user_withdraw_apply"
    __table_args__ = (
        # user_id 单值索引 —— 按用户查询提现记录
        Index("idx_user_id", "user_id"),
        # status 单值索引 —— 按状态筛选
        Index("idx_status", "status"),
        # create_time 单值索引 —— 按时间范围查询
        Index("idx_create_time", "create_time"),
        # 联合索引 —— 用户+状态高频联查
        Index("idx_user_status", "user_id", "status"),
        {"comment": "用户提现申请表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 提现单号（GAKW前缀+时间+随机，全局唯一）
    apply_no = Column(String(64), nullable=False, comment="提现单号（GAKW前缀+时间+随机，全局唯一）")
    # 平台用户ID
    user_id = Column(BigInteger, nullable=False, comment="平台用户ID")
    # 申请提现金额(元)
    apply_amount = Column(Numeric(10, 2), nullable=False, comment="申请提现金额(元)")
    # 手续费(元)
    fee = Column(Numeric(10, 2), default=0.00, nullable=False, comment="手续费(元)")
    # 实际到账金额(元) = apply_amount - fee
    actual_amount = Column(Numeric(10, 2), default=0.00, nullable=False, comment="实际到账金额(元)=apply_amount-fee")
    # 状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED
    status = Column(String(32), default="PENDING", nullable=False, comment="状态：PENDING/APPROVED/PROCESSING/SUCCESS/REJECTED")
    # 审核人ID（后台管理员）
    review_user_id = Column(BigInteger, nullable=True, comment="审核人ID（后台管理员）")
    # 审核备注
    review_remark = Column(String(512), default="", comment="审核备注")
    # 审核时间
    review_time = Column(DateTime, nullable=True, comment="审核时间")
    # 微信转账批次ID
    transfer_batch_id = Column(String(64), default="", comment="微信转账批次ID")
    # 打款完成时间
    transfer_time = Column(DateTime, nullable=True, comment="打款完成时间")
    # 驳回原因（含打款失败原因）
    reject_reason = Column(String(512), default="", comment="驳回原因（含打款失败原因）")
    # 备注
    remark = Column(String(512), default="", comment="备注")

# @ai-generated
"""
X02-1 用户会员记录表 ORM 模型（新建文件，不修改 B01-B15 任何基线模型）

表：user_member_record - 用户会员开通/到期记录表
    记录用户会员开通、到期、撤销全生命周期；
    套餐名称与会员分佣比例做快照，避免套餐改价/改比例影响历史记录。
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class UserMemberRecord(Base, SerializableMixin, SoftDeleteMixin):
    """用户会员开通/到期记录表"""

    __tablename__ = "user_member_record"
    __table_args__ = (
        Index("idx_member_record_user_id", "user_id"),
        Index("idx_member_record_status", "status"),
        Index("idx_member_record_expire_at", "expire_at"),
        {"comment": "用户会员开通/到期记录表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 平台用户ID（与 orders.user_id / user_commission_account.user_id 联动）
    user_id = Column(BigInteger, nullable=False, comment="平台用户ID")
    # 会员套餐ID
    package_id = Column(Integer, nullable=False, comment="会员套餐ID")
    # 套餐名称快照
    package_name = Column(String(64), default="", nullable=False, comment="套餐名称快照")
    # 会员分佣比例快照（0~1）
    member_commission_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="会员分佣比例快照(0~1)")
    # 会员状态：active-生效中 expired-已到期 revoked-已撤销
    status = Column(String(16), default="active", nullable=False, comment="会员状态：active-生效中 expired-已到期 revoked-已撤销")
    # 开通时间
    started_at = Column(DateTime, nullable=False, comment="开通时间")
    # 到期时间
    expire_at = Column(DateTime, nullable=False, comment="到期时间")
    # 开通来源订单ID（可为空，如后台手动开通）
    order_id = Column(BigInteger, nullable=True, comment="开通来源订单ID")
    # 备注
    remark = Column(String(256), default="", comment="备注")

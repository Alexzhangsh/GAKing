# @ai-generated
"""
用户管理扩展表 ORM 模型
表名：user_admin_profile
业务说明：C端用户管理扩展表，存储平台对 C 端用户的管理标记（冻结状态/备注/冻结原因）
         C 端用户基础身份通过 user_id 标识（来自微信登录 B05），资产在 user_commission_account 表
         本表仅存"管理标记"，通过 user_id 与 user_commission_account 一对一关联
id / is_delete / create_time / update_time 由 Base 基类统一提供。
"""
from sqlalchemy import Column, String, BigInteger, DateTime, Index

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class UserAdminProfile(Base, SerializableMixin, SoftDeleteMixin):
    """用户管理扩展表"""

    __tablename__ = "user_admin_profile"
    __table_args__ = (
        # user_id 唯一索引 —— 一对一关联用户佣金账户
        Index("idx_user_id_unique", "user_id", unique=True),
        # status 单值索引 —— 按冻结状态筛选
        Index("idx_status", "status"),
        {
            "comment": "用户管理扩展表（C端用户冻结/备注管理标记）",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    # 平台用户ID（与 user_commission_account.user_id 一致）
    user_id = Column(BigInteger, nullable=False, comment="平台用户ID")
    # 管理状态：normal=正常 / frozen=冻结
    status = Column(String(16), default="normal", nullable=False, comment="管理状态")
    # 冻结原因（冻结时必填）
    frozen_reason = Column(String(512), default="", nullable=False, comment="冻结原因")
    # 冻结操作管理员ID
    frozen_by = Column(BigInteger, default=0, nullable=False, comment="冻结操作管理员ID")
    # 冻结时间
    frozen_time = Column(DateTime, nullable=True, comment="冻结时间")
    # 解冻操作管理员ID
    unfrozen_by = Column(BigInteger, default=0, nullable=False, comment="解冻操作管理员ID")
    # 最后解冻时间
    unfrozen_time = Column(DateTime, nullable=True, comment="最后解冻时间")
    # 管理员备注
    admin_remark = Column(String(512), default="", nullable=False, comment="管理员备注")
    # 最后操作管理员ID
    last_admin_id = Column(
        BigInteger, default=0, nullable=False, comment="最后操作管理员ID"
    )

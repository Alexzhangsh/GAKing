# @ai-generated
"""
F04-2 渠道佣金策略表 ORM 模型（新建文件，不修改 B01-B15 任何基线模型）

表1：gaking_channel_commission_strategy - 渠道佣金策略主表
    多渠道独立分佣（channel_code 唯一）+ 策略生效开关（enabled）+ 阶梯维度
表2：gaking_channel_commission_tier     - 阶梯佣金明细表
    普通用户/付费会员（user_type）× 阶梯区间（tier_min/tier_max）× 双比例
"""
from sqlalchemy import (
    Boolean,
    Column,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class ChannelCommissionStrategy(Base, SerializableMixin, SoftDeleteMixin):
    """渠道佣金策略主表"""

    __tablename__ = "gaking_channel_commission_strategy"
    __table_args__ = (
        UniqueConstraint("channel_code", name="uk_strategy_channel_code"),
        Index("idx_strategy_channel_code", "channel_code"),
        {"comment": "渠道佣金策略主表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 渠道标识：myq-喵有券 / orderx-订单侠 / dta-大淘客
    channel_code = Column(String(32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠 / dta-大淘客")
    # 策略名称
    strategy_name = Column(String(128), default="", nullable=False, comment="策略名称")
    # 策略生效开关：True-生效 False-停用
    enabled = Column(Boolean, default=False, nullable=False, comment="策略生效开关：True-生效 False-停用")
    # 阶梯维度：1-按订单金额 2-按订单数量
    tier_dimension = Column(Integer, default=1, nullable=False, comment="阶梯维度：1-按订单金额 2-按订单数量")
    # 备注说明
    remark = Column(String(512), default="", comment="备注说明")


class ChannelCommissionTier(Base, SerializableMixin, SoftDeleteMixin):
    """渠道佣金阶梯明细表"""

    __tablename__ = "gaking_channel_commission_tier"
    __table_args__ = (
        Index("idx_tier_strategy_id", "strategy_id"),
        {"comment": "渠道佣金阶梯明细表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 策略主表ID
    strategy_id = Column(Integer, nullable=False, comment="策略主表ID")
    # 用户类型：1-普通用户 2-付费会员
    user_type = Column(Integer, nullable=False, comment="用户类型：1-普通用户 2-付费会员")
    # 阶梯名称
    tier_name = Column(String(64), default="", comment="阶梯名称")
    # 阶梯下限（含）
    tier_min = Column(Numeric(12, 2), default=0.00, nullable=False, comment="阶梯下限（含）")
    # 阶梯上限（不含），0 表示无上限
    tier_max = Column(Numeric(12, 2), default=0.00, nullable=False, comment="阶梯上限（不含），0表示无上限")
    # 用户返利比例（0~1）
    user_commission_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="用户返利比例(0~1)")
    # 平台留存比例（0~1）
    platform_retention_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="平台留存比例(0~1)")
    # 排序号
    sort_order = Column(Integer, default=0, nullable=False, comment="排序号")

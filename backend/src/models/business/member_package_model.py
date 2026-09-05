# @ai-generated
"""
X02-1 会员套餐表 ORM 模型（新建文件，不修改 B01-B15 任何基线模型）

表：member_package - 会员套餐表
    套餐新增/编辑/上下架、有效期（duration_days）、会员分佣比例升级配置（member_commission_rate）
"""
from sqlalchemy import (
    Column,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from src.models.base import Base, SerializableMixin, SoftDeleteMixin


class MemberPackage(Base, SerializableMixin, SoftDeleteMixin):
    """会员套餐表"""

    __tablename__ = "member_package"
    __table_args__ = (
        UniqueConstraint("package_code", name="uk_member_package_code"),
        Index("idx_member_package_status", "status"),
        {"comment": "会员套餐表", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    # 套餐编码（唯一）
    package_code = Column(String(32), nullable=False, comment="套餐编码（唯一）")
    # 套餐名称
    package_name = Column(String(64), nullable=False, comment="套餐名称")
    # 套餐价格（元）
    price = Column(Numeric(10, 2), default=0.00, nullable=False, comment="套餐价格（元）")
    # 有效期（天）
    duration_days = Column(Integer, default=30, nullable=False, comment="有效期（天）")
    # 会员分佣比例（0~1）：会员用户订单结算时的用户返利比例
    member_commission_rate = Column(Numeric(5, 4), default=0.00, nullable=False, comment="会员分佣比例(0~1)")
    # 上下架状态：1-上架 0-下架
    status = Column(Integer, default=1, nullable=False, comment="上下架状态：1-上架 0-下架")
    # 排序号（越小越靠前）
    sort_order = Column(Integer, default=0, nullable=False, comment="排序号")
    # 套餐描述
    description = Column(String(512), default="", comment="套餐描述")

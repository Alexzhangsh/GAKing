# @ai-generated
"""add goods_management + user_admin_profile tables (B13-补全 + B14-补全)

新增 B13/B14 补全模块所需的两张管理扩展表：
- goods_management   商品管理扩展表（CPS 商品本地管理标记：上下架/排序/备注）
- user_admin_profile 用户管理扩展表（C端用户冻结/备注管理标记）

设计原则：不修改任何已基线固化的 B01-B15 存量表，仅新建扩展表
执行方式：
  alembic upgrade head     # 建表
  alembic downgrade -1     # 回滚删除表

Revision ID: 0007_add_b13_b14_admin_tables
Revises: 0006_add_admin_menu_b14
Create Date: 2026-08-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_add_b13_b14_admin_tables"
down_revision: Union[str, None] = "0006_add_admin_menu_b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建表：goods_management + user_admin_profile"""

    # 1. 商品管理扩展表
    op.create_table(
        "goods_management",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("goods_id", sa.String(length=128), nullable=False, comment="CPS 渠道商品唯一ID"),
        sa.Column("source_channel", sa.String(length=16), nullable=False, comment="来源渠道码"),
        sa.Column("goods_title", sa.String(length=512), nullable=False, server_default="", comment="商品标题"),
        sa.Column("goods_img", sa.String(length=1024), nullable=False, server_default="", comment="商品主图链接"),
        sa.Column("sale_price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00", comment="销售价(元)"),
        sa.Column("commission_rate", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0.00", comment="佣金比例(%)"),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="", comment="商品类目"),
        sa.Column("shop_name", sa.String(length=128), nullable=False, server_default="", comment="店铺名称"),
        sa.Column("shelf_status", sa.String(length=16), nullable=False, server_default="on_shelf", comment="上下架状态"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序权重"),
        sa.Column("admin_remark", sa.String(length=512), nullable=False, server_default="", comment="管理员备注"),
        sa.Column("last_admin_id", sa.BigInteger(), nullable=False, server_default="0", comment="最后操作管理员ID"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goods_id", "source_channel", name="uq_goods_channel"),
        sa.Index("idx_goods_channel", "goods_id", "source_channel", unique=True),
        sa.Index("idx_shelf_status", "shelf_status"),
        sa.Index("idx_category", "category"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="商品管理扩展表（CPS 商品本地管理标记）",
    )

    # 2. 用户管理扩展表
    op.create_table(
        "user_admin_profile",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="平台用户ID"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="normal", comment="管理状态"),
        sa.Column("frozen_reason", sa.String(length=512), nullable=False, server_default="", comment="冻结原因"),
        sa.Column("frozen_by", sa.BigInteger(), nullable=False, server_default="0", comment="冻结操作管理员ID"),
        sa.Column("frozen_time", sa.DateTime(), nullable=True, comment="冻结时间"),
        sa.Column("unfrozen_by", sa.BigInteger(), nullable=False, server_default="0", comment="解冻操作管理员ID"),
        sa.Column("unfrozen_time", sa.DateTime(), nullable=True, comment="最后解冻时间"),
        sa.Column("admin_remark", sa.String(length=512), nullable=False, server_default="", comment="管理员备注"),
        sa.Column("last_admin_id", sa.BigInteger(), nullable=False, server_default="0", comment="最后操作管理员ID"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_user_id_unique", "user_id", unique=True),
        sa.Index("idx_status", "status"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="用户管理扩展表（C端用户冻结/备注管理标记）",
    )


def downgrade() -> None:
    """回滚：删除两张扩展表"""
    op.drop_table("user_admin_profile")
    op.drop_table("goods_management")

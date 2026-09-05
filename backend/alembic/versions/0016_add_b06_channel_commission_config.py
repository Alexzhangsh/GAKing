# @ai-generated
"""
B06-1 渠道管理模块：新建渠道佣金比例配置表

迁移内容：
1. 新建渠道佣金比例配置表 gaking_channel_commission_config
2. 为 gaking_channel_mapping 表新增联系人/联系电话字段
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. 新建渠道佣金比例配置表 ────────────────────────
    op.create_table(
        "gaking_channel_commission_config",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
        sa.Column("channel_code", sa.String(32), nullable=False, comment="渠道标识：myq-喵有券 / orderx-订单侠"),
        sa.Column("user_type", sa.Integer(), nullable=False, comment="用户类型：1-普通用户 2-付费会员"),
        sa.Column("user_commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="用户返利比例(0~1)"),
        sa.Column("platform_retention_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000", comment="平台留存比例(0~1)"),
        sa.Column("remark", sa.String(512), server_default="", comment="备注说明"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.UniqueConstraint("channel_code", "user_type", name="uk_channel_user_type"),
        sa.Index("idx_channel_code", "channel_code"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="渠道佣金比例配置表",
    )

    # ── 2. gaking_channel_mapping 新增字段 ────────────────
    op.add_column(
        "gaking_channel_mapping",
        sa.Column("contact_name", sa.String(64), server_default="", comment="联系人"),
    )
    op.add_column(
        "gaking_channel_mapping",
        sa.Column("contact_phone", sa.String(32), server_default="", comment="联系电话"),
    )


def downgrade():
    # 1. 删除新增字段
    op.drop_column("gaking_channel_mapping", "contact_phone")
    op.drop_column("gaking_channel_mapping", "contact_name")

    # 2. 删除佣金比例配置表
    op.drop_table("gaking_channel_commission_config")
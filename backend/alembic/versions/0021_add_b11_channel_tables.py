# @ai-generated
"""
B11-1 渠道管理模块：新建渠道黑名单表、渠道每日统计表、渠道配置变更日志表

迁移内容：
1. 新建渠道黑名单表 gaking_channel_blacklist
2. 新建渠道每日统计表 gaking_channel_daily_stat
3. 新建渠道配置变更日志表 gaking_channel_config_log
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. 渠道黑名单表 ──────────────────────────────────
    op.create_table(
        "gaking_channel_blacklist",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),

        sa.Column("channel_code", sa.String(32), nullable=False, comment="渠道标识：myq/orderx"),
        sa.Column("blacklist_type", sa.String(32), nullable=False, comment="黑名单类型：user/ip/order"),
        sa.Column("blacklist_value", sa.String(128), nullable=False, comment="黑名单值（用户ID/IP地址/订单号）"),
        sa.Column("reason", sa.String(512), nullable=False, server_default="", comment="拉黑原因"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1"), comment="状态：0-禁用 1-启用"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="操作人ID"),
        sa.Column("operator_name", sa.String(64), nullable=False, server_default="", comment="操作人名称"),

        sa.Index("idx_cb_channel_code", "channel_code"),
        sa.Index("idx_cb_blacklist_type", "blacklist_type"),
        sa.Index("idx_cb_blacklist_value", "blacklist_value"),
        sa.Index("idx_cb_channel_type", "channel_code", "blacklist_type"),
        sa.Index("idx_cb_status", "status"),

        sa.PrimaryKeyConstraint("id"),
        mysql_comment="渠道黑名单表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 2. 渠道每日统计表 ────────────────────────────────
    op.create_table(
        "gaking_channel_daily_stat",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),

        sa.Column("stat_date", sa.Date(), nullable=False, comment="统计日期"),
        sa.Column("channel_code", sa.String(32), nullable=False, comment="渠道标识：myq/orderx"),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="订单总数"),
        sa.Column("total_pay_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00"), comment="支付总金额(元)"),
        sa.Column("total_commission", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00"), comment="总佣金(元)"),
        sa.Column("user_commission", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00"), comment="用户佣金(元)"),
        sa.Column("platform_commission", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00"), comment="平台佣金(元)"),
        sa.Column("settled_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="已结算订单数"),
        sa.Column("refund_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="退款订单数"),
        sa.Column("refund_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00"), comment="退款金额(元)"),

        sa.UniqueConstraint("stat_date", "channel_code", name="uk_stat_date_channel"),
        sa.Index("idx_cds_channel_code", "channel_code"),
        sa.Index("idx_cds_stat_date", "stat_date"),
        sa.Index("idx_cds_channel_date", "channel_code", "stat_date"),

        sa.PrimaryKeyConstraint("id"),
        mysql_comment="渠道每日统计表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ── 3. 渠道配置变更日志表 ────────────────────────────
    op.create_table(
        "gaking_channel_config_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),

        sa.Column("channel_code", sa.String(32), nullable=False, comment="渠道标识：myq/orderx"),
        sa.Column("config_key", sa.String(64), nullable=False, server_default="", comment="配置键名"),
        sa.Column("old_value", sa.String(512), nullable=False, server_default="", comment="变更前值"),
        sa.Column("old_value_label", sa.String(256), nullable=False, server_default="", comment="变更前值中文描述"),
        sa.Column("new_value", sa.String(512), nullable=False, server_default="", comment="变更后值"),
        sa.Column("new_value_label", sa.String(256), nullable=False, server_default="", comment="变更后值中文描述"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="操作人ID"),
        sa.Column("operator_name", sa.String(64), nullable=False, server_default="", comment="操作人名称"),
        sa.Column("operation_type", sa.String(32), nullable=False, server_default="", comment="操作类型"),
        sa.Column("remark", sa.Text(), nullable=False, comment="备注"),

        sa.Index("idx_ccl_channel_code", "channel_code"),
        sa.Index("idx_ccl_operation_type", "operation_type"),
        sa.Index("idx_ccl_operator", "operator_id"),
        sa.Index("idx_ccl_create_time", "created_at"),
        sa.Index("idx_ccl_channel_op", "channel_code", "operation_type"),

        sa.PrimaryKeyConstraint("id"),
        mysql_comment="渠道配置变更日志表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade():
    op.drop_table("gaking_channel_config_log")
    op.drop_table("gaking_channel_daily_stat")
    op.drop_table("gaking_channel_blacklist")
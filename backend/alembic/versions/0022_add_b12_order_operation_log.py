# @ai-generated
"""
B12-1 订单状态机管控模块：新建订单操作日志表

迁移内容：
1. 新建订单操作日志表 gaking_order_operation_log
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gaking_order_operation_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),

        sa.Column("order_id", sa.BigInteger(), nullable=False, comment="订单ID"),
        sa.Column("out_order_no", sa.String(64), nullable=False, server_default="", comment="渠道订单号"),
        sa.Column("internal_order_no", sa.String(64), nullable=False, server_default="", comment="平台内部订单号"),
        sa.Column("order_status_from", sa.SmallInteger(), nullable=False, server_default=sa.text("0"), comment="操作前状态"),
        sa.Column("order_status_to", sa.SmallInteger(), nullable=False, server_default=sa.text("0"), comment="操作后状态"),
        sa.Column("status_from_label", sa.String(32), nullable=False, server_default="", comment="操作前状态中文描述"),
        sa.Column("status_to_label", sa.String(32), nullable=False, server_default="", comment="操作后状态中文描述"),
        sa.Column("operation_type", sa.String(32), nullable=False, server_default="", comment="操作类型"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default=sa.text("0"), comment="操作人ID（0=系统自动）"),
        sa.Column("operator_name", sa.String(64), nullable=False, server_default="", comment="操作人名称"),
        sa.Column("remark", sa.Text(), nullable=False, comment="操作原因/备注"),

        sa.Index("idx_ool_order_id", "order_id"),
        sa.Index("idx_ool_order_status", "order_status_from", "order_status_to"),
        sa.Index("idx_ool_operation_type", "operation_type"),
        sa.Index("idx_ool_operator", "operator_id"),
        sa.Index("idx_ool_create_time", "created_at"),
        sa.Index("idx_ool_order_time", "order_id", "created_at"),

        sa.PrimaryKeyConstraint("id"),
        mysql_comment="订单操作日志表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade():
    op.drop_table("gaking_order_operation_log")
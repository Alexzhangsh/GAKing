# @ai-generated
"""
B10-1 站内消息通知模块：新建用户站内消息表

迁移内容：
1. 新建用户站内消息表 gaking_user_message
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gaking_user_message",
        # === 基础字段 ===
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="软删除标记"),

        # === 业务字段 ===
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="接收用户ID"),
        sa.Column("message_type", sa.String(32), nullable=False, comment="消息业务类型：commission/withdraw/order/refund"),
        sa.Column("title", sa.String(256), nullable=False, comment="消息标题"),
        sa.Column("content", sa.Text(), nullable=False, comment="消息内容"),
        sa.Column("biz_id", sa.String(64), nullable=False, server_default="", comment="关联业务ID（用于前端跳转）"),
        sa.Column("is_read", sa.SmallInteger(), nullable=False, server_default=sa.text("0"), comment="已读状态：0=未读 1=已读"),
        sa.Column("read_time", sa.String(32), nullable=False, server_default="", comment="已读时间（YYYY-MM-DD HH:mm:ss）"),
        sa.Column("push_status", sa.SmallInteger(), nullable=False, server_default=sa.text("0"), comment="推送状态：0=待推送 1=已推送 2=推送失败"),
        sa.Column("push_error", sa.String(512), nullable=False, server_default="", comment="推送失败原因"),

        # === 索引 ===
        sa.Index("idx_user_read", "user_id", "is_read"),
        sa.Index("idx_um_user_id", "user_id"),
        sa.Index("idx_um_message_type", "message_type"),
        sa.Index("idx_um_create_time", "created_at"),
        sa.Index("idx_um_user_time", "user_id", "created_at"),

        # === 表配置 ===
        sa.PrimaryKeyConstraint("id"),
        mysql_comment="用户站内消息表",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade():
    op.drop_table("gaking_user_message")
# @ai-generated
"""
B06-2 渠道订单报表导出与佣金账单对账：新建渠道导出任务日志表

迁移内容：
1. 新建渠道导出任务日志表 gaking_channel_export_task_log
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gaking_channel_export_task_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, comment="主键ID"),
        sa.Column("task_type", sa.String(32), nullable=False, comment="任务类型：order_export/commission_bill"),
        sa.Column("channel_code", sa.String(32), server_default="", comment="渠道标识"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROCESSING", comment="任务状态：PROCESSING/SUCCESS/FAILED"),
        sa.Column("file_path", sa.String(512), server_default="", comment="导出文件路径"),
        sa.Column("file_name", sa.String(256), server_default="", comment="导出文件名"),
        sa.Column("file_size", sa.BigInteger(), server_default="0", comment="文件大小(字节)"),
        sa.Column("row_count", sa.Integer(), server_default="0", comment="导出行数"),
        sa.Column("params", sa.Text(), nullable=True, comment="查询参数快照(JSON)（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息（MySQL 8.0.13+ TEXT 禁止默认值，置 NULL 代替）"),
        sa.Column("operator_id", sa.BigInteger(), nullable=False, server_default="0", comment="操作人ID"),
        sa.Column("operator_name", sa.String(64), server_default="", comment="操作人姓名"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="任务开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="任务结束时间"),
        sa.Column("is_delete", sa.Boolean(), nullable=False, server_default="0", comment="软删除：0-未删除 1-已删除"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now(), comment="更新时间"),
        sa.Index("idx_task_type", "task_type"),
        sa.Index("idx_operator_id", "operator_id"),
        sa.Index("idx_status", "status"),
        sa.Index("idx_create_time", "create_time"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="渠道导出任务日志表",
    )


def downgrade():
    op.drop_table("gaking_channel_export_task_log")